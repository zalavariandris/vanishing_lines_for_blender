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

from pyglm import glm

# Constants
FONT_SIZE = 16
LINE_HEIGHT = 18

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
    _context_space = None
    _msgbus_owner = None  # Owner object for msgbus subscription
    _draw_handler = None  # Store the draw handler reference
    
    def invoke(self, context, event):
        ##########################################
        # Get the camera and the initial context #
        ##########################################
        self._context_area = context.area
        self._context_space = context.space_data
        
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

        ######################################
        # Initialize vl_settings to defaults #
        ######################################
        vl_settings = camera_object.vl_settings

        # Initialize defaults
        if not vl_settings.initialized:
            # Load existing parameters from camera
            vl_properties_camera.set_defaults(vl_settings)
            vl_settings.initialized = True

        #############################################
        # Set anchor point based on cursor position #
        #############################################
        cursor = context.scene.cursor.location.copy()
        
        # check if cursor is behind the camera
        _, view = vl_utils.get_camera_matrices(camera_object, solver.types.Rect(-1,-1,2,2))
        cursor_camera_space = view * glm.vec4(cursor.x, cursor.y, cursor.z, 1.0)
        is_cursor_behind = cursor_camera_space.z > 0

        if is_cursor_behind:
            orbit_location = context.area.spaces.active.region_3d.view_location
            vl_settings.anchor_world = (orbit_location.x, orbit_location.y, orbit_location.z)
        else:
            vl_settings.anchor_world = context.scene.cursor.location.to_tuple()

        ######################################
        # Match VLSettings to current Camera #
        ######################################
        # update vl_settings matrices to current camera
        glm_proj, glm_view = vl_utils.get_camera_matrices(camera_object, solver.types.Rect(-1,-1,2,2))
        vl_settings.proj_array = vl_utils.matrix_to_array(vl_utils.glm_to_blender_mat(glm.transpose(glm_proj)))
        vl_settings.view_array = vl_utils.matrix_to_array(vl_utils.glm_to_blender_mat(glm.transpose(glm_view)))
        ###########
        # unsolve #
        ###########
        viewport = solver.types.Rect(-1,-1,2,2)
        axis_map = {
            'X+': solver.types.Axis.PositiveX,
            'Y+': solver.types.Axis.PositiveY,
            'Z+': solver.types.Axis.PositiveZ,
            'X-': solver.types.Axis.NegativeX,
            'Y-': solver.types.Axis.NegativeY,
            'Z-': solver.types.Axis.NegativeZ
        }

        # adjust vanishing lines #TODO: refactor this part
        vp1, vp2, vp3 = solver.utils.orientation_to_three_vanishing_points(
            glm.mat3(glm_view), 
            glm_proj, 
            viewport=viewport, 
            first_axis=axis_map[vl_settings.first_axis], 
            second_axis=axis_map[vl_settings.second_axis]
        )

        vl_utils.adjust_vanishing_lines_to_camera(
            vl_settings, 
            glm_proj,
            glm_view
        )

        # adjust anchor screen
        anchor_screen:glm.vec2 = glm.project(
            glm.vec3(vl_settings.anchor_world.x, vl_settings.anchor_world.y, vl_settings.anchor_world.z), 
            glm_view, glm_proj, tuple(viewport)
        ).xy
        vl_settings.anchor_screen = (anchor_screen.x, anchor_screen.y)

        # adjust reference scale
        anchor_world = glm.vec3(vl_settings.anchor_world[0], vl_settings.anchor_world[1], vl_settings.anchor_world[2])
        match vl_settings.reference_scale_mode:
            case 'ANCHOR':
                # world distance from anchor
                camera_locationera_quat = solver.utils.decompose_extrinsics(glm_view)
                anchor_distance = glm.length(anchor_world - camera_locationera_quat.position)
            case 'SCREEN' | 'X_AXIS' | 'Y_AXIS' | 'Z_AXIS':
                match vl_settings.reference_scale_mode:
                    case 'X_AXIS':
                        ref_axis_vec = glm.vec3(1, 0, 0)
                    case 'Y_AXIS':
                        ref_axis_vec = glm.vec3(0, 1, 0)
                    case 'Z_AXIS':
                        ref_axis_vec = glm.vec3(0, 0, 1)
                    case 'SCREEN' | _:
                        # Right vector is column 0 of the inverse view matrix
                        ref_axis_vec = glm.vec3(glm.inverse(view)[0])

        # --- 2. Measure current world length on screen ---
        A_screen = glm.project(anchor_world, view, glm_proj, tuple(viewport)).xy
        V_screen = glm.project(anchor_world + ref_axis_vec, view, glm_proj, tuple(viewport)).xy
        dir_screen = glm.normalize(V_screen - anchor_screen)

        def get_world_pos(screen_pos):
            ray = solver.utils.cast_ray(screen_pos, glm_view, glm_proj, tuple(viewport))
            return solver.utils.closest_point_between_lines((glm.vec3(0,0,0), glm.vec3(0,0,0) + ref_axis_vec), ray)

        reference_offset, reference_length = vl_settings.reference_screen_segment
        ref_start_world = get_world_pos(A_screen + dir_screen * reference_offset)
        ref_end_world = get_world_pos(A_screen + dir_screen * (reference_offset + reference_length))
        world_length = glm.length(ref_end_world - ref_start_world)

        vl_settings.reference_scene_scale = world_length


        # # Set anchor point based on cursor position
        # cursor = context.scene.cursor.location.copy()
        # _, view = vl_utils.get_camera_matrices(camera_object, solver.types.Rect(-1,-1,2,2))
        # cursor_camera_space = view * glm.vec4(cursor.x, cursor.y, cursor.z, 1.0)
        # is_cursor_behind = cursor_camera_space.z > 0
        # print("cursor_camera_space.z", cursor_camera_space.z, "is_cursor_behind", is_cursor_behind)
        # if is_cursor_behind:
        #     orbit_location = context.area.spaces.active.region_3d.view_location
        #     vl_settings.anchor_world = (orbit_location.x, orbit_location.y, orbit_location.z)
        # else:
        #     print("Setting anchor to cursor location:", cursor)
        #     vl_settings.anchor_world = context.scene.cursor.location.to_tuple()

        # vl_settings.from_camera(camera_object)
        # vl_settings.unsolve()

        # vl_utils.adjust_vanishing_lines_to_camera(self.vl_settings, camera_object) # adjust vanishing lines to the current transform of the camera
        # self.vl_settings.mode = 'TWO_POINT'  # default mode
        # self.vl_settings.focal_length = camera_object.data.lens # initialize focal length for one point mode. TODO: update this, in other modes, so on switch, the camera lens is preserved
        # self.vl_settings.reference_scale_mode = 'ANCHOR'

        # reference_axis = {
        #     'ANCHOR': None,
        #     'SCREEN': solver.types.ReferenceAxis.Screen,
        #     'X_AXIS': solver.types.ReferenceAxis.X_Axis,
        #     'Y_AXIS': solver.types.ReferenceAxis.Y_Axis,
        #     'Z_AXIS': solver.types.ReferenceAxis.Z_Axis
        # }[self.vl_settings.reference_scale_mode]

        
        # match self.vl_settings.anchor_mode:
        #     case 'CURSOR':
        #         cursor = context.scene.cursor.location.copy()
        #         anchor_world = glm.vec3(cursor.x, cursor.y, cursor.z)
        #     case 'VIEW_ORBIT':
        #         orbit_location = self._context_space.region_3d.view_location.copy()
        #         anchor_world = glm.vec3(orbit_location.x, orbit_location.y, orbit_location.z)
        #     case 'WORLD_ORIGIN':
        #         anchor_world = glm.vec3(0.0, 0.0, 0.0)

        # projection, view = vl_utils.get_camera_matrices(camera_object, solver.types.Rect(-1,-1,2,2))
        # unsolve_result = solver.core.unsolve(
        #     viewport=solver.types.Rect(-1,-1,2,2),
        #     projection=projection,
        #     view=view,
        #     reference_axis=reference_axis
        #     anchor_world=anchor_world,
        #     first_axis=solver.types.Axis.PositiveX,
        #     second_axis=solver.types.Axis.PositiveY
        # )
        # print("unsolve_result",unsolve_result)
        # self.vl_settings.origin = (unsolve_result.anchor.x, unsolve_result.anchor.y)
        # # Always set reference_scale_mode and scene_scale to the unsolve result
        # self.vl_settings.reference_scale_mode = 'ANCHOR'
        # self.vl_settings.scene_scale = unsolve_result.anchor_distance
        # if unsolve_result.anchor_distance < 0:
        #     print("[invoke] Origin is behind the camera. Negative scene_scale:", unsolve_result.anchor_distance)

        # Register the statusbar draw callback
        bpy.context.workspace.status_text_set(lambda header, context: self.status_text(header, context))

        # Initialize UIView3D for drawing and interaction in the viewport
        self.uiview = View3DUI()

        # initial solve
        self.update_solve(context)

        # # Subscribe to camera lens changes for this operator instance
        # self._msgbus_owner = object()
        # bpy.msgbus.subscribe_rna(
        #     key=(bpy.types.Camera, "lens"),
        #     owner=self._msgbus_owner,
        #     args=(),
        #     notify=camera_lens_changed,
        # )

        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            self.view3d_draw, 
            (context, ), 
            'WINDOW', 
            'POST_PIXEL' # POST_VIEW | POS_PIXEL | ...
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
        if changed:
            # self.update_solve(context)
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

        return {'PASS_THROUGH'}
        
        # return {'RUNNING_MODAL'}

    def update_solve(self, context):
        camera_object = context.space_data.camera
        vl_settings = context.space_data.camera.vl_settings

        # vl_settings.solve()
        # vl_settings.to_camera(camera_object)

        if self._context_area.type == 'VIEW_3D':
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
        # Unsubscribe from msgbus
        if self._msgbus_owner is not None:
            bpy.msgbus.clear_by_owner(self._msgbus_owner)
            self._msgbus_owner = None

        # remove draw hundler
        if self._draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None
        
        # Redraw area to clear drawings
        if self._context_area:
            self._context_area.tag_redraw()

        # Clear status bar
        bpy.context.workspace.status_text_set(None)
    
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
        vl_settings = context.space_data.camera.vl_settings
        
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
        if not vl_settings.error_message:
            if vl_settings.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
                try:
                    vp1 = solver.core.compute_vanishing_point([
                        (glm.vec2(*line.start), glm.vec2(*line.end)) 
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
                            (glm.vec2(first_line.start.x, first_line.start.y), glm.vec2(last_line.start.x, last_line.start.y)),
                            (glm.vec2(first_line.end.x, first_line.end.y), glm.vec2(last_line.end.x, last_line.end.y))]

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
                            (glm.vec2(*line.start), glm.vec2(*line.end)) 
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
                        (glm.vec2(*line.start), glm.vec2(*line.end)) 
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

######################
def view_menu_func(self, context):
    self.layout.operator("view3d.vl_solve_orientation", text="Vanishing Lines - Orientation")

# def rv3d_draw_function():
#     # global draw_list
#     """Wrapper function to call the draw_view method of the operator instance."""
#     # print("rv3d_draw_function")
#     if op:=vl_utils.get_running_operator_by_idname('VIEW3D_OT_vl_solve_orientation'):
#         # Only draw in the area and region where the operator was invoked
#         if bpy.context.area == op._context_area and bpy.context.region == op._context_region:
#             op.view3d_draw(bpy.context)

# def camera_lens_changed():
#     # print("camera_lens_changed called")
#     """Callback when camera lens changes"""
#     # Only proceed if the operator is running
#     op = vl_utils.get_running_operator_by_idname('VIEW3D_OT_vl_solve_orientation')
#     if not op:
#         # print("camera_lens_changed: operator not running")
#         return
    
#     # Only update if the changed camera is the one being used by the operator
#     if not op._context_area or not op._context_area.spaces.active.camera:
#         # print("camera_lens_changed: no context area or camera")
#         return
    
#     def deferred_update():
#         """Deferred update to run outside msgbus callback context"""
#         if op := vl_utils.get_running_operator_by_idname('VIEW3D_OT_vl_solve_orientation'):
#             # Find the window containing the stored area
#             for window in bpy.context.window_manager.windows:
#                 if op._context_area in window.screen.areas[:]:
#                     op.update_solve()
#                     op._context_area.tag_redraw()
#                     # print("camera_lens_changed: updated operator")
#                     break
#         return None  # Don't repeat the timer
#     deferred_update()
#     # Schedule update to run outside msgbus callback context
    
#     # bpy.app.timers.register(deferred_update, first_interval=0.0)


def register():
    # bpy.utils.register_class(VIEW3D_MT_vl_solve_orientation_context)
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
    # bpy.utils.unregister_class(VIEW3D_MT_vl_solve_orientation_context)

    
