# standard library
from typing import Tuple
import warnings

# Blender
import bpy

import blf
import mathutils
from bpy_extras import view3d_utils

# third party
from pyglm import glm

# local
from . import solver
from . import vl_utils
from . import vl_coord_utils
from . uiview3d import UIView3D
from . vl_params import set_defaults


# Constants
FONT_SIZE = 16
LINE_HEIGHT = 18
ERROR_TEXT_X_OFFSET = 20
ERROR_TEXT_Y_OFFSET = 40

###############
# VL OPERATOR #
###############
# commands
def update_solve(camera_object:bpy.types.Object, compute_space:solver.types.Rect = solver.types.Rect(-1, -1, 2, 2)):
    vl_settings = camera_object.data.vl_settings

    if not vl_settings.enable_manual_principal:
        vl_settings.principal = compute_space.center

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

        second_vanishing_lines = [(line.start, line.end) for line in vl_settings.second_vanishing_lines]
        if vl_settings.quad_mode and mode in {solver.types.SolverMode.TwoVP, solver.types.SolverMode.ThreeVP}:
            first_line = vl_settings.first_vanishing_lines[ 0]
            last_line =  vl_settings.first_vanishing_lines[-1]

            second_vanishing_lines = [
                (first_line.start, last_line.start), (first_line.end, last_line.end)
            ]
        
        projection, view = solver.core.solve(
            mode = mode,
            viewport=compute_space,
            first_vanishing_lines= [(line.start, line.end) for line in  vl_settings.first_vanishing_lines],
            second_vanishing_lines=second_vanishing_lines,
            third_vanishing_lines= [(line.start, line.end) for line in  vl_settings.third_vanishing_lines],

            f = camera_object.data.lens / camera_object.data.sensor_width * compute_space.height,
            P = (vl_settings.principal[0], vl_settings.principal[1]), # TODO: is [0], [1] necessary?
            O = (vl_settings.origin[0], vl_settings.origin[1]),

            reference_axis=reference_axis, # TODO: make configurable
            reference_distance_segment=(vl_settings.reference_distance_segment[0], vl_settings.reference_distance_segment[1]-vl_settings.reference_distance_segment[0]), # TODO: make fist value configurable
            reference_world_size=vl_settings.scene_scale,

            first_axis=first_axis,
            second_axis=second_axis
        )

        vl_utils.apply_solver_results_to_blender_camera(
            projection=projection, 
            view=view, 
            camera_object=camera_object, 
            compute_space=compute_space, 
            fit_mode=camera_object.data.sensor_fit
        )

        vl_settings.error_message = ""
                
    except Exception as e:
        error_type = type(e).__name__  # Gets 'ValueError' as a string
        error_message = str(e)         # Gets the actual message you wrote in 'raise'
        vl_settings.error_message = f"{error_type}\n{error_message}"
        import traceback
        traceback.print_exc()


class VIEW_OT_VanishingLinesStartOperator(bpy.types.Operator):
    """align the camera based on vanishing lines"""
    bl_idname = "view.vanishing_lines_operator"
    bl_label = "Vanishing Lines Operator"
    bl_options = {"REGISTER", "UNDO"}
    bl_description  = "Start calibrating the active camera using vanishing lines"
    
    # solver    
    _active_camera: bpy.types.Object|None = None

    # rendering
    uiview: UIView3D|None = None
    
    # Operator
    def invoke(self, context, event):
        # validate context
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
        self._active_camera = vl_utils.get_calibration_camera(context)
        if self._active_camera is None:
            self.report({'ERROR'}, "Scene has no active camera set")
            return {'CANCELLED'}
        
        vl_utils.set_view_camera(context, self._active_camera)
        
        # Setup controls layer
        self.uiview = UIView3D()
        
        # Setup default props if not initialized
        vl_settings = self._active_camera.data.vl_settings # type: ignore
        if vl_settings.initialized is False:
            set_defaults(vl_settings)
            vl_settings.initialized = True

        # Initial Solve
        update_solve(self._active_camera)

        # # trigger redraw
        if area.type == 'VIEW_3D':
           area.tag_redraw()

        # run as modal
        window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        # cleanup
        self.uiview = None
        self._active_camera = None # when active camera is None, modal will finish

        # trigger redraw
        area: bpy.types.Area|None = context.area
        if area and area.type == 'VIEW_3D':
           area.tag_redraw()

    def modal(self, context, event):
        if self._active_camera != vl_utils.get_view_camera(context): 
            if context.area and context.area.type == 'VIEW_3D':
                context.area.tag_redraw()
            self.cleanup()
            return {'FINISHED'}
        
        result = self.uiview.event(context, event)
        # if self._active_camera.data.vl_settings.update_strategy == 'ON_UI_CHANGE':
        #     if result & {'RUNNING_MODAL', 'FINISHED'}:
        #         update_solve(self._active_camera)

        if result & {'CANCEL', 'FINISHED'}:
            self.cleanup()


        return result
    
    def cleanup(self):
        if on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update)

    def view3d_draw(self, context):
        try:
            if self.uiview is None:
                warnings.warn("Draw layer not initialized. Skipping draw.")
                return
        except ReferenceError as e:
            warnings.warn(f"Draw layer reference error. Skipping draw. {e}")
            return
        
        # self.uiview.update_viewport_state(context)
        self.uiview.begin()
        
        # set UIVIEW projection and viewport
        camera_frame = vl_coord_utils.get_view_camera_frame_rect(context)
        if not camera_frame:
            x, y = 0, 0
            w, h = context.region.width, context.region.height
            self.uiview.set_projection(glm.ortho(x, w, 0.0, h, -1000.0, 1000.0))
            self.uiview.set_viewport((0, 0, w, h))
            self.uiview.end()
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
                    warnings.warn(f"Could not compute VP2: {e}")
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
                    axis_vectors = {'X_AXIS': (1, 0, 0), 'Y_AXIS': (0, 1, 0), 'Z_AXIS': (0, 0, 1)}
                    axis_vector = axis_vectors[vl_settings.scene_scale_mode]

                    region = context.region
                    rv3d = context.space_data.region_3d
                    R = view3d_utils.location_3d_to_region_2d(region, rv3d, axis_vector)
                    R = self.uiview.unproject((R.x, R.y))
                    R = mathutils.Vector((R[0], R[1]))
                    O = mathutils.Vector((vl_settings.origin[0], vl_settings.origin[1]))
                    return (R - O).normalized()

            unit_settings = bpy.context.scene.unit_settings
            system = unit_settings.system
            scale = unit_settings.scale_length
            length_unit = unit_settings.length_unit
            match length_unit:
                case 'METERS':
                    length_unit = "m"
                case 'CENTIMETERS':
                    length_unit = "cm"
                case 'INCHES':
                    length_unit = "in"
                
            self.uiview.prop_distance_segment(vl_settings, "reference_distance_segment", 
                origin=vl_settings.origin,
                direction=get_distance_measurement_direction(),
                text=f"{vl_settings.scene_scale:.2f}{length_unit}",
                color=ORANGE)

        # Draw error messages
        if error_msg:=vl_settings.error_message:
            lines = str(error_msg).splitlines()
            text_height = LINE_HEIGHT * len(lines)
            font_id = 0
            blf.position(font_id, ERROR_TEXT_X_OFFSET, text_height + ERROR_TEXT_Y_OFFSET, 0)
            blf.size(font_id, FONT_SIZE)
            blf.color(font_id, 0.7, 0.2, 0.2, 1)
            for i, line in enumerate(lines):
                blf.position(font_id, ERROR_TEXT_X_OFFSET, text_height - LINE_HEIGHT * i + ERROR_TEXT_Y_OFFSET, 0)
                blf.draw(font_id, f"{line}")

        # Execute the draw calls
        self.uiview.end()
  
        
    def get_compute_space(self) -> solver.types.Rect:
        """compute space is a normalized square"""
        # TODO: make this user definable
        return solver.types.Rect(-1, -1, 2, 2)
    

class VIEW_OT_VanishingLinesStopOperator(bpy.types.Operator):
    bl_idname = "view.vanishing_lines_stop_operator"
    bl_label = "Stop Vanishing Lines Operator"
    bl_description  = "Stop calibrating the active camera."

    def execute(self, context):
        for op in bpy.context.window.modal_operators:
            if op.bl_idname == 'VIEW_OT_vanishing_lines_operator':
                op.cancel(context)
                return {'FINISHED'}
        self.report({'WARNING'}, "No active Vanishing Lines Operator found")
        return {'CANCELLED'}


######################
# REGISTER FUNCTIONS #
######################
def view_menu_func(self, context):
    self.layout.operator(VIEW_OT_VanishingLinesStartOperator.bl_idname, text="Vanishing Lines Modal Operator")

def view_draw_func():
    # global draw_list
    """Wrapper function to call the view3d_draw method of the operator instance."""
    if op:=vl_utils.get_running_operator_by_idname("VIEW_OT_vanishing_lines_operator"):
        op.view3d_draw(bpy.context)

def on_depsgraph_update(scene, depsgraph):
    """when the depsgraph changes, regarding the active camera, 
    or the output resolution, we update the solve."""
    for update in depsgraph.updates:
        if isinstance(update.id, bpy.types.Camera):
            if update.id.vl_settings.update_strategy == 'ON_DEPSGRAPH_UPDATE':
                camera_objects = [obj for obj in bpy.data.objects if obj.data.name == update.id.name and obj.type == 'CAMERA']
                for camera_object in camera_objects:
                    update_solve(camera_object)

draw_handler = None
def register():
    global draw_handler
    bpy.utils.register_class(VIEW_OT_VanishingLinesStartOperator)
    bpy.utils.register_class(VIEW_OT_VanishingLinesStopOperator)

    draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            view_draw_func, 
            (), 
            'WINDOW', 
            'POST_PIXEL' # POST_VIEW | POS_PIXEL | ...
        )
    
    if on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update) #TODO: this might supposed to be _pre_ update?
    bpy.types.VIEW3D_MT_view.append(view_menu_func)

def unregister():
    global draw_handler
    if draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handler, 'WINDOW')
        draw_handler = None

    if on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update)
    # bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update)
    bpy.types.VIEW3D_MT_view.remove(view_menu_func)
    bpy.utils.unregister_class(VIEW_OT_VanishingLinesStopOperator)
    bpy.utils.unregister_class(VIEW_OT_VanishingLinesStartOperator)
    