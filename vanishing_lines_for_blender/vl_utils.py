import bpy
import math
import mathutils
from typing import Tuple, Iterable, cast
from . import solver
from pyglm import glm
import warnings


####################
# HELPER FUNCTIONS #
####################
from typing import Literal

def is_operator_running(op_idname):
    modal_operators = bpy.context.window.modal_operators
    # print([op.bl_idname if op else None for op in modal_operators])
    for op in modal_operators:
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

def apply_solver_results_to_blender_camera(
        projection: glm.mat4,
        view: glm.mat4, 
        camera_object: bpy.types.Object,
        compute_space: Tuple[float, float, float, float],
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
    P, f = solver.utils.decompose_intrinsics(solver.types.Rect(*compute_space), projection)
    camera_data: bpy.types.Camera = cast(bpy.types.Camera, camera_object.data)
    camera_data.sensor_fit = fit_mode

    # Calculate the aspect ratio correction factor
    match fit_mode:
        case 'AUTO':
            effective_sensor_size = camera_data.sensor_width # when sensor_fit is AUTO, blender uses the _sensor_width_ parameter as sensor effective size for both dimensions.
            focal_length = f / compute_space[2] * effective_sensor_size
            camera_data.lens = focal_length
            # effective_sensor_size = camera_data.sensor_width # when sensor_fit is AUTO, blender uses the _sensor_width_ parameter as sensor effective size for both dimensions.
            # if compute_aspect >= output_aspect:
            #     focal_length = f / compute_space.width * effective_sensor_size
            #     camera_data.lens = focal_length
            # else:
            #     focal_length = f / compute_space.height * effective_sensor_size
            #     camera_data.lens = focal_length

        case 'HORIZONTAL':
            focal_length = f / compute_space[2] * camera_data.sensor_width
            camera_data.lens = focal_length
            
        case 'VERTICAL':
            focal_length = f / compute_space[3] * camera_data.sensor_height
            camera_data.lens = focal_length


    # Apply lens shift
    center_x = compute_space[0] + compute_space[2] / 2
    center_y = compute_space[1] + compute_space[3] / 2
    shift_x = -(P.x - center_x) / (compute_space[2] / 2)
    shift_y = -(P.y - center_y) / (compute_space[3] / 2)

    camera_data.shift_x = shift_x/2
    camera_data.shift_y = shift_y/2

def apply_solver_results_to_view3d(
        projection: glm.mat4,
        view: glm.mat4, 
        context: bpy.types.Context,
        compute_space: Tuple[float, float, float, float],
        fit_mode: Literal['COVER', 'CONTAIN', 'HORIZONTAL', 'VERTICAL'] = 'COVER'
    ) -> None:
    """
    Apply solver results to Blender 3D Viewport
    Args:
        results: Solver results with transform and FOV
        context: Blender context with 3D Viewport
        compute_space: The viewport used for computation (e.g., [-1,-1,2,2])
        fit_mode: How to fit the compute space to the region space
    1. 'HORIZONTAL': Fit based on horizontal dimension
    2. 'VERTICAL': Fit based on vertical dimension
    3. 'CONTAIN': Fit based on larger dimension
    3. 'COVER': Fit based on larger dimension
    """

    if fit_mode != 'COVER':
        raise NotImplementedError("Only 'COVER' fit_mode is implemented for View3D.")
    
    ## apply solver results to blender view
    match context.space_data.region_3d.view_perspective:
        case 'CAMERA':
            camera_object = context.space_data.camera
            apply_solver_results_to_blender_camera(
                projection=projection, 
                view=view, 
                camera_object=camera_object, 
                compute_space=compute_space, 
                fit_mode=camera_object.data.sensor_fit
            )

        case 'PERSP':
            viewport = 0, 0, context.region.width, context.region.height
            principal, focal_length = solver.utils.decompose_intrinsics(solver.types.Rect(*viewport), projection)
            region_aspect = context.region.width / context.region.height
            if region_aspect >= 1.0:
                context.space_data.lens = focal_length*36 / context.region.width * 2 * region_aspect
            else:
                context.space_data.lens = focal_length*36 / context.region.height * 2

            context.space_data.region_3d.view_matrix = glm_to_blender_mat(view)

        case 'ORTHO':
            assert False, "Should not reach here, ORTHO case handled above."

def get_camera_matrices(
    camera_object: bpy.types.Object,
    compute_space: solver.types.Rect
) -> Tuple[glm.mat4, glm.mat4]:
    """
    Extract projection and view matrices from a Blender camera.
    
    Args:
        camera_object: Blender camera object
        compute_space: The viewport rectangle used for computation (e.g., Rect(-1, -1, 2, 2))
    
    Returns:
        Tuple of (projection_matrix, view_matrix) as glm.mat4
    """
    camera_data = camera_object.data
    
    # Calculate focal length in compute space units
    focal_length = camera_data.lens / camera_data.sensor_width * compute_space.height
    
    # Extract principal point from camera shift (reverse of apply_solver_results_to_blender_camera)
    center_x = compute_space.x + compute_space.width / 2
    center_y = compute_space.y + compute_space.height / 2
    # Reverse the operations: shift_x = -(P.x - center_x) / (compute_space.width / 2) / 2
    # So: P.x = center_x - shift_x * 2 * (compute_space.width / 2)
    P_x = center_x - camera_data.shift_x * 2 * (compute_space.width / 2)
    P_y = center_y - camera_data.shift_y * 2 * (compute_space.height / 2)
    principal_point = glm.vec2(P_x, P_y)
    
    # Build projection matrix
    projection = solver.utils.compose_intrinsics(
        viewport=compute_space,
        f=focal_length,
        P=principal_point,
        near=camera_data.clip_start,
        far=camera_data.clip_end
    )
    
    # Build view matrix from camera transform
    view = glm.mat4(*[v for col in camera_object.matrix_world.inverted().transposed() for v in col])
    
    return projection, view



def projection_matrix_from_fov(
    fov_y: float,
    aspect_ratio: float,
    near: float = 0.01,
    far: float = 1000.0
) -> glm.mat4:
    """
    Create a perspective projection matrix from vertical field of view.
    
    Args:
        fov_y: Vertical field of view in radians
        aspect_ratio: Width / Height ratio
        near: Near clipping plane distance
        far: Far clipping plane distance
    
    Returns:
        A 4x4 perspective projection matrix
    """
    f = 1.0 / math.tan(fov_y / 2.0)
    
    return glm.mat4(
        f / aspect_ratio, 0.0, 0.0, 0.0,
        0.0, f, 0.0, 0.0,
        0.0, 0.0, (far + near) / (near - far), (2.0 * far * near) / (near - far),
        0.0, 0.0, -1.0, 0.0
    )

def get_running_operator_by_idname(op_idname):
    for op in bpy.context.window.modal_operators:
        # print(f"Checking operator: {op.bl_idname!r}")
        if op and op.bl_idname == op_idname:
            return op
    return None

def glm_to_blender_mat(glm_mat:glm.mat4) -> mathutils.Matrix:
    """
    Converts a glm.mat4 object to a Blender mathutils.Matrix (4x4).
    
    PyGLM matrices are column-major iterables. 
    Blender's Matrix((...)) constructor expects rows.
    """
    # 1. Feed the 4 columns of the glm.mat4 into the constructor
    # 2. Transpose the result to flip it from column-major to row-major
    return mathutils.Matrix(tuple(glm_mat)).transposed()

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
 