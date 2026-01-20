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
from .view3d_ui import View3DUI
from . import vl_properties_camera
from . import solver
from . import vl_utils
from . import vl_properties_camera

# Constants
FONT_SIZE = 16
LINE_HEIGHT = 18


def unsolve(projection: glm.mat4, view: glm.mat4):
    return vp1, vp2, vp3

class VIEW3D_MT_vl_solve_orientation_context(bpy.types.Menu):
    bl_label = "Vanishing Lines Context Menu"
    bl_idname = "VIEW3D_MT_vl_solve_orientation_context"

    @classmethod
    def poll(kls, context):
        return vl_utils.is_operator_running('VIEW3D_OT_vl_solve_orientation')

    def draw(self, context):
        layout = self.layout.column()
        if op:=vl_utils.get_running_operator_by_idname('VIEW3D_OT_vl_solve_orientation'):
            vl_settings = op.vl_settings
            layout.prop_tabs_enum(vl_settings, 'mode')

            row = layout.row()
            row.enabled = vl_settings.mode in {'ONE_POINT'}
            row.prop(context.area.spaces.active.camera.data, 'lens')
            
            row = layout.row()
            row.enabled = vl_settings.mode in {'TWO_POINT', 'THREE_POINT'}
            row.prop(vl_settings, 'quad_mode')

            row = layout.row()
            row.enabled = vl_settings.mode in {'ONE_POINT', 'TWO_POINT'}
            # row.prop(vl_settings, 'enable_manual_principal')
            layout.prop_menu_enum(vl_settings, 'first_axis')
            layout.prop_menu_enum(vl_settings, 'second_axis')
            layout.prop_menu_enum(vl_settings, 'scene_scale_mode')

            layout.prop(vl_settings, 'scene_scale')
            col = layout.column()
            col.enabled = vl_settings.scene_scale_mode != 'ORIGIN'
            col.prop(vl_settings, 'reference_distance_segment', index=0)
            col.prop(vl_settings, 'reference_distance_segment', index=1)
        

class VIEW3D_OT_vl_solve_orientation(bpy.types.Operator):
    bl_idname = "view3d.vl_solve_orientation"
    bl_label = "Vanishing Lines View Tool"
    bl_options = {'REGISTER', 'UNDO'} # TODO: review other options {'BLOCKING', 'GRAB_CURSOR'}

    vl_settings: bpy.props.PointerProperty(type=vl_properties_camera.VLSettings) # type: ignore

    navigation_mode: bpy.props.EnumProperty(
        items=[
            ('NONE', "None", ""),
            ('ORBIT', "Orbit", ""),
            ('PAN', "Pan", ""),
            ('DOLLY', "Dolly", ""),
        ],
        default='NONE'
    ) # type: ignore

    mouse_dragging: bpy.props.BoolProperty(default=False) # type: ignore

    # Store initial camera state for restoration on cancel
    _initial_camera_matrix: mathutils.Matrix = None  # type: ignore
    _initial_camera_lens: float = 0.0
    _initial_camera_shift_x: float = 0.0
    _initial_camera_shift_y: float = 0.0
    _middle_mouse_pressed: bool = False
    _context_area = None  # Store the area where operator is running
    _context_region = None  # Store the region where operator was invoked
    _msgbus_owner = None  # Owner object for msgbus subscription
    
    def invoke(self, context, event):
        # Store the area and region where this operator is running
        self._context_area = context.area
        
        # Detect quadview and use quad[3] (camera view) if available
        target_region = context.region
        if context.area and context.area.spaces.active.region_quadviews:
            quad_regions = [r for r in context.area.regions if r.type == 'WINDOW']
            if len(quad_regions) >= 4:
                target_region = quad_regions[3]
        
        self._context_region = target_region
        
        # Switch to camera view
        self._context_area.spaces.active.region_3d.view_perspective = 'CAMERA'
        camera_object = self._context_area.spaces.active.camera

        if camera_object is None:
            self.report({'WARNING'}, "No camera found in the active 3D Viewport.")
            return {'CANCELLED'}

        # Initialize UIView3D for drawing and interaction in the viewport
        self.uiview = View3DUI()

        # Save initial camera state for restoration on cancel
        self._initial_camera_matrix = camera_object.matrix_world.copy()
        self._initial_camera_lens = camera_object.data.lens
        self._initial_camera_shift_x = camera_object.data.shift_x
        self._initial_camera_shift_y = camera_object.data.shift_y

        # Initialize vl_params if not already done
        if vl_settings:=self.vl_settings:
            if not vl_settings.initialized:
                # Load existing parameters from camera
                vl_properties_camera.set_defaults(vl_settings)
                vl_settings.initialized = True

        # Register the statusbar draw callback
        bpy.context.workspace.status_text_set(lambda header, context: self.status_text(header, context))

        # adjust vanishing lines to the current transform of the camera
        vl_utils.adjust_vanishing_lines_to_camera(self.vl_settings, camera_object)

        # initial solve
        # self.update_solve()

        # Subscribe to camera lens changes for this operator instance
        self._msgbus_owner = object()
        bpy.msgbus.subscribe_rna(
            key=(bpy.types.Camera, "lens"),
            owner=self._msgbus_owner,
            args=(),
            notify=camera_lens_changed,
        )

        # Run the modal operator with correct region context
        with context.temp_override(region=self._context_region):
            context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        # -------------------------------------------------
        # Exit conditions
        # -------------------------------------------------
        
        if event.type in {'ESC'}:
            self._context_area.tag_redraw()
            return self.finish(context)
        
        if event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            self._context_area.tag_redraw()
            return self.finish(context)
        
        mouse_is_in_area = (
            event.mouse_region_x>0 and 
            event.mouse_region_x<context.area.width and 
            event.mouse_region_y>0 and 
            event.mouse_region_y<context.area.height
        )

        if not mouse_is_in_area:
            return {'PASS_THROUGH'}
        
        if context.region.type != 'WINDOW':
            return {'PASS_THROUGH'}
        
        ##########################
        # Handle Keyboard Events #
        ##########################
        vl_settings = self.vl_settings
        if event.value == 'PRESS':
            match event.type:
                case 'ONE' | 'NUMPAD_1':
                    vl_settings.mode = 'ONE_POINT'
                    self.update_solve()
                    return {'RUNNING_MODAL'}
                case 'TWO' | 'NUMPAD_2':
                    vl_settings.mode = 'TWO_POINT'
                    self.update_solve()
                    return {'RUNNING_MODAL'}
                case 'THREE' | 'NUMPAD_3':
                    vl_settings.mode = 'THREE_POINT'
                    self.update_solve()
                    return {'RUNNING_MODAL'}
                case 'Q':
                    vl_settings.quad_mode = not vl_settings.quad_mode
                    self.update_solve()
                    return {'RUNNING_MODAL'}
                
        # capture ui controls events
        changed = self.uiview.event(context, event)
        if changed:
            self.update_solve()
            return {'RUNNING_MODAL'}  



        # ############# #
        # CONTEXT MENUI #
        # ############# #

        if event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
            bpy.ops.wm.call_menu(name="VIEW3D_MT_vl_solve_orientation_context")
            return {'RUNNING_MODAL'}
        
        # ##########################
        # Handle NAVIGATION Events #
        # ##########################
        if event.type == 'MIDDLEMOUSE':
            if event.value == 'PRESS':
                self._middle_mouse_pressed = True
                return {'RUNNING_MODAL'}
            elif event.value == 'RELEASE':
                self._middle_mouse_pressed = False
                return {'RUNNING_MODAL'}
        
        # match event.type:

        #     case 'MOUSEMOVE' if self._middle_mouse_pressed and event.ctrl:
        #         # SMOOTH DOLLY CAMERA
        #         # Match Blender's native dolly speed: proportional to view_distance
        #         camera = self._context_area.spaces.active.camera
        #         rv3d = self._context_area.spaces.active.region_3d
                
        #         # Blender dolly formula: zfac = 1.0 + (pixel_delta * 0.01 * dist)
        #         # For wheel events, we simulate ~20 pixel movement per wheel step
        #         pixel_delta = event.mouse_y - event.mouse_prev_y
        #         zfac = 1.0 + (pixel_delta/20 * 0.003 * rv3d.view_distance)
                
        #         # Move camera along its local Z-axis by (1 - zfac) * dist
        #         dolly_distance = (1.0 - zfac) * rv3d.view_distance
        #         forward = camera.matrix_world.to_3x3() @ mathutils.Vector((0, 0, 1.0))
        #         camera.location += forward * dolly_distance
        #         vl_utils.adjust_vanishing_lines_to_camera(camera)
        #         return {'RUNNING_MODAL'}
            
        #     case 'WHEELUPMOUSE' | 'WHEELDOWNMOUSE':
        #         # STEP DOLLY CAMERA
        #         # Match Blender's native dolly speed: proportional to view_distance
        #         camera = self._context_area.spaces.active.camera
        #         rv3d = self._context_area.spaces.active.region_3d
                
        #         # Blender dolly formula: zfac = 1.0 + (pixel_delta * 0.01 * dist)
        #         # For wheel events, we simulate ~20 pixel movement per wheel step
        #         pixel_delta = 1 if event.type == 'WHEELUPMOUSE' else -1
        #         zfac = 1.0 + (pixel_delta * 0.003 * rv3d.view_distance)
                
        #         # Move camera along its local Z-axis by (1 - zfac) * dist
        #         dolly_distance = (1.0 - zfac) * rv3d.view_distance
        #         forward = camera.matrix_world.to_3x3() @ mathutils.Vector((0, 0, 1.0))
        #         camera.location += forward * dolly_distance
        #         vl_utils.adjust_vanishing_lines_to_camera(camera)
        #         return {'RUNNING_MODAL'}
            
        #     case 'MOUSEMOVE' if self._middle_mouse_pressed and event.shift:
        #         def pan_camera(camera, rv3d, region, delta_x, delta_y, pivot):
        #             """
        #             Pan camera by screen-space delta using Blender's built-in projection.
        #             pivot: the point to keep in focus (like view pivot)
        #             """
        #             # Original screen coordinate of pivot
        #             pivot_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, pivot)

        #             # New 2D coordinate with mouse delta
        #             new_2d = pivot_2d + mathutils.Vector((delta_x, delta_y))

        #             # Project back into world space at pivot depth
        #             new_world = view3d_utils.region_2d_to_location_3d(region, rv3d, new_2d, pivot)

        #             # Offset vector
        #             offset = pivot - new_world

        #             # Move camera by that offset
        #             camera.location += offset

        #         camera = self._context_area.spaces.active.camera
        #         rv3d = self._context_area.spaces.active.region_3d
        #         region = context.region

        #         delta_x = event.mouse_x - event.mouse_prev_x
        #         delta_y = event.mouse_y - event.mouse_prev_y    

        #         # pivot = center of view or custom pivot point
        #         pivot = rv3d.view_location

        #         pan_camera(camera, rv3d, region, delta_x, delta_y, pivot)
        #         vl_utils.adjust_vanishing_lines_to_camera(camera)
        #         return {'RUNNING_MODAL'}
            
            # case 'MOUSEMOVE' if self._middle_mouse_pressed:
            #     # ORBIT CAMERA
            #     print("orbit camera")
            #     camera = self._context_area.spaces.active.camera
            #     camera_transform = vl_utils.glm_from_blender_mat(camera.matrix_world)
            #     delta_x = event.mouse_prev_x - event.mouse_x
            #     delta_y = event.mouse_prev_y - event.mouse_y
            #     camera.matrix_world = vl_utils.glm_to_blender_mat(
            #         vl_utils.ball_control(camera_transform, glm.vec3(0,0,0), delta_x * 0.01, delta_y * 0.01))
            #     vl_utils.adjust_vanishing_lines_to_camera(camera)
            #     return {'RUNNING_MODAL'}
            
            # case 'WHEELUPMOUSE' | 'WHEELDOWNMOUSE':
            #     # Adjust camera zoom
            #     self._context_area.spaces.active.region_3d.view_camera_zoom += (1 if event.type == 'WHEELUPMOUSE' else -1) * 6
            #     return {'RUNNING_MODAL'}
            
            # case 'MOUSEMOVE' if self._middle_mouse_pressed and event.ctrl and event.alt and vl_settings.mode == 'ONE_POINT':
            #     # Adjust focal length
            #     delta = event.mouse_prev_y - event.mouse_y
            #     camera_object = self._context_area.spaces.active.camera
            #     camera_object.data.lens *= math.pow(1.1, -delta * 0.03)
            #     self.update_solve()
            #     return {'RUNNING_MODAL'}
                                            
            #     # # Move origin / Pan Camera # TODO: actually move the camera, and update the origin accordingly?
            #     # proj_mouse_x, proj_mouse_y = self.uiview.unproject((event.mouse_x, event.mouse_y))
            #     # proj_mouse_prev_x, proj_mouse_prev_y = self.uiview.unproject((event.mouse_prev_x, event.mouse_prev_y))
            #     # proj_mouse_delta_x = proj_mouse_prev_x - proj_mouse_x
            #     # proj_mouse_delta_y = proj_mouse_prev_y - proj_mouse_y
            #     # vl_settings.origin[0] -= proj_mouse_delta_x
            #     # vl_settings.origin[1] -= proj_mouse_delta_y
            #     return {'RUNNING_MODAL'}
            
            # case 'MOUSEMOVE' if self._middle_mouse_pressed:
            #     # Pan camera
            #     mouse_delta_x = event.mouse_prev_x - event.mouse_x
            #     mouse_delta_y = event.mouse_prev_y - event.mouse_y
            #     region = context.region

            #     # Get zoom factor to match coordinate projection
            #     view_camera_zoom = self._context_area.spaces.active.region_3d.view_camera_zoom
            #     zoom_fac = ((math.sqrt(2.0) + view_camera_zoom / 50.0) ** 2) / 4.0  # Blender magic zoom formula

            #     offset_delta_x = mouse_delta_x / (2.0 * zoom_fac * region.width)
            #     offset_delta_y = mouse_delta_y / (2.0 * zoom_fac * region.height)
            #     self._context_area.spaces.active.region_3d.view_camera_offset[0] += offset_delta_x
            #     self._context_area.spaces.active.region_3d.view_camera_offset[1] += offset_delta_y
            #     return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}
        
        # return {'RUNNING_MODAL'}
    
    def status_text(self, header, context):
        # keyboard
        header.layout.label(text="",  icon='EVENT_ONEKEY')
        header.layout.label(text="", icon='EVENT_TWOKEY')
        header.layout.label(text="", icon='EVENT_THREEKEY')
        header.layout.label(text="Set 1pt/2pt/3pt mode")
        header.layout.label(text="Scale mode", icon='EVENT_R')
        header.layout.label(text="Toggle Quad Mode", icon='EVENT_Q')
        header.layout.label(text=" Cancel", icon='EVENT_ESC')
        header.layout.label(text="Finish", icon='EVENT_RETURN')

        # mouse
        header.layout.label(text="", icon='EVENT_CTRL')
        header.layout.label(text="Move Origin", icon='MOUSE_MMB_DRAG')
        header.layout.label(text="", icon='EVENT_CTRL')
        header.layout.label(text="World Distance", icon='MOUSE_MMB_SCROLL')

        # context menu
        header.layout.label(text="Options", icon='MOUSE_RMB')
        
    def cancel(self, context):
        # Restore previous camera state
        # if context.area.spaces.active.camera and self._initial_camera_matrix is not None:
        #     camera_object = context.area.spaces.active.camera

        #     camera_object.matrix_world = self._initial_camera_matrix
        #     camera_object.data.lens = self._initial_camera_lens
        #     camera_object.data.shift_x = self._initial_camera_shift_x
        #     camera_object.data.shift_y = self._initial_camera_shift_y
        
        # Unsubscribe from msgbus
        if self._msgbus_owner is not None:
            bpy.msgbus.clear_by_owner(self._msgbus_owner)
            self._msgbus_owner = None
        
        if self._context_area:
            self._context_area.tag_redraw()
        bpy.context.workspace.status_text_set(None)
    
    def finish(self, context):
        # Unsubscribe from msgbus
        if self._msgbus_owner is not None:
            bpy.msgbus.clear_by_owner(self._msgbus_owner)
            self._msgbus_owner = None
        
        if self._context_area:
            self._context_area.tag_redraw()
        bpy.context.workspace.status_text_set(None)
        return {'FINISHED'}
    
    def view3d_draw(self, context):
        # draw only in the correct region
        if context.area != self._context_area:
            return
        
        # get the region


        self.uiview.begin()
        # get SpaceView3D
        if not context.area.spaces.active or context.area.spaces.active.type != 'VIEW_3D':
            warnings.warn("Context is not a 3D Viewport!")
            return
        
        window_region = next((r for r in context.area.regions if r.type == 'WINDOW'), None)
        if window_region is None:
            return
        
        region_aspect = window_region.width / window_region.height

        if context.area.spaces.active.region_3d.view_perspective == 'CAMERA':
            self.uiview.set_coordinate_system_to_camera_frame(context)
        else:
            self.uiview.set_view(glm.mat4(1.0))
            if region_aspect >= 1.0:
                self.uiview.set_projection(glm.ortho(-1, 1, -1/region_aspect, 1/region_aspect, -1000.0, 1000.0))
            else:
                self.uiview.set_projection(glm.ortho(-1*region_aspect, 1*region_aspect, -1, 1, -1000.0, 1000.0))
            self.uiview.set_viewport((0, 0, window_region.width, window_region.height))
        ##

        GREEN = (0,1,0,1)
        RED = (1,0,0,1)
        BLUE = (0,0.3, 1.0, 1.0)
        YELLOW = (1,0.9,0,1)
        ORANGE = (1.0, 0.5, 0.0, 1.0)

        ###########################
        # Vanishing Line CONTROLS #
        ###########################
        vl_settings = self.vl_settings
        
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

        # normalize vanishing lines for drawing

        if vl_settings.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
            # Draw first vanishing lines
            for line in vl_settings.first_vanishing_lines:
                self.uiview.prop_line(line, color=get_axis_color(first_axis))

        if vl_settings.mode in {'ONE_POINT'}:
            # Draw the horizontal line for the vp1 mode:
            self.uiview.prop_line(vl_settings.second_vanishing_lines[0], color=get_axis_color(second_axis))

        if vl_settings.mode in {'TWO_POINT', 'THREE_POINT'}:
            if vl_settings.quad_mode:
                # transpose first vanishing lines for quad mode
                first_line = vl_settings.first_vanishing_lines[ 0]
                last_line =  vl_settings.first_vanishing_lines[-1]
                second_vanishing_lines_coordinates = [(first_line.start, last_line.start), (first_line.end, last_line.end)]
                
                for P, Q in second_vanishing_lines_coordinates:
                    self.uiview._painter.add_line(self.uiview.project(P), self.uiview.project(Q), get_axis_color(second_axis))
                    
            else:
                for line in vl_settings.second_vanishing_lines:
                    self.uiview.prop_line(line, color=get_axis_color(second_axis))

        if vl_settings.mode in {'THREE_POINT'}:
            for line in vl_settings.third_vanishing_lines:
                self.uiview.prop_line(line, color=get_axis_color(third_axis))

        ###############################
        # reference distance CONTROLS #
        ###############################
        if vl_settings.scene_scale_mode != 'ORIGIN':
            def get_distance_measurement_direction() -> Tuple[float, float]:
                if vl_settings.scene_scale_mode == 'SCREEN':
                    return (1.0,0.0)
                else:
                    axis_vectors = {'X_AXIS': (1, 0, 0), 'Y_AXIS': (0, 1, 0), 'Z_AXIS': (0, 0, 1)}
                    axis_vector = axis_vectors[vl_settings.scene_scale_mode]

                    region = context.region
                    rv3d = context.area.spaces.active.region_3d
                    R = view3d_utils.location_3d_to_region_2d(region, rv3d, axis_vector)
                    R = self.uiview.unproject((R.x, R.y))
                    R = mathutils.Vector((R[0], R[1]))
                    O = mathutils.Vector((vl_settings.origin[0], vl_settings.origin[1]))

                    dir_vector = (R - O).normalized()
                    return dir_vector.x, dir_vector.y

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
                
            # self.uiview.prop_distance_segment(vl_settings, "reference_distance_segment", 
            #     origin=vl_settings.origin,
            #     direction=get_distance_measurement_direction(),
            #     text=f"{vl_settings.scene_scale:.2f}{length_unit}",
            #     color=ORANGE)
            
        # _ = self.uiview.prop_point(vl_settings, "origin",    
        #     text="O",
        #     color=YELLOW)

        ###########################################
        # DRAW Extended lines to vanishing points #
        ###########################################
        if not vl_settings.error_message:
            if vl_settings.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
                try:
                    vp1 = solver.core.compute_vanishing_point([
                        (line.start, line.end) 
                        for line in vl_settings.first_vanishing_lines])

                    for line in vl_settings.first_vanishing_lines:
                        self.uiview._painter.add_line(
                            self.uiview.project(vl_utils.closest_point_to_target([line.start, line.end], vp1)), 
                            self.uiview.project(vp1), vl_utils.dim_color(get_axis_color(first_axis)))
                        
                except solver.exceptions.VanishingLinesError as e:
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
                            self.uiview._painter.add_line(
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
                            self.uiview._painter.add_line(
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
                        self.uiview._painter.add_line(
                            self.uiview.project(vl_utils.closest_point_to_target([line.start, line.end], vp3)), 
                            self.uiview.project(vp3), 
                            vl_utils.dim_color(get_axis_color(third_axis)))
                        
                except ValueError as e:
                    warnings.warn(f"Could not compute VP3: {e}")

                projection, view = vl_utils.get_camera_matrices(camera_object=context.area.spaces.active.camera,
                    compute_space=solver.types.Rect(-1,-1,2,2))
                principal, f = solver.utils.decompose_intrinsics(solver.types.Rect(-1,-1,2,2), projection)
                self.uiview._painter.add_point(
                    pos=self.uiview.project(principal),
                    color=glm.vec4(1.0, 0.7, 0.0, 1.0),
                    shape='X',
                )

                self.uiview._painter.add_annotation(
                    pos=self.uiview.project(principal),
                    text="P",
                    color=glm.vec4(1.0, 0.7, 0.0, 1.0)
                )

        # Draw error messages
        if error_msg:=vl_settings.error_message:
            lines = str(error_msg).splitlines()
            text_block_height = LINE_HEIGHT * len(lines)
            text_block_width = max([blf.dimensions(0, line)[0] for line in lines])
            font_id = 0
            center = context.region.width/2, context.region.height/2
            blf.size(font_id, FONT_SIZE)
            blf.color(font_id, 0.7, 0.2, 0.2, 1)
            for i, line in enumerate(lines):
                line_width = blf.dimensions(font_id, line)[0]
                blf.position(font_id, center[0] - line_width/2, center[1] - LINE_HEIGHT * i - text_block_height/2, 0)
                blf.draw(font_id, f"{line}")

        ## draw compute space
        x_min, y_min = self.uiview.project((-1,-1))
        x_max, y_max = self.uiview.project((1, 1))
        self.uiview._painter.add_rect(
            (x_min, y_min),
            (x_max - x_min, y_max - y_min),
            color=(0,1,1,0.1)
        )

        ## draw info
        self.uiview._painter.add_annotation(
            pos=(x_min+(x_max-x_min)/2, y_min),
            text="Vanishing Lines · Beta Version",
            color=(0,1,1,0.3)
        )

        self.uiview.end()

        # self.update_solve(context)

    def update_solve(self):
        compute_space = solver.types.Rect(-1,-1,2,2)
        vl_settings = self.vl_settings
        try:
            # map props to solver
            mode = {
                "ONE_POINT":   solver.types.SolverMode.OneVP,
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

            # if self._context_area.spaces.active.lock_camera
            # focal_length = camera_object.data.lens / camera_object.data.sensor_width * compute_space.height
            match self._context_area.spaces.active.region_3d.view_perspective:
                case 'CAMERA':
                    camera_object = self._context_area.spaces.active.camera
                    focal_length = camera_object.data.lens / camera_object.data.sensor_width * compute_space.height

                case 'PERSP':
                    # print("compute for PERSP view")
                    # region_aspect = self._context_area.width / self._context_area.height
                    # get region aspect from context area
                    region = next((r for r in self._context_area.regions if r.type == 'WINDOW'), None)
                    region_aspect = region.width / region.height
                    if region_aspect >= 1.0:
                        focal_length = self._context_area.spaces.active.lens / 36.0 * compute_space.width
                    else:
                        # print("compute for PERSP view - height")
                        focal_length = self._context_area.spaces.active.lens / 24.0 * compute_space.height

                case 'ORTHO':
                    self._context_area.spaces.active.region_3d.view_perspective = 'PERSP'
                    focal_length = self._context_area.spaces.active.lens / 36.0 * compute_space.height

            # if not vl_settings.enable_manual_principal:
            #     vl_settings.principal = compute_space.center

            # print("compute:", compute_space)
            projection, view = solver.core.solve(
                mode = mode,
                viewport=compute_space,
                first_vanishing_lines= [(line.start, line.end) for line in  vl_settings.first_vanishing_lines],
                second_vanishing_lines=second_vanishing_lines,
                third_vanishing_lines= [(line.start, line.end) for line in  vl_settings.third_vanishing_lines],

                f = focal_length,
                P = (0,0), # TODO: is [0], [1] necessary?
                O = (vl_settings.origin[0],    vl_settings.origin[1]),
                reference_axis=reference_axis, # TODO: make configurable
                reference_distance_segment=(vl_settings.reference_distance_segment[0], vl_settings.reference_distance_segment[1]-vl_settings.reference_distance_segment[0]), # TODO: make fist value configurable
                reference_world_size=vl_settings.scene_scale,

                first_axis=first_axis,
                second_axis=second_axis
            )

            # Store current projected position of pivot point
            camera_object = self._context_area.spaces.active.camera
            
            # Use view orbit point as pivot
            orbit_point = self._context_area.spaces.active.region_3d.view_location
            pivot_point = glm.vec3(orbit_point.x, orbit_point.y, orbit_point.z)
            current_projection, current_view = vl_utils.get_camera_matrices(
                camera_object=camera_object,
                compute_space=solver.types.Rect(*compute_space)
            )
            viewport = glm.vec4(compute_space.x, compute_space.y, compute_space.width, compute_space.height)
            pivot_screen_full = glm.project(pivot_point, current_view, current_projection, viewport)
            pivot_screen = glm.vec2(pivot_screen_full.x, pivot_screen_full.y)
            
            # Apply projection and orientation changes
            vl_utils.apply_projection_to_blender_camera(
                projection,
                camera_object,
                compute_space=tuple(compute_space),
                fit_mode=camera_object.data.sensor_fit
            )

            vl_utils.apply_orientation_to_blender_camera(
                view, 
                camera_object
            )
            
            # Adjust camera position to keep pivot point at same screen position
            vl_utils.adjust_camera_to_keep_point_at_screen_position(
                camera_object=camera_object,
                world_point=pivot_point,
                target_screen_position=pivot_screen,
                projection=projection,
                compute_space=tuple(compute_space)
            )

            # ## apply solver results to blender view
            # vl_utils.apply_solver_results_to_view3d(
            #     projection, 
            #     view, 
            #     self._context_area, 
            #     compute_space=tuple(compute_space), 
            #     fit_mode='COVER'
            # )

            vl_settings.error_message = ""
                    
        except solver.exceptions.VanishingLinesError as e:
            error_type = type(e).__name__  # Gets 'ValueError' as a string
            error_message = str(e)         # Gets the actual message you wrote in 'raise'
            vl_settings.error_message = f"{error_type}\n{error_message}"
        except Exception as e:
            import traceback
            traceback.print_exc()

        if self._context_area.type == 'VIEW_3D':
            self._context_area.tag_redraw()


######################
def view_menu_func(self, context):
    self.layout.operator("view3d.vl_solve_orientation", text="Vanishing Lines - Orientation")

def rv3d_draw_function():
    # global draw_list
    """Wrapper function to call the draw_view method of the operator instance."""
    # print("rv3d_draw_function")
    if op:=vl_utils.get_running_operator_by_idname('VIEW3D_OT_vl_solve_orientation'):
        # Only draw in the area and region where the operator was invoked
        if bpy.context.area == op._context_area and bpy.context.region == op._context_region:
            op.view3d_draw(bpy.context)

def camera_lens_changed():
    # print("camera_lens_changed called")
    """Callback when camera lens changes"""
    # Only proceed if the operator is running
    op = vl_utils.get_running_operator_by_idname('VIEW3D_OT_vl_solve_orientation')
    if not op:
        # print("camera_lens_changed: operator not running")
        return
    
    # Only update if the changed camera is the one being used by the operator
    if not op._context_area or not op._context_area.spaces.active.camera:
        # print("camera_lens_changed: no context area or camera")
        return
    
    def deferred_update():
        """Deferred update to run outside msgbus callback context"""
        if op := vl_utils.get_running_operator_by_idname('VIEW3D_OT_vl_solve_orientation'):
            # Find the window containing the stored area
            for window in bpy.context.window_manager.windows:
                if op._context_area in window.screen.areas[:]:
                    op.update_solve()
                    op._context_area.tag_redraw()
                    # print("camera_lens_changed: updated operator")
                    break
        return None  # Don't repeat the timer
    deferred_update()
    # Schedule update to run outside msgbus callback context
    
    # bpy.app.timers.register(deferred_update, first_interval=0.0)

draw_handler = None

def register():
    bpy.utils.register_class(VIEW3D_MT_vl_solve_orientation_context)
    bpy.utils.register_class(VIEW3D_OT_vl_solve_orientation)
    bpy.types.VIEW3D_MT_view.append(view_menu_func)

    global draw_handler
    draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            rv3d_draw_function, 
            (), 
            'WINDOW', 
            'POST_PIXEL' # POST_VIEW | POS_PIXEL | ...
        )

def unregister():
    bpy.context.workspace.status_text_set(None)

    global draw_handler
    if draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handler, 'WINDOW')
        draw_handler = None

    for op in bpy.context.window.modal_operators:
        try:
            op.cancel(bpy.context)
        except AttributeError:
            pass

        try:
            op.cancel(bpy.context)
        except AttributeError:
            pass

    bpy.utils.unregister_class(VIEW3D_OT_vl_solve_orientation)
    bpy.types.VIEW3D_MT_view.remove(view_menu_func)
    bpy.utils.unregister_class(VIEW3D_MT_vl_solve_orientation_context)

    
