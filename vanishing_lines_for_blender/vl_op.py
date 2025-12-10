# standard library
import math
from typing import Any, Iterable, List, Tuple, Literal, cast
import warnings

# Blender
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import blf
import mathutils
from bpy_extras import view3d_utils

# third party
import glm

# local
from . core import solver_functional as solver
from . core import utils

from . draw_layer import DrawLayer

from typing import Protocol


class PointLike(Protocol):
    x: float
    y: float


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

def apply_solver_results_to_blender_camera(
        projection: glm.mat4,
        view: glm.mat4, 
        camera_object: bpy.types.Object,
        compute_space: solver.Rect,
        output_space: solver.Rect
    ) -> None:
    """
    Apply solver results to Blender camera, accounting for aspect ratio differences
    between compute space and output space.
    
    Args:
        results: Solver results with transform and FOV
        camera_object: Blender camera object to modify
        compute_space: The viewport used for computation (e.g., [-1,-1,2,2])
        output_space: The actual render output viewport
    """
    if not isinstance(camera_object.data, bpy.types.Camera):
        raise TypeError("Expected a Camera data-block")
    
    P, f, shift = solver.decompose_intrinsics(compute_space, projection)
    fovy = solver.utils.fov_from_focal_length(f, compute_space.height)
    position, orientation = solver.decompose_extrinsics(view)
    aspect = compute_space.width / compute_space.height
    transform = glm.inverse(view)

    camera_data: bpy.types.Camera = cast(bpy.types.Camera, camera_object.data)

    # Apply transform
    
    transform_list = [[v for v in row] for row in glm.transpose(transform)]
    camera_object.matrix_world = mathutils.Matrix(transform_list)

    # Calculate the aspect ratio correction factor
    compute_aspect = compute_space.width / compute_space.height
    output_aspect = output_space.width / output_space.height
    
    # The focal length needs to be adjusted based on which dimension is constraining
    # When compute space is cropped to match output aspect, the effective sensor size changes
    
    if compute_aspect > output_aspect:
        # Compute space is wider - height is constraining dimension
        # Use results.fovy directly, but adjust sensor width
        focal_length = utils.focal_length_from_fov(fovy, camera_data.sensor_height)
    else:
        # Compute space is taller - width is constraining dimension  
        # Need to calculate fovx and derive focal length from that
        fovx = 2.0 * math.atan(math.tan(fovy / 2.0) * aspect)
        focal_length = utils.focal_length_from_fov(fovx, camera_data.sensor_width)
    
    camera_data.lens = focal_length
    
    # Apply lens shift
    center_x = compute_space.x + compute_space.width / 2
    center_y = compute_space.y + compute_space.height / 2
    shift_x =  (P.x - center_x) / (compute_space.width / 2)
    shift_y = -(P.y - center_y) / (compute_space.height / 2)
    camera_data.shift_x = shift_x/2 #  results.shift_x / 2
    camera_data.shift_y = shift_y/2 # -results.shift_y / 2 / results.aspect

def closest_point_to_vp(points, vp)->glm.vec2:
    return sorted(points, key=lambda P: glm.distance2(glm.vec2(P.x, P.y), glm.vec2(vp.x, vp.y)))[0]

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

# class ControlPoint:
#     def __init__(self, name:str, pos:glm.vec2):
#         self.name = name
#         self.pos = pos

class ControlPointProp():
    def __init__(self, data:str, prop:str, text:str=""):
        self._data = data
        self._prop = prop
        self._text = text

        self._draw_layer = DrawLayer()

    @property
    def value(self):
        return getattr(self._data, f"{self._prop}")
    
    @value.setter
    def value(self, value:glm.vec2): # todo: we should use the actual _bpy prop_ type here, but how?
        point = getattr(self._data, f"{self._prop}")
        point.x = value.x
        point.y = value.y

class ControlsLayer:
    def __init__(self):
        self._controls: dict[Tuple[bpy.types.ID, str], ControlPointProp] = dict()

    def clear(self):
        self._controls.clear()

    def control_point_prop(self, data:bpy.types.ID, prop:str) -> ControlPointProp:
        control_point = ControlPointProp(data, prop)
        self[data, prop] = control_point
        return control_point

    def draw(self, context:bpy.types.Context):
        """it is like the bpy.types.Panel.draw function, but for our control points"""
        # validate context
        camera = context.scene.camera
        if camera is None:
            self.layout.label(text="No active camera in the scene.")
            return
        
        self.layout.label(text=f"Active Camera: '{camera.name}'")

        # todo: move is_operator_running from vl_sidepanel, to utils, and import here
        # if not is_operator_running("VIEW_OT_vanishing_lines_operator"):
        #     self.layout.operator("view.vanishing_lines_operator", text="Start Vanishing Lines")
        #     return

        self.control_point_prop(camera.data.vl_settings, "origin", text="O")
        self.control_point_prop(camera.data.vl_settings, "principal", text="principal")

    def _execute_draw_calls(self, context:bpy.types.Context):
        """draw all control points in this layer"""
        for cp in self._controls.values():
            pos = cp.pos
            screen_pos = map_from_outputframe_to_region_space((pos.x, pos.y), context)
            cp._draw_layer.add_point(screen_pos, (1,1,1,1))
            cp._draw_layer.add_text(screen_pos, cp._text, (1,1,1,1))
            
        self._draw_layer.draw()

    def event(self, event:bpy.types.Event, context:bpy.types.Context):
        for cp in self._controls:
            ...

class VIEW_OT_VanishingLinesOperator(bpy.types.Operator):
    """alignt the camer based on vanishing lines"""
    
    bl_idname = "view.vanishing_lines_operator"
    bl_label = "Vanishing Lines Operator"
    bl_options = {"REGISTER", "UNDO"}
    
    # interaction
    _active_name: str|None = None
    _hovered_name: str|None = None
    _active_id: Tuple[bpy.types.ID, str]|None = None
    _hovered_id: Tuple[bpy.types.ID, str]|None = None

    _is_left_mouse_down = False
    _mouse_tracking = False # set this True, to get mouse move events even when no buttons are held down
    _props: Any= None
    _depsgraph_update_post_handler: Any= None

    # draw
    _view_draw_screen_handler: Any= None # keep our drawing handler
    _draw_layer: DrawLayer|None = None
    _controls: dict[Tuple[bpy.types.ID, str], ControlPointProp] = dict()

    # solver
    _active_camera: bpy.types.Object|None = None
    _solve_error: Exception|None = None

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

    def init_controls(self):
        self._controls = {}

    def draw_controls(self, context:bpy.types.Context):
        print("--draw_controls--")
        vl_settings = self._active_camera.data.vl_settings

        GREEN = (0,1,0,1)
        RED = (1,0,0,1)
        BLUE = (0,0.3, 1.0, 1.0)
        YELLOW = (1,1,0,1)

        # Draw Origin and Principal Point
        _ = self.control_point(context, vl_settings, "origin",    text="Origin",    color=YELLOW)
        _ = self.control_point(context, vl_settings, "principal", text="principal", color=YELLOW)

        # Draw Vanishing Lines
        vl_settings = self._active_camera.data.vl_settings

        if vl_settings.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
            # Draw first vanishing lines
            # vp1 = tuple(solver.utils.least_squares_intersection_of_lines(self.get_first_vanishing_lines()))
            for line in vl_settings.first_vanishing_lines:
                _ = self.control_point(context, line, "start", text=f"VL1 start", color=GREEN)
                _ = self.control_point(context, line, "end",   text=f"VL1 end",   color=GREEN)

                self._draw_layer.add_line(
                    self._project(context, glm.vec2(line.start.x, line.start.y)), 
                    self._project(context, glm.vec2(line.end.x,   line.end.y)), 
                    GREEN)
                
                # self._draw_layer.add_line(
                #     self._project(context, closest_point_to_vp([line.start, line.end], vp1)), 
                #     self._project(context, glm.vec2(vp1.x, vp1.y)), dim_color(GREEN))

        if vl_settings.mode in {'ONE_POINT'}:
            # Draw the horizontal line for the vp1 mode:
            line = vl_settings.second_vanishing_lines[0]
            _ = self.control_point(context, line, "start", text=f"VL1 start", color=RED)
            _ = self.control_point(context, line, "end",   text=f"VL1 end",   color=RED)

            self._draw_layer.add_line(
                self._project(context, line.start), 
                self._project(context, line.end), 
                RED)

        if vl_settings.mode in {'TWO_POINT', 'THREE_POINT'}:
            # Draw second vanishing lines
            # TODO: Quad Mode
            # vp2 = tuple(solver.utils.least_squares_intersection_of_lines(second_vl))
            for line in vl_settings.second_vanishing_lines:
                _ = self.control_point(context, line, "start", text=f"VL2 start", color=RED)
                _ = self.control_point(context, line, "end",   text=f"VL2 end",   color=RED)

                self._draw_layer.add_line(
                    self._project(context, glm.vec2(line.start.x, line.start.y)), 
                    self._project(context, glm.vec2(line.end.x,   line.end.y)), 
                    RED)
                
                # self._draw_layer.add_line(
                #     self._project(context, closest_point_to_vp(line, vp2)), 
                #     self._project(context, vp2), 
                #     dim_color(RED))

        if vl_settings.mode in {'THREE_POINT'}:
            # vp3 = tuple(solver.utils.least_squares_intersection_of_lines(self.get_third_vanishing_lines()))
            for line in vl_settings.third_vanishing_lines:
                _ = self.control_point(context, line, "start", text=f"VL3 start", color=BLUE)
                _ = self.control_point(context, line, "end",   text=f"VL3 end",   color=BLUE)

                self._draw_layer.add_line(
                    self._project(context, glm.vec2(line.start.x, line.start.y)), 
                    self._project(context, glm.vec2(line.end.x,   line.end.y)), 
                    BLUE)
                
                # self._draw_layer.add_line(
                #     self._project(context, closest_point_to_vp(line, vp3)), 
                #     self._project(context, vp3), 
                #     dim_color(BLUE))

        # # Draw active / hovered control point info
        # if self._active_name is not None:
        #     cp_name, cp_pos = self.get_control_point_by_name(self._active_name)  # ensure index is valid
        #     self._draw_layer.add_point(self._project(context, (cp_pos.x, cp_pos.y)), (1,1,1,1))
        #     self._draw_layer.add_text( self._project(context, (cp_pos.x, cp_pos.y)), f"■{cp_pos.x:.2f}{cp_pos.y:.2f}", (1,1,1,1))

        # elif self._hovered_name is not None:
        #     cp_name, cp_pos = self.get_control_point_by_name(self._hovered_name)  # ensure index is valid
        #     self._draw_layer.add_point(self._project(context, (cp_pos.x, cp_pos.y)), (1,1,1,1))
        #     self._draw_layer.add_text( self._project(context, (cp_pos.x, cp_pos.y)), f"{cp_name}:{cp_pos.x:.2f},{cp_pos.y:.2f}", (1,1,1,0.5))

        # # Draw reference distance
        # match vl_settings.scene_scale_mode:
        #     case 'ORIGIN':
        #         pass

        #     case 'X_AXIS':
        #         pass

        #     case 'Y_AXIS':
        #         ...

        #     case 'Z_AXIS':
        #         ...

        # Draw compute space frame
        self._draw_layer.add_rect(
            top_left = self._project(context, (self.get_compute_space().x, self.get_compute_space().y)),
            bottom_right = self._project(context, (self.get_compute_space().x+self.get_compute_space().width, self.get_compute_space().y+self.get_compute_space().height)),
            color=(0,1,1,0.5)
        )

        compute_min = (self.get_compute_space().x,                                self.get_compute_space().y)
        compute_max = (self.get_compute_space().x+self.get_compute_space().width, self.get_compute_space().y+self.get_compute_space().height)
        self._draw_layer.add_text(
            self._project(context, (self.get_compute_space().x, self.get_compute_space().y)),
            f"Compute Space {compute_min[0]:.1f},{compute_min[1]:.1f}",
            (0,1,1,1)
        )
        self._draw_layer.add_text(
            self._project(context, (self.get_compute_space().x+self.get_compute_space().width, self.get_compute_space().y + self.get_compute_space().height)),
            f"Compute Space {compute_max[0]:.1f},{compute_max[1]:.1f}",
            (0,1,1,1)
        )

    def get_closest_id(self, context, mouse_region_x, mouse_region_y, threshold:float=22.0) -> Tuple[bpy.types.ID, str]|None:
        closest_key:Tuple[bpy.types.ID, str]|None = None
        closest_dist_sq = threshold * threshold

        for control_id, control_point in self._controls.items():
            P = glm.vec2(self._project(context, glm.vec2(control_point.value.x, control_point.value.y)))
            dist_sq = (P.x - mouse_region_x) ** 2 + (P.y - mouse_region_y) ** 2
            if dist_sq < closest_dist_sq:
                closest_dist_sq = dist_sq
                closest_key = control_id

        return closest_key
    
    def control_point(self, context, data:bpy.types.ID, prop:str, text:str="", color=(1,1,1,1)) -> ControlPointProp:
        key = (data, prop)
        if key not in self._controls:
            self._controls[key] = ControlPointProp(data, prop, text)
        cp = self._controls[key]
        self._draw_layer.add_point(self._project(context, (cp.value.x, cp.value.y)), color)
        self._draw_layer.add_text( self._project(context, (cp.value.x, cp.value.y)), f"{text} ({cp.value.x:.2f}, {cp.value.y:.2f})", color)
        return self._controls[key]

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
        _set_viewer_camera(context, scene.camera)
        self._active_camera = _get_viewer_camera(context)
        if self._active_camera is None:
            self.report({'ERROR'}, "Scene has no active camera set")
            return {'CANCELLED'}
        
        # Setup controls layer
        self.init_controls()

        # Setup Drawing
        self._draw_layer = DrawLayer()

        # register draw handler
        if not self._view_draw_screen_handler:
            self._view_draw_screen_handler = bpy.types.SpaceView3D.draw_handler_add(
                self._on_view_draw, 
                (context, ), 
                'WINDOW', 
                'POST_PIXEL' # POST_VIEW | POS_PIXEL | ...
            )

        # Setup Solver
        self.set_compute_space(solver.Rect(-1,-1,2,2))
        
        # Setup default props if not initialized
        if not self._active_camera.data.vl_settings.initialized:
            self.set_origin(glm.vec2(0, -0.25))
            self.set_principal(glm.vec2(0, 0))
            self._active_camera.data.vl_settings.initialized = True

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
        
        # deps update handler
        if not self._depsgraph_update_post_handler:
            self._depsgraph_update_post_handler = bpy.app.handlers.depsgraph_update_post.append(self._on_deps_graph_update)

        # trigger redraw
        if area.type == 'VIEW_3D':
           area.tag_redraw()

        # Initial Solve
        self.update_solve(context)

        # run as modal
        window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _on_deps_graph_update(self, scene, depsgraph:bpy.types.Depsgraph):
        """when the depsgraph changes, regarding the active camera, or the output resolution, we update the solve."""
        updates:bpy.types.bpy_prop_collection[bpy.types.DepsgraphUpdate] = depsgraph.updates
        for update in updates:
            # print("Depsgraph update:", update)
            # print("  id:", update.id) # the actual datablock that was updated
            # print("    - id_type", update.id.id_type)
            # print("    - name", update.id.name)
            # print("    - name_full", update.id.name_full)
            # print("  is_updated_geometry:", update.is_updated_geometry)
            # print("  is_updated_shading:", update.is_updated_shading)
            # print("  is_updated_transform:", update.is_updated_transform)
            if isinstance(update.id, bpy.types.Camera):
                self.update_solve(bpy.context)

    def _on_view_draw(self, context):
        """draw the vanishing lines and control points in the 3D view"""
        if self._draw_layer is None:
            warnings.warn("Draw layer not initialized. Skipping draw.")
            return
        
        # GREEN = (0,1,0,1)
        # RED = (1,0,0,1)
        # BLUE = (0,0.3, 1.0, 1.0)
        # YELLOW = (1,1,0,1)
        
        self._draw_layer.clear()

        # # Draw Origin and Principal Point
        # # self._draw_layer.add_point(self._project(context, (self.get_origin().x,    self.get_origin().y)),         YELLOW)
        # # self._draw_layer.add_text( self._project(context, (self.get_origin().x,    self.get_origin().y)),   "O",  YELLOW)
        # self._draw_layer.add_point(self._project(context, (self.get_principal().x, self.get_principal().y)),      YELLOW)
        # self._draw_layer.add_text( self._project(context, (self.get_principal().x, self.get_principal().y)), "P", YELLOW)

        # # Draw Vanishing Lines
        # vl_settings = self._active_camera.data.vl_settings
        # if vl_settings.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
        #     # Draw first vanishing lines
        #     vp1 = tuple(solver.utils.least_squares_intersection_of_lines(self.get_first_vanishing_lines()))
        #     for line in self.get_first_vanishing_lines():
        #         for cp in line:
        #             P = self._project(context, (cp.x, cp.y))
        #             self._draw_layer.add_point( P, GREEN )
        #         self._draw_layer.add_line(self._project(context, line[0]), self._project(context, line[1]), GREEN)
        #         self._draw_layer.add_line(self._project(context, closest_point_to_vp(line, vp1)), self._project(context, vp1), dim_color(GREEN))

        # if vl_settings.mode in {'ONE_POINT'}:
        #     # Draw the horizontal line for the vp1 mode:
        #     line = self.get_second_vanishing_lines()[0]
        #     for cp in line:
        #         P = self._project(context, (cp.x, cp.y))
        #         self._draw_layer.add_point( P, RED )
        #     self._draw_layer.add_line(self._project(context, line[0]), self._project(context, line[1]), RED)

        # if vl_settings.mode in {'TWO_POINT', 'THREE_POINT'}:
        #     # Draw second vanishing lines
        #     if vl_settings.quad_mode:
        #         second_vl = self.get_quad_mode_second_vanishing_lines()
        #     else:
        #         second_vl = self.get_second_vanishing_lines()

        #     vp2 = tuple(solver.utils.least_squares_intersection_of_lines(second_vl))
        #     for line in second_vl:
        #         for cp in line:
        #             P = self._project(context, (cp.x, cp.y))
        #             self._draw_layer.add_point( P, RED )
        #         self._draw_layer.add_line(self._project(context, line[0]), self._project(context, line[1]), RED)
        #         self._draw_layer.add_line(self._project(context, closest_point_to_vp(line, vp2)), self._project(context, vp2), dim_color(RED))

        # if vl_settings.mode in {'THREE_POINT'}:
        #     vp3 = tuple(solver.utils.least_squares_intersection_of_lines(self.get_third_vanishing_lines()))
        #     for line in self.get_third_vanishing_lines():
        #         for cp in line:
        #             P = self._project(context, (cp.x, cp.y))
        #             self._draw_layer.add_point(P, BLUE)
        #         self._draw_layer.add_line(self._project(context, line[0]), self._project(context, line[1]), BLUE)
        #         self._draw_layer.add_line(self._project(context, closest_point_to_vp(line, vp3)), self._project(context, vp3), dim_color(BLUE))

        # # Draw active / hovered control point info
        # if self._active_name is not None:
        #     cp_name, cp_pos = self.get_control_point_by_name(self._active_name)  # ensure index is valid
        #     self._draw_layer.add_point(self._project(context, (cp_pos.x, cp_pos.y)), (1,1,1,1))
        #     self._draw_layer.add_text( self._project(context, (cp_pos.x, cp_pos.y)), f"■{cp_pos.x:.2f}{cp_pos.y:.2f}", (1,1,1,1))

        # elif self._hovered_name is not None:
        #     cp_name, cp_pos = self.get_control_point_by_name(self._hovered_name)  # ensure index is valid
        #     self._draw_layer.add_point(self._project(context, (cp_pos.x, cp_pos.y)), (1,1,1,1))
        #     self._draw_layer.add_text( self._project(context, (cp_pos.x, cp_pos.y)), f"{cp_name}:{cp_pos.x:.2f},{cp_pos.y:.2f}", (1,1,1,0.5))

        # # Draw reference distance
        # match vl_settings.scene_scale_mode:
        #     case 'ORIGIN':
        #         pass

        #     case 'X_AXIS':
        #         pass

        #     case 'Y_AXIS':
        #         ...

        #     case 'Z_AXIS':
        #         ...

        # # Draw compute space frame
        # self._draw_layer.add_rect(
        #     top_left = self._project(context, (self.get_compute_space().x, self.get_compute_space().y)),
        #     bottom_right = self._project(context, (self.get_compute_space().x+self.get_compute_space().width, self.get_compute_space().y+self.get_compute_space().height)),
        #     color=(0,1,1,0.5)
        # )

        # compute_min = (self.get_compute_space().x,                                self.get_compute_space().y)
        # compute_max = (self.get_compute_space().x+self.get_compute_space().width, self.get_compute_space().y+self.get_compute_space().height)
        # self._draw_layer.add_text(
        #     self._project(context, (self.get_compute_space().x, self.get_compute_space().y)),
        #     f"Compute Space {compute_min[0]:.1f},{compute_min[1]:.1f}",
        #     (0,1,1,1)
        # )
        # self._draw_layer.add_text(
        #     self._project(context, (self.get_compute_space().x+self.get_compute_space().width, self.get_compute_space().y + self.get_compute_space().height)),
        #     f"Compute Space {compute_max[0]:.1f},{compute_max[1]:.1f}",
        #     (0,1,1,1)
        # )

        # Execute the draw calls
        self.draw_controls(context)
        self._draw_layer.draw()

        # Draw error messages
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

        
    # CONTROL POINT ACCESSORS OLD
    def get_control_points(self)->Iterable[Tuple[str, PointLike]]:
        """Returns references to the actual point objects (not copies).
        note: control points are in compute space coordinates."""
        if self._active_camera is None:
            return
        
        vl_settings = self._active_camera.data.vl_settings
        
        # origin and principal
        # yield 'origin', vl_settings.origin
        yield 'principal', vl_settings.principal

        # vanishing lines
        if vl_settings.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
            # yield all first vanishing lines
            for idx, line in enumerate(vl_settings.first_vanishing_lines):
                yield f"vl1.{idx}.start", line.start
                yield f"vl1.{idx}.end",   line.end

            # first line of second vanishing lines
            yield f"vl2.{0}.start", vl_settings.second_vanishing_lines[0].start
            yield f"vl2.{0}.end",   vl_settings.second_vanishing_lines[0].end

        if vl_settings.mode in {'TWO_POINT', 'THREE_POINT'}:
            if not vl_settings.quad_mode:
                # all (but first) second vanishing lines
                for idx, line in enumerate(vl_settings.second_vanishing_lines[1:], start=1):
                    yield f"vl2.{idx}.start", line.start
                    yield f"vl2.{idx}.end", line.end

        if vl_settings.mode in {'THREE_POINT'}:
            # all third vanishing lines
            for idx, line in enumerate(vl_settings.third_vanishing_lines):
                yield f"vl3.{idx}.start", line.start
                yield f"vl3.{idx}.end", line.end

    def set_control_point(self, name: str, pos: Tuple[float, float]):
        for cp in self.get_control_points():
            cp_name, cp_pos = cp
            if cp_name == name:
                cp_pos.x = pos[0]
                cp_pos.y = pos[1]
                return
      
    def get_control_point_by_name(self, name: str) -> Tuple[str, glm.vec2]|None:
        for cp in self.get_control_points():
            cp_name, cp_pos = cp
            if cp_name == name:
                return cp_name, glm.vec2(cp_pos.x, cp_pos.y)
        return None

    # @warnings.deprecated("Use get_closest_control_point instead")
    def get_closest_point_name(self, context, mouse_region_x, mouse_region_y, threshold:float=22.0) -> str|None:
        closest_name = None
        closest_dist_sq = threshold * threshold

        for idx, cp in enumerate(self.get_control_points()):
            cp_name, cp_pos = cp
            P = glm.vec2(self._project(context, glm.vec2(cp_pos.x, cp_pos.y)))
            dist_sq = (P.x - mouse_region_x) ** 2 + (P.y - mouse_region_y) ** 2
            if dist_sq < closest_dist_sq:
                closest_dist_sq = dist_sq
                closest_name = cp_name

        return closest_name
  
    # GETTERS / SETTERS
    def get_compute_space(self) -> solver.Rect:
        if self._active_camera is None:
            raise RuntimeError("No active camera set")
        
        vl_settings = self._active_camera.data.vl_settings
        cs = list(vl_settings.compute_space)
        return solver.Rect(cs[0], cs[1], cs[2], cs[3])
    
    def set_compute_space(self, viewport: solver.Rect)->None:
        if self._active_camera is None:
            raise RuntimeError("No active camera set")
        
        vl_settings = self._active_camera.data.vl_settings
        vl_settings.compute_space = (viewport.x, viewport.y, viewport.width, viewport.height)

    def get_output_space(self, context) -> solver.Rect:
        return solver.Rect(
            0,
            0, 
            context.scene.render.resolution_x, 
            context.scene.render.resolution_y
        )
    
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

            # activate cp under mouse
            self._active_id = self.get_closest_id(context, event.mouse_region_x, event.mouse_region_y)    
            # trigger redraw
            if area.type == 'VIEW_3D':
                area.tag_redraw()

            if self._active_id is not None:
                return {'RUNNING_MODAL'}
            else:
                return {'PASS_THROUGH'}
        
        elif MouseIsInRegion and event.type == 'MOUSEMOVE':
            if not self._is_left_mouse_down:
                """Mouse Move"""
                # update hover

                new_hovered_id = self.get_closest_id(context, event.mouse_region_x, event.mouse_region_y)

                if new_hovered_id != self._hovered_id:
                    self._hovered_id = new_hovered_id

                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

                if self._hovered_name is not None:
                    return {'RUNNING_MODAL'}
                else:
                    return {'PASS_THROUGH'}

                # new_hovered_name = self.get_closest_point_name(context, event.mouse_region_x, event.mouse_region_y)
                # if new_hovered_name != self._hovered_name:
                #     self._hovered_name = new_hovered_name

                #     if area.type == 'VIEW_3D':
                #         area.tag_redraw()

                # if self._hovered_name is not None:
                #     return {'RUNNING_MODAL'}
                # else:
                #     return {'PASS_THROUGH'}

            elif self._active_id is not None:
                """Mouse Drag"""
                # move active control point
                mouse_x_unproj, mouse_y_unproj = self._unproject(context, (event.mouse_region_x, event.mouse_region_y))

                self._controls[self._active_id].value = glm.vec2(mouse_x_unproj, mouse_y_unproj)
                # self.set_control_point(self._active_name, (mouse_x_unproj, mouse_y_unproj))
                self.update_solve(context)

                # trigger redraw
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                
                return {'RUNNING_MODAL'}
            else:
                return {'PASS_THROUGH'}
            
        elif self._is_left_mouse_down and event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._is_left_mouse_down = False
            """Mouse Release Event"""
            if self._active_name is not None:
                self._active_name = None

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
            crop_space_to_aspect(self.get_compute_space(), self.get_output_space(context).width / self.get_output_space(context).height), 
            self.get_output_space(context)
        )
        coord = map_from_outputframe_to_region_space(coord, context)
        return coord

    def _unproject(self, context, coord):
        """map from region space to computation viewport"""
        coord = map_from_region_to_output_space(coord, context)
        coord = map_space(coord, 
            self.get_output_space(context),
            crop_space_to_aspect(self.get_compute_space(), self.get_output_space(context).width / self.get_output_space(context).height)
        )
        return coord
    
    def cleanup(self, context):
        if self._view_draw_screen_handler:
            ##### CLEANUP #####
            bpy.types.SpaceView3D.draw_handler_remove(self._view_draw_screen_handler, 'WINDOW')
            self._view_draw_screen_handler = None
            self._active_camera = None
            self._is_left_mouse_down = False

    def update_solve(self, context):
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



        # compute scene scale fromr eference distance
        vl_settings = camera_data.vl_settings
        region = context.region            # The active region (usually VIEW_3D window)
        rv3d   = context.region_data       # The RegionView3D for this region

        print("Solving camera...", region, rv3d)

        try:
            self._solve_error = None
            match self._active_camera.data.vl_settings.mode:
                case "ONE_POINT":
                    if not camera_data.vl_settings.enable_manual_principal:
                        center_x = self.get_compute_space().width/2.0 + self.get_compute_space().x
                        center_y = self.get_compute_space().height/2.0 + self.get_compute_space().y
                        self.set_principal(glm.vec2(center_x, center_y))

                    focal_length_pixel = camera_data.lens / camera_data.sensor_width * self.get_compute_space().height
        
                    # results = solver.solve1vp(
                    #             viewport=               self.get_compute_space(),
                    #             Fu=                     vp1,
                    #             second_vanishing_line = second_vanishing_line,
                    #             f =                     focal_length_pixel,
                    #             P =                     self.get_principal(),
                    #             O =                     self.get_origin(),
                    #             first_axis =            solver.Axis.PositiveY, # Blenders camera axes
                    #             second_axis =           solver.Axis.NegativeX, # - " -
                    #             scale =                 vl_settings.scene_scale,
                    #             reference_distance =    vl_settings.reference_distance
                    # )

                    results:dict = solver.solve(
                        mode = solver.SolverMode.OneVP,
                        viewport =               self.get_compute_space(),

                        first_vanishing_lines =  self.get_first_vanishing_lines(),
                        second_vanishing_lines = self.get_second_vanishing_lines(),
                        third_vanishing_lines =  [],

                        f =                      focal_length_pixel,
                        P =                      self.get_principal(),
                        O =                      self.get_origin(),

                        reference_axis=          solver.ReferenceAxis.X_Axis,
                        reference_distance_segment=[0, 100],
                        reference_world_size=vl_settings.scene_scale,

                        first_axis =             solver.Axis.PositiveY, # Blenders camera axes
                        second_axis =            solver.Axis.NegativeX, # - " -               
                    )

                    apply_solver_results_to_blender_camera(
                        results['projection'], 
                        results['view'], 
                        camera_object, 
                        self.get_compute_space(), 
                        self.get_output_space(context)
                    )
                        
                case "TWO_POINT":
                    if not self._active_camera.data.vl_settings.quad_mode:
                        second_vanishing_lines = self.get_second_vanishing_lines()
                    else:
                        second_vanishing_lines = self.get_quad_mode_second_vanishing_lines()

                    if not camera_data.vl_settings.enable_manual_principal:
                        center_x = self.get_compute_space().width/2.0 + self.get_compute_space().x
                        center_y = self.get_compute_space().height/2.0 + self.get_compute_space().y
                        self.set_principal(glm.vec2(center_x, center_y))

                    # results = solver.solve2vp(
                    #             viewport=               self.get_compute_space(),
                    #             Fu=                     vp1,
                    #             Fv=                     vp2,
                    #             P =                     self.get_principal(),
                    #             O =                     self.get_origin(),
                    #             first_axis =            solver.Axis.PositiveY, # Blenders camera axes
                    #             second_axis =           solver.Axis.NegativeX, # - " -
                    #             scale =                 vl_settings.scene_scale,
                    #             reference_distance =    vl_settings.reference_distance
                    # )

                    results:dict = solver.solve(
                        mode = solver.SolverMode.TwoVP,
                        viewport =               self.get_compute_space(),

                        first_vanishing_lines =  self.get_first_vanishing_lines(),
                        second_vanishing_lines = second_vanishing_lines,
                        third_vanishing_lines =  [],

                        f =                      None,
                        P =                      self.get_principal(),
                        O =                      self.get_origin(),

                        reference_axis=          solver.ReferenceAxis.X_Axis,
                        reference_distance_segment=[0, 100],
                        reference_world_size=vl_settings.scene_scale,

                        first_axis =             solver.Axis.PositiveY, # Blenders camera axes
                        second_axis =            solver.Axis.NegativeX, # - " -               
                    )

                    apply_solver_results_to_blender_camera(
                        results['projection'], 
                        results['view'], 
                        camera_object, 
                        self.get_compute_space(), 
                        self.get_output_space(context)
                    )

                case "THREE_POINT":
                    first_vanishing_lines = self.get_first_vanishing_lines()
                    if not self._active_camera.data.vl_settings.quad_mode:
                        second_vanishing_lines = self.get_second_vanishing_lines()
                    else:
                        second_vanishing_lines = self.get_quad_mode_second_vanishing_lines()
                    third_vanishing_lines = self.get_third_vanishing_lines()



                    # results = solver.solve2vp(
                    #             viewport=               self.get_compute_space(),
                    #             Fu=                     vp1,
                    #             Fv=                     vp2,
                    #             P =                     self.get_principal(),
                    #             O =                     self.get_origin(),
                    #             first_axis =            solver.Axis.PositiveY, # Blenders camera axes
                    #             second_axis =           solver.Axis.NegativeX, # - " -
                    #             scale =                 vl_settings.scene_scale,
                    #             reference_distance =    vl_settings.reference_distance
                    # )

                    results:dict = solver.solve(
                        mode = solver.SolverMode.ThreeVP,
                        viewport =               self.get_compute_space(),

                        first_vanishing_lines =  first_vanishing_lines,
                        second_vanishing_lines = second_vanishing_lines,
                        third_vanishing_lines =  third_vanishing_lines,

                        f =                      None,
                        P =                      self.get_principal(),
                        O =                      self.get_origin(),

                        reference_axis=          solver.ReferenceAxis.X_Axis,
                        reference_distance_segment=[0, 100],
                        reference_world_size=vl_settings.scene_scale,

                        first_axis =             solver.Axis.PositiveY, # Blenders camera axes
                        second_axis =            solver.Axis.NegativeX, # - " -               
                    )

                    apply_solver_results_to_blender_camera(
                        results['projection'], 
                        results['view'], 
                        camera_object, 
                        self.get_compute_space(), 
                        self.get_output_space(context)
                    )
                    
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
