from typing import List, Tuple, Callable, overload, Iterable
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
from .view3d_painter import View3dPainter, dim_color
from . import vl_props
from . import vl_utils
from . import solver

# Constants
FONT_SIZE = 16
LINE_HEIGHT = 18




class MODAL_MT_VLContextMenu(bpy.types.Menu):
    bl_label = "Vanishing Lines Context Menu"
    bl_idname = "MODAL_MT_vl_context_menu"

    @classmethod
    def poll(cls, context):
        vl = vl_props.get_current(context)
        if not vl.active:
            return False

        if not context.area.spaces.active.region_3d.view_perspective == 'CAMERA':
            return
        
        return True

    def draw(self, context):
        vl = vl_props.get_current(context)
        if not vl.active:
            return False
        
        if not context.area.spaces.active.region_3d.view_perspective == 'CAMERA':
            return
        
        layout = self.layout
        assert layout is not None, "Layout is None in VL Context Menu"
        
        layout.label(text="Mode", icon='VIEW_PERSPECTIVE')
        mode_col = layout.column(heading="Vanishing Lines Mode", align=True)
        mode_col.emboss = 'NORMAL'
        mode_col.prop_tabs_enum(vl, 'mode')

        layout.separator()
        layout.label(text="Settings", icon='SETTINGS')

        row = layout.row()
        row.enabled = vl.mode in {'ONE_POINT'}
        row.prop(vl, 'fovx')
        
        row = layout.row()
        row.enabled = vl.mode in {'TWO_POINT', 'THREE_POINT'}
        row.prop(vl, 'quad_mode')

        row = layout.row()
        row.enabled = vl.mode in {'ONE_POINT', 'TWO_POINT'}

        layout.separator()
        # layout.label(text="Axes", icon='AXIS_TOP')
        # layout.label(text="Axes", icon='EMPTY_DATA')
        layout.label(text="Axes", icon='EMPTY_AXIS')
        # layout.label(text="Axes", icon='EMPTY_ARROWS')
        layout.prop_menu_enum(vl, 'first_axis')
        
        layout.prop_menu_enum(vl, 'first_axis_sign')

        layout.prop_menu_enum(vl, 'second_axis')
        layout.prop_menu_enum(vl, 'second_axis_sign')
        layout.separator()
        layout.label(text="Size", icon='DRIVER_DISTANCE')

        layout.prop_menu_enum(vl, 'reference_scale_mode')

        layout.prop(vl, 'reference_scene_scale')
        col = layout.column()
        col.enabled = vl.reference_scale_mode != 'ORIGIN'
        col.prop(vl, 'reference_screen_segment', index=0)
        col.prop(vl, 'reference_screen_segment', index=1)


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
        
        # Get viewport camera
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

        # update last camera view matrix, to compare changes later
        self._last_camera_view_matrix = camera_object.matrix_world.copy()

        # --- GET VLProps ---
        vl = vl_props.get_current(context)

        ############################################
        # Initialize vl_props to current camera #
        ############################################
        vl.camera_object = camera_object
        vl.active = True
        vl.auto_solve = False
        print("auto solve OFF")
        vl_props.ensure_vanishing_lines(vl)

        # Set the anchor point based on cursor position
        glm_proj, glm_view = vl_utils.get_camera_matrices(camera_object, solver.types.Rect(-1,-1,2,2))
        
        cursor = context.scene.cursor.location.copy()
        cursor_camera_space = glm_view * glm.vec4(cursor.x, cursor.y, cursor.z, 1.0)
        is_cursor_behind = cursor_camera_space.z > 0
        if is_cursor_behind:
            orbit_location = context.area.spaces.active.region_3d.view_location
            vl.anchor_world = (orbit_location.x, orbit_location.y, orbit_location.z)
        else:
            vl.anchor_world = context.scene.cursor.location.to_tuple()

        # Match VLProps to current Camera
        vl.fovx = camera_object.data.angle_x
        vl_props.unsolve(vl)
        print("auto solve ON")
        vl.auto_solve = True

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
        self.view3d_gui_loop(context) # setup initial gui
        context.area.tag_redraw()

        # Register the statusbar draw callback
        bpy.context.workspace.status_text_set(lambda header, context: self.status_text(header, context))

        # Subscribe to property changes
        self._subscribe_to_properties(context)

        # Run the modal operator with correct region context
        with context.temp_override(region=self._context_region):
            context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    
    def _subscribe_to_properties(self, context):
        """Subscribe to VL property changes to trigger redraws"""
        wm = context.window_manager
        
        subscribe_to = [
            "first_axis", "first_axis_sign",
            "second_axis", "second_axis_sign",
            "mode", "quad_mode",
        ]

        def property_change_callback(self):
            self._context_area.tag_redraw()
            print("VL property changed, triggering redraw")
        
        for prop_name in subscribe_to:
            bpy.msgbus.subscribe_rna(
                key=wm.path_resolve(f"vanishing_lines.{prop_name}", False),
                owner=self,
                args=(self,),
                notify=property_change_callback
            )

    def modal(self, context, event):
        vl = vl_props.get_current(context)

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
        
        if context.area.spaces.active.region_3d.view_perspective != 'CAMERA':
            self.cleanup(context)
            return {'FINISHED'}

        if vl.camera_object != self._context_area.spaces.active.camera:
            self.cleanup(context)
            return {'FINISHED'}
        
        # --- Handle Keyboard Events
        if event.value == 'PRESS':
            match event.type:
                case 'ONE' | 'NUMPAD_1':
                    vl.mode = 'ONE_POINT'
                    self.view3d_gui_loop(context)
                    self._context_area.tag_redraw()
                    return {'RUNNING_MODAL'}
                
                case 'TWO' | 'NUMPAD_2':
                    vl.mode = 'TWO_POINT'
                    self.view3d_gui_loop(context)
                    self._context_area.tag_redraw()
                    return {'RUNNING_MODAL'}
                
                case 'THREE' | 'NUMPAD_3':
                    vl.mode = 'THREE_POINT'
                    self.view3d_gui_loop(context)
                    self._context_area.tag_redraw()
                    return {'RUNNING_MODAL'}
                
                case 'Q':
                    vl.quad_mode = not vl.quad_mode
                    self.view3d_gui_loop(context)
                    self._context_area.tag_redraw()
                    return {'RUNNING_MODAL'}
                
        # capture ui controls events
        changed = self.uiview.event(context, event)
        self.view3d_gui_loop(context)
        
        if event.type == 'MIDDLEMOUSE':
            if event.value == 'PRESS':
                self._middle_mouse_pressed = True
            elif event.value == 'RELEASE':
                self._middle_mouse_pressed = False
        
        # --- MOUSE INPUT ---
        match event.type:
            case 'WHEELUPMOUSE' | 'WHEELDOWNMOUSE':
                # Adjust reference scene scale
                distance = vl.reference_scene_scale
                base_zoom = 1.1 # Base zoom factor (1.1 = 10% per wheel step)
                wheel_direction = -1 if event.type == 'WHEELUPMOUSE' else 1
                distance_scale = math.log2(distance + 1.0)
                zoom_factor = math.pow(base_zoom, wheel_direction * distance_scale)
                vl.reference_scene_scale *= zoom_factor
                
                return {'RUNNING_MODAL'}
            
            case 'MOUSEMOVE' if self._middle_mouse_pressed and event.ctrl:
                # Adjust reference scene scale
                distance = vl.reference_scene_scale
                base_zoom = 1.003 # Base zoom factor (1.1 = 10% per wheel step)
                delta_y = event.mouse_prev_y - event.mouse_y
                distance_scale = math.log2(distance + 1.0)
                zoom_factor = math.pow(base_zoom, delta_y * distance_scale)
                vl.reference_scene_scale *= zoom_factor
                
                return {'RUNNING_MODAL'}
 
            case 'MOUSEMOVE' if self._middle_mouse_pressed:
                # Pan camera TODO: refactor, this is duplicated code and unnecesseraly complex. find an elegant solution
                view_camera_zoom =   context.space_data.region_3d.view_camera_zoom
                view_camera_offset = context.space_data.region_3d.view_camera_offset
                sensor_fit =         context.space_data.camera.data.sensor_fit  # get the camera associated with the viewport
                output_size =        context.scene.render.resolution_x, context.scene.render.resolution_y
                region_size =        context.region.width, context.region.height

                mouse_prev_x, mouse_prev_y = vl_utils._map_region_to_output(
                    fit_mode = sensor_fit,
                    output_size = output_size,
                    region_size = region_size,
                    view_camera_zoom = view_camera_zoom,
                    view_camera_offset = view_camera_offset,
                    region_coords = (event.mouse_prev_x, event.mouse_prev_y))
                
                mouse_x, mouse_y = vl_utils._map_region_to_output(
                    fit_mode = sensor_fit,
                    output_size = output_size,
                    region_size = region_size,
                    view_camera_zoom = view_camera_zoom,
                    view_camera_offset = view_camera_offset,
                    region_coords = (event.mouse_x, event.mouse_y))
                
                mouse_delta_x, mouse_delta_y = mouse_x - mouse_prev_x , mouse_y - mouse_prev_y

                vl.anchor_screen = (
                    vl.anchor_screen[0] + mouse_delta_x/output_size[0]*2, # TODO
                    vl.anchor_screen[1] + mouse_delta_y/output_size[0]*2
                )
                
                return {'RUNNING_MODAL'}

        if vl.error_message:
            context.area.header_text_set(f"⚠ {vl.error_message}")
        else:
            context.area.header_text_set("")

        return {'RUNNING_MODAL'}
        
    def view3d_gui_loop(self, context):
        assert self.uiview is not None, "UIView3D not initialized"
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
        vl = vl_props.get_current(context)
        
        def get_axis_color(axis:solver.types.Axis) -> mathutils.Vector:
            match axis:
                case solver.types.Axis.PositiveX | solver.types.Axis.NegativeX:
                    return RED
                case solver.types.Axis.PositiveY | solver.types.Axis.NegativeY:
                    return GREEN
                case solver.types.Axis.PositiveZ | solver.types.Axis.NegativeZ:
                    return BLUE
        
        first_axis =  vl_utils.to_solver_axis(vl.first_axis, vl.first_axis_sign)
        second_axis = vl_utils.to_solver_axis(vl.second_axis, vl.second_axis_sign)
        third_axis =  solver.helpers.third_axis(first_axis, second_axis) # find third axis based on the first two

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
        
        first_prop, second_prop, third_prop = vl_props.get_vanishing_line_prop_names_in_order(vl)

        if vl.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
            vp1 = solver.core.compute_vanishing_point([((line.start[0], line.start[1]), (line.end[0], line.end[1])) for line in getattr(vl, first_prop)])
            # Draw first vanishing lines
            for idx, line in enumerate(getattr(vl, first_prop)):
                self.uiview.prop_point(line, 'start', text=" ", color=get_axis_color(first_axis))
                self.uiview.prop_point(line, 'end', text=" ", color=get_axis_color(first_axis))
                self.uiview.prop_point(vl, first_prop, text=f"{vl.first_axis}", index=idx, color=get_axis_color(first_axis), set_transform=set_vl_transform(vp1), get_transform=get_midpoint_transform)
                self.uiview._painter.add_line(line.start, line.end, get_axis_color(first_axis))

        if vl.mode in {'ONE_POINT'}:
            # Draw the horizontal line for the vp1 mode:
            line = getattr(vl, second_prop)[0]
            self.uiview.prop_point(line, 'start', text=" ", color=get_axis_color(second_axis))
            self.uiview.prop_point(line, 'end', text=" ", color=get_axis_color(second_axis))
            self.uiview.prop_point(vl, second_prop, text="", index=0, color=get_axis_color(second_axis), set_transform=set_midpoint_transform, get_transform=get_midpoint_transform)
            self.uiview._painter.add_line(line.start, line.end, get_axis_color(second_axis))

        if vl.mode in {'TWO_POINT', 'THREE_POINT'}:
            if vl.quad_mode:
                # transpose first vanishing lines for quad mode
                first_line = getattr(vl, first_prop)[ 0]
                last_line =  getattr(vl, first_prop)[-1]
                second_vanishing_lines_coordinates = [(first_line.start, last_line.start), (first_line.end, last_line.end)]
                
                for P, Q in second_vanishing_lines_coordinates:
                    self.uiview._painter.add_line(P, Q, get_axis_color(second_axis))
                    
            else:
                vp2 = solver.core.compute_vanishing_point([((line.start[0], line.start[1]), (line.end[0], line.end[1])) for line in getattr(vl, second_prop)])
                for idx, line in enumerate(getattr(vl, second_prop)):
                    self.uiview.prop_point(line, 'start', text=" ", color=get_axis_color(second_axis))
                    self.uiview.prop_point(line, 'end', text=" ", color=get_axis_color(second_axis))
                    self.uiview.prop_point(vl, second_prop, text=f"{vl.second_axis}", index=idx, color=get_axis_color(second_axis), set_transform=set_vl_transform(vp2), get_transform=get_midpoint_transform)
                    self.uiview._painter.add_line(line.start, line.end, get_axis_color(second_axis))

        if vl.mode in {'THREE_POINT'}:
            vp3 = solver.core.compute_vanishing_point([((line.start[0], line.start[1]), (line.end[0], line.end[1])) for line in getattr(vl, third_prop)])
            vl_third_axis, vl_third_axis_sign = vl_utils.from_solver_axis(third_axis)
            for idx, line in enumerate(getattr(vl, third_prop)):
                self.uiview.prop_point(line, 'start', text=" ", color=get_axis_color(third_axis))
                self.uiview.prop_point(line, 'end', text=" ", color=get_axis_color(third_axis))
                self.uiview.prop_point(vl, third_prop, text=f"{vl_third_axis}", index=idx, color=get_axis_color(third_axis), set_transform=set_vl_transform(vp3), get_transform=get_midpoint_transform)
                self.uiview._painter.add_line(line.start, line.end, get_axis_color(third_axis))

        ###############################
        # reference distance CONTROLS #
        ###############################
        # anchor_is_behind = vl.scene_scale < 0
        # if not anchor_is_behind:
        if vl.reference_scale_mode != 'ANCHOR':
            def get_distance_measurement_direction() -> Tuple[float, float]:
                if vl.reference_scale_mode == 'SCREEN':
                    return (1.0,0.0)
                else:
                    axis_vectors = {'X_AXIS': (1, 0, 0), 'Y_AXIS': (0, 1, 0), 'Z_AXIS': (0, 0, 1)}
                    axis_vector = axis_vectors[vl.reference_scale_mode]

                    region = context.region
                    rv3d = context.area.spaces.active.region_3d
                    R = view3d_utils.location_3d_to_region_2d(region, rv3d, axis_vector)
                    R = self.uiview.unproject((R.x, R.y))
                    R = mathutils.Vector((R[0], R[1]))
                    O = mathutils.Vector((vl.anchor_screen[0], vl.anchor_screen[1]))

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
                
            self.uiview.prop_distance_segment(vl, "reference_screen_segment", 
                origin=vl.anchor_screen,
                direction=get_distance_measurement_direction(),
                text=f"{vl.reference_scene_scale:.2f}{length_unit}",
                color=ORANGE)
        
        _ = self.uiview.prop_point(vl, "anchor_screen",    
            text="O",
            color=YELLOW)
        
        ###########################################
        # DRAW Extended lines to vanishing points #
        ###########################################
        if not vl.error_message:
            if vl.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
                try:
                    vp1 = solver.core.compute_vanishing_point([
                        (glm.vec2(*line.start), glm.vec2(*line.end)) 
                        for line in getattr(vl, first_prop)])

                    for line in getattr(vl, first_prop):
                        start, end = vl_utils.extend_line(mathutils.Vector(line.start), mathutils.Vector(line.end), mathutils.Vector(vp1))
                        self.uiview._painter.add_line(
                            start, end, 
                            dim_color(get_axis_color(first_axis))
                        )
                        
                except solver.exceptions.VanishingLinesError as e:
                    warnings.warn(f"Could not compute VP1: {e}")

            if vl.mode in {'TWO_POINT', 'THREE_POINT'}:
                if vl.quad_mode:
                    try:
                        first_line = getattr(vl, first_prop)[0]
                        last_line =  getattr(vl, first_prop)[-1]

                        second_vanishing_lines = [
                            (glm.vec2(first_line.start.x, first_line.start.y), glm.vec2(last_line.start.x, last_line.start.y)),
                            (glm.vec2(first_line.end.x, first_line.end.y), glm.vec2(last_line.end.x, last_line.end.y))]

                        vp2 = solver.core.compute_vanishing_point(second_vanishing_lines)
                        
                        for line in second_vanishing_lines:
                            start, end = vl_utils.extend_line(mathutils.Vector(line[0]), mathutils.Vector(line[1]), mathutils.Vector(vp2))
                            self.uiview._painter.add_line(
                                start, end,
                                dim_color(get_axis_color(second_axis))
                            )
                    except ValueError as e:
                        warnings.warn(f"Could not compute VP2: {e}")
                else:
                    try:
                        vp2 = solver.core.compute_vanishing_point([
                            (glm.vec2(*line.start), glm.vec2(*line.end)) 
                            for line in getattr(vl, second_prop)])
                        
                        for line in getattr(vl, second_prop):
                            start, end = vl_utils.extend_line(mathutils.Vector(line.start), mathutils.Vector(line.end), mathutils.Vector(vp2))
                            self.uiview._painter.add_line(
                                start, end,
                                dim_color(get_axis_color(second_axis))
                            )

                    except ValueError as e:
                        warnings.warn(f"Could not compute VP2: {e}")

            if vl.mode in {'THREE_POINT'}:
                try:
                    vp3 = solver.core.compute_vanishing_point([
                        (glm.vec2(*line.start), glm.vec2(*line.end)) 
                        for line in getattr(vl, third_prop)])
                    
                    for line in getattr(vl, third_prop):
                        start, end = vl_utils.extend_line(mathutils.Vector(line.start), mathutils.Vector(line.end), mathutils.Vector(vp3))
                        self.uiview._painter.add_line(
                            start, end,
                            dim_color(get_axis_color(third_axis))
                        )
                        
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
        header.layout.separator()
        header.layout.label(text="", icon='EVENT_CTRL')
        header.layout.label(text="Move Origin", icon='MOUSE_MMB_DRAG')
        header.layout.label(text="", icon='EVENT_CTRL')
        header.layout.label(text="World Distance", icon='MOUSE_MMB_SCROLL')

        # context menu
        header.layout.separator()
        header.layout.label(text="Options", icon='MOUSE_RMB')

        # show error message if any
        vl = vl_props.get_current(context)
        if vl.error_message:
            header.layout.alert = True
            header.layout.label(text=f"{vl.error_message}", icon='ERROR')
            header.layout.alert = False
    
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
        vl = vl_props.get_current(context)
        vl.active = False
        vl.auto_solve = False

        # Unsubscribe from property changes
        bpy.msgbus.clear_by_owner(self)  # Clean up subscriptions

        # remove draw handler
        if self._draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None
        
        # Redraw area to clear drawings
        if self._context_area:
            self._context_area.tag_redraw()

        # Clear status bar
        bpy.context.workspace.status_text_set(None)

    def handle_draw(self):
        if bpy.context.area.spaces.active.region_3d.view_perspective != 'CAMERA':
            return
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

        # Draw error messages
        vl = vl_props.get_current(context)
        if vl.error_message:
            error_msg = vl.error_message
            lines = str(error_msg).splitlines()
            text_block_height = LINE_HEIGHT * len(lines)
            text_block_width = max([blf.dimensions(0, line)[0] for line in lines])
            font_id = 0
            center = context.region.width/2, context.region.height/2
            blf.size(font_id, FONT_SIZE)
            blf.color(font_id, 0.7, 0.2, 0.2, 1)

            print("Draw VL Error:", vl.error_message, lines)
            for i, line in enumerate(lines):
                line_width = blf.dimensions(font_id, line)[0]
                blf.position(font_id, center[0] - line_width/2, center[1] - LINE_HEIGHT * i - text_block_height/2, 0)
                blf.draw(font_id, f"{line}")

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

    
