from typing import Tuple, Callable, overload, Iterable
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
from .view3d_gui import View3dGUI
from .view3d_painter import View3dPainter
from . import vl_properties_camera
from . import solver
from . import vl_utils
from . import vl_properties_camera

from pyglm import glm

# Constants
FONT_SIZE = 16
LINE_HEIGHT = 18




class MODAL_MT_VLContextMenu(bpy.types.Menu):
    bl_label = "Vanishing Lines Context Menu"
    bl_idname = "MODAL_MT_vl_context_menu"

    vl_settings: vl_properties_camera.VLSettingsCamera|None = None  # type: ignore

    fov: bpy.props.FloatProperty(
        name="Focal Length",
        default=50.0,
        description="Set the camera focal length",
        unit='CAMERA',
        update=lambda self, context: vl_utils.update_fov_in_running_operator(self.fov, context
    ) # type: ignore


    @classmethod
    def poll(kls, context):
        return vl_utils.is_operator_running('VIEW3D_OT_vl_solve_orientation')

    def draw(self, context):
        layout = self.layout.column()
        vl_settings = context.space_data.camera.vl_settings # get vl settings from the active camera

        

        if op:=vl_utils.get_running_operator_by_idname('VIEW3D_OT_vl_solve_orientation'):
            # vl_settings = op.get_vl_settings(context)
            # layout.prop_tabs_enum(vl_settings, 'mode')

            # row = layout.row()
            # row.enabled = vl_settings.mode in {'ONE_POINT'}
            # row.prop(context.area.spaces.active.camera.data, 'lens')
            
            # row = layout.row()
            # row.enabled = vl_settings.mode in {'TWO_POINT', 'THREE_POINT'}
            # row.prop(vl_settings, 'quad_mode')

            # row = layout.row()
            # row.enabled = vl_settings.mode in {'ONE_POINT', 'TWO_POINT'}
            # # row.prop(vl_settings, 'enable_manual_principal')
            # layout.prop_menu_enum(vl_settings, 'first_axis')
            # layout.prop_menu_enum(vl_settings, 'second_axis')
            # layout.prop_menu_enum(vl_settings, 'scene_scale_mode')

            # layout.prop(vl_settings, 'scene_scale')
            # col = layout.column()
            # col.enabled = vl_settings.scene_scale_mode != 'ORIGIN'
            # col.prop(vl_settings, 'reference_distance_segment', index=0)
            # col.prop(vl_settings, 'reference_distance_segment', index=1)


class VIEW3D_OT_vl_solve_orientation(bpy.types.Operator):
    bl_idname = "view3d.vl_solve_orientation"
    bl_label = "Vanishing Lines View Tool"
    bl_options = {'REGISTER', 'UNDO'} # TODO: review other options {'BLOCKING', 'GRAB_CURSOR'}

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

    # _msgbus_owner = None  # Owner object for msgbus subscription
    _draw_handler = None  # Store the draw handler reference

    uiview: View3dGUI|None=None  # type: ignore
    
    def invoke(self, context, event):
        ##########################################
        # Get the camera and the initial context #
        ##########################################
        self._context_area = context.area
        
        # Detect quadview and use quad[3] (camera view) if available
        target_region = context.region
        if context.area and context.area.spaces.active.region_quadviews:
            quad_regions = [r for r in context.area.regions if r.type == 'WINDOW']
            if len(quad_regions) >= 4:
                target_region = quad_regions[3]
        
        self._context_region = target_region
        
        # Get the camera object
        self._context_area.spaces.active.region_3d.view_perspective = 'CAMERA'
        camera_object = self._context_area.spaces.active.camera

        if camera_object is None:
            self.report({'WARNING'}, "No camera found in the active 3D Viewport.")
            return {'CANCELLED'}

        # Save initial camera state for restoration on cancel
        self._initial_camera_matrix = camera_object.matrix_world.copy()
        self._initial_camera_lens = camera_object.data.lens
        self._initial_camera_shift_x = camera_object.data.shift_x
        self._initial_camera_shift_y = camera_object.data.shift_y

        ############################################
        # Initialize vl_settings to current camera #
        ############################################
        glm_proj, glm_view = vl_utils.get_camera_matrices(camera_object, solver.types.Rect(-1,-1,2,2))
        vl_settings = camera_object.vl_settings # TODO: move vl_settings to operator?
        vl_settings.ensure_vanishing_lines()

        # Set the anchor point based on cursor position
        cursor = context.scene.cursor.location.copy()
        cursor_camera_space = glm_view * glm.vec4(cursor.x, cursor.y, cursor.z, 1.0)
        is_cursor_behind = cursor_camera_space.z > 0
        if is_cursor_behind:
            orbit_location = context.area.spaces.active.region_3d.view_location
            vl_settings.anchor_world = (orbit_location.x, orbit_location.y, orbit_location.z)
        else:
            vl_settings.anchor_world = context.scene.cursor.location.to_tuple()

        # Match VLSettings to current Camera
        vl_settings.proj_array = vl_utils.matrix_to_array(vl_utils.glm_to_blender_mat(glm_proj))
        vl_settings.view_array = vl_utils.matrix_to_array(vl_utils.glm_to_blender_mat(glm_view))
        _, f = solver.utils.decompose_intrinsics(solver.types.Rect(-1,-1,2,2), glm_proj)
        fovx = solver.utils.fov_from_focal_length(f, 2)
        vl_settings.fovx = fovx
        vl_settings.unsolve()

        ##################################
        # Initialize UIView3D for drawing and interaction in the viewport
        #################################
        self.uiview = View3dGUI()

        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            self.handle_draw, 
            tuple(), 
            'WINDOW', 
            'POST_PIXEL' # POST_VIEW | POS_PIXEL | ...
        )
        self.view3d_tick(context) # setup initial gui
        context.area.tag_redraw()

        # # Subscribe to camera lens changes for this operator instance
        # self._msgbus_owner = object()
        # bpy.msgbus.subscribe_rna(
        #     key=(camera_object, "data"),
        #     owner=self._msgbus_owner,
        #     args=tuple(),
        #     notify=lambda: self.on_camera_lens_changed(),
        # )

        # Register the statusbar draw callback
        bpy.context.workspace.status_text_set(lambda header, context: self.status_text(header, context))

        # Run the modal operator with correct region context
        with context.temp_override(region=self._context_region):
            context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        if event.type in {'ESC'}:
            self._context_area.tag_redraw()
            self.cleanup(context)
            return {'CANCELLED'}
        
        if event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            self._context_area.tag_redraw()
            self.cleanup(context)
            return {'FINISHED'}
        
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
        
        if event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
            # This triggers the menu at the mouse location
            bpy.ops.wm.call_menu(name=MODAL_MT_VLContextMenu.bl_idname)
            return {'RUNNING_MODAL'}
        
        #########################
        #########################
        vl_settings = context.space_data.camera.vl_settings
        
        ##########################
        # Handle Keyboard Events #
        ##########################
        if event.value == 'PRESS':
            match event.type:
                case 'ONE' | 'NUMPAD_1':
                    vl_settings.mode = 'ONE_POINT'
                    self.update_solve(context)
                    return {'RUNNING_MODAL'}
                
                case 'TWO' | 'NUMPAD_2':
                    vl_settings.mode = 'TWO_POINT'
                    self.update_solve(context)
                    return {'RUNNING_MODAL'}
                
                case 'THREE' | 'NUMPAD_3':
                    vl_settings.mode = 'THREE_POINT'
                    self.update_solve(context)
                    return {'RUNNING_MODAL'}
                
                case 'Q':
                    vl_settings.quad_mode = not vl_settings.quad_mode
                    self.update_solve(context)
                    return {'RUNNING_MODAL'}
                
        # capture ui controls events
        changed = self.uiview.event(context, event)
        self.view3d_tick(context)
        if changed:
            vl_settings.solve()
            vl_settings.to_camera(context.space_data.camera)
            self.update_solve(context)
            return {'RUNNING_MODAL'}  

        # ############# #
        # CONTEXT MENUI #
        # ############# #
        
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

        # return {'PASS_THROUGH'}
        
        return {'RUNNING_MODAL'}
    
    def view3d_tick(self, context):        
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

        GREEN =  mathutils.Vector((0,1,0,1))
        RED =    mathutils.Vector((1,0,0,1))
        BLUE =   mathutils.Vector((0,0.3, 1.0, 1.0))
        YELLOW = mathutils.Vector((1,0.9,0,1))
        ORANGE = mathutils.Vector((1.0, 0.5, 0.0, 1.0))

        ###########################
        # Vanishing Line CONTROLS #
        ###########################
        vl_settings = context.space_data.camera.vl_settings
        
        def get_axis_color(axis:solver.types.Axis) -> mathutils.Vector:
            match axis:
                case solver.types.Axis.PositiveX | solver.types.Axis.NegativeX:
                    return RED
                case solver.types.Axis.PositiveY | solver.types.Axis.NegativeY:
                    return GREEN
                case solver.types.Axis.PositiveZ | solver.types.Axis.NegativeZ:
                    return BLUE

        axis_map = {
            'X+': solver.types.Axis.PositiveX,
            'Y+': solver.types.Axis.PositiveY,
            'Z+': solver.types.Axis.PositiveZ,
            'X-': solver.types.Axis.NegativeX,
            'Y-': solver.types.Axis.NegativeY,
            'Z-': solver.types.Axis.NegativeZ
        }
        first_axis = axis_map[vl_settings.first_axis]
        second_axis = axis_map[vl_settings.second_axis]
        third_axis = solver.helpers.third_axis(first_axis, second_axis) # find third axis based on the first two

        # create line midpoint handlers
        def set_midpoint_transform(data:'bpy.types.ID', prop:str, index:int, value:Tuple[float, float]):
            line = getattr(data, prop)[index]
            mid_point_x = line.start[0] + (line.end[0] - line.start[0]) / 2
            mid_point_y = line.start[1] + (line.end[1] - line.start[1]) / 2

            new_mid_x = value[0]
            new_mid_y = value[1]

            dx = new_mid_x - mid_point_x
            dy = new_mid_y - mid_point_y

            new_start_x = line.start[0] + dx
            new_start_y = line.start[1] + dy
            new_start = (new_start_x, new_start_y)
            new_end_x = line.end[0] + dx
            new_end_y = line.end[1] + dy
            new_end = (new_end_x, new_end_y)
            getattr(data, prop)[index].start = new_start
            getattr(data, prop)[index].end = new_end


        def set_vl_transform(vp:Tuple[float, float]):
            def set_vl_midpoint_transform(data:'bpy.types.ID', prop:str, index:int, value:Tuple[float, float]):
                line = getattr(data, prop)[index]

                # get current start, end point 't' parameter
                VP = mathutils.Vector((vp[0], vp[1]))
                P = mathutils.Vector((line.start[0], line.start[1]))
                Q = mathutils.Vector((line.end[0], line.end[1]))
                M = (P + Q) / 2
                D = (VP - M).normalized()


                t_start = (P - M).dot(D)
                t_end = (Q - M).dot(D)

                # get current midpoint
                M1 = mathutils.Vector((value[0], value[1]))
                D1 = (VP - M1).normalized()

                # cacl new start, end points based on 't' parameter
                P1 = M1 + D1 * t_start
                Q1 = M1 + D1 * t_end


                getattr(data, prop)[index].start = P1.x, P1.y
                getattr(data, prop)[index].end =   Q1.x, Q1.y
            return set_vl_midpoint_transform

        def get_midpoint_transform(data:'bpy.types.ID', prop:str, index:int) -> Tuple[float, float]:
            line = getattr(data, prop)[index]
            mid_x = (line.start[0] + line.end[0]) / 2
            mid_y = (line.start[1] + line.end[1]) / 2
            return (mid_x, mid_y)

        if vl_settings.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
            vp1 = solver.core.compute_vanishing_point([((line.start[0], line.start[1]), (line.end[0], line.end[1])) for line in vl_settings.first_vanishing_lines])
            # Draw first vanishing lines
            for idx, line in enumerate(vl_settings.first_vanishing_lines):
                self.uiview.prop_point(line, 'start', text=" ", color=get_axis_color(first_axis))
                self.uiview.prop_point(line, 'end', text=" ", color=get_axis_color(first_axis))
                self.uiview.prop_point(vl_settings, 'first_vanishing_lines', text="", index=idx, color=get_axis_color(first_axis), set_transform=set_vl_transform(vp1), get_transform=get_midpoint_transform)
                self.uiview._painter.add_line(line.start, line.end, get_axis_color(first_axis))

        if vl_settings.mode in {'ONE_POINT'}:
            # Draw the horizontal line for the vp1 mode:
            line = vl_settings.second_vanishing_lines[0]
            self.uiview.prop_point(line, 'start', text=" ", color=get_axis_color(second_axis))
            self.uiview.prop_point(line, 'end', text=" ", color=get_axis_color(second_axis))
            self.uiview.prop_point(vl_settings, 'second_vanishing_lines', text="", index=0, color=get_axis_color(second_axis), set_transform=set_midpoint_transform, get_transform=get_midpoint_transform)
            self.uiview._painter.add_line(line.start, line.end, get_axis_color(second_axis))

        if vl_settings.mode in {'TWO_POINT', 'THREE_POINT'}:
            if vl_settings.quad_mode:
                # transpose first vanishing lines for quad mode
                first_line = vl_settings.first_vanishing_lines[ 0]
                last_line =  vl_settings.first_vanishing_lines[-1]
                second_vanishing_lines_coordinates = [(first_line.start, last_line.start), (first_line.end, last_line.end)]
                
                for P, Q in second_vanishing_lines_coordinates:
                    self.uiview._painter.add_line(P, Q, get_axis_color(second_axis))
                    
            else:
                vp2 = solver.core.compute_vanishing_point([((line.start[0], line.start[1]), (line.end[0], line.end[1])) for line in vl_settings.second_vanishing_lines])
                for idx, line in enumerate(vl_settings.second_vanishing_lines):
                    self.uiview.prop_point(line, 'start', text=" ", color=get_axis_color(second_axis))
                    self.uiview.prop_point(line, 'end', text=" ", color=get_axis_color(second_axis))
                    self.uiview.prop_point(vl_settings, 'second_vanishing_lines', text="", index=idx, color=get_axis_color(second_axis), set_transform=set_vl_transform(vp2), get_transform=get_midpoint_transform)
                    self.uiview._painter.add_line(line.start, line.end, get_axis_color(second_axis))

        if vl_settings.mode in {'THREE_POINT'}:
            vp3 = solver.core.compute_vanishing_point([((line.start[0], line.start[1]), (line.end[0], line.end[1])) for line in vl_settings.third_vanishing_lines])
            for idx, line in enumerate(vl_settings.third_vanishing_lines):
                self.uiview.prop_point(line, 'start', text=" ", color=get_axis_color(third_axis))
                self.uiview.prop_point(line, 'end', text=" ", color=get_axis_color(third_axis))
                self.uiview.prop_point(vl_settings, 'third_vanishing_lines', text="", index=idx, color=get_axis_color(third_axis), set_transform=set_vl_transform(vp3), get_transform=get_midpoint_transform)
                self.uiview._painter.add_line(line.start, line.end, get_axis_color(third_axis))

        ###############################
        # reference distance CONTROLS #
        ###############################
        # anchor_is_behind = vl_settings.scene_scale < 0
        # if not anchor_is_behind:
        if vl_settings.reference_scale_mode != 'ANCHOR':
            def get_distance_measurement_direction() -> Tuple[float, float]:
                if vl_settings.reference_scale_mode == 'SCREEN':
                    return (1.0,0.0)
                else:
                    axis_vectors = {'X_AXIS': (1, 0, 0), 'Y_AXIS': (0, 1, 0), 'Z_AXIS': (0, 0, 1)}
                    axis_vector = axis_vectors[vl_settings.reference_scale_mode]

                    region = context.region
                    rv3d = context.area.spaces.active.region_3d
                    R = view3d_utils.location_3d_to_region_2d(region, rv3d, axis_vector)
                    R = self.uiview.unproject((R.x, R.y))
                    R = mathutils.Vector((R[0], R[1]))
                    O = mathutils.Vector((vl_settings.anchor_screen[0], vl_settings.anchor_screen[1]))

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
                
            self.uiview.prop_distance_segment(vl_settings, "reference_screen_segment", 
                origin=vl_settings.anchor_screen,
                direction=get_distance_measurement_direction(),
                text=f"{vl_settings.reference_scene_scale:.2f}{length_unit}",
                color=ORANGE)
        
        _ = self.uiview.prop_point(vl_settings, "anchor_screen",    
            text="O",
            color=YELLOW)
        
        ###########################################
        # DRAW Extended lines to vanishing points #
        ###########################################
        
        def closest_to_point(points: Iterable[Tuple[float, float]], P:Tuple[float, float]) -> Tuple[float, float]:
            sorted_points = sorted(points, key=lambda Q: (Q[0]-P[0])**2 + (Q[1]-P[1])**2)
            if len(sorted_points) == 0:
                raise ValueError("No points provided to find closest point to vanishing point.")
            return sorted_points[0]
        
        if not vl_settings.error_message:
            if vl_settings.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
                try:
                    vp1 = solver.core.compute_vanishing_point([
                        (glm.vec2(*line.start), glm.vec2(*line.end)) 
                        for line in vl_settings.first_vanishing_lines])

                    for line in vl_settings.first_vanishing_lines:
                        self.uiview._painter.add_line(
                            mathutils.Vector(closest_to_point([line.start, line.end], vp1)), 
                            mathutils.Vector(vp1), 
                            vl_utils.dim_color(get_axis_color(first_axis))
                        )
                        
                except solver.exceptions.VanishingLinesError as e:
                    warnings.warn(f"Could not compute VP1: {e}")

            if vl_settings.mode in {'TWO_POINT', 'THREE_POINT'}:
                if vl_settings.quad_mode:
                    try:
                        first_line = vl_settings.first_vanishing_lines[ 0]
                        last_line =  vl_settings.first_vanishing_lines[-1]

                        second_vanishing_lines = [
                            (glm.vec2(first_line.start.x, first_line.start.y), glm.vec2(last_line.start.x, last_line.start.y)),
                            (glm.vec2(first_line.end.x, first_line.end.y), glm.vec2(last_line.end.x, last_line.end.y))]

                        vp2 = solver.core.compute_vanishing_point(second_vanishing_lines)
                        
                        for line_start, line_end in second_vanishing_lines:
                            self.uiview._painter.add_line(
                                closest_to_point([line_start, line_end], vp2), 
                                vp2, 
                                vl_utils.dim_color(get_axis_color(second_axis)))
                    except ValueError as e:
                        warnings.warn(f"Could not compute VP2: {e}")
                else:
                    try:
                        vp2 = solver.core.compute_vanishing_point([
                            (glm.vec2(*line.start), glm.vec2(*line.end)) 
                            for line in vl_settings.second_vanishing_lines])
                        
                        for line in vl_settings.second_vanishing_lines:
                            self.uiview._painter.add_line(
                                mathutils.Vector(closest_to_point([line.start, line.end], vp2)), 
                                mathutils.Vector(vp2), 
                                vl_utils.dim_color(get_axis_color(second_axis)))

                    except ValueError as e:
                        warnings.warn(f"Could not compute VP2: {e}")

            if vl_settings.mode in {'THREE_POINT'}:
                try:
                    vp3 = solver.core.compute_vanishing_point([
                        (glm.vec2(*line.start), glm.vec2(*line.end)) 
                        for line in vl_settings.third_vanishing_lines])
                    
                    for line in vl_settings.third_vanishing_lines:
                        self.uiview._painter.add_line(
                            mathutils.Vector(closest_to_point([line.start, line.end], vp3)), 
                            mathutils.Vector(vp3), 
                            vl_utils.dim_color(get_axis_color(third_axis)))
                        
                except ValueError as e:
                    warnings.warn(f"Could not compute VP3: {e}")

                projection, view = vl_utils.get_camera_matrices(camera_object=context.area.spaces.active.camera,
                    compute_space=solver.types.Rect(-1,-1,2,2))
                principal, f = solver.utils.decompose_intrinsics(solver.types.Rect(-1,-1,2,2), projection)
                self.uiview._painter.add_marker(
                    pos=mathutils.Vector(principal),
                    color=mathutils.Vector((1.0, 0.7, 0.0, 1.0)),
                    shape='x',
                )

                self.uiview._painter.add_annotation(
                    pos=mathutils.Vector(principal),
                    text="P",
                    color=mathutils.Vector((1.0, 0.7, 0.0, 1.0))
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
        rect_min = mathutils.Vector((-1,-1))
        rect_max = mathutils.Vector(( 1, 1))
        rect_size = rect_max - rect_min
        self.uiview._painter.add_rect(
            rect_min,
            rect_size,
            color=mathutils.Vector((0,1,1,0.1))
        )

        ## draw info
        self.uiview._painter.add_annotation(
            pos=rect_min + mathutils.Vector((rect_size.x/2, 0)),
            text="Vanishing Lines · Beta Version",
            color=mathutils.Vector((0,1,1,0.3))
        )

        self.uiview.end()

    def update_solve(self, context):
        camera_object = context.space_data.camera
        camera_object.vl_settings.solve()
        camera_object.vl_settings.to_camera(camera_object)

        self.view3d_tick(context)
        self._context_area.tag_redraw()

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
        print("Cancel Vanishing Lines Orientation Operator")
        # Restore previous camera state
        # if context.area.spaces.active.camera and self._initial_camera_matrix is not None:
        #     camera_object = context.area.spaces.active.camera

        #     camera_object.matrix_world = self._initial_camera_matrix
        #     camera_object.data.lens = self._initial_camera_lens
        #     camera_object.data.shift_x = self._initial_camera_shift_x
        #     camera_object.data.shift_y = self._initial_camera_shift_y
        
        self.cleanup(context)
        
    def cleanup(self, context):
        # # Unsubscribe from msgbus
        # if self._msgbus_owner is not None:
        #     bpy.msgbus.clear_by_owner(self._msgbus_owner)
        #     self._msgbus_owner = None

        # remove draw hundler
        if self._draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None
        
        # Redraw area to clear drawings
        if self._context_area:
            self._context_area.tag_redraw()

        # Clear status bar
        bpy.context.workspace.status_text_set(None)

    def handle_draw(self):
        # draw only in the correct region TODO: this is probably too much
        context = bpy.context
        if context.area != self._context_area:
            return
        
        if context.region.type != 'WINDOW':
            return
        
        if context.space_data.type != 'VIEW_3D':
            return
        
        quads = context.space_data.region_quadviews
        if quads and context.region_data != quads[3]:
            return

        if context.region != self._context_region:
            return
        
        self.uiview.render()
    
    def on_camera_lens_changed(self):
        """Callback when camera lens changes"""
        print("camera_lens_changed called")
        
        # # Only proceed if the operator is running
        # op = vl_utils.get_running_operator_by_idname('VIEW3D_OT_vl_solve_orientation')
        # if not op:
        #     # print("camera_lens_changed: operator not running")
        #     return
        
        # Only update if the changed camera is the one being used by the operator
        if not self._context_area or not self._context_area.spaces.active.camera:
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

######################
def view_menu_func(self, context):
    self.layout.operator("view3d.vl_solve_orientation", text="Vanishing Lines - Orientation")

def register():
    # bpy.utils.register_class(VIEW3D_MT_vl_solve_orientation_context)
    bpy.utils.register_class(MODAL_MT_VLContextMenu)
    bpy.utils.register_class(VIEW3D_OT_vl_solve_orientation)
    bpy.types.VIEW3D_MT_view.append(view_menu_func)

def unregister():
    bpy.context.workspace.status_text_set(None)

    # cancel any running operator
    for op in bpy.context.window.modal_operators:
        # check if operator is of our type
        if not isinstance(op, VIEW3D_OT_vl_solve_orientation):
            continue
        try:
            op.cancel(bpy.context)
        except AttributeError:
            pass

    bpy.utils.unregister_class(VIEW3D_OT_vl_solve_orientation)
    bpy.types.VIEW3D_MT_view.remove(view_menu_func)
    bpy.utils.unregister_class(MODAL_MT_VLContextMenu)
    # bpy.utils.unregister_class(VIEW3D_MT_vl_solve_orientation_context)

    
