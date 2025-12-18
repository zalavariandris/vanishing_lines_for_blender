import bpy
import math
import mathutils
from typing import Tuple, Iterable, cast
from . core import solver_functional as solver
import glm

####################
# HELPER FUNCTIONS #
####################
from typing import Literal


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


###################
# BLENDER HELPERS #
###################
def apply_solver_results_to_blender_camera(
        projection: glm.mat4,
        view: glm.mat4, 
        camera_object: bpy.types.Object,
        compute_space: solver.Rect,
        output_space: solver.Rect,
        fit_mode: Literal['HORIZONTAL', 'VERTICAL', 'AUTO']='HORIZONTAL'
    ) -> None:
    """
    Apply solver results to Blender camera, accounting for aspect ratio differences
    between compute space and output space.
    
    Args:
        results: Solver results with transform and FOV
        camera_object: Blender camera object to modify
        compute_space: The viewport used for computation (e.g., [-1,-1,2,2])
        output_space: The actual render output viewport

    fit_mode: How to fit the compute space to the output space
    Important: this has the same behavior as the 'sensor_fit' parameter in blender.
        'HORIZONTAL': Fit based on horizontal dimension
        'VERTICAL': Fit based on vertical dimension
        'AUTO': Fit based on larger dimension

    """
    if not isinstance(camera_object.data, bpy.types.Camera):
        raise TypeError("Expected a Camera data-block")
    
    # Apply transform
    transform = glm.inverse(view)
    transform_list = [[v for v in row] for row in glm.transpose(transform)]
    camera_object.matrix_world = mathutils.Matrix(transform_list)

    # Apply focal length
    P, f, shift = solver.decompose_intrinsics(compute_space, projection)
    camera_data: bpy.types.Camera = cast(bpy.types.Camera, camera_object.data)

    # Calculate the aspect ratio correction factor
    compute_aspect = compute_space.width / compute_space.height
    output_aspect = output_space.width / output_space.height

    match fit_mode:
        case 'AUTO':
            if compute_aspect >= output_aspect:
                effective_sensor_size = max(camera_data.sensor_width, camera_data.sensor_height)
                focal_length = f / compute_space.width * effective_sensor_size
                camera_data.lens = focal_length
            else:
                effective_sensor_size = max(camera_data.sensor_width, camera_data.sensor_height)
                focal_length = f / compute_space.height * effective_sensor_size
                camera_data.lens = focal_length

        case 'HORIZONTAL':
            focal_length = f / compute_space.width * camera_data.sensor_width
            camera_data.lens = focal_length
            
        case 'VERTICAL':
            focal_length = f / compute_space.height * camera_data.sensor_height
            camera_data.lens = focal_length

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

