# standard library
import math
from typing import Any, Iterable, List, Sequence, Tuple, Literal, cast
import warnings

# Blender
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import blf
import mathutils
from bpy_extras import view3d_utils

from pyglm import glm

from . import vl_utils
from . import vl_coord_utils
from .vl_coord_utils import (
    get_view3d_zoom_to_fac,
    project_output_to_region,
    unproject_output_from_region,
    get_sensor_size,
    project_sensor_to_region,
    unproject_sensor_from_region,
    project_compute_to_region,
    unproject_compute_from_region,
    fit_space_to_aspect,
    map_space,
    crop_space_to_aspect
)



from . uiview3d import UIView3D

# local
from . import solver
from . draw_layer import DrawLayer

###############
# VL OPERATOR #
###############
from typing import Callable


class ControlPoint():
    def __init__(self, data:bpy.types.ID, prop:str, *, 
            setter:Callable|None=None, 
            getter:Callable|None=None):
        self._data = data
        self._prop = prop

        if setter is None:
            self._setter = lambda data, prop, value: setattr(self._data, self._prop, value)
        else:
            self._setter = setter
        
        if getter is None:
            self._getter = lambda data, prop: getattr(self._data, self._prop)
        else:
            self._getter = getter
        
    @property
    def value(self):
        return self._getter(self._data, self._prop)
    
    @value.setter
    def value(self, value): # todo: we should use the actual _bpy prop_ type here, but how?
        self._setter(self._data, self._prop, value)


class VIEW_OT_VanishingLinesOperator(bpy.types.Operator):
    """align the camera based on vanishing lines"""
    
    bl_idname = "view.vanishing_lines_operator"
    bl_label = "Vanishing Lines Operator"
    bl_options = {"REGISTER", "UNDO"}
    
    # solver
    _active_camera: bpy.types.Object|None = None
    _solve_error: Exception|None = None

    # rendering
    uiview: UIView3D|None = None
    
    # Operator
    def invoke(self, context, event):
        # validate context
        print("Invoking Vanishing Lines Operator")
        scene = context.scene
        if scene is None:
            self.report({'ERROR'}, "No active scene found")
            return {'CANCELLED'}
        
        area: bpy.types.Area|None = context.area
        if area is None:
            self.report({'ERROR'}, "No active area found")
            return {'CANCELLED'}
        
        window_manager = context.window_manager
        if window_manager is None:
            self.report({'ERROR'}, "No active window manager found")
            return {'CANCELLED'}
        
        # activate the camera view
        if scene.camera is None:
            self.report({'ERROR'}, "Scene has no active camera set")
            return {'CANCELLED'}

        vl_utils.set_viewer_camera(context, scene.camera)
        self._active_camera = vl_utils.get_viewer_camera(context)
        if self._active_camera is None:
            self.report({'ERROR'}, "Scene has no active camera set")
            return {'CANCELLED'}
        
        # Setup controls layer
        self.uiview = UIView3D()
        
        # Setup default props if not initialized
        vl_settings = self._active_camera.data.vl_settings # type: ignore

        def setup_defaults_props():
            if not vl_settings.initialized:
                vl_settings.origin = 0.0,  -0.25
                vl_settings.principal = 0.0,  0.0
                vl_settings.initialized = True

            if len(vl_settings.first_vanishing_lines) == 0:
                item = vl_settings.first_vanishing_lines.add()
                item.start = -0.2, -0.53
                item.end =    0.6,  0.12

                item = vl_settings.first_vanishing_lines.add()
                item.start = -0.88, 0.0
                item.end =    0.09, 0.20

            if len(vl_settings.second_vanishing_lines) == 0:
                item = vl_settings.second_vanishing_lines.add()
                item.start =  0.22, -0.48
                item.end =   -0.80,  0.05

                item = vl_settings.second_vanishing_lines.add()
                item.start =  0.65, 0.05
                item.end =   -0.10, 0.20

            if len(vl_settings.third_vanishing_lines) == 0:
                item = vl_settings.third_vanishing_lines.add()
                item.start = -0.3, -0.52
                item.end =   -0.4, 0.5

                item = vl_settings.third_vanishing_lines.add()
                item.start = 0.3, -0.52
                item.end =   0.4, 0.5

        setup_defaults_props()

        # Initial Solve
        self._active_camera = vl_utils.get_viewer_camera(context)
        self.update_solve(context)

        # # trigger redraw
        if area.type == 'VIEW_3D':
           area.tag_redraw()

        # run as modal
        window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if self._active_camera != vl_utils.get_viewer_camera(context): 
            if context.area.type == 'VIEW_3D':
                context.area.tag_redraw()
            return {'FINISHED'}
        return self.uiview.event(context, event)

    def _on_deps_graph_update(self, scene, depsgraph:bpy.types.Depsgraph):
        """when the depsgraph changes, regarding the active camera, 
        or the output resolution, we update the solve."""
        
        updates:bpy.types.bpy_prop_collection[bpy.types.DepsgraphUpdate] = depsgraph.updates
        for update in updates:
            # print("Depsgraph update:", update.id)
            if isinstance(update.id, bpy.types.Camera):
                self.update_solve(bpy.context)

    # commands
    def update_solve(self, context):
        # print("update solve called")
        # region = context.region
        # rv3d = context.space_data.region_3d
        if self._active_camera is None:
            self.report({'ERROR'}, "Scene has no active camera set")
            return
        
        camera_object: bpy.types.Object = self._active_camera
        if camera_object.type != 'CAMERA':
            self.report({'ERROR'}, "Active camera is not a camera object")
            return

        vl_settings = camera_object.data.vl_settings
        
        if vl_settings.solver_is_paused:
            return

        if not vl_settings.enable_manual_principal:
            vl_settings.principal = self.get_compute_space().center

        try:
            mode = {"ONE_POINT":   solver.types.SolverMode.OneVP,
                    "TWO_POINT":   solver.types.SolverMode.TwoVP,
                    "THREE_POINT": solver.types.SolverMode.ThreeVP
            }[vl_settings.mode]

            reference_axis = {
                'ORIGIN': None,# TODO: ORIGIN option
                'SCREEN': solver.types.ReferenceAxis.Screen,
                'X_AXIS': solver.types.ReferenceAxis.X_Axis,
                'Y_AXIS': solver.types.ReferenceAxis.Y_Axis,
                'Z_AXIS': solver.types.ReferenceAxis.Z_Axis
            }[vl_settings.scene_scale_mode]

            first_axis = {
                'X+': solver.types.Axis.PositiveX,
                'Y+': solver.types.Axis.PositiveY,
                'Z+': solver.types.Axis.PositiveZ,
                'X-': solver.types.Axis.NegativeX,
                'Y-': solver.types.Axis.NegativeY,
                'Z-': solver.types.Axis.NegativeZ
            }[vl_settings.first_axis]

            second_axis = {
                'X+': solver.types.Axis.PositiveX,
                'Y+': solver.types.Axis.PositiveY,
                'Z+': solver.types.Axis.PositiveZ,
                'X-': solver.types.Axis.NegativeX,
                'Y-': solver.types.Axis.NegativeY,
                'Z-': solver.types.Axis.NegativeZ
            }[vl_settings.second_axis]


            third_axis = solver.helpers.third_axis(first_axis, second_axis)

            
            second_vanishing_lines = [(line.start, line.end) for line in vl_settings.second_vanishing_lines]
            if vl_settings.quad_mode and mode in {solver.types.SolverMode.TwoVP, solver.types.SolverMode.ThreeVP}:
                first_line = vl_settings.first_vanishing_lines[ 0]
                last_line =  vl_settings.first_vanishing_lines[-1]

                second_vanishing_lines = [
                    (first_line.start, last_line.start), (first_line.end, last_line.end)
                ]
            
            self._solve_error = None
            projection, view = solver.core.solve(
                mode = mode,
                viewport=self.get_compute_space(),
                first_vanishing_lines= [(line.start, line.end) for line in  vl_settings.first_vanishing_lines],
                second_vanishing_lines=second_vanishing_lines,
                third_vanishing_lines= [(line.start, line.end) for line in  vl_settings.third_vanishing_lines],

                f = camera_object.data.lens / camera_object.data.sensor_width * self.get_compute_space().height,
                P = (vl_settings.principal[0], vl_settings.principal[1]), # TODO: is [0], [1] necessary?
                O = (vl_settings.origin[0], vl_settings.origin[1]),

                reference_axis=reference_axis, # TODO: make configurable
                reference_distance_segment=(0, vl_settings.reference_distance), # TODO: make fist value configurable
                reference_world_size=vl_settings.scene_scale,

                first_axis=first_axis,
                second_axis=second_axis
            )

            vl_utils.apply_solver_results_to_blender_camera(
                projection=projection, 
                view=view, 
                camera_object=camera_object, 
                compute_space=self.get_compute_space(), 
                output_size=(context.scene.render.resolution_x, context.scene.render.resolution_y),
                fit_mode=camera_object.data.sensor_fit
            )

            vl_settings.error_message = ""
                    
        except Exception as e:
            vl_settings.error_message = str(e)
            import traceback
            traceback.print_exc()

    def draw_view(self, context):
        try:
            if self.uiview is None:
                warnings.warn("Draw layer not initialized. Skipping draw.")
                return
        except ReferenceError as e:
            warnings.warn(f"Draw layer reference error. Skipping draw. {e}")
            return
        
        # self.uiview.update_viewport_state(context)
        self.uiview._draw_layer.clear()
        self.uiview._controls.clear()
        

        # set UIVIEW projection and viewport
        camera_frame = vl_coord_utils.get_view_camera_frame_rect(context)
        if not camera_frame:
            x, y = 0, 0
            w, h = context.region.width, context.region.height
            self.uiview.set_projection(glm.ortho(x, w, 0.0, h, -1000.0, 1000.0))
            self.uiview.set_viewport((0, 0, w, h))
            self.uiview.render()
            return
        
        # match UIVIEW layout frame to camera frame
        self.uiview.set_coordinate_system_to_camera_frame(context)
        
        # Draw Camera Frame
        self.uiview._draw_layer.add_rect(
                camera_frame[0:2],
                camera_frame[2:4],
                color=(1,1,1,0.2))
        
        x_min, y_min = self.uiview.project((-1,-1))
        x_max, y_max = self.uiview.project((1, 1))
        self.uiview._draw_layer.add_rect(
            (x_min, y_min),
            (x_max - x_min, y_max - y_min),
            color=(0,1,1,1.0)
        )

        # add controls
        vl_settings = self._active_camera.data.vl_settings # type: ignore

        GREEN = (0,1,0,1)
        RED = (1,0,0,1)
        BLUE = (0,0.3, 1.0, 1.0)
        YELLOW = (1,1,0,1)
        ORANGE = (1.0, 0.5, 0.0, 1.0)

        ###########################
        # Vanishing Line CONTROLS #
        ###########################
        _ = self.uiview.prop_point(vl_settings, "origin",    
            text="O",
            color=YELLOW)
        
        _ = self.uiview.prop_point(vl_settings, "principal", 
            text="P",
            color=YELLOW)
        def get_axis_color(axis:solver.types.Axis) -> Tuple[float, float, float, float]:
            match axis:
                case solver.types.Axis.PositiveX | solver.types.Axis.NegativeX:
                    return RED
                case solver.types.Axis.PositiveY | solver.types.Axis.NegativeY:
                    return GREEN
                case solver.types.Axis.PositiveZ | solver.types.Axis.NegativeZ:
                    return BLUE

        axes_mapping = {
            'X+': solver.types.Axis.PositiveX,
            'Y+': solver.types.Axis.PositiveY,
            'Z+': solver.types.Axis.PositiveZ,
            'X-': solver.types.Axis.NegativeX,
            'Y-': solver.types.Axis.NegativeY,
            'Z-': solver.types.Axis.NegativeZ
        }
        first_axis = axes_mapping[vl_settings.first_axis]
        second_axis = axes_mapping[vl_settings.second_axis]
        third_axis = solver.helpers.third_axis(first_axis, second_axis) # find third axis based on the first two

        if vl_settings.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
            # Draw first vanishing lines
            for line in vl_settings.first_vanishing_lines:
                self.uiview.prop_line(line, color=get_axis_color(first_axis))

        if vl_settings.mode in {'ONE_POINT'}:
            # Draw the horizontal line for the vp1 mode:
            self.uiview.prop_line(vl_settings.second_vanishing_lines[0], color=get_axis_color(second_axis))

        if vl_settings.mode in {'TWO_POINT', 'THREE_POINT'}:
            if vl_settings.quad_mode:
                first_line = vl_settings.first_vanishing_lines[ 0]
                last_line =  vl_settings.first_vanishing_lines[-1]
                
                for line_start, line_end in [(first_line.start, last_line.start), (first_line.end, last_line.end)]:
                    self.uiview._draw_layer.add_line(
                        self.uiview.project(line_start), 
                        self.uiview.project(line_end), 
                        get_axis_color(second_axis))
                    
            else:
                for line in vl_settings.second_vanishing_lines:
                    self.uiview.prop_line(line, color=get_axis_color(second_axis))

        if vl_settings.mode in {'THREE_POINT'}:
            for line in vl_settings.third_vanishing_lines:
                self.uiview.prop_line(line, color=get_axis_color(third_axis))

        ###########################################
        # DRAW Extended lines to vanishing points #
        ###########################################
        if vl_settings.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
            try:
                vp1 = solver.core.compute_vanishing_point([
                    (line.start, line.end) 
                    for line in vl_settings.first_vanishing_lines])

                for line in vl_settings.first_vanishing_lines:
                    self.uiview._draw_layer.add_line(
                        self.uiview.project(vl_utils.closest_point_to_target([line.start, line.end], vp1)), 
                        self.uiview.project(vp1), vl_utils.dim_color(get_axis_color(first_axis)))
                    
            except ValueError as e:
                warnings.warn(f"Could not compute VP1: {e}")

        if vl_settings.mode in {'TWO_POINT', 'THREE_POINT'}:
            
            if vl_settings.quad_mode:
                try:
                    first_line = vl_settings.first_vanishing_lines[ 0]
                    last_line =  vl_settings.first_vanishing_lines[-1]

                    second_vanishing_lines = [
                        (first_line.start, last_line.start),
                        (first_line.end, last_line.end)]

                    vp2 = solver.core.compute_vanishing_point(second_vanishing_lines)
                    
                    for line_start, line_end in second_vanishing_lines:
                        self.uiview._draw_layer.add_line(
                            self.uiview.project(vl_utils.closest_point_to_target([line_start, line_end], vp2)), 
                            self.uiview.project(vp2), 
                            vl_utils.dim_color(get_axis_color(second_axis)))
                except ValueError as e:
                    warnings.warn(f"Could not compute VP1: {e}")
            else:
                try:
                    vp2 = solver.core.compute_vanishing_point([
                        (line.start, line.end) 
                        for line in vl_settings.second_vanishing_lines])
                    
                    for line in vl_settings.second_vanishing_lines:
                        self.uiview._draw_layer.add_line(
                            self.uiview.project(vl_utils.closest_point_to_target([line.start, line.end], vp2)), 
                            self.uiview.project(vp2), 
                            vl_utils.dim_color(get_axis_color(second_axis)))

                except ValueError as e:
                    warnings.warn(f"Could not compute VP2: {e}")

        if vl_settings.mode in {'THREE_POINT'}:
            try:
                vp3 = solver.core.compute_vanishing_point([
                    (line.start, line.end) 
                    for line in vl_settings.third_vanishing_lines])
                
                for line in vl_settings.third_vanishing_lines:
                    self.uiview._draw_layer.add_line(
                        self.uiview.project(vl_utils.closest_point_to_target([line.start, line.end], vp3)), 
                        self.uiview.project(vp3), 
                        vl_utils.dim_color(get_axis_color(third_axis)))
                    
            except ValueError as e:
                warnings.warn(f"Could not compute VP3: {e}")

        if vl_settings.scene_scale_mode != 'ORIGIN':
            def get_distance_measurement_direction() -> mathutils.Vector:
                if vl_settings.scene_scale_mode == 'SCREEN':
                    return mathutils.Vector((1,0))
                else:
                    match vl_settings.scene_scale_mode:
                        case 'X_AXIS':
                            axis_vector = (1,0,0)
                        case 'Y_AXIS':
                            axis_vector = (0,1,0)
                        case 'Z_AXIS':
                            axis_vector = (0,0,1)
                    region = context.region
                    rv3d = context.space_data.region_3d
                    R = view3d_utils.location_3d_to_region_2d(region, rv3d, axis_vector)
                    R = self.uiview.unproject((R.x, R.y))
                    R = mathutils.Vector((R[0], R[1]))
                    O = mathutils.Vector((vl_settings.origin[0], vl_settings.origin[1]))
                    return (R - O).normalized()

            self.uiview.prop_distance(vl_settings, "reference_distance", 
                origin=vl_settings.origin,
                direction=get_distance_measurement_direction(),
                text="R",
                color=ORANGE)

        # # Reference Distance
        # self.uiview._draw_layer.add_point(
        #     self.uiview.project(
        #         self.get_reference_distance_point(vl_settings)), 
        #         (1.0, 1.0, 1.0, 1.0))
        
        # if vl_settings.scene_scale_mode != 'ORIGIN':
        #     _ = self.uiview.prop_point(vl_settings, "reference_distance", 
        #         text="R",
        #         color=ORANGE,
        #         setter=lambda data, prop, value: self.set_reference_distance_point(vl_settings, value),
        #         getter=lambda data, prop: 
        #             self.get_reference_distance_point(vl_settings))
                
        #     self.uiview._draw_layer.add_line(
        #         self.uiview.project(vl_settings.origin), 
        #         self.uiview.project(
        #             self.get_reference_distance_point(vl_settings)),
        #         vl_utils.dim_color(ORANGE, factor=0.7 if self.is_item_hovered() else 0.1))


        # # draw sensor frame
        # def draw_sensor_frame():
        #     sensor_size = self.get_sensor_size()
        #     bottom_left = self.project_sensor_to_region((0,0))
        #     top_right = self.project_sensor_to_region(
        #         (sensor_size[0], sensor_size[1]))

        #     self._draw_layer.add_rect(
        #         bottom_left,
        #         (top_right[0]-bottom_left[0], top_right[1]-bottom_left[1]),
        #         color=(0,1,1,0.5))

        #     self._draw_layer.add_text(
        #         bottom_left,
        #         f"Sensor Frame",
        #         color=(0,1,1,1))
            
        # draw_sensor_frame()
    
        # Execute the draw calls
        self.uiview.render()

        # # Draw error messages
        # if self._solve_error:
        #     lines = str(self._solve_error).splitlines()
        #     line_height = 12
        #     text_height = line_height * len(lines)
        #     font_id = 0
        #     blf.position(font_id, 20, text_height+40, 0)
        #     blf.size(font_id, 12)
        #     blf.color(font_id, 1,0,0,1)
        #     for i, line in enumerate(lines):
        #         blf.position(font_id, 20, text_height-line_height*i+40, 0)
        #         blf.draw(font_id, f"{line}")
  
    # GETTERS / SETTERS
    def get_reference_distance_point(self, 
        vl_settings) -> Tuple[float, float]:
        """Get the reference distance point based on origin and reference distance."""

        Ox, Oy = vl_settings.origin
        O = mathutils.Vector((Ox, Oy))

        if vl_settings.scene_scale_mode in {'SCREEN', 'ORIGIN'}:
            rd = vl_settings.reference_distance
            return (O.x + rd, O.y)

        match vl_settings.scene_scale_mode:
            case 'X_AXIS':
                axis_vector = (1,0,0)
            case 'Y_AXIS':
                axis_vector = (0,1,0)
            case 'Z_AXIS':
                axis_vector = (0,0,1)

        R = view3d_utils.location_3d_to_region_2d(self._region, self._region_data, axis_vector)
        
        R = self.unproject_compute_from_region((R.x, R.y))

        R = mathutils.Vector((R[0], R[1]))
        
        d = vl_settings.reference_distance
        n = (R - O).normalized()
        v = n*d
        R = O + v
        return (R.x, R.y)
        
    def set_reference_distance_point(self, 
        vl_settings, point:Tuple[float, float]) -> None:
        """Set the reference distance based on a point and the origin."""

        Ox, Oy = vl_settings.origin
        O = mathutils.Vector((Ox, Oy))

        if vl_settings.scene_scale_mode in {'SCREEN', 'ORIGIN'}:
            Px, Py = point
            vl_settings.reference_distance = math.sqrt((Px - Ox) ** 2 + (Py - Oy) ** 2)
        
        else:
            match vl_settings.scene_scale_mode:
                case 'X_AXIS':
                    axis_vector = (1,0,0)
                case 'Y_AXIS':
                    axis_vector = (0,1,0)
                case 'Z_AXIS':
                    axis_vector = (0,0,1)

            R = view3d_utils.location_3d_to_region_2d(self._region, self._region_data, axis_vector)
            R = self.unproject_compute_from_region((R.x, R.y))
            R = mathutils.Vector((R[0], R[1]))
            l = (R - O).magnitude
            n = (R - O) / l
            P = mathutils.Vector((point[0], point[1]))
            d = (P - O).dot(n)
            vl_settings.reference_distance = d
        
    def get_compute_space(self) -> solver.types.Rect:
        """compute space is a normalized square"""
        # for now this is hardcoded. TODO: make this user definable
        return solver.types.Rect(-1,-1,2,2)

    def get_sensor_size(self) -> Tuple[float, float]:
        return get_sensor_size(
            self._active_camera.data.sensor_fit,
            (self._active_camera.data.sensor_width, self._active_camera.data.sensor_height))

    # # Coordinate Mapping
    # def _project_output_to_region(self, output_coords: Tuple[float, float]) -> Tuple[float, float]:
    #     """Convert output frame coordinates to region space using cached viewport state"""
    #     assert self._output_size is not None, "Viewport state not initialized"

    #     return project_output_to_region(
    #         fit_mode=self._active_camera.data.sensor_fit,
    #         output_size = self._output_size,
    #         region_size = self._region_size,
    #         view_camera_zoom = self._view_camera_zoom,
    #         view_camera_offset = self._view_camera_offset,
    #         output_coords=output_coords)

    # def _unproject_output_from_region(self, region_coords: Tuple[float, float]) -> Tuple[float, float]:
    #     """Convert region coordinates to output frame space using cached viewport state"""
    #     assert self._output_size is not None, "Viewport state not initialized"

    #     return unproject_output_from_region(
    #         fit_mode=self._active_camera.data.sensor_fit,
    #         output_size = self._output_size,
    #         region_size = self._region_size,
    #         view_camera_zoom = self._view_camera_zoom,
    #         view_camera_offset = self._view_camera_offset,
    #         region_coords=region_coords)

    # def project_sensor_to_region(self, sensor_coord:Tuple[float, float]) -> Tuple[float, float]:
    #     """Project from sensor space to region space (uses cached viewport state)"""
    #     assert self._output_size is not None, "Viewport state not initialized"

    #     sensor_size = self.get_sensor_size()
    #     sensor_rect = solver.types.Rect(
    #         x=0,
    #         y=0,
    #         width=sensor_size[0],
    #         height=sensor_size[1])
        
    #     return project_sensor_to_region(
    #         fit_mode=self._active_camera.data.sensor_fit,
    #         sensor_size = (sensor_rect.width, sensor_rect.height),
    #         output_size = self._output_size,
    #         region_size = self._region_size,
    #         view_camera_zoom = self._view_camera_zoom,
    #         view_camera_offset = self._view_camera_offset,
    #         sensor_coords=sensor_coord)
    
    # def unproject_sensor_from_region(self, coord: Tuple[float, float]) -> Tuple[float, float]:
    #     raise NotImplementedError("unproject_sensor_from_region not implemented yet")

    # def project_compute_to_region(self, coord:Tuple[float, float]) -> Tuple[float, float]:
    #     """Project from computation viewport to region space (uses cached viewport state)"""
    #     x, y = coord
    #     assert isinstance(x, (int, float)), f"got: {x}"
    #     assert isinstance(y, (int, float)), f"got: {y}"
    #     assert self._output_size is not None, "Viewport state not initialized"

    #     x, y, w, h = self.get_compute_space()
    #     return project_compute_to_region(
    #         fit_mode=self._active_camera.data.sensor_fit,
    #         compute_rect = (x, y, w, h),
    #         output_size = self._output_size,
    #         region_size = self._region_size,
    #         view_camera_zoom = self._view_camera_zoom,
    #         view_camera_offset = self._view_camera_offset,
    #         compute_coords=coord
    #     )

    # def unproject_compute_from_region(self, coord: Tuple[float, float]) -> Tuple[float, float]:
    #     """Map from region space to computation viewport (uses cached viewport state)"""
    #     x, y = coord
    #     assert isinstance(x, (int, float)), f"got: {x}"
    #     assert isinstance(y, (int, float)), f"got: {y}"
    #     assert self._output_size is not None, "Viewport state not initialized"

    #     x, y, w, h = self.get_compute_space()
    #     return unproject_compute_from_region(
    #         fit_mode=self._active_camera.data.sensor_fit,
    #         compute_rect = (x, y, w, h),
    #         output_size = self._output_size,
    #         region_size = self._region_size,
    #         view_camera_zoom = self._view_camera_zoom,
    #         view_camera_offset = self._view_camera_offset,
    #         region_coords=coord
    #     )
    

######################
# REGISTER FUNCTIONS #
######################
def view_menu_func(self, context):
    self.layout.operator(VIEW_OT_VanishingLinesOperator.bl_idname, text="Vanishing Lines Modal Operator")

def view_draw_func():
    # global draw_list
    """Wrapper function to call the draw_view method of the operator instance."""
    if op:=vl_utils.get_running_operator_by_idname("VIEW_OT_vanishing_lines_operator"):
        op.draw_view(bpy.context)

def on_depsgraph_update(scene, depsgraph):
    if op:=vl_utils.get_running_operator_by_idname("VIEW_OT_vanishing_lines_operator"):
        op._on_deps_graph_update(scene, depsgraph)

draw_handler = None
def register():
    global draw_handler
    bpy.utils.register_class(VIEW_OT_VanishingLinesOperator)
    draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            view_draw_func, 
            (), 
            'WINDOW', 
            'POST_PIXEL' # POST_VIEW | POS_PIXEL | ...
        )
    bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update)

    bpy.types.VIEW3D_MT_view.append(view_menu_func)

def unregister():
    global draw_handler
    bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update)
    if draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handler, 'WINDOW')
        draw_handler = None

    bpy.types.VIEW3D_MT_view.remove(view_menu_func)
    bpy.utils.unregister_class(VIEW_OT_VanishingLinesOperator)


# TODO:
# consider using a message bus to trigger updates instead of depsgraph updates
# import bpy

# # 1. Define the function that should run when the property changes
# def notify_test(context):
#     print("VL Settings changed!")
#     # Force a redraw of all 3D views
#     for area in context.screen.areas:
#         if area.type == 'VIEW_3D':
#             area.tag_redraw()

# # We need a persistent reference to the handle
# subscription_handle = object()

# def register():
#     # ... your existing registration ...
    
#     # 2. Subscribe to the 'vl_settings' property on any Camera
#     subscribe_to = (bpy.types.Camera, "vl_settings")
    
#     bpy.msgbus.subscribe_rna(
#         key=subscribe_to,
#         owner=subscription_handle,
#         args=(bpy.context,),
#         notify=notify_test,
#     )

# def unregister():
#     # 3. Clean up the subscription
#     bpy.msgbus.clear_by_owner(subscription_handle)
#     # ... your existing unregistration ...