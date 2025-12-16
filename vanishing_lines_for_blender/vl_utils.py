import bpy
import math
import mathutils
from typing import Tuple, Iterable, cast
from .core import solver_functional as solver
import glm

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
    Returns a rectangle that fills the aspect ratio by cropping the excess.
    (Crop)
    """
    sx, sy, sw, sh = source
    source_ar = sw / sh

    if source_ar > target_aspect:
        # Source too wide → match width, expand height
        new_w = sw
        new_h = new_w / target_aspect
        new_x = sx
        new_y = sy - (new_h - sh) / 2
    else:
        # Source too tall → match height, expand width
        new_h = sh
        new_w = new_h * target_aspect
        new_x = sx - (new_w - sw) / 2
        new_y = sy

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
    
    # Apply transform
    transform = glm.inverse(view)
    transform_list = [[v for v in row] for row in glm.transpose(transform)]
    camera_object.matrix_world = mathutils.Matrix(transform_list)

    # Apply focal length
    P, f, shift = solver.decompose_intrinsics(compute_space, projection)
    fovy = solver.utils.fov_from_focal_length(f, compute_space.height)
    camera_data: bpy.types.Camera = cast(bpy.types.Camera, camera_object.data)

    # Calculate the aspect ratio correction factor
    compute_aspect = compute_space.width / compute_space.height
    output_aspect = output_space.width / output_space.height
    sensor_aspect = camera_data.sensor_width / camera_data.sensor_height
    
    # The focal length needs to be adjusted based on which dimension is constraining
    # When compute space is cropped to match output aspect, the effective sensor size changes
    
    # camera_data.angle_y = fovy/2
    # if compute_aspect > output_aspect:
        # Compute space is wider - height is constraining dimension
        # Use results.fovy directly, but adjust sensor width
        # focal_length = utils.focal_length_from_fov(fovy, camera_data.sensor_height)
        # camera_data.lens = focal_length
        # camera_data.angle_y = fovy
    # else:
        # Compute space is taller - width is constraining dimension  
        # Need to calculate fovx and derive focal length from that
    # fovx = 2.0 * math.atan(math.tan(fovy / 2.0) / compute_aspect)
    # camera_data.angle_x = fovx
        # focal_length = utils.focal_length_from_fov(fovx, camera_data.sensor_width)
        # camera_data.lens = focal_length
    
    camera_data.lens = solver.utils.focal_length_from_fov(fovy, camera_data.sensor_width)
    
    
    # Apply lens shift
    
    center_x = compute_space.x + compute_space.width / 2
    center_y = compute_space.y + compute_space.height / 2
    shift_x =  (P.x - center_x) / (compute_space.width / 2)
    shift_y = -(P.y - center_y) / (compute_space.height / 2)
    camera_data.shift_x = shift_x/2
    camera_data.shift_y = shift_y/2

def get_viewer_camera(context) -> bpy.types.Object|None:
    for area in context.window.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    if space.region_3d.view_perspective == 'CAMERA': # only return if viewing through camera
                        return space.camera # get the camera associated with the viewport
    return None

def set_viewer_camera(context, camera_object: bpy.types.Object):
    for area in context.window.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.camera = camera_object  # Set the viewport camera
                    space.region_3d.view_perspective = 'CAMERA'  # Switch to camera view

def get_view3d_zoom_to_fac(camzoom: float) -> float:
    """Blender internal zoom conversion"""
    return ((math.sqrt(2.0) + camzoom / 50.0) ** 2) / 4.0
