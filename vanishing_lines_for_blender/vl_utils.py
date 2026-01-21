
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
            # Only set if value actually changed to avoid triggering msgbus callbacks
            if abs(camera_data.lens - focal_length) > 0.0000001:
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
            # Only set if value actually changed to avoid triggering msgbus callbacks
            if abs(camera_data.lens - focal_length) > 0.0000001:
                camera_data.lens = focal_length
            
        case 'VERTICAL':
            focal_length = f / compute_space[3] * camera_data.sensor_height
            # Only set if value actually changed to avoid triggering msgbus callbacks
            if abs(camera_data.lens - focal_length) > 0.0000001:
                camera_data.lens = focal_length


    # Apply lens shift
    center_x = compute_space[0] + compute_space[2] / 2
    center_y = compute_space[1] + compute_space[3] / 2
    shift_x = -(P.x - center_x) / (compute_space[2] / 2)
    shift_y = -(P.y - center_y) / (compute_space[3] / 2)

    camera_data.shift_x = shift_x/2
    camera_data.shift_y = shift_y/2

def apply_orientation_to_blender_camera(
        view: glm.mat4,
        camera_object: bpy.types.Object
    ) -> None:
    """
    Apply orientation from solver view matrix to Blender camera object.
    Keeps the current camera position, only changes rotation.
    
    Args:
        view: Solver view matrix (glm.mat4)
        camera_object: Blender camera object to modify
    """
    if not isinstance(camera_object.data, bpy.types.Camera):
        raise TypeError("Expected a Camera data-block")
    
    if not isinstance(view, glm.mat4):
        raise TypeError("Expected view to be glm.mat4")
    
    # Get current camera position
    current_transform = glm_from_blender_mat(camera_object.matrix_world)
    current_position = glm.vec3(current_transform[3])
    
    # Apply new orientation (rotation only)
    new_transform = glm.inverse(view)
    
    # Keep the current position
    new_transform[3] = glm.vec4(current_position, 1.0)
    
    # Apply to Blender camera
    transform_list = [[v for v in row] for row in glm.transpose(new_transform)]
    camera_object.matrix_world = mathutils.Matrix(transform_list)

def apply_projection_to_blender_camera(
        projection: glm.mat4,
        camera_object: bpy.types.Object,
        compute_space: Tuple[float, float, float, float],
        fit_mode: Literal['HORIZONTAL', 'VERTICAL', 'AUTO']
    ) -> None:
    """
    Apply projection matrix to Blender camera (focal length and lens shift).
    
    Args:
        projection: Projection matrix from solver
        camera_object: Blender camera object to modify
        compute_space: The viewport used for computation (e.g., (-1, -1, 2, 2))
        fit_mode: How to fit the compute space ('HORIZONTAL', 'VERTICAL', 'AUTO')
    """
    if not isinstance(camera_object.data, bpy.types.Camera):
        raise TypeError("Expected a Camera data-block")
    
    if tuple(compute_space) != (-1, -1, 2, 2):
        raise ValueError(f"Compute space other than [-1,-1,2,2] is not supported; got {compute_space}.")
    
    # Decompose intrinsics to get principal point and focal length
    P, f = solver.utils.decompose_intrinsics(solver.types.Rect(*compute_space), projection)
    camera_data: bpy.types.Camera = cast(bpy.types.Camera, camera_object.data)
    camera_data.sensor_fit = fit_mode

    # Calculate and apply focal length based on fit mode
    match fit_mode:
        case 'AUTO':
            effective_sensor_size = camera_data.sensor_width
            focal_length = f / compute_space[2] * effective_sensor_size
            if abs(camera_data.lens - focal_length) > 0.0000001:
                camera_data.lens = focal_length

        case 'HORIZONTAL':
            focal_length = f / compute_space[2] * camera_data.sensor_width
            if abs(camera_data.lens - focal_length) > 0.0000001:
                camera_data.lens = focal_length
            
        case 'VERTICAL':
            focal_length = f / compute_space[3] * camera_data.sensor_height
            if abs(camera_data.lens - focal_length) > 0.0000001:
                camera_data.lens = focal_length

    # Apply lens shift from principal point
    center_x = compute_space[0] + compute_space[2] / 2
    center_y = compute_space[1] + compute_space[3] / 2
    shift_x = -(P.x - center_x) / (compute_space[2] / 2)
    shift_y = -(P.y - center_y) / (compute_space[3] / 2)

    camera_data.shift_x = shift_x / 2
    camera_data.shift_y = shift_y / 2

def adjust_camera_to_keep_point_at_screen_position(
        camera_object: bpy.types.Object,
        anchor_point: glm.vec3,
        target_screen_position: glm.vec2,
        projection: glm.mat4,
        compute_space: Tuple[float, float, float, float]
    ) -> None:
    """
    Adjust camera position so that a world point projects to specific screen coordinates.
    Uses ray casting to maintain the exact distance to the pivot point.
    
    Args:
        camera_object: Blender camera object to modify
        world_point: Point in 3D world space (the pivot point)
        target_screen_position: Target screen position (x, y in screen/compute space)
        projection: Projection matrix
        compute_space: Compute space as (x, y, width, height)
    """
    # Get current camera transform
    current_transform = glm_from_blender_mat(camera_object.matrix_world)
    current_camera_pos = glm.vec3(current_transform[3])
    
    # Calculate distance from current camera to world point
    target_distance = glm.length(anchor_point - current_camera_pos)
    
    # Get current view matrix
    current_view = glm_from_blender_mat(camera_object.matrix_world.inverted())
    
    # Create a view matrix with rotation only (no translation)
    view_rotation_only = glm.mat4(
        current_view[0],
        current_view[1],
        current_view[2],
        glm.vec4(0, 0, 0, 1)
    )
    
    # Define viewport
    viewport = glm.vec4(compute_space[0], compute_space[1], compute_space[2], compute_space[3])

    proj, view = get_camera_matrices(camera_object)
    
    # Unproject the screen position at near and far plane to get ray direction
    near_point = glm.unProject(
        glm.vec3(target_screen_position.x, target_screen_position.y, 0.0),
        view_rotation_only, 
        projection, 
        viewport
    )
    far_point = glm.unProject(
        glm.vec3(target_screen_position.x, target_screen_position.y, 1.0),
        view_rotation_only, 
        projection, 
        viewport
    )
    
    # Calculate ray direction (from camera into scene)
    ray_direction = glm.normalize(far_point - near_point)
    
    # Calculate camera position: world_point - distance * ray_direction
    # This places the camera at 'target_distance' away from world_point, opposite to ray_direction
    new_camera_position = anchor_point - target_distance * ray_direction
    
    # Update camera position
    current_transform[3] = glm.vec4(new_camera_position, 1.0)
    
    # Apply to Blender camera
    transform_list = [[v for v in row] for row in glm.transpose(current_transform)]
    camera_object.matrix_world = mathutils.Matrix(transform_list)

def apply_solver_results_to_view3d(
        projection: glm.mat4,
        view: glm.mat4, 
        area: bpy.types.Area,
        compute_space: Tuple[float, float, float, float],
        fit_mode: Literal['COVER', 'CONTAIN', 'HORIZONTAL', 'VERTICAL'] = 'COVER'
    ) -> None:
    """
    Apply solver results to Blender 3D Viewport
    Args:
        results: Solver results with transform and FOV
        area: Blender 3D Viewport area
        compute_space: The viewport used for computation (e.g., [-1,-1,2,2])
        fit_mode: How to fit the compute space to the region space
    1. 'HORIZONTAL': Fit based on horizontal dimension
    2. 'VERTICAL': Fit based on vertical dimension
    3. 'CONTAIN': Fit based on larger dimension
    3. 'COVER': Fit based on larger dimension
    """

    if fit_mode != 'COVER':
        raise NotImplementedError("Only 'COVER' fit_mode is implemented for View3D.")
    
    space = area.spaces.active
    window_region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    if not window_region:
        raise ValueError("No WINDOW region found in area")
    
    ## apply solver results to blender view
    match space.region_3d.view_perspective:
        case 'CAMERA':
            camera_object = space.camera
            apply_solver_results_to_blender_camera(
                projection=projection, 
                view=view, 
                camera_object=camera_object, 
                compute_space=compute_space, 
                fit_mode=camera_object.data.sensor_fit
            )

        case 'PERSP':
            viewport = 0, 0, window_region.width, window_region.height
            principal, focal_length = solver.utils.decompose_intrinsics(solver.types.Rect(*viewport), projection)
            region_aspect = window_region.width / window_region.height
            if region_aspect >= 1.0:
                new_lens = focal_length*36 / window_region.width * 2 * region_aspect
            else:
                new_lens = focal_length*36 / window_region.height * 2
            
            # Only set if value actually changed to avoid triggering msgbus callbacks
            if abs(space.lens - new_lens) > 0.0000001:
                space.lens = new_lens

            space.region_3d.view_matrix = glm_to_blender_mat(view)

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

def ball_control(M:glm.mat4, pivot:glm.vec3, yaw:float, pitch:float) -> glm.mat4:
    # TODO: use blender mathutils for this!
    up = glm.vec3(0,0,1)
    forward = -M[2].xyz
    horizontal_axis = glm.normalize(glm.cross(up, forward))
    vertical_axis = up

    M = glm.rotate(glm.mat4(1.0), yaw, vertical_axis) * glm.rotate(glm.mat4(1.0), pitch, horizontal_axis) * M
    
    return M

# adjust vanishing lines to new camera orientation
def adjust_vanishing_lines_to_camera(vl_settings, projection_matrix:glm.mat4, view_matrix:glm.mat4):
    print("Adjusting vanishing lines to camera orientation...")

    first_vanishing_lines =  [(line.start, line.end) for line in vl_settings.first_vanishing_lines]
    second_vanishing_lines = [(line.start, line.end) for line in vl_settings.second_vanishing_lines]
    third_vanishing_lines =  [(line.start, line.end) for line in vl_settings.third_vanishing_lines]

    axes_mapping = {
        'X+': solver.types.Axis.PositiveX,
        'Y+': solver.types.Axis.PositiveY,
        'Z+': solver.types.Axis.PositiveZ,
        'X-': solver.types.Axis.NegativeX,
        'Y-': solver.types.Axis.NegativeY,
        'Z-': solver.types.Axis.NegativeZ
    }

    new_line_sets = solver.utils.adjust_vanishing_lines_to_camera_orientation(
        first_vanishing_lines,
        second_vanishing_lines,
        third_vanishing_lines,
        axes_mapping[vl_settings.first_axis],
        axes_mapping[vl_settings.second_axis],
        glm.mat3(view_matrix),
        projection_matrix,
    )

    # update vl_settings lines
    for vl_setting_lines, new_lines in zip(
        [
            vl_settings.first_vanishing_lines, 
            vl_settings.second_vanishing_lines, 
            vl_settings.third_vanishing_lines
        ],
        new_line_sets
    ):
        for i in range(len(vl_setting_lines)):
            vl_setting_lines[i].start = new_lines[i][0]
            vl_setting_lines[i].end =   new_lines[i][1]

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

def get_view_orbit_point(context) -> mathutils.Vector|None:
    """
    Get the point around which the 3D view orbits.
    
    Returns:
        The 3D location that the view orbits around, or None if not in a 3D view.
    """
    space = context.space_data
    if not space or space.type != 'VIEW_3D':
        return None
    
    return space.region_3d.view_location.copy() # note: view_location is actually the Orbit Pivot Point (the target), not the camera's physical position in world space.
 
def glm_to_blender_mat(glm_mat:glm.mat4) -> mathutils.Matrix:
    """
    Converts a glm.mat4 object to a Blender mathutils.Matrix (4x4).
    """
    # 1. Feed the 4 columns of the glm.mat4 into the constructor
    # 2. Transpose the result to flip it from column-major to row-major
    return mathutils.Matrix(tuple(glm_mat)).transposed()

def glm_from_blender_mat(blender_mat:mathutils.Matrix) -> glm.mat4:
    """
    Converts a Blender mathutils.Matrix (4x4) to a glm.mat4 object.
    """
    # 1. Transpose the Blender matrix to convert from row-major to column-major
    # 2. Feed the resulting iterable into the glm.mat4 constructor
    return glm.mat4(*flatten(blender_mat.transposed()))

def matrix_to_array(mat: mathutils.Matrix) -> list[float]:
    """
    Convert a 4x4 mathutils.Matrix to a flat list of 16 floats (row-major order).
    """
    if not isinstance(mat, mathutils.Matrix) or len(mat.col) != 4 or len(mat.row) != 4:
        raise ValueError("Input must be a 4x4 mathutils.Matrix")
    return [v for row in mat for v in row]

def array_to_matrix(arr: list[float]) -> mathutils.Matrix:
    """
    Convert a flat list of 16 floats to a 4x4 mathutils.Matrix (row-major order).
    """
    if not isinstance(arr, (list, tuple)) or len(arr) != 16:
        raise ValueError(f"Input must be a list or tuple of 16 floats got: {arr}")
    return mathutils.Matrix([arr[i*4:(i+1)*4] for i in range(4)])