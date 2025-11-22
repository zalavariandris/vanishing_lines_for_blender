# standard library
import math
from typing import Any, List, Tuple

# Blender
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import blf
import mathutils

# third party
import glm

# local
from . import solver

####################
# HELPER FUNCTIONS #
####################
def view3d_zoom_to_fac(camzoom: float) -> float:
            """Blender internal zoom conversion"""
            return ((math.sqrt(2.0) + camzoom / 50.0) ** 2) / 4.0

def map_from_image_to_region_space(coord, context):
    """
    Convert render-resolution image coordinates (in pixels)
    to region pixel space, respecting camera zoom, pan, and aspect ratio.
    Works in locked camera view (Blender 4.5).
    """    
    x, y = coord
    assert isinstance(x, (int, float)), f"got: {x}"
    assert isinstance(y, (int, float)), f"got: {y}"

    # get relevant context properties
    region_width, region_height = context.region.width, context.region.height
    view_camera_zoom, view_camera_offset = context.space_data.region_3d.view_camera_zoom, context.space_data.region_3d.view_camera_offset
    resolution_x, resolution_y = context.scene.render.resolution_x, context.scene.render.resolution_y
    
    # Convert image pixels to centered NDC (-1..1)
    x = (x / resolution_x - 0.5) * 2.0
    y = (y / resolution_y - 0.5) * 2.0
    
    # Apply zoom
    zoom_fac = view3d_zoom_to_fac(view_camera_zoom)
    x *= zoom_fac
    y *= zoom_fac
    
    # Correct aspect ratio mismatch between region and render
    region_aspect = region_width / region_height
    render_aspect = resolution_x / resolution_y
    
    if region_aspect > 1:
        y *= region_aspect / render_aspect
    else:
        x /= region_aspect
        y /= render_aspect
    
    # Apply camera pan
    offset_x, offset_y = view_camera_offset
    x -= offset_x * 4.0 * zoom_fac
    y -= offset_y * 4.0 * zoom_fac
    
    # Convert NDC to region pixels
    x = (x / 2.0 + 0.5) * region_width
    y = (y / 2.0 + 0.5) * region_height
    
    return x, y

def map_from_region_to_image_space(coord, context):
    """
    Convert region pixel coordinates to render-resolution image coordinates.
    Inverse of map_from_image_to_region_space.
    Works in locked camera view (Blender 4.5).
    """
    x, y = coord
    assert isinstance(x, (int, float)), f"got: {x}"
    assert isinstance(y, (int, float)), f"got: {y}"

    # get relevant context properties
    region_width, region_height = context.region.width, context.region.height
    view_camera_zoom, view_camera_offset = context.space_data.region_3d.view_camera_zoom, context.space_data.region_3d.view_camera_offset
    resolution_x, resolution_y = context.scene.render.resolution_x, context.scene.render.resolution_y
    
    # Convert region pixels to NDC (-1..1)
    x = (x / region_width - 0.5) * 2.0
    y = (y / region_height - 0.5) * 2.0
    
    # Unapply camera pan
    zoom_fac = view3d_zoom_to_fac(view_camera_zoom)
    offset_x, offset_y = view_camera_offset
    x += offset_x * 4.0 * zoom_fac
    y += offset_y * 4.0 * zoom_fac
    
    # Unapply aspect ratio correction
    region_aspect = region_width / region_height
    render_aspect = resolution_x / resolution_y
    
    if region_aspect > 1:
        y /= region_aspect / render_aspect
    else:
        x *= region_aspect
        y *= render_aspect
    
    # Unapply zoom
    x /= zoom_fac
    y /= zoom_fac
    
    # Convert NDC to image pixels
    x = (x * 0.5 + 0.5) * resolution_x
    y = (y * 0.5 + 0.5) * resolution_y
    
    return x, y

# camera helpers
def _get_viewer_camera(context) -> bpy.types.Object|None:
    for area in context.window.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    if space.region_3d.view_perspective == 'CAMERA': # only return if viewing through camera
                        return space.camera # get the camera associated with the viewport
    return None

def _set_viewer_camera(context, camera_object: bpy.types.Object):
    for area in context.window.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.camera = camera_object  # Set the viewport camera
                    space.region_3d.view_perspective = 'CAMERA'  # Switch to camera view

def _hit_test_point(pos:glm.vec2, mouse_x:float, mouse_y:float, padding:float=35.0)->bool:
    return (mouse_x >= pos.x - padding and
            mouse_x <= pos.x + padding and
            mouse_y >= pos.y - padding and 
            mouse_y <= pos.y + padding)

def flatten(xss):
    return [x for xs in xss for x in xs]

###############
# VL OPERATOR #
###############
class VIEW_OT_VanishingLinesOperator(bpy.types.Operator):
    """alignt the camer based on vanishing lines"""
    
    bl_idname = "view.vanishing_lines_operator"
    bl_label = "Vanishing Lines Operator"
    bl_options = {"REGISTER", "UNDO"}
    
    # interaction
    _active_idx: int|None = None
    _hovered_idx: int|None = None
    _is_left_mouse_down = False
    _mouse_tracking = False # set this True, to get mouse move events even when no buttons are held down
    _props: Any= None
    _depsgraph_update_post_handler: Any= None

    # draw
    _view_draw_screen_handler: Any= None # keep our drawing handler
    shader: gpu.types.GPUShader|None = None
    point_batch: gpu.types.GPUBatch|None = None
    lines_batch: gpu.types.GPUBatch|None = None

    # solver
    _active_camera: bpy.types.Object|None = None
    _solve_error: Exception|None = None

    def invoke(self, context, event):
        # Setup Drawing
        self.shader = gpu.shader.from_builtin('FLAT_COLOR')
        if not self._view_draw_screen_handler:
            self._view_draw_screen_handler = bpy.types.SpaceView3D.draw_handler_add(
                self._on_view_draw, 
                (context, ), 
                'WINDOW', 
                'POST_PIXEL' # POST_VIEW | POS_PIXEL | ...
            )

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
        
        self._props = scene.vl_settings

        # Default Control Points
        self.set_origin(glm.vec2(700, 450))
        self.set_first_vanishing_lines([
            (glm.vec2(300, 350),  glm.vec2(600, 500)),
            (glm.vec2(1115, 130), glm.vec2(830, 400))
        ])
        self.set_second_vanishing_lines([
            (glm.vec2(450, 650), glm.vec2(1020, 700)),
            (glm.vec2(450, 100), glm.vec2(1020, 100))
        ])        
        
        # activate the camera view
        _set_viewer_camera(context, scene.camera)
        self._active_camera = _get_viewer_camera(context)

        if not self._depsgraph_update_post_handler:
            self._depsgraph_update_post_handler = bpy.app.handlers.depsgraph_update_post.append(self._on_deps_graph_update)

        # trigger redraw
        if area.type == 'VIEW_3D':
           area.tag_redraw()

        # Initial Solve
        self.solve_camera(context)

        # run as modal
        window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _on_deps_graph_update(self, scene, depsgraph):
        # when the depsgraph updates, check for camera lens changes and update solve
        for update in depsgraph.updates:
            if isinstance(update.id, bpy.types.Camera):
                self.solve_camera(bpy.context)

    def _on_view_draw(self, context):
        """create batches for drawing points and lines"""
        if self.shader is None:
            return
        
        point_attributes: dict[str, List[Tuple[float, ...]]] = {
            "pos":   [],
            "color": [],
        }
        line_attributes = {
            "pos":   [],
            "color": [],
        }

        def add_point(pos, color:Tuple[float, float, float, float]):
            point_attributes['pos'].append( pos )
            point_attributes['color'].append( color )

        def add_line(start, end, color:Tuple[float, float, float, float]):
            line_attributes['pos'].append( start )
            line_attributes['color'].append( color )
            line_attributes['pos'].append( end )
            line_attributes['color'].append( color )

        YELLOW = (1,1,0,1)
        point_attributes['pos'].append( self._project(context, (self.get_origin().x, self.get_origin().y)) )
        point_attributes['color'].append( YELLOW )

        GREEN = (0,1,0,1)
        for line in self.get_first_vanishing_lines():
            for cp in line:
                P = self._project(context, (cp.x, cp.y))
                add_point( P, GREEN )
            add_line(self._project(context, line[0]), self._project(context, line[1]), GREEN)

        RED = (1,0,0,1)
        match self._props.mode:
            case "ONE_POINT":
                line = self.get_second_vanishing_lines()[0]
                for cp in line:
                    P = self._project(context, (cp.x, cp.y))
                    add_point( P, RED )
                add_line(self._project(context, line[0]), self._project(context, line[1]), RED)

            case "TWO_POINT":
                if self._props.quad_mode:
                    for line in self.get_second_vanishing_lines():
                        for cp in line:
                            P = self._project(context, (cp.x, cp.y))
                            add_point( P, RED )
                        add_line(self._project(context, line[0]), self._project(context, line[1]), RED)
                else:        
                    for line in self.get_second_vanishing_lines():
                        for cp in line:
                            P = self._project(context, (cp.x, cp.y))
                            add_point( P, RED )
                        add_line(self._project(context, line[0]), self._project(context, line[1]), RED)

        # override color for hovered/active control points
        if self._hovered_idx is not None:
            point_attributes['color'][self._hovered_idx] = (1,1,1,1)

        if self._active_idx is not None:
            point_attributes['color'][self._active_idx] = (1,1,1,1)

        # render points
        self.point_batch = batch_for_shader(
            self.shader, 
            'POINTS', 
            point_attributes
        )
        self.point_batch.draw(self.shader)

        self.lines_batch = batch_for_shader(
            self.shader,
            "LINES",
            line_attributes
        )

        self.lines_batch.draw(self.shader)

        # draw circles around hovered/active control points
        if self._hovered_idx is not None :
            ...

        # draw text
        for name, pos, color in zip(["Origin", "y", "y", "y", "y", "x", "x", "x", "x"], point_attributes['pos'], point_attributes['color']):
            x, y = pos
            font_id = 0
            blf.position(font_id, x+3 , y+6, 0)
            blf.size(font_id, 12)
            blf.color(font_id, *color)
            blf.draw(font_id, f"{name}")

        # draw error message
        if self._solve_error:
            lines = str(self._solve_error).splitlines()
            line_height = 12
            text_height = line_height * len(lines)
            blf.position(font_id, 20, text_height+40, 0)
            blf.size(font_id, 12)
            blf.color(font_id, 1,0,0,1)
            for i, line in enumerate(lines):
                blf.position(font_id, 20, text_height-line_height*i+40, 0)
                blf.draw(font_id, f"{line}")
        
    def _get_control_point_refs(self):
        """Returns references to the actual point objects (not copies)."""
        yield self._props.origin

        match self._props.mode:
            case "ONE_POINT":
                for line in self._props.first_vanishing_lines:
                    yield line.start
                    yield line.end
                yield self._props.second_vanishing_lines[0].start
                yield self._props.second_vanishing_lines[0].end

            case "TWO_POINT":
                for line in self._props.first_vanishing_lines:
                    yield line.start
                    yield line.end
                if not self._props.quad_mode:
                    for line in self._props.second_vanishing_lines:
                        yield line.start
                        yield line.end
    
    def _set_control_point(self, idx: int, pos: Tuple[float, float]):
        # Build the same list structure as get_control_points
        control_points = list(self._get_control_point_refs())
        if 0 <= idx < len(control_points):
            control_points[idx].x = pos[0]
            control_points[idx].y = pos[1]

    def get_origin(self):
        return glm.vec2(
            self._props.origin.x, 
            self._props.origin.y
        )
    
    def set_origin(self, origin:glm.vec2):
        self._props.origin.x = origin.x
        self._props.origin.y = origin.y
    
    def get_first_vanishing_lines(self)->List[Tuple[glm.vec2, glm.vec2]]:
        vl1 = self._props.first_vanishing_lines
        return [
            (
                glm.vec2(vl1[0].start.x, vl1[0].start.y),
                glm.vec2(vl1[0].end.x, vl1[0].end.y)
            ),
            (
                glm.vec2(vl1[1].start.x, vl1[1].start.y),
                glm.vec2(vl1[1].end.x, vl1[1].end.y)
            )
        ]

    def set_first_vanishing_lines(self, lines:List[Tuple[glm.vec2, glm.vec2]]):
        vl1 = self._props.first_vanishing_lines
        if len(vl1) < len(lines):
            while len(vl1) < len(lines):
                vl1.add()
        elif len(vl1) > len(lines):
            while len(vl1) > len(lines):
                vl1.remove(len(vl1)-1)

        vl1[0].start.x = lines[0][0].x
        vl1[0].start.y = lines[0][0].y
        vl1[0].end.x =   lines[0][1].x
        vl1[0].end.y =   lines[0][1].y
        vl1[1].start.x = lines[1][0].x
        vl1[1].start.y = lines[1][0].y
        vl1[1].end.x =   lines[1][1].x
        vl1[1].end.y =   lines[1][1].y

    def get_second_vanishing_lines(self)->List[Tuple[glm.vec2, glm.vec2]]:
        vl2 = self._props.second_vanishing_lines
        return [
            (
                glm.vec2(vl2[0].start.x, vl2[0].start.y),
                glm.vec2(vl2[0].end.x, vl2[0].end.y)
            ),
            (
                glm.vec2(vl2[1].start.x, vl2[1].start.y),
                glm.vec2(vl2[1].end.x, vl2[1].end.y)
            )
        ]
    
    def set_second_vanishing_lines(self, lines:List[Tuple[glm.vec2, glm.vec2]]):
        vl2 = self._props.second_vanishing_lines
        if len(vl2) < len(lines):
            while len(vl2) < len(lines):
                vl2.add()
        elif len(vl2) > len(lines):
            while len(vl2) > len(lines):
                vl2.remove(len(vl2)-1)

        vl2[0].start.x = lines[0][0].x
        vl2[0].start.y = lines[0][0].y
        vl2[0].end.x =   lines[0][1].x
        vl2[0].end.y =   lines[0][1].y
        vl2[1].start.x = lines[1][0].x
        vl2[1].start.y = lines[1][0].y
        vl2[1].end.x =   lines[1][1].x
        vl2[1].end.y =   lines[1][1].y
                
    # modal event loop
    def modal(self, context, event):
        ###
        # Event Helpers
        ###
        area: bpy.types.Area|None = context.area
        if area is None:
            return {'PASS_THROUGH'}
        
        region: bpy.types.Region|None = context.region
        if region is None:
            return {'PASS_THROUGH'}

        """Cancel on ESC or camera change"""
        if event.type in {'ESC'}:
            self.cleanup(context)
            if area.type == 'VIEW_3D':
                area.tag_redraw()
            return {'CANCELLED'}
        
        if self._active_camera != _get_viewer_camera(context):
            self.cleanup(context)
            if area.type == 'VIEW_3D':
                area.tag_redraw()
            return {'FINISHED'}
        
        ###
        #  HANDLE MOUSE EVENTS
        ###
        MouseIsInArea = (
            event.mouse_region_x>0 and 
            event.mouse_region_x<area.width and 
            event.mouse_region_y>0 and 
            event.mouse_region_y<area.height
        )

        MouseIsInRegion = (
            0 <= event.mouse_region_x < region.width and
            0 <= event.mouse_region_y < region.height
        )

        """Mouse Events"""
        if not MouseIsInRegion:
            self.report({'INFO'}, "mouse is not in area")
            return {'PASS_THROUGH'}
        
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            """Wheel Events"""
            if area.type == 'VIEW_3D':
                area.tag_redraw()
            return {'PASS_THROUGH'}

        if MouseIsInRegion and event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._is_left_mouse_down = True
            mouse_x_unproj, mouse_y_unproj = self._unproject(context, (event.mouse_region_x, event.mouse_region_y))

            # activate cp under mouse
            self._active_idx = None
            for idx, cp in enumerate(self._get_control_point_refs()):
                if _hit_test_point(glm.vec2(cp.x, cp.y), mouse_x_unproj, mouse_y_unproj):
                    self._active_idx = idx
                    break

            # trigger redraw
            if area.type == 'VIEW_3D':
                area.tag_redraw()

            if self._active_idx is not None:
                return {'RUNNING_MODAL'}
            else:
                return {'PASS_THROUGH'}
        
        elif MouseIsInRegion and event.type == 'MOUSEMOVE':
            if not self._is_left_mouse_down:
                """Mouse Move"""
                mouse_x_unproj, mouse_y_unproj = self._unproject(context, (event.mouse_region_x, event.mouse_region_y))

                # update hover
                new_hovered_idx = None
                for idx, cp in enumerate(self._get_control_point_refs()):
                    if _hit_test_point(glm.vec2(cp.x, cp.y), mouse_x_unproj, mouse_y_unproj):
                        new_hovered_idx = idx
                        break

                if new_hovered_idx != self._hovered_idx:
                    self._hovered_idx = new_hovered_idx

                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

                if self._hovered_idx is not None:
                    return {'RUNNING_MODAL'}
                else:
                    return {'PASS_THROUGH'}

            elif self._active_idx is not None:
                """Mouse Drag"""
                # move active control point
                mouse_x_unproj, mouse_y_unproj = self._unproject(context, (event.mouse_region_x, event.mouse_region_y))
                cps = list(self._get_control_point_refs())
                self._set_control_point(self._active_idx, (mouse_x_unproj, mouse_y_unproj))

                self.solve_camera(context)

                # trigger redraw
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                
                return {'RUNNING_MODAL'}
            else:
                return {'PASS_THROUGH'}
            
        elif self._is_left_mouse_down and event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._is_left_mouse_down = False
            """Mouse Release Event"""
            if self._active_idx is not None:
                self._active_idx = None

                # trigger redraw
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                
                return {'RUNNING_MODAL'}
            else:
                return {'PASS_THROUGH'}

        return {'PASS_THROUGH'}

    def _project(self, context, coord:Tuple[float, float]):
        return map_from_image_to_region_space(coord, context)

    def _unproject(self, context, coord):
        return map_from_region_to_image_space(coord, context)
    
    def cleanup(self, context):
        if self._view_draw_screen_handler:
            ##### CLEANUP #####
            bpy.types.SpaceView3D.draw_handler_remove(self._view_draw_screen_handler, 'WINDOW')
            self._view_draw_screen_handler = None
            self._active_camera = None
            self._is_left_mouse_down = False

    def solve_camera(self, context):
        # region = context.region
        # rv3d = context.space_data.region_3d
        if self._active_camera is None:
            self.report({'ERROR'}, "Scene has no active camera set")
            return
        
        camera_object: bpy.types.Object = self._active_camera
        if camera_object.type != 'CAMERA':
            self.report({'ERROR'}, "Active camera is not a camera object")
            return

        camera_data: bpy.types.Camera = camera_object.data
        width = context.scene.render.resolution_x
        height = context.scene.render.resolution_y
        resolution_x = context.scene.render.resolution_x
        resolution_y = context.scene.render.resolution_y

        principal = glm.vec2(resolution_x / 2.0, resolution_y / 2.0) # TODO: assume center principal point
        origin = self.get_origin()

        try:
            self._solve_error = None
            match self._props.mode:
                case "ONE_POINT":
                    first_vanishing_lines = self.get_first_vanishing_lines()
                    second_vanishing_line = self.get_second_vanishing_lines()[0]
                    vp1 =  solver.least_squares_intersection_of_lines(first_vanishing_lines)
                    focal_length_pixel = camera_data.lens / camera_data.sensor_width * resolution_x
        
                    camera_transform = solver.solve1vp(
                                width =                 width, 
                                height =                height, 
                                Fu=                     vp1,
                                second_vanishing_line = second_vanishing_line,
                                f =                     focal_length_pixel,
                                P =                     principal,
                                O =                     origin,
                                first_axis =            solver.Axis.PositiveY, # Blenders camera axes
                                second_axis =           solver.Axis.NegativeX, # - " -
                                scale =                 10.0
                    )
                    
                    transform_list = [[v for v in row] for row in glm.transpose(camera_transform)]
                    camera_object.matrix_world = mathutils.Matrix(transform_list)
                        
                    

                case "TWO_POINT":
                    first_vanishing_lines = self.get_first_vanishing_lines()
                    second_vanishing_lines = self.get_second_vanishing_lines()

                    vp1 = solver.least_squares_intersection_of_lines(first_vanishing_lines)
                    vp2 = solver.least_squares_intersection_of_lines(second_vanishing_lines)
                    fovy, camera_transform = solver.solve2vp(
                                width =                 width, 
                                height =                height, 
                                Fu=                     vp1,
                                Fv=                     vp2,
                                P =                     principal,
                                O =                     origin,
                                first_axis =            solver.Axis.PositiveY, # Blenders camera axes
                                second_axis =           solver.Axis.NegativeX, # - " -
                                scale =                 10.0
                    )
                    
                    transform_list = [[v for v in row] for row in glm.transpose(camera_transform)]
                    aspect_ratio = resolution_x / resolution_y
                    focal_length = solver.focal_length_from_fov(fovy, camera_data.sensor_width/aspect_ratio) # TODO: currently this is slightly wrong, because blender fit the sensor, the region and the rendersize based on paameters.
                    camera_data.lens = focal_length  
                    camera_object.matrix_world = mathutils.Matrix(transform_list)

        except Exception as e:
            self._solve_error = e
            import traceback
            traceback.print_exc()

######################
# REGISTER FUNCTIONS #
######################
def view_menu_func(self, context):
    self.layout.operator(VIEW_OT_VanishingLinesOperator.bl_idname, text="Vanishing Lines Modal Operator")

def register():
    bpy.utils.register_class(VIEW_OT_VanishingLinesOperator)
    bpy.types.VIEW3D_MT_view.append(view_menu_func)

def unregister():
    bpy.types.VIEW3D_MT_view.remove(view_menu_func)
    bpy.utils.unregister_class(VIEW_OT_VanishingLinesOperator)
