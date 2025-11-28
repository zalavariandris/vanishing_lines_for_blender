# standard library
import math
from typing import Any, Iterable, List, Tuple, Literal, cast

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

class DrawLayer:
    def __init__(self):
        self.shader = gpu.shader.from_builtin('FLAT_COLOR')

        self._point_attributes: dict[str, List[Tuple[float, ...]]] = {
            "pos":   [],
            "color": [],
        }

        self._line_attributes = {
            "pos":   [],
            "color": [],
        }

        self._annotations = []

    def clear(self):
        self._point_attributes = {
            "pos":   [],
            "color": [],
        }
        self._line_attributes = {
            "pos":   [],
            "color": [],
        }
        self._annotations = []

    def add_line(self, start, end, color):
        self._line_attributes['pos'].append( start )
        self._line_attributes['color'].append( color )
        self._line_attributes['pos'].append( end )
        self._line_attributes['color'].append( color )

    def add_rect(self, top_left, bottom_right, color):
        x0, y0 = top_left
        x1, y1 = bottom_right

        self.add_line( (x0, y0), (x1, y0), color ) # top
        self.add_line( (x1, y0), (x1, y1), color ) # right
        self.add_line( (x1, y1), (x0, y1), color ) # bottom
        self.add_line( (x0, y1), (x0, y0), color ) # left

    def add_point(self, pos, color):
        self._point_attributes['pos'].append( pos )
        self._point_attributes['color'].append( color )

    def add_text(self, pos, text, color):
            self._annotations.append( (pos, text, color) )

    def draw(self):
        gpu.state.blend_set('ALPHA')

        # render points
        self.point_batch = batch_for_shader(
            self.shader, 
            'POINTS', 
            self._point_attributes
        )
        self.point_batch.draw(self.shader)

        self.lines_batch = batch_for_shader(
            self.shader,
            "LINES",
            self._line_attributes
        )

        self.lines_batch.draw(self.shader)


        # render annotations
        for pos, text, color in self._annotations:
            font_id = 0
            blf.position(font_id, pos[0]+10, pos[1]+10, 0)
            blf.size(font_id, 12)
            blf.color(font_id, *color)
            blf.draw(font_id, f"{text}")

####################
# HELPER FUNCTIONS #
####################
def map_space(
        coord: tuple[float, float],
        source: Tuple[float, float, float, float],
        target: Tuple[float, float, float, float]
    ) -> tuple[float, float]:
        """
        Map coord from source space to target space.

        Params:
            coord: (x, y) coordinate in source space
            source: (x, y, width, height) defining the source rectangle
            target: (x, y, width, height) defining the target rectangle
        """
        sx, sy, sw, sh = source
        tx, ty, tw, th = target
        x, y = coord

        # Normalize coord within source [0–1]
        nx = (x - sx) / sw
        ny = (y - sy) / sh

        # Scale to target
        mapped_x = tx + nx * tw
        mapped_y = ty + ny * th

        return mapped_x, mapped_y

def fit_space_to_aspect(
    space: tuple[float, float, float, float],
    target_aspect: float
) -> tuple[float, float, float, float]:
    """
    Returns a rectangle inside `source` that fits the given aspect ratio.
    (Letterbox)
    """
    sx, sy, sw, sh = space
    source_ar = sw / sh

    if source_ar > target_aspect:
        # Source too wide → match height, reduce width
        new_h = sh
        new_w = new_h * target_aspect
        new_x = sx + (sw - new_w) / 2
        new_y = sy
    else:
        # Source too tall → match width, reduce height
        new_w = sw
        new_h = new_w / target_aspect
        new_x = sx
        new_y = sy + (sh - new_h) / 2

    return new_x, new_y, new_w, new_h

def crop_space_to_aspect(
    source: tuple[float, float, float, float],
    target_aspect: float
) -> tuple[float, float, float, float]:
    """
    Returns a rectangle inside `source` that *fills* the given aspect ratio.
    (Crop)
    """
    sx, sy, sw, sh = source
    source_ar = sw / sh

    if source_ar > target_aspect:
        # Source too wide → match height, crop width
        new_h = sh
        new_w = new_h * target_aspect
        new_x = sx + (sw - new_w) / 2
        new_y = sy
    else:
        # Source too tall → match width, crop height
        new_w = sw
        new_h = new_w / target_aspect
        new_x = sx
        new_y = sy + (sh - new_h) / 2

    return new_x, new_y, new_w, new_h

def apply_solver_results_to_blender_camera(results:solver.SolverResults, camera_object: bpy.types.Object)->None:
    if not isinstance(camera_object.data, bpy.types.Camera):
        raise TypeError("Expected a Camera data-block")
    
    camera_data: bpy.types.Camera = cast(bpy.types.Camera, camera_object.data)

    transform_list = [[v for v in row] for row in glm.transpose(results.transform)]
    camera_object.matrix_world = mathutils.Matrix(transform_list)

    focal_length = solver.focal_length_from_fov(results.fovy, camera_data.sensor_width/results.aspect) # TODO: currently this is slightly wrong, because blender fit the sensor, the region and the rendersize based on paameters.
    camera_data.lens = focal_length  
    
    camera_data.shift_x = results.shift_x/2
    camera_data.shift_y = -results.shift_y/2 / results.aspect

def closest_point_to_vp(points, vp)->glm.vec2:
    return sorted([points[0], points[1]], key=lambda P: glm.distance2(P, vp))[0]

def dim_color(color:Tuple[float, float, float, float], factor:float=0.18)->Tuple[float, float, float, float]:
    return (color[0], color[1], color[2], color[3]*factor)

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

def get_view3d_zoom_to_fac(camzoom: float) -> float:
    """Blender internal zoom conversion"""
    return ((math.sqrt(2.0) + camzoom / 50.0) ** 2) / 4.0

def map_from_outputframe_to_region_space(coord, context):
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
    zoom_fac = get_view3d_zoom_to_fac(view_camera_zoom)
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

def map_from_region_to_output_space(coord, context):
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
    zoom_fac = get_view3d_zoom_to_fac(view_camera_zoom)
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
from typing import Sequence


class GraphicsLines:
    def __init__(self):
        # --- SHADER ---
        vertex_shader = '''
        uniform mat4 ModelViewProjectionMatrix;
        in vec3 pos;
        void main()
        {
            gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);
        }
        '''

        fragment_shader = '''
        out vec4 FragColor;
        void main()
        {
            FragColor = vec4(1.0, 0.0, 0.0, 1.0); // red
        }
        '''

        self._shader = gpu.types.GPUShader(vertex_shader, fragment_shader)

        # simple triangle in front of the camera
        self._content = {
            'pos': [
                (-0.5, -0.5, 0),
                ( 0.5, -0.5, 0),
                ( 0.0,  0.5, 0),
            ]
        }

        self._batch = batch_for_shader(self._shader , 'TRIS', self._content)

    def draw(self):
        self._batch.draw(self._shader)

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
    _draw_layer: DrawLayer|None = None
    _point_batch: gpu.types.GPUBatch|None = None
    _lines_batch: gpu.types.GPUBatch|None = None

    # solver
    _active_camera: bpy.types.Object|None = None
    _solve_error: Exception|None = None

    def get_compute_space(self) -> solver.Viewport:
        if self._active_camera is None:
            raise RuntimeError("No active camera set")
        
        vl_settings = self._active_camera.data.vl_settings
        cs = list(vl_settings.compute_space)
        return solver.Viewport(cs[0], cs[1], cs[2], cs[3])
    
    def set_compute_space(self, viewport: solver.Viewport)->None:
        if self._active_camera is None:
            raise RuntimeError("No active camera set")
        
        vl_settings = self._active_camera.data.vl_settings
        vl_settings.compute_space = (viewport.x, viewport.y, viewport.width, viewport.height)

    @classmethod
    def cleanup_handlers(cls):
        # remove depsgraph handler
        if cls._depsgraph_update_post_handler:
            bpy.app.handlers.depsgraph_update_post.remove(cls._depsgraph_update_post_handler)
            cls._depsgraph_update_post_handler = None

        # remove draw handler
        if cls._view_draw_screen_handler:
            bpy.types.SpaceView3D.draw_handler_remove(cls._view_draw_screen_handler, 'WINDOW')
            cls._view_draw_screen_handler = None

    def invoke(self, context, event):
        # Setup Drawing
        self._draw_layer = DrawLayer()
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
        
        # activate the camera view
        _set_viewer_camera(context, scene.camera)
        self._active_camera = _get_viewer_camera(context)
        if self._active_camera is None:
            self.report({'ERROR'}, "Scene has no active camera set")
            return {'CANCELLED'}
        
        self._output_space = solver.Viewport(
            0,
            0, 
            context.scene.render.resolution_x, context.scene.render.resolution_y
        )

        # self._compute_space = solver.Viewport(0,0, context.scene.render.resolution_x, context.scene.render.resolution_y)
        # aspect = context.scene.render.resolution_x / context.scene.render.resolution_y
        # self._compute_space = solver.Viewport(0,0,1,1/aspect)
        self.set_compute_space(solver.Viewport(-1,-1,2,2))
        
        # Default Control Points
        # # OUTPUT_SPACE
        # if not self._active_camera.data.vl_settings.initialized:
        #     self.set_origin(glm.vec2(700, 450))
        #     self.set_principal(glm.vec2(700, 550))

        # if not self.get_first_vanishing_lines():
        #     self.set_first_vanishing_lines([
        #         (glm.vec2(300, 350),  glm.vec2(600, 500)),
        #         (glm.vec2(1115, 130), glm.vec2(830, 400))
        #     ])
        # if not self.get_second_vanishing_lines():
        #     self.set_second_vanishing_lines([
        #         (glm.vec2(450, 650), glm.vec2(1020, 700)),
        #         (glm.vec2(450, 100), glm.vec2(1020, 100))
        #     ])
        # if not self.get_third_vanishing_lines():
        #     self.set_third_vanishing_lines([
        #         (glm.vec2(450, 650), glm.vec2(1020, 700)),
        #         (glm.vec2(450, 100), glm.vec2(1020, 100))
        #     ])

        if not self._active_camera.data.vl_settings.initialized:
            self.set_origin(glm.vec2(0, -0.25))
            self.set_principal(glm.vec2(0, 0))

        if not self.get_first_vanishing_lines():
            self.set_first_vanishing_lines([
                (glm.vec2(0.2, 0.5),  glm.vec2(0.9, 0.7)),
                (glm.vec2(-0.9, 0), glm.vec2(0.4, 0.5))
            ])

        if not self.get_second_vanishing_lines():
            self.set_second_vanishing_lines([
                (glm.vec2(-0.3, -0.52), glm.vec2(-0.9, 0)),
                (glm.vec2(0.9, 0.1), glm.vec2(0, 0.4))
            ])

        if not self.get_third_vanishing_lines():
            self.set_third_vanishing_lines([
                (glm.vec2(-0.3, -0.52), glm.vec2(-0.4, 0.5)),
                (glm.vec2(0.3, -0.52), glm.vec2(0.4, 0.5))
            ])
        self._active_camera.data.vl_settings.initialized = True
        
        # deps update handler
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
        if self._draw_layer is None:
            return
        
        GREEN = (0,1,0,1)
        RED = (1,0,0,1)
        BLUE = (0,0.3, 1.0, 1.0)
        YELLOW = (1,1,0,1)

        self._draw_layer.clear()
        self._draw_layer.add_point(self._project(context, (self.get_origin().x, self.get_origin().y)), YELLOW)
        self._draw_layer.add_text(self._project(context, (self.get_origin().x, self.get_origin().y)), "O", YELLOW)
        self._draw_layer.add_point(self._project(context, (self.get_principal().x, self.get_principal().y)), YELLOW)
        self._draw_layer.add_text(self._project(context, (self.get_principal().x, self.get_principal().y)), "P", YELLOW)

        NumberOfVanishigPoints = {
            "ONE_POINT": 1,
            "TWO_POINT": 2,
            "THREE_POINT": 3
        }[self._active_camera.data.vl_settings.mode]

        if NumberOfVanishigPoints >= 1:
            # draw first vanishing lines
            vp1 = tuple(solver.least_squares_intersection_of_lines(self.get_first_vanishing_lines()))
            for line in self.get_first_vanishing_lines():
                for cp in line:
                    P = self._project(context, (cp.x, cp.y))
                    self._draw_layer.add_point( P, GREEN )
                self._draw_layer.add_line(self._project(context, line[0]), self._project(context, line[1]), GREEN)
                self._draw_layer.add_line(self._project(context, closest_point_to_vp(line, vp1)), self._project(context, vp1), dim_color(GREEN))

            # draw second vanishing line (first line only)
            if not self._active_camera.data.vl_settings.quad_mode or NumberOfVanishigPoints == 1:
                line = self.get_second_vanishing_lines()[0]
                for cp in line:
                    P = self._project(context, (cp.x, cp.y))
                    self._draw_layer.add_point( P, RED )
                self._draw_layer.add_line(self._project(context, line[0]), self._project(context, line[1]), RED)

        if NumberOfVanishigPoints >= 2:
            # draw second vanishing lines
            if self._active_camera.data.vl_settings.quad_mode:
                second_vl = self.get_quad_mode_second_vanishing_lines()
            else:
                second_vl = self.get_second_vanishing_lines()

            vp2 = tuple(solver.least_squares_intersection_of_lines(second_vl))
            for line in second_vl:
                for cp in line:
                    P = self._project(context, (cp.x, cp.y))
                    self._draw_layer.add_point( P, RED )
                self._draw_layer.add_line(self._project(context, line[0]), self._project(context, line[1]), RED)
                self._draw_layer.add_line(self._project(context, closest_point_to_vp(line, vp2)), self._project(context, vp2), dim_color(RED))

        if NumberOfVanishigPoints >= 3:
            vp3 = tuple(solver.least_squares_intersection_of_lines(self.get_third_vanishing_lines()))
            for line in self.get_third_vanishing_lines():
                for cp in line:
                    P = self._project(context, (cp.x, cp.y))
                    self._draw_layer.add_point(P, BLUE)
                self._draw_layer.add_line(self._project(context, line[0]), self._project(context, line[1]), BLUE)
                self._draw_layer.add_line(self._project(context, closest_point_to_vp(line, vp3)), self._project(context, vp3), dim_color(BLUE))

        # override color for hovered/active control points
        if self._active_idx is not None:
            cp = list(self._get_control_point_refs())[self._active_idx]  # ensure index is valid
            self._draw_layer.add_point(self._project(context, (cp.x, cp.y)), (1,1,1,1))
            self._draw_layer.add_text( self._project(context, (cp.x, cp.y)), f"■{cp.x:.2f}{cp.y:.2f}", (1,1,1,1))
        elif self._hovered_idx is not None:
            cp = list(self._get_control_point_refs())[self._hovered_idx]  # ensure index is valid
            self._draw_layer.add_point(self._project(context, (cp.x, cp.y)), (1,1,1,1))
            self._draw_layer.add_text( self._project(context, (cp.x, cp.y)), f"●{cp.x:.2f}{cp.y:.2f}", (1,1,1,1))

        

        # draw compute space
        self._draw_layer.add_rect(
            top_left = self._project(context, (self.get_compute_space().x, self.get_compute_space().y)),
            bottom_right = self._project(context, (self.get_compute_space().x+self.get_compute_space().width, self.get_compute_space().y+self.get_compute_space().height)),
            color=(1,1,1,1)
        )

        self._draw_layer.draw()

        # draw error message
        if self._solve_error:
            lines = str(self._solve_error).splitlines()
            line_height = 12
            text_height = line_height * len(lines)
            font_id = 0
            blf.position(font_id, 20, text_height+40, 0)
            blf.size(font_id, 12)
            blf.color(font_id, 1,0,0,1)
            for i, line in enumerate(lines):
                blf.position(font_id, 20, text_height-line_height*i+40, 0)
                blf.draw(font_id, f"{line}")
        
    def _get_control_point_refs(self)->Iterable:
        """Returns references to the actual point objects (not copies)."""
        if self._active_camera is None:
            return
        
        yield self._active_camera.data.vl_settings.origin
        yield self._active_camera.data.vl_settings.principal

        NumberOfVanishigPoints = {
            "ONE_POINT": 1,
            "TWO_POINT": 2,
            "THREE_POINT": 3
        }[self._active_camera.data.vl_settings.mode]

        if NumberOfVanishigPoints >= 1:
            # yield all first vanishing lines
            for line in self._active_camera.data.vl_settings.first_vanishing_lines:
                yield line.start
                yield line.end

            # first line of second vanishing lines
            yield self._active_camera.data.vl_settings.second_vanishing_lines[0].start
            yield self._active_camera.data.vl_settings.second_vanishing_lines[0].end

        if NumberOfVanishigPoints >= 2:
            if not self._active_camera.data.vl_settings.quad_mode:
                # all (but first) second vanishing lines
                for line in self._active_camera.data.vl_settings.second_vanishing_lines[1:]:
                    yield line.start
                    yield line.end

        if NumberOfVanishigPoints >= 3:
            # all third vanishing lines
            for line in self._active_camera.data.vl_settings.third_vanishing_lines:
                yield line.start
                yield line.end
    
    def _set_control_point(self, idx: int, pos: Tuple[float, float]):
        # Build the same list structure as get_control_points
        control_points = list(self._get_control_point_refs())
        if 0 <= idx < len(control_points):
            control_points[idx].x = pos[0]
            control_points[idx].y = pos[1]

    # GETTERS / SETTERS
    def get_origin(self):
        return glm.vec2(
            self._active_camera.data.vl_settings.origin.x, 
            self._active_camera.data.vl_settings.origin.y
        )
    
    def set_origin(self, origin:glm.vec2):
        self._active_camera.data.vl_settings.origin.x = origin.x
        self._active_camera.data.vl_settings.origin.y = origin.y

    def get_principal(self):
        return glm.vec2(
            self._active_camera.data.vl_settings.principal.x, 
            self._active_camera.data.vl_settings.principal.y
        )
    
    def set_principal(self, principal:glm.vec2):
        self._active_camera.data.vl_settings.principal.x = principal.x
        self._active_camera.data.vl_settings.principal.y = principal.y
    
    def get_first_vanishing_lines(self)->List[Tuple[glm.vec2, glm.vec2]]:
        lines = []
        for line in self._active_camera.data.vl_settings.first_vanishing_lines:
            start = glm.vec2(line.start.x, line.start.y)
            end = glm.vec2(line.end.x, line.end.y)
            lines.append((start, end))
        return lines

    def set_first_vanishing_lines(self, lines:List[Tuple[glm.vec2, glm.vec2]]):
        vl = self._active_camera.data.vl_settings.first_vanishing_lines
        if len(vl) < len(lines):
            while len(vl) < len(lines):
                vl.add()

        elif len(vl) > len(lines):
            while len(vl) > len(lines):
                vl.remove(len(vl)-1)

        for i, line in enumerate(lines):
            vl[i].start.x = line[0].x
            vl[i].start.y = line[0].y

            vl[i].end.x = line[1].x
            vl[i].end.y = line[1].y

    def get_second_vanishing_lines(self)->List[Tuple[glm.vec2, glm.vec2]]:
        lines = []
        for line in self._active_camera.data.vl_settings.second_vanishing_lines:
            start = glm.vec2(line.start.x, line.start.y)
            end = glm.vec2(line.end.x, line.end.y)
            lines.append((start, end))
        return lines
    
    def get_quad_mode_second_vanishing_lines(self)->List[Tuple[glm.vec2, glm.vec2]]:
        """Returns the second vanishing line in quad mode, computed from the first vanishing lines.
        these lines are connecting the opposite corners of the rectangle defined by the first vanishing lines."""
        vl1 = self.get_first_vanishing_lines()
        line1 = vl1[0]
        line2 = vl1[-1]
        
        return [
            (glm.vec2(line1[0].x, line1[0].y), glm.vec2(line2[0].x, line2[0].y)),
            (glm.vec2(line1[1].x, line1[1].y), glm.vec2(line2[1].x, line2[1].y))
        ]
    
    def set_second_vanishing_lines(self, lines:List[Tuple[glm.vec2, glm.vec2]]): 
        vl = self._active_camera.data.vl_settings.second_vanishing_lines
        if len(vl) < len(lines):
            while len(vl) < len(lines):
                vl.add()

        elif len(vl) > len(lines):
            while len(vl) > len(lines):
                vl.remove(len(vl)-1)

        for i, line in enumerate(lines):
            vl[i].start.x = line[0].x
            vl[i].start.y = line[0].y

            vl[i].end.x = line[1].x
            vl[i].end.y = line[1].y

    def get_third_vanishing_lines(self)->List[Tuple[glm.vec2, glm.vec2]]:
        lines = []
        for line in self._active_camera.data.vl_settings.third_vanishing_lines:
            start = glm.vec2(line.start.x, line.start.y)
            end = glm.vec2(line.end.x, line.end.y)
            lines.append((start, end))
        return lines
    
    def set_third_vanishing_lines(self, lines:List[Tuple[glm.vec2, glm.vec2]]):
        vl = self._active_camera.data.vl_settings.third_vanishing_lines
        if len(vl) < len(lines):
            while len(vl) < len(lines):
                vl.add()

        elif len(vl) > len(lines):
            while len(vl) > len(lines):
                vl.remove(len(vl)-1)

        for i, line in enumerate(lines):
            vl[i].start.x = line[0].x
            vl[i].start.y = line[0].y

            vl[i].end.x = line[1].x
            vl[i].end.y = line[1].y

    # modal event loop
    def get_closest_point_idx(self, context, mouse_region_x, mouse_region_y, threshold:float=22.0) -> int|None:
        closest_idx = None
        closest_dist_sq = threshold * threshold

        for idx, cp in enumerate(self._get_control_point_refs()):
            P = glm.vec2(self._project(context, glm.vec2(cp.x, cp.y)))
            dist_sq = (P.x - mouse_region_x) ** 2 + (P.y - mouse_region_y) ** 2
            if dist_sq < closest_dist_sq:
                closest_dist_sq = dist_sq
                closest_idx = idx

        return closest_idx
    
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
            return {'FINISHED'}
        
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
            self._active_idx = self.get_closest_point_idx(context, event.mouse_region_x, event.mouse_region_y)

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
                # update hover
                new_hovered_idx = self.get_closest_point_idx(context, event.mouse_region_x, event.mouse_region_y)

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
        """ project from computation viewport to region space"""
        # map from computation viewport to output space
        coord = map_space(coord, 
            crop_space_to_aspect(self.get_compute_space(), self._output_space.width / self._output_space.height), 
            self._output_space
        )
        coord = map_from_outputframe_to_region_space(coord, context)
        return coord

    def _unproject(self, context, coord):
        """map from region space to computation viewport"""
        coord = map_from_region_to_output_space(coord, context)
        coord = map_space(coord, 
            self._output_space,
            crop_space_to_aspect(self.get_compute_space(), self._output_space.width / self._output_space.height)
        )
        return coord
    
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
        
        if camera_data.vl_settings.solver_is_paused:
            return

        if not camera_data.vl_settings.enable_manual_principal:
            center_x = self.get_compute_space().width/2.0 + self.get_compute_space().x
            center_y = self.get_compute_space().height/2.0 + self.get_compute_space().y
            self.set_principal(glm.vec2(center_x, center_y))

        scene_scale = self._active_camera.data.vl_settings.scene_scale

        try:
            self._solve_error = None
            match self._active_camera.data.vl_settings.mode:
                case "ONE_POINT":
                    first_vanishing_lines = self.get_first_vanishing_lines()
                    second_vanishing_line = self.get_second_vanishing_lines()[0]
                    vp1 =  solver.least_squares_intersection_of_lines(first_vanishing_lines)

                    if not camera_data.vl_settings.enable_manual_principal:
                        center_x = self.get_compute_space().width/2.0 + self.get_compute_space().x
                        center_y = self.get_compute_space().height/2.0 + self.get_compute_space().y
                        self.set_principal(glm.vec2(center_x, center_y))

                    focal_length_pixel = camera_data.lens / camera_data.sensor_width * self.get_compute_space().height
        
                    results = solver.solve1vp(
                                viewport=               self.get_compute_space(),
                                Fu=                     vp1,
                                second_vanishing_line = second_vanishing_line,
                                f =                     focal_length_pixel,
                                P =                     self.get_principal(),
                                O =                     self.get_origin(),
                                first_axis =            solver.Axis.PositiveY, # Blenders camera axes
                                second_axis =           solver.Axis.NegativeX, # - " -
                                scale =                 scene_scale
                    )

                    apply_solver_results_to_blender_camera(results, camera_object)
                        
                case "TWO_POINT":
                    first_vanishing_lines = self.get_first_vanishing_lines()
                    if not self._active_camera.data.vl_settings.quad_mode:
                        second_vanishing_lines = self.get_second_vanishing_lines()
                    else:
                        second_vanishing_lines = self.get_quad_mode_second_vanishing_lines()

                    vp1 = solver.least_squares_intersection_of_lines(first_vanishing_lines)
                    vp2 = solver.least_squares_intersection_of_lines(second_vanishing_lines)

                    if not camera_data.vl_settings.enable_manual_principal:
                        center_x = self.get_compute_space().width/2.0 + self.get_compute_space().x
                        center_y = self.get_compute_space().height/2.0 + self.get_compute_space().y
                        self.set_principal(glm.vec2(center_x, center_y))

                    results = solver.solve2vp(
                                viewport=               self.get_compute_space(),
                                Fu=                     vp1,
                                Fv=                     vp2,
                                P =                     self.get_principal(),
                                O =                     self.get_origin(),
                                first_axis =            solver.Axis.PositiveY, # Blenders camera axes
                                second_axis =           solver.Axis.NegativeX, # - " -
                                scale =                 scene_scale
                    )

                    apply_solver_results_to_blender_camera(results, camera_object)

                case "THREE_POINT":
                    first_vanishing_lines = self.get_first_vanishing_lines()
                    if not self._active_camera.data.vl_settings.quad_mode:
                        second_vanishing_lines = self.get_second_vanishing_lines()
                    else:
                        second_vanishing_lines = self.get_quad_mode_second_vanishing_lines()
                    third_vanishing_lines = self.get_third_vanishing_lines()

                    vp1 = solver.least_squares_intersection_of_lines(first_vanishing_lines)
                    vp2 = solver.least_squares_intersection_of_lines(second_vanishing_lines)
                    vp3 = solver.least_squares_intersection_of_lines(third_vanishing_lines)
                    self.set_principal(solver.triangle_ortho_center(vp1, vp2, vp3))

                    results = solver.solve2vp(
                                viewport=               self.get_compute_space(),
                                Fu=                     vp1,
                                Fv=                     vp2,
                                P =                     self.get_principal(),
                                O =                     self.get_origin(),
                                first_axis =            solver.Axis.PositiveY, # Blenders camera axes
                                second_axis =           solver.Axis.NegativeX, # - " -
                                scale =                 scene_scale
                    )

                    apply_solver_results_to_blender_camera(results, camera_object)
                    
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
    VIEW_OT_VanishingLinesOperator.cleanup_handlers()
    bpy.utils.unregister_class(VIEW_OT_VanishingLinesOperator)
