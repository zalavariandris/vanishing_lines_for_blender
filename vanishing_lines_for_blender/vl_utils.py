import bpy
import math
import mathutils
from typing import Tuple, Iterable, cast
from . import solver
import glm
import warnings
####################
# HELPER FUNCTIONS #
####################
from typing import Literal

def is_operator_running(op_idname):
    for op in bpy.context.window.modal_operators:
        if op.bl_idname == op_idname:
            return True
    return False

def closest_point_to_target(points: Iterable[Tuple[float, float]], P:Tuple[float, float]) -> Tuple[float, float]:
    sorted_points = sorted(points, key=lambda Q: (Q[0]-P[0])**2 + (Q[1]-P[1])**2)
    if len(sorted_points) == 0:
        raise ValueError("No points provided to find closest point to vanishing point.")
    return sorted_points[0]

def dim_color(color:Tuple[float, float, float, float], factor:float=0.18)->Tuple[float, float, float, float]:
    return (color[0], color[1], color[2], color[3]*factor)

def flatten(xss):
    return [x for xs in xss for x in xs]

###################
# BLENDER HELPERS #
###################

def get_running_operator_by_idname(op_idname):
    for op in bpy.context.window.modal_operators:
        if op and op.bl_idname == op_idname:
            return op
    return None

def apply_solver_results_to_blender_camera(
        projection: glm.mat4,
        view: glm.mat4, 
        camera_object: bpy.types.Object,
        compute_space: solver.types.Rect,
        fit_mode: Literal['HORIZONTAL', 'VERTICAL', 'AUTO']
    ) -> None:
    """
    Apply solver results to Blender camera, accounting for aspect ratio differences
    between compute space and output space.
    
    Args:
        results: Solver results with transform and FOV
        camera_object: Blender camera object to modify
        compute_space: The viewport used for computation (e.g., [-1,-1,2,2])
        output_size: The actual render output size

    fit_mode: How to fit the compute space to the output space
    Important: this has the same behavior as the 'sensor_fit' parameter in blender, and it has to match the way the camera is set up.
        'HORIZONTAL': Fit based on horizontal dimension
        'VERTICAL': Fit based on vertical dimension
        'AUTO': Fit based on larger dimension

    """
    if not isinstance(camera_object.data, bpy.types.Camera):
        raise TypeError("Expected a Camera data-block")
    
    if tuple(compute_space) != (-1, -1, 2, 2):
        raise ValueError(f"Compute space other than [-1,-1,2,2] is not supported; got {compute_space}.")
    
    # Apply transform
    transform = glm.inverse(view)
    transform_list = [[v for v in row] for row in glm.transpose(transform)]
    camera_object.matrix_world = mathutils.Matrix(transform_list)

    # Apply focal length
    P, f = solver.utils.decompose_intrinsics(compute_space, projection)
    camera_data: bpy.types.Camera = cast(bpy.types.Camera, camera_object.data)
    camera_data.sensor_fit = fit_mode

    # Calculate the aspect ratio correction factor
    match fit_mode:
        case 'AUTO':
            effective_sensor_size = camera_data.sensor_width # when sensor_fit is AUTO, blender uses the _sensor_width_ parameter as sensor effective size for both dimensions.
            focal_length = f / compute_space.width * effective_sensor_size
            camera_data.lens = focal_length
            # effective_sensor_size = camera_data.sensor_width # when sensor_fit is AUTO, blender uses the _sensor_width_ parameter as sensor effective size for both dimensions.
            # if compute_aspect >= output_aspect:
            #     focal_length = f / compute_space.width * effective_sensor_size
            #     camera_data.lens = focal_length
            # else:
            #     focal_length = f / compute_space.height * effective_sensor_size
            #     camera_data.lens = focal_length

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

def set_view_camera(context, camera_object: bpy.types.Object):
    space = context.space_data
    if not space or space.type != 'VIEW_3D':
        warnings.warn("Context is not a 3D Viewport!")
        return None

    space.camera = camera_object  # Set the viewport camera
    space.region_3d.view_perspective = 'CAMERA'  # Switch to camera view

def get_view_camera(context):
    space = context.space_data
    if not space or space.type != 'VIEW_3D':
        # warnings.warn("Context is not a 3D Viewport!")
        return None

    # If the viewport is locked to a camera
    if space.region_3d.view_perspective != 'CAMERA':
        # warnings.warn("View does not use a Camera!")
        return None

    return space.camera

def get_scene_camera(context)-> bpy.types.Object|None:
    camera = context.scene.camera
    return camera

def get_calibration_camera(context) -> bpy.types.Object|None:
    if camera := get_view_camera(context):
        return camera
    elif camera := get_scene_camera(context):
        return camera
    return None
 