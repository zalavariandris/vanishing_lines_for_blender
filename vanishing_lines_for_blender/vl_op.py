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

# third party
import glm

# local
from . core import solver_functional as solver
from . core import utils

from . draw_layer import DrawLayer

from typing import Protocol

####################
# HELPER FUNCTIONS #
####################
def map_space(
        coord:  tuple[float, float],
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
    Returns a rectangle that fits within the aspect ratio.
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
    Retrurns a rectangle that fills the aspect ratio by cropping the excess.
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

def closest_point_to_target(points: Iterable[Tuple[float, float]], P:Tuple[float, float]) -> Tuple[float, float]:
    sorted_points = sorted(points, key=lambda Q: (Q[0]-P[0])**2 + (Q[1]-P[1])**2)
    if len(sorted_points) == 0:
        raise ValueError("No points provided to find closest point to vanishing point.")
    return sorted_points[0]

def dim_color(color:Tuple[float, float, float, float], factor:float=0.18)->Tuple[float, float, float, float]:
    return (color[0], color[1], color[2], color[3]*factor)

def _hit_test_point(pos:Tuple[float, float], mouse_x:float, mouse_y:float, padding:float=35.0)->bool:
    return (mouse_x >= pos[0] - padding and
            mouse_x <= pos[0] + padding and
            mouse_y >= pos[1] - padding and 
            mouse_y <= pos[1] + padding)

def flatten(xss):
    return [x for xs in xss for x in xs]


##################
# BLENDER HELERS #
##################
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
    camera_data.shift_x = shift_x/2
    camera_data.shift_y = shift_y/2

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

def map_from_outputframe_to_region_space(coord:Tuple[float, float], context)->Tuple[float, float]:
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

def map_from_region_to_output_space(coord:Tuple[float, float], context)->Tuple[float, float]:
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


###############
# VL OPERATOR #
###############
from typing import Callable

class ControlPoint():
    def __init__(self, data:bpy.types.ID, prop:str, setter:Callable|None=None, getter:Callable|None=None):
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
    """alignt the camer based on vanishing lines"""
    
    bl_idname = "view.vanishing_lines_operator"
    bl_label = "Vanishing Lines Operator"
    bl_options = {"REGISTER", "UNDO"}
    
    # interaction
    _active_id: Tuple[bpy.types.ID, str]|None = None
    _hovered_id: Tuple[bpy.types.ID, str]|None = None

    _is_left_mouse_down = False
    _mouse_tracking = False # set this True, to get mouse move events even when no buttons are held down
    _props: Any= None
    _depsgraph_update_post_handler: Any= None

    # draw
    _view_draw_screen_handler: Any= None # keep our drawing handler
    _draw_layer: DrawLayer|None = None
    _controls: dict[Tuple[bpy.types.ID, str], ControlPoint] = dict()

    # solver
    _active_camera: bpy.types.Object|None = None
    _solve_error: Exception|None = None

    # Cached viewport state
    _output_space: solver.Rect|None = None
    _region_width: int = 0
    _region_height: int = 0
    _view_camera_zoom: float = 0.0
    _view_camera_offset: Tuple[float, float] = (0.0, 0.0)

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

    def _update_viewport_state(self, context) -> None:
        """Update cached viewport state from context"""
        self._output_space = self.get_output_space(context)
        self._region_width = context.region.width
        self._region_height = context.region.height
        self._view_camera_zoom = context.space_data.region_3d.view_camera_zoom
        self._view_camera_offset = context.space_data.region_3d.view_camera_offset
        self._region = context.region
        self._region_data = context.region_data       # The RegionView3D for this region # TODO: context.space_data.region_3d might be more accurate?

    def get_closest_id(self, mouse_region_x: float, mouse_region_y: float, threshold:float=22.0) -> Tuple[bpy.types.ID, str]|None:
        closest_key:Tuple[bpy.types.ID, str]|None = None
        closest_dist_sq = threshold * threshold

        for control_id, control_point in self._controls.items():
            P = (self.map_from_compute_to_region_space(control_point.value))
            dist_sq = (P[0] - mouse_region_x) ** 2 + (P[1] - mouse_region_y) ** 2
            if dist_sq < closest_dist_sq:
                closest_dist_sq = dist_sq
                closest_key = control_id

        return closest_key
    
    def control_point(self, data:bpy.types.ID, prop:str, text:str="", color=(1.0,0.5,0.0,1.0), setter:Callable|None=None, getter:Callable|None=None) -> ControlPoint:
        assert self._draw_layer is not None, "Draw layer not initialized"
        key = (data, prop)
        if key not in self._controls:
            self._controls[key] = ControlPoint(data, prop, setter=setter, getter=getter)
        cp = self._controls[key]

        if self._hovered_id == key:
            color = (1.0, 1.0, 1.0, 1.0)
            text = f"{text} ({cp.value[0]:.2f}, {cp.value[1]:.2f})"
            
        if self._active_id == key:
            color = (1.0, 1.0, 1.0, 1.0)

        pos = self.map_from_compute_to_region_space(cp.value)
        self._draw_layer.add_text( pos, text, color)
        self._draw_layer.add_point(pos, color)
        
        return self._controls[key]
    
    def is_item_hovered(self):
        last_id = list(self._controls.keys())[-1]
        return self._hovered_id == last_id
    
    def is_item_active(self):
        last_id = list(self._controls.keys())[-1]
        return self._active_id == last_id

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
        if scene.camera is None:
            self.report({'ERROR'}, "Scene has no active camera set")
            return {'CANCELLED'}

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
                self.draw_view, 
                (context, ), 
                'WINDOW', 
                'POST_PIXEL' # POST_VIEW | POS_PIXEL | ...
            )

        # Setup Solver
        self.set_compute_space(solver.Rect(-1,-1,2,2))
        
        # Initialize viewport state cache
        self._update_viewport_state(context)
        
        # Setup default props if not initialized
        vl_settings = self._active_camera.data.vl_settings # type: ignore
        if not vl_settings.initialized:
            vl_settings.origin = 0.0,  -0.25

            vl_settings.principal = 0.0,  0.0

            vl_settings.initialized = True

        if len(vl_settings.first_vanishing_lines) == 0:
            item = vl_settings.first_vanishing_lines.add()
            item.start = 0.2,  0.5
            item.end = 0.9, 0.7

            item = vl_settings.first_vanishing_lines.add()
            item.start = -0.9, 0.0
            item.end = 0.4, 0.5


        if len(vl_settings.second_vanishing_lines) == 0:
            item = vl_settings.second_vanishing_lines.add()
            item.start = -0.3, -0.52
            item.end =   -0.9, 0

            item = vl_settings.second_vanishing_lines.add()
            item.start = 0.9, 0.1
            item.end =   0, 0.4

        if len(vl_settings.third_vanishing_lines) == 0:
            item = vl_settings.third_vanishing_lines.add()
            item.start = -0.3, -0.52
            item.end =   -0.4, 0.5

            item = vl_settings.third_vanishing_lines.add()
            item.start = 0.3, -0.52
            item.end =   0.4, 0.5

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

    def _on_deps_graph_update(self, 
        scene, depsgraph:bpy.types.Depsgraph):
        """when the depsgraph changes, regarding the active camera, 
        or the output resolution, we update the solve."""
        
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

    def draw(self, context):
        pass
        # todo:
        """The draw method in a Blender operator will only be called if:
        The operator uses INVOKE_DEFAULT with properties - When you invoke an 
        operator that has properties, Blender can show a dialog/popup with 
        those properties, and the draw method is used to customize how that 
        dialog looks.
        The operator is used in a panel's draw method - If you create a UI panel
        and call layout.operator() or use the operator in a menu, 
        and the operator has properties that need to be shown.

        The operator returns {'RUNNING_MODAL'} and uses 
        context.window_manager.invoke_props_dialog() - This explicitly shows
        a property dialog where your draw method controls the layout.

        In this case, we're using invoke() which returns {'RUNNING_MODAL'} and 
        runs modally, but you never call invoke_props_dialog() or similar, 
        so the draw method is never called."""

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

        R = view3d_utils.location_3d_to_region_2d(
            self._region, self._region_data, axis_vector)
        
        R = self.map_from_region_to_compute_space((R.x, R.y))

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

        match vl_settings.scene_scale_mode:
            case 'X_AXIS':
                axis_vector = (1,0,0)
            case 'Y_AXIS':
                axis_vector = (0,1,0)
            case 'Z_AXIS':
                axis_vector = (0,0,1)

        R = view3d_utils.location_3d_to_region_2d(self._region, self._region_data, axis_vector)
        R = self.map_from_region_to_compute_space((R.x, R.y))
        R = mathutils.Vector((R[0], R[1]))
        l = (R - O).magnitude
        n = (R - O) / l
        P = mathutils.Vector((point[0], point[1]))
        d = (P - O).dot(n)
        vl_settings.reference_distance = d
        
    def draw_view(self, context):
        """draw the vanishing lines and control points in the 3D view"""
        if self._draw_layer is None:
            warnings.warn("Draw layer not initialized. Skipping draw.")
            return
        
        # Update viewport state for drawing
        self._update_viewport_state(context)
        
        self._draw_layer.clear()
        self._controls.clear()

        # Execute the draw calls
        vl_settings = self._active_camera.data.vl_settings # type: ignore

        GREEN = (0,1,0,1)
        RED = (1,0,0,1)
        BLUE = (0,0.3, 1.0, 1.0)
        YELLOW = (1,1,0,1)
        ORANGE = (1.0, 0.5, 0.0, 1.0)

        # draw reference line
        
        self._draw_layer.add_point(
            self.map_from_compute_to_region_space(
                self.get_reference_distance_point(vl_settings)), 
                (1.0, 1.0, 1.0, 1.0))
        # self.map_compute_to_region_space((ref_point_2d.x, ref_point_2d.y))

        # Draw Origin and Principal Point
        _ = self.control_point(vl_settings, "origin",    
            text="O",
            color=YELLOW)
        
        _ = self.control_point(vl_settings, "principal", 
            text="P",
            color=YELLOW)
        
        if vl_settings.scene_scale_mode != 'ORIGIN':
            _ = self.control_point(vl_settings, "reference_distance", 
                text="R",
                color=ORANGE,
                setter=lambda data, prop, value: self.set_reference_distance_point(vl_settings, value),
                getter=lambda data, prop: 
                    self.get_reference_distance_point(vl_settings))
                
            self._draw_layer.add_line(
                self.map_from_compute_to_region_space(vl_settings.origin), 
                self.map_from_compute_to_region_space(
                    self.get_reference_distance_point(vl_settings)),
                dim_color(ORANGE, factor=0.7 if self.is_item_hovered() else 0.1))

        # Draw Vanishing Lines
        vl_settings = self._active_camera.data.vl_settings # type: ignore

        if vl_settings.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
            # Draw first vanishing lines
            for line in vl_settings.first_vanishing_lines:
                _ = self.control_point(line, "start", text=f"", color=GREEN)
                _ = self.control_point(line, "end",   text=f"",   color=GREEN)

                self._draw_layer.add_line(
                    self.map_from_compute_to_region_space(line.start), 
                    self.map_from_compute_to_region_space(line.end), 
                    GREEN)

        try:
            # draw extended lines to vanishing point
            vp1 = solver.utils.least_squares_intersection_of_lines([
                (line.start, line.end) 
                for line in vl_settings.first_vanishing_lines])

            for line in vl_settings.first_vanishing_lines:
                self._draw_layer.add_line(
                    self.map_from_compute_to_region_space(closest_point_to_target([line.start, line.end], vp1)), 
                    self.map_from_compute_to_region_space(vp1), dim_color(GREEN))
        except ValueError as e:
            warnings.warn(f"Could not compute VP1: {e}")

        if vl_settings.mode in {'ONE_POINT'}:
            # Draw the horizontal line for the vp1 mode:
            line = vl_settings.second_vanishing_lines[0]
            _ = self.control_point(line, "start", text=f"", color=RED)
            _ = self.control_point(line, "end",   text=f"",   color=RED)

            self._draw_layer.add_line(
                self.map_from_compute_to_region_space(line.start), 
                self.map_from_compute_to_region_space(line.end), 
                RED)

        if vl_settings.mode in {'TWO_POINT', 'THREE_POINT'}:
            if vl_settings.quad_mode:
                first_line = vl_settings.first_vanishing_lines[ 0]
                last_line =  vl_settings.first_vanishing_lines[-1]
                
                for line_start, line_end in [(first_line.start, last_line.start), (first_line.end, last_line.end)]:
                    self._draw_layer.add_line(
                        self.map_from_compute_to_region_space(line_start), 
                        self.map_from_compute_to_region_space(line_end), 
                        RED)
                    
            else:
                for line in vl_settings.second_vanishing_lines:
                    _ = self.control_point(line, "start", text="", color=RED)
                    _ = self.control_point(line, "end",   text="",   color=RED)

                    self._draw_layer.add_line(
                        self.map_from_compute_to_region_space(line.start), 
                        self.map_from_compute_to_region_space(line.end), 
                        RED)

        try:
            if vl_settings.quad_mode:
                first_line = vl_settings.first_vanishing_lines[ 0]
                last_line =  vl_settings.first_vanishing_lines[-1]

                vp2 = solver.utils.least_squares_intersection_of_lines(
                    [(first_line.start, first_line.end),
                    (last_line.start, last_line.end)])
                
                for line in [first_line, last_line]:
                    self._draw_layer.add_line(
                        self.map_from_compute_to_region_space(closest_point_to_target([line_start, line_end], vp2)), 
                        self.map_from_compute_to_region_space(vp2), 
                        dim_color(RED))
            else:
                vp2 = solver.utils.least_squares_intersection_of_lines([
                    (line.start, line.end) 
                    for line in vl_settings.second_vanishing_lines])
                
                for line in vl_settings.second_vanishing_lines:
                    self._draw_layer.add_line(
                        self.map_from_compute_to_region_space(closest_point_to_target([line.start, line.end], vp2)), 
                        self.map_from_compute_to_region_space(vp2), 
                        dim_color(RED))

        except ValueError as e:
            warnings.warn(f"Could not compute VP2: {e}")

        if vl_settings.mode in {'THREE_POINT'}:
            for line in vl_settings.third_vanishing_lines:
                _ = self.control_point(line, "start", text="", color=BLUE)
                _ = self.control_point(line, "end",   text="",   color=BLUE)

                self._draw_layer.add_line(
                    self.map_from_compute_to_region_space(line.start), 
                    self.map_from_compute_to_region_space(line.end), 
                    BLUE)
                
        try:
            vp3 = solver.utils.least_squares_intersection_of_lines([
                (line.start, line.end) 
                for line in vl_settings.third_vanishing_lines])
            for line in vl_settings.third_vanishing_lines:
                self._draw_layer.add_line(
                    self.map_from_compute_to_region_space(closest_point_to_target([line.start, line.end], vp3)), 
                    self.map_from_compute_to_region_space(vp3), 
                    dim_color(BLUE))
        except ValueError as e:
            warnings.warn(f"Could not compute VP3: {e}")

        # Draw compute space frame
        def draw_space_frame(space):
            x, y =         self.map_from_compute_to_region_space((space.x, space.y))
            bottom_right = self.map_from_compute_to_region_space((space.x + space.width, space.y + space.height))
            w, h = bottom_right[0]-x, bottom_right[1]-y

            self._draw_layer.add_rect(
                (x, y),
                (w, h),
                color=(0,1,1,0.5))

            self._draw_layer.add_text(
                (x, y),
                f"Compute Space",
                color=(0,1,1,1))
        
        draw_space_frame(self.get_compute_space())

        # Execute the draw calls
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
  
    # GETTERS / SETTERS
    def get_compute_space(self) -> solver.Rect:
        if self._active_camera is None:
            raise RuntimeError("No active camera set")
        
        vl_settings = self._active_camera.data.vl_settings #type: ignore
        cs = list(vl_settings.compute_space)
        return solver.Rect(cs[0], cs[1], cs[2], cs[3])
    
    def set_compute_space(self, viewport: solver.Rect)->None:
        if self._active_camera is None:
            raise RuntimeError("No active camera set")
        
        vl_settings = self._active_camera.data.vl_settings #type: ignore
        vl_settings.compute_space = (viewport.x, viewport.y, viewport.width, viewport.height)

    def get_output_space(self, context) -> solver.Rect:
        return solver.Rect(
            0,
            0, 
            context.scene.render.resolution_x, 
            context.scene.render.resolution_y
        )
    
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
        
        # Update viewport state cache every frame
        self._update_viewport_state(context)

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
            self._active_id = self.get_closest_id(event.mouse_region_x, event.mouse_region_y)    
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

                new_hovered_id = self.get_closest_id(event.mouse_region_x, event.mouse_region_y)

                if new_hovered_id != self._hovered_id:
                    self._hovered_id = new_hovered_id

                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

                if self._hovered_id is not None:
                    return {'RUNNING_MODAL'}
                else:
                    return {'PASS_THROUGH'}

            elif self._active_id is not None:
                """Mouse Drag"""
                # move active control point
                mouse_x_unproj, mouse_y_unproj = self.map_from_region_to_compute_space((event.mouse_region_x, event.mouse_region_y))

                self._controls[self._active_id].value = (mouse_x_unproj, mouse_y_unproj)
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
            if self._active_id is not None:
                self._active_id = None

                # trigger redraw
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                
                return {'RUNNING_MODAL'}
            else:
                return {'PASS_THROUGH'}

        return {'PASS_THROUGH'}

    def _map_from_outputframe_to_region_space(self, coord: Tuple[float, float]) -> Tuple[float, float]:
        """Convert output frame coordinates to region space using cached viewport state"""
        x, y = coord
        assert isinstance(x, (int, float)), f"got: {x}"
        assert isinstance(y, (int, float)), f"got: {y}"
        assert self._output_space is not None, "Viewport state not initialized"

        resolution_x, resolution_y = self._output_space.width, self._output_space.height
        
        # Convert image pixels to centered NDC (-1..1)
        x = (x / resolution_x - 0.5) * 2.0
        y = (y / resolution_y - 0.5) * 2.0
        
        # Apply zoom
        zoom_fac = get_view3d_zoom_to_fac(self._view_camera_zoom)
        x *= zoom_fac
        y *= zoom_fac
        
        # Correct aspect ratio mismatch between region and render
        region_aspect = self._region_width / self._region_height
        render_aspect = resolution_x / resolution_y
        
        if region_aspect > 1:
            y *= region_aspect / render_aspect
        else:
            x /= region_aspect
            y /= render_aspect
        
        # Apply camera pan
        offset_x, offset_y = self._view_camera_offset
        x -= offset_x * 4.0 * zoom_fac
        y -= offset_y * 4.0 * zoom_fac
        
        # Convert NDC to region pixels
        x = (x / 2.0 + 0.5) * self._region_width
        y = (y / 2.0 + 0.5) * self._region_height
        
        return x, y

    def _map_from_region_to_output_space(self, coord: Tuple[float, float]) -> Tuple[float, float]:
        """Convert region coordinates to output frame space using cached viewport state"""
        x, y = coord
        assert isinstance(x, (int, float)), f"got: {x}"
        assert isinstance(y, (int, float)), f"got: {y}"
        assert self._output_space is not None, "Viewport state not initialized"

        resolution_x, resolution_y = self._output_space.width, self._output_space.height
        
        # Convert region pixels to NDC (-1..1)
        x = (x / self._region_width - 0.5) * 2.0
        y = (y / self._region_height - 0.5) * 2.0
        
        # Unapply camera pan
        zoom_fac = get_view3d_zoom_to_fac(self._view_camera_zoom)
        offset_x, offset_y = self._view_camera_offset
        x += offset_x * 4.0 * zoom_fac
        y += offset_y * 4.0 * zoom_fac
        
        # Unapply aspect ratio correction
        region_aspect = self._region_width / self._region_height
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

    def map_from_compute_to_region_space(self, coord:Tuple[float, float]) -> Tuple[float, float]:
        """Project from computation viewport to region space (uses cached viewport state)"""
        assert self._output_space is not None, "Viewport state not initialized"
        # map from computation viewport to output space
        coord = map_space(coord, 
            source=crop_space_to_aspect(self.get_compute_space(), self._output_space.width / self._output_space.height), 
            target=self._output_space)
        
        coord = self._map_from_outputframe_to_region_space(coord)
        return coord

    def map_from_region_to_compute_space(self, coord: Tuple[float, float]) -> Tuple[float, float]:
        """Map from region space to computation viewport (uses cached viewport state)"""
        assert self._output_space is not None, "Viewport state not initialized"
        coord = self._map_from_region_to_output_space(coord)
        coord = map_space(coord, 
            source=self._output_space,
            target=crop_space_to_aspect(self.get_compute_space(), self._output_space.width / self._output_space.height))
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

        vl_settings = camera_object.data.vl_settings
        
        if vl_settings.solver_is_paused:
            return

        if not vl_settings.enable_manual_principal:
            center_x = self.get_compute_space().width/2.0 + self.get_compute_space().x
            center_y = self.get_compute_space().height/2.0 + self.get_compute_space().y

            vl_settings.principal = center_x, center_y


        # compute scene scale fromr eference distance
        region = context.region            # The active region (usually VIEW_3D window)
        rv3d   = context.region_data       # The RegionView3D for this region # TODO: context.space_data.region_3d might be more accurate?

        print("Solving camera...", region, rv3d)

        try:
            self._solve_error = None
            match vl_settings.mode:
                case "ONE_POINT":
                    if not vl_settings.enable_manual_principal:
                        center_x = self.get_compute_space().width/2.0 + self.get_compute_space().x
                        center_y = self.get_compute_space().height/2.0 + self.get_compute_space().y
                        vl_settings.principal = center_x,  center_y

                    first_vanishing_lines = [
                        (glm.vec2(*line.start), 
                            glm.vec2(*line.end)) 
                        for line in vl_settings.first_vanishing_lines]

                    second_vanishing_lines = [
                        (glm.vec2(*line.start), 
                            glm.vec2(*line.end)) 
                        for line in vl_settings.second_vanishing_lines]

                    focal_length_pixel = camera_object.data.lens / camera_object.data.sensor_width * self.get_compute_space().height
        
                    # results:dict = solver.solve(
                    #     mode = solver.SolverMode.OneVP,
                    #     viewport =               self.get_compute_space(),

                    #     first_vanishing_lines =  first_vanishing_lines,
                    #     second_vanishing_lines = second_vanishing_lines,
                    #     third_vanishing_lines =  [],

                    #     f =                      focal_length_pixel,
                    #     P =                      glm.vec2(*vl_settings.principal),
                    #     O =                      glm.vec2(*vl_settings.origin),

                    #     reference_axis=          solver.ReferenceAxis.Screen,
                    #     reference_distance_segment=(0, vl_settings.reference_distance),
                    #     reference_world_size=vl_settings.scene_scale,

                    #     first_axis =             solver.Axis.PositiveY, # Blenders camera axes
                    #     second_axis =            solver.Axis.NegativeX, # - " -               
                    # )

                    vp1 = utils.least_squares_intersection_of_lines(first_vanishing_lines)
                    vp2 = None
                    vp3 = None
                    projection, view = solver.orientation_from_one_vanishing_point(
                        self.get_compute_space(),
                        vp1=vp1,
                        second_line=second_vanishing_lines[0],
                        f=focal_length_pixel,
                        P=glm.vec2(*vl_settings.principal)
                    )
                        
                case "TWO_POINT":
                    if not vl_settings.enable_manual_principal:
                        center_x = self.get_compute_space().width/2.0 + self.get_compute_space().x
                        center_y = self.get_compute_space().height/2.0 + self.get_compute_space().y
                        vl_settings.principal = center_x,  center_y

                    first_vanishing_lines = [
                        (glm.vec2(*line.start), 
                            glm.vec2(*line.end)) 
                        for line in vl_settings.first_vanishing_lines]

                    if vl_settings.quad_mode:
                        first_line = vl_settings.first_vanishing_lines[ 0]
                        last_line = vl_settings.first_vanishing_lines[-1]
                        
                        second_vanishing_lines = [
                            (glm.vec2(*first_line.start), glm.vec2(*last_line.start)),
                            (glm.vec2(*first_line.end),   glm.vec2(*last_line.end))
                        ]
                    else:
                        second_vanishing_lines = [
                            (glm.vec2(*line.start), 
                                glm.vec2(*line.end)) 
                            for line in vl_settings.second_vanishing_lines]
                        
                    vp1 = utils.least_squares_intersection_of_lines(first_vanishing_lines)
                    vp2 = utils.least_squares_intersection_of_lines(second_vanishing_lines)
                    vp3 = None
                    projection, view = solver.orientation_from_two_vanishing_points(
                        self.get_compute_space(),
                        vp1=vp1,
                        vp2=vp2,
                        P=glm.vec2(*vl_settings.principal)
                    )
                    
                case "THREE_POINT":
                    first_vanishing_lines = [
                        (glm.vec2(*line.start), 
                            glm.vec2(*line.end)) 
                        for line in vl_settings.first_vanishing_lines]

                    if vl_settings.quad_mode:
                        first_line = vl_settings.first_vanishing_lines[ 0]
                        last_line = vl_settings.first_vanishing_lines[-1]
                        
                        second_vanishing_lines = [
                            (glm.vec2(*first_line.start), glm.vec2(*last_line.start)),
                            (glm.vec2(*first_line.end),   glm.vec2(*last_line.end))
                        ]
                    else:
                        second_vanishing_lines = [
                            (glm.vec2(*line.start), 
                                glm.vec2(*line.end)) 
                            for line in vl_settings.second_vanishing_lines]
                    
                    third_vanishing_lines = [
                        (glm.vec2(*line.start),
                            glm.vec2(*line.end))
                        for line in vl_settings.third_vanishing_lines]

                    vp1 = utils.least_squares_intersection_of_lines(first_vanishing_lines)
                    vp2 = utils.least_squares_intersection_of_lines(second_vanishing_lines)
                    vp3 = utils.least_squares_intersection_of_lines(third_vanishing_lines)

                    projection, view = solver.orientation_from_three_vanishing_points(
                        self.get_compute_space(),
                        vp1=vp1,
                        vp2=vp2,
                        vp3=vp3
                    )

            # validate if matrix is a purely rotational matrix
            if solver.validate_orthogonality(glm.mat3(view)) is False:
                view = glm.mat4(utils.apply_gram_schmidt_orthogonalization(glm.mat3(view))) # note this will remove scaling and translation
                warnings.warn('Warning: Invalid vanishing point configuration.\n'+"View orientation matrix was not orthogonal, applied Gram-Schmidt orthogonalization")
            
            view = solver.adjust_position_to_origin(
                self.get_compute_space(), 
                projection, 
                glm.vec2(*vl_settings.origin), 
                view,
                distance = vl_settings.scene_scale if vl_settings.scene_scale_mode == 'ORIGIN' else 1.0
            )
            if vl_settings.scene_scale_mode != 'ORIGIN':
                view = solver.adjust_scale_to_reference_distance(
                    self.get_compute_space(), 
                    projection, 
                    vl_settings.scene_scale, 
                    solver.ReferenceAxis.Screen, 
                    (0, vl_settings.reference_distance), 
                    view
                )

            view = solver.adjust_axis_assignment(
                solver.Axis.PositiveY,
                solver.Axis.NegativeX,
                view
            )

            apply_solver_results_to_blender_camera(
                projection, 
                view, 
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
