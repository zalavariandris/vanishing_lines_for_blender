from typing import Tuple, Callable
import math
import warnings

# Blender
import bpy

import blf
import mathutils
from bpy_extras import view3d_utils

# third party
from pyglm import glm

# local
from . uiview3d import UIView3D
from . import vl_params
from . import solver
from . import vl_utils

# Constants
FONT_SIZE = 16
LINE_HEIGHT = 18
ERROR_TEXT_X_OFFSET = 20
ERROR_TEXT_Y_OFFSET = 40


class MODAL_MT_RightClickMenu(bpy.types.Menu):
    bl_label = "Vanishig Lines"
    bl_idname = "MODAL_MT_right_click_menu"

    def draw(self, context):
        layout = self.layout.column()
        
        if op:=vl_utils.get_running_operator_by_idname('VIEW_OT_vanishing_lines_view_tool'):
            layout.prop_tabs_enum(op, 'mode')

            row = layout.row()
            row.enabled = op.mode in {'ONE_POINT'}
            row.prop(context.space_data.camera.data, 'lens')
            
            layout.prop(op, 'quad_mode')
            row = layout.row()
            row.enabled = op.mode in {'ONE_POINT', 'TWO_POINT'}
            row.prop(op, 'enable_manual_principal')
            layout.prop_menu_enum(op, 'first_axis')
            layout.prop_menu_enum(op, 'second_axis')
            layout.prop_menu_enum(op, 'scene_scale_mode')

            layout.prop(op, 'scene_scale')
            col = layout.column()
            col.enabled = op.scene_scale_mode != 'ORIGIN'
            col.prop(op, 'reference_distance_segment', index=0)
            col.prop(op, 'reference_distance_segment', index=1)
            
            
            
        # op.data_path = "scene.modal_bridge"
        # op.value = "RESET"
        
        # op = layout.operator("wm.context_set_string", text="Finish Tool")
        # op.data_path = "scene.modal_bridge"
        # op.value = "FINISH"


class VIEW_OT_VanishingLinesViewTool(bpy.types.Operator):
    bl_idname = "view.vanishing_lines_view_tool"
    bl_label = "Vanishing Lines View Tool"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name="Perspective Mode",
        items=[
            ('ONE_POINT',   "1-Point", "Find camera orientation."),
            ('TWO_POINT',   "2-Point", "Compute focal length from second vanishing point."),
            ('THREE_POINT', "3-Point", "Use the third vanishing point to find the principal point.")
        ],
        default='TWO_POINT',
        description="Number of vanishing points to use for camera calibration", 
        options=set()
    ) # type: ignore

    enable_manual_principal: bpy.props.BoolProperty(
        name="Manual Principal Point",
        default=False,
        description="Manually set the principal point instead of using the image center", 
        options=set()
    ) # type: ignore

    quad_mode: bpy.props.BoolProperty(
        name="Quad Mode",
        default=False,
        description="Use quadrilateral corners to define second vanishing point", 
        options=set()
    ) # type: ignore

    scene_scale_mode: bpy.props.EnumProperty(
        name="Scene Scale Mode",
        items=[
            ('SCREEN', "Screen", "Scale relative to screen space"),
            ('ORIGIN', "Origin", "Scale from origin point"),
            ('X_AXIS', "X Axis", "Scale along world X axis"),
            ('Y_AXIS', "Y Axis", "Scale along world Y axis"),
            ('Z_AXIS', "Z Axis", "Scale along world Z axis")
        ],
        default='X_AXIS',
        description="Method for determining scene scale reference", 
        options=set()
    ) # type: ignore

    scene_scale: bpy.props.FloatProperty(
        name="Scene Scale",
        default=10.0,
        min=0.01,
        max=99999.0,
        unit='LENGTH',
        subtype='DISTANCE',
        description="Real-world size of the reference measurement for scale calibration", 
        options=set()
    ) # type: ignore

    reference_distance_segment: bpy.props.FloatVectorProperty(
        name="Reference Distance Segment",
        size=2,
        default=(0.0, 0.5),
        description="Start and end points of the reference distance segment for scale measurement", 
        options=set()
    ) # type: ignore

    first_axis: bpy.props.EnumProperty(
        name="First Axis",
        items=[
            ('X+', "X+", "Positive X axis direction"),
            ('X-', "X-", "Negative X axis direction"),
            ('Y+', "Y+", "Positive Y axis direction"),
            ('Y-', "Y-", "Negative Y axis direction"),
            ('Z+', "Z+", "Positive Z axis direction"),
            ('Z-', "Z-", "Negative Z axis direction")
        ],
        default='Y+',
        description="First vanishing point axis orientation", 
        options=set()
    ) # type: ignore

    second_axis: bpy.props.EnumProperty(
        name="Second Axis",
        items=[
            ('X+', "X+", "Positive X axis direction"),
            ('X-', "X-", "Negative X axis direction"),
            ('Y+', "Y+", "Positive Y axis direction"),
            ('Y-', "Y-", "Negative Y axis direction"),
            ('Z+', "Z+", "Positive Z axis direction"),
            ('Z-', "Z-", "Negative Z axis direction")
        ],
        default='X-',
        description="Second vanishing point axis orientation", 
        options=set()
    ) # type: ignore

    origin: bpy.props.FloatVectorProperty(
        name="Origin",
        size=2,
        default=(0.0, 0.0),
        description="Origin point for reference measurements in normalized image space", 
        options=set()
    ) # type: ignore
    
    principal: bpy.props.FloatVectorProperty(
        name="Principal",
        size=2,
        default=(0.0, 0.0),
        description="Principal point (optical center) in normalized image space", 
        options=set()
    ) # type: ignore

    # Collections: Note that 'update' on the collection itself 
    # only fires if the collection pointer changes.
    # The actual updates are driven by the 'Line' properties above.
    first_vanishing_lines: bpy.props.CollectionProperty(
        type=vl_params.Line, 
        options=set()) # type: ignore
    second_vanishing_lines: bpy.props.CollectionProperty(
        type=vl_params.Line, 
        options=set()) # type: ignore
    third_vanishing_lines: bpy.props.CollectionProperty(
        type=vl_params.Line, 
        options=set()) # type: ignore
    
    error_message: str = ""
    
    # Store initial camera state for restoration on cancel
    _initial_camera_matrix: mathutils.Matrix = None  # type: ignore
    _initial_camera_lens: float = 0.0
    _initial_camera_shift_x: float = 0.0
    _initial_camera_shift_y: float = 0.0
    
    def invoke(self, context, event):
        vl_params.set_defaults(self)
        self.uiview = UIView3D()
        self.middle_mouse_pressed = False

        context.space_data.region_3d.view_perspective = 'CAMERA'
        
        # Save initial camera state for restoration on cancel
        if context.space_data.camera:
            camera_object = context.space_data.camera
            self._initial_camera_matrix = camera_object.matrix_world.copy()
            self._initial_camera_lens = camera_object.data.lens
            self._initial_camera_shift_x = camera_object.data.shift_x
            self._initial_camera_shift_y = camera_object.data.shift_y
        
        context.window_manager.modal_handler_add(self)
        bpy.context.workspace.status_text_set(lambda header, context: self.status_text(header, context))

        self.update_solve(context)
        return {'RUNNING_MODAL'}
    
    def get_vl_params(self, context):
        return self
    
    def status_text(self, header, context) -> str:
        header.layout.label(text="vanishing point", icon='EVENT_ONEKEY')
        header.layout.label(text="vanishing points", icon='EVENT_TWOKEY')
        header.layout.label(text="vanishing points", icon='EVENT_THREEKEY')
        header.layout.label(text="cycle scale mode", icon='EVENT_R')
        header.layout.label(text="cancel", icon='EVENT_ESC')
        header.layout.label(text="finish", icon='EVENT_RETURN')
        
    def cancel(self, context):
        # Restore previous camera state
        # if context.space_data.camera and self._initial_camera_matrix is not None:
        #     camera_object = context.space_data.camera
        #     camera_object.matrix_world = self._initial_camera_matrix
        #     camera_object.data.lens = self._initial_camera_lens
        #     camera_object.data.shift_x = self._initial_camera_shift_x
        #     camera_object.data.shift_y = self._initial_camera_shift_y

        context.area.tag_redraw()
        bpy.context.workspace.status_text_set(None)
        return {'CANCELLED'}
    
    def finish(self, context):
        bpy.context.workspace.status_text_set(None)
        return {'FINISHED'}
    
    def modal(self, context, event):
        print("modal", event.type, event.value)
        if event.type in {'ESC'}:
            context.area.tag_redraw()
            return self.finish(context)
        
        if event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            context.area.tag_redraw()
            return self.finish(context)
        ##################
        # Control params #
        ##################
        vl_params = self.get_vl_params(context)
        if event.type in {'ONE', 'TWO', 'THREE', 'NUMPAD_1', 'NUMPAD_2', 'NUMPAD_3'} and event.value == 'PRESS':
            match event.type:
                case 'ONE' | 'NUMPAD_1':
                    vl_params.mode = 'ONE_POINT'
                case 'TWO' | 'NUMPAD_2':
                    vl_params.mode = 'TWO_POINT'
                case 'THREE' | 'NUMPAD_3':
                    vl_params.mode = 'THREE_POINT'
            self.update_solve(context)
            return {'RUNNING_MODAL'}
        
        if context.space_data.region_3d.view_perspective != 'CAMERA':
            return self.cancel(context)

        
        if event.type == 'MIDDLEMOUSE':
            if event.value == 'PRESS':
                self.middle_mouse_pressed = True
            elif event.value == 'RELEASE':
                self.middle_mouse_pressed = False


        if event.shift:
            # move region 3d
            if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
                context.space_data.region_3d.view_camera_zoom += (1 if event.type == 'WHEELUPMOUSE' else -1) * 6
                return {'RUNNING_MODAL'}
            
            elif event.type == 'MOUSEMOVE' and self.middle_mouse_pressed:
                # repimplement camera offset
                mouse_delta_x = event.mouse_prev_x - event.mouse_x
                mouse_delta_y = event.mouse_prev_y - event.mouse_y
                region = context.region

                # Get zoom factor to match coordinate projection
                view_camera_zoom = context.space_data.region_3d.view_camera_zoom
                zoom_fac = ((math.sqrt(2.0) + view_camera_zoom / 50.0) ** 2) / 4.0 # matches Blender magic zoom formula

                offset_delta_x = mouse_delta_x / (2.0 * zoom_fac * region.width)
                offset_delta_y = mouse_delta_y / (2.0 * zoom_fac * region.height)
                context.space_data.region_3d.view_camera_offset[0] += offset_delta_x
                context.space_data.region_3d.view_camera_offset[1] += offset_delta_y
                return {'RUNNING_MODAL'}
        else:
            # adjust parameters
            if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
                # delta = (1 if event.type == 'WHEELDOWNMOUSE' else -1) * 50
                # vl_params.scene_scale *= math.pow(1.1, delta * 0.03)
                distance_length = vl_params.reference_distance_segment[1] - vl_params.reference_distance_segment[0]
                distance_length*= (0.9 if event.type == 'WHEELUPMOUSE' else 1.1)
                vl_params.reference_distance_segment[1] = vl_params.reference_distance_segment[0] + distance_length
                self.update_solve(context)
                return {'RUNNING_MODAL'}
            
            elif event.type == 'MOUSEMOVE' and self.middle_mouse_pressed:
                if event.ctrl:
                    delta = event.mouse_prev_y - event.mouse_y
                    # vl_params.scene_scale *= math.pow(1.1, delta * 0.03)
                    distance_length = vl_params.reference_distance_segment[1] - vl_params.reference_distance_segment[0]
                    distance_length*=  math.pow(1.1, delta * 0.03)
                    vl_params.reference_distance_segment[1] = vl_params.reference_distance_segment[0] + distance_length
                    self.update_solve(context)
                    return {'RUNNING_MODAL'}
                else:
                    proj_mouse_x, proj_mouse_y = self.uiview.unproject((event.mouse_x, event.mouse_y))         # to update internal matrices
                    proj_mouse_prev_x, proj_mouse_prev_y = self.uiview.unproject((event.mouse_prev_x, event.mouse_prev_y)) # to update internal matrices
                    proj_mouse_delta_x = proj_mouse_prev_x - proj_mouse_x
                    proj_mouse_delta_y = proj_mouse_prev_y - proj_mouse_y
                    vl_params.origin[0] -=   proj_mouse_delta_x
                    vl_params.origin[1] -=   proj_mouse_delta_y
                    self.update_solve(context)
                    return {'RUNNING_MODAL'}

        if event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
            # This triggers the menu at the mouse location
            bpy.ops.wm.call_menu(name=MODAL_MT_RightClickMenu.bl_idname)
            return {'RUNNING_MODAL'}

        # capture ui controls events
        changed = self.uiview.event(context, event)
        if changed:
            self.update_solve(context)
        
        return {'RUNNING_MODAL'}
    
    def view3d_draw(self, context):
        self.uiview.begin()
        x, y = 0, 0
        w, h = context.region.width, context.region.height
        region_aspect = w / h

        # get SpaceView3D
        space = context.space_data
        if not space or space.type != 'VIEW_3D':
            warnings.warn("Context is not a 3D Viewport!")
            return

        if context.space_data.region_3d.view_perspective == 'CAMERA':
            self.uiview.set_coordinate_system_to_camera_frame(context)
        else:
            self.uiview.set_view(glm.mat4(1.0))
            if region_aspect >= 1.0:
                self.uiview.set_projection(glm.ortho(-1, 1, -1/region_aspect, 1/region_aspect, -1000.0, 1000.0))
            else:
                self.uiview.set_projection(glm.ortho(-1*region_aspect, 1*region_aspect, -1, 1, -1000.0, 1000.0))
            self.uiview.set_viewport((0, 0, w, h))
        ##

        GREEN = (0,1,0,1)
        RED = (1,0,0,1)
        BLUE = (0,0.3, 1.0, 1.0)
        YELLOW = (1,1,0,1)
        ORANGE = (1.0, 0.5, 0.0, 1.0)

        ###########################
        # Vanishing Line CONTROLS #
        ###########################
        vl_params = self.get_vl_params(context)
        _ = self.uiview.prop_point(vl_params, "origin",    
            text="O",
            color=YELLOW)
        
        _ = self.uiview.prop_point(vl_params, "principal", 
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
        first_axis = axes_mapping[vl_params.first_axis]
        second_axis = axes_mapping[vl_params.second_axis]
        third_axis = solver.helpers.third_axis(first_axis, second_axis) # find third axis based on the first two

        if vl_params.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
            # Draw first vanishing lines
            for line in self.first_vanishing_lines:
                self.uiview.prop_line(line, color=get_axis_color(first_axis))

        if vl_params.mode in {'ONE_POINT'}:
            # Draw the horizontal line for the vp1 mode:
            self.uiview.prop_line(vl_params.second_vanishing_lines[0], color=get_axis_color(second_axis))

        if vl_params.mode in {'TWO_POINT', 'THREE_POINT'}:
            if self.quad_mode:
                first_line = vl_params.first_vanishing_lines[ 0]
                last_line =  vl_params.first_vanishing_lines[-1]
                
                for line_start, line_end in [(first_line.start, last_line.start), (first_line.end, last_line.end)]:
                    self.uiview._draw_layer.add_line(
                        self.uiview.project(line_start), 
                        self.uiview.project(line_end), 
                        get_axis_color(second_axis))
                    
            else:
                for line in vl_params.second_vanishing_lines:
                    self.uiview.prop_line(line, color=get_axis_color(second_axis))

        if vl_params.mode in {'THREE_POINT'}:
            for line in vl_params.third_vanishing_lines:
                self.uiview.prop_line(line, color=get_axis_color(third_axis))

        ###############################
        # reference distance CONTROLS #
        ###############################
        if vl_params.scene_scale_mode != 'ORIGIN':
            def get_distance_measurement_direction() -> mathutils.Vector:
                if vl_params.scene_scale_mode == 'SCREEN':
                    return mathutils.Vector((1,0))
                else:
                    axis_vectors = {'X_AXIS': (1, 0, 0), 'Y_AXIS': (0, 1, 0), 'Z_AXIS': (0, 0, 1)}
                    axis_vector = axis_vectors[vl_params.scene_scale_mode]

                    region = context.region
                    rv3d = context.space_data.region_3d
                    R = view3d_utils.location_3d_to_region_2d(region, rv3d, axis_vector)
                    R = self.uiview.unproject((R.x, R.y))
                    R = mathutils.Vector((R[0], R[1]))
                    O = mathutils.Vector((vl_params.origin[0], vl_params.origin[1]))
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
                
            self.uiview.prop_distance_segment(self, "reference_distance_segment", 
                origin=self.origin,
                direction=get_distance_measurement_direction(),
                text=f"{self.scene_scale:.2f}{length_unit}",
                color=ORANGE)
            
        # draw vanishing points
        if context.space_data.region_3d.view_perspective == 'CAMERA':
            camera_object = context.space_data.camera
            compute_space = solver.types.Rect(-1, -1, 2, 2)
            
            # Get camera intrinsics
            projection, view = vl_utils.get_camera_intrinsics(camera_object, compute_space)
            vp1, vp2, vp3 = solver.helpers.vanishing_points_from_camera(projection, view)


            nr_of_vps = {'ONE_POINT': 1,'TWO_POINT': 2,'THREE_POINT': 3}[vl_params.mode]
            for vp, color in [(vp1, RED), (vp2, GREEN), (vp3, BLUE)][:nr_of_vps]:
                x, y = self.uiview.project((vp.x, vp.y))
                self.uiview._draw_layer.add_point(
                    (x, y),
                    color=color
                )

                # for P, Q in vl_params.first_vanishing_lines:
                #     self.uiview._draw_layer.add_line(
                #         self.uiview.project(vl_utils.closest_point_to_target([P, Q], vp1)), 
                #         self.uiview.project(vp1), 
                #         vl_utils.dim_color(RED))
                
        # Draw error messages
        if error_msg:=vl_params.error_message:
            lines = str(error_msg).splitlines()
            text_block_height = LINE_HEIGHT * len(lines)
            text_block_width = max([blf.dimensions(0, line)[0] for line in lines])
            font_id = 0
            center = context.region.width/2, context.region.height/2
            blf.size(font_id, FONT_SIZE)
            blf.color(font_id, 0.7, 0.2, 0.2, 1)
            for i, line in enumerate(lines):
                line_width = blf.dimensions(font_id, line)[0]
                blf.position(font_id, center[0] - line_width/2, center[1] + LINE_HEIGHT * i - text_block_height/2, 0)
                blf.draw(font_id, f"{line}")

        ## draw compute space
        x_min, y_min = self.uiview.project((-1,-1))
        x_max, y_max = self.uiview.project((1, 1))
        self.uiview._draw_layer.add_rect(
            (x_min, y_min),
            (x_max - x_min, y_max - y_min),
            color=(0,1,1,0.1)
        )

        ## draw info
        self.uiview._draw_layer.add_annotation(
            pos=glm.vec2(100, 100),
            text="Info",
            color=glm.vec4(1.0, 1.0, 0.0, 1.0)
        )

        self.uiview.end()

        # self.update_solve(context)

    def update_solve(self, context):
        compute_space = solver.types.Rect(-1,-1,2,2)

        vl_params = self.get_vl_params(context)
        try:
            # map props to solver
            mode = {
                "ONE_POINT":   solver.types.SolverMode.OneVP,
                "TWO_POINT":   solver.types.SolverMode.TwoVP,
                "THREE_POINT": solver.types.SolverMode.ThreeVP
            }[vl_params.mode]

            reference_axis = {
                'ORIGIN': None,# TODO: ORIGIN option
                'SCREEN': solver.types.ReferenceAxis.Screen,
                'X_AXIS': solver.types.ReferenceAxis.X_Axis,
                'Y_AXIS': solver.types.ReferenceAxis.Y_Axis,
                'Z_AXIS': solver.types.ReferenceAxis.Z_Axis
            }[vl_params.scene_scale_mode]

            first_axis = {
                'X+': solver.types.Axis.PositiveX,
                'Y+': solver.types.Axis.PositiveY,
                'Z+': solver.types.Axis.PositiveZ,
                'X-': solver.types.Axis.NegativeX,
                'Y-': solver.types.Axis.NegativeY,
                'Z-': solver.types.Axis.NegativeZ
            }[vl_params.first_axis]

            second_axis = {
                'X+': solver.types.Axis.PositiveX,
                'Y+': solver.types.Axis.PositiveY,
                'Z+': solver.types.Axis.PositiveZ,
                'X-': solver.types.Axis.NegativeX,
                'Y-': solver.types.Axis.NegativeY,
                'Z-': solver.types.Axis.NegativeZ
            }[vl_params.second_axis]

            second_vanishing_lines = [(line.start, line.end) for line in vl_params.second_vanishing_lines]
            if vl_params.quad_mode and mode in {solver.types.SolverMode.TwoVP, solver.types.SolverMode.ThreeVP}:
                first_line = vl_params.first_vanishing_lines[ 0]
                last_line =  vl_params.first_vanishing_lines[-1]

                second_vanishing_lines = [
                    (first_line.start, last_line.start), (first_line.end, last_line.end)
                ]

            # if context.space_data.lock_camera
            # focal_length = camera_object.data.lens / camera_object.data.sensor_width * compute_space.height
            match context.space_data.region_3d.view_perspective:
                case 'CAMERA':
                    camera_object = context.space_data.camera
                    focal_length = camera_object.data.lens / camera_object.data.sensor_width * compute_space.height

                case 'PERSP':
                    # print("compute for PERSP view")
                    region_aspect = context.region.width / context.region.height
                    if region_aspect >= 1.0:
                        focal_length = context.space_data.lens / 36.0 * compute_space.width
                    else:
                        # print("compute for PERSP view - height")
                        focal_length = context.space_data.lens / 24.0 * compute_space.height

                case 'ORTHO':
                    context.space_data.region_3d.view_perspective = 'PERSP'
                    focal_length = context.space_data.lens / 36.0 * compute_space.height

            if not self.enable_manual_principal:
                self.principal = compute_space.center
            # print("compute:", compute_space)
            projection, view = solver.core.solve(
                mode = mode,
                viewport=compute_space,
                first_vanishing_lines= [(line.start, line.end) for line in  self.first_vanishing_lines],
                second_vanishing_lines=second_vanishing_lines,
                third_vanishing_lines= [(line.start, line.end) for line in  self.third_vanishing_lines],

                f = focal_length,
                P = (self.principal[0], self.principal[1]), # TODO: is [0], [1] necessary?
                O = (self.origin[0],    self.origin[1]),

                reference_axis=reference_axis, # TODO: make configurable
                reference_distance_segment=(self.reference_distance_segment[0], self.reference_distance_segment[1]-self.reference_distance_segment[0]), # TODO: make fist value configurable
                reference_world_size=self.scene_scale,

                first_axis=first_axis,
                second_axis=second_axis
            )

            ## apply solver results to blender view
            vl_utils.apply_solver_results_to_view3d(
                projection, 
                view, 
                context, 
                compute_space=tuple(compute_space), 
                fit_mode='COVER'
            )

            vl_params.error_message = ""
                    
        except Exception as e:
            error_type = type(e).__name__  # Gets 'ValueError' as a string
            error_message = str(e)         # Gets the actual message you wrote in 'raise'
            vl_params.error_message = f"{error_type}\n{error_message}"
            import traceback
            traceback.print_exc()

        if context.area.type == 'VIEW_3D':
            context.area.tag_redraw()


    # def execute(self, context):
    #     vl_settings = self
    #     ...


######################
def view_menu_func(self, context):
    self.layout.operator(VIEW_OT_VanishingLinesViewTool.bl_idname, text="Calibrate View with Vanishing Lines")

def rv3d_draw_function():
    # global draw_list
    """Wrapper function to call the draw_view method of the operator instance."""
    # print("rv3d_draw_function")
    if op:=vl_utils.get_running_operator_by_idname('VIEW_OT_vanishing_lines_view_tool'):
        op.view3d_draw(bpy.context)

draw_handler = None
def register():
    bpy.utils.register_class(MODAL_MT_RightClickMenu)
    bpy.utils.register_class(VIEW_OT_VanishingLinesViewTool)
    bpy.types.VIEW3D_MT_view.append(view_menu_func)

    global draw_handler
    draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            rv3d_draw_function, 
            (), 
            'WINDOW', 
            'POST_PIXEL' # POST_VIEW | POS_PIXEL | ...
        )

def unregister():
    global draw_handler
    if draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handler, 'WINDOW')
        draw_handler = None

    modal_operators = bpy.context.window.modal_operators
    # print([op.bl_idname if op else None for op in modal_operators])
    for op in bpy.context.window.modal_operators:
        if hasattr(op, 'cancel'):
            op.cancel(bpy.context)
        if hasattr(op, 'cleanup'):
            op.cleanup(bpy.context)


    bpy.utils.unregister_class(VIEW_OT_VanishingLinesViewTool)
    bpy.types.VIEW3D_MT_view.remove(view_menu_func)
    bpy.utils.unregister_class(MODAL_MT_RightClickMenu)

    
