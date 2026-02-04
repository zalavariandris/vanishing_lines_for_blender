
import bpy
import math
import mathutils
from typing import List, Tuple, Iterable, cast
from . import solver
from pyglm import glm
import warnings


####################
# HELPER FUNCTIONS #
####################
from typing import Literal

# def is_operator_running(op_idname):
#     modal_operators = bpy.context.window.modal_operators
#     # print([op.bl_idname if op else None for op in modal_operators])
#     for op in modal_operators:
#         if op.bl_idname == op_idname:
#             return True
#     return False


def extend_line(line_start:mathutils.Vector, line_end:mathutils.Vector, point:mathutils.Vector) -> Tuple[mathutils.Vector, mathutils.Vector]:
    line_dir = (line_end - line_start).normalized()
    line_normal = mathutils.Vector((-line_dir.y, line_dir.x))
    point_vec = point - line_start
    distance_to_line = point_vec.dot(line_normal)

    # Project point onto line
    projected_point = point - distance_to_line * line_normal

    # Determine which direction to extend
    to_start = (projected_point - line_start).dot(line_dir)
    to_end = (projected_point - line_end).dot(line_dir)

    if abs(to_start) < abs(to_end):
        extended_start = projected_point
        extended_end = line_end
    else:
        extended_start = line_start
        extended_end = projected_point

    return extended_start, extended_end

# def find_nearest_point(points: List[mathutils.Vector], target_point:mathutils.Vector) -> mathutils.Vector:
#     points = list(points)  # make a copy to avoid modifying the original list
#     assert all(isinstance(Q, mathutils.Vector) for Q in points), "All points must be mathutils.Vector"
#     assert isinstance(target_point, mathutils.Vector), "P must be a mathutils.Vector"

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


#     sorted_points = sorted(points, key=lambda Q: (Q-target_point).length_squared)

#     if len(sorted_points) == 0:
#         raise ValueError("No points provided to find closest point to vanishing point.")
#     return sorted_points[0]

# adjust vanishing lines to new camera orientation
# def adjust_vanishing_lines_to_matrices(vl_settings, projection_matrix:glm.mat4, view_matrix:glm.mat4):
#     print("Adjusting vanishing lines to camera orientation...")

#     first_vanishing_lines =  [(line.start, line.end) for line in vl_settings.first_vanishing_lines]
#     second_vanishing_lines = [(line.start, line.end) for line in vl_settings.second_vanishing_lines]
#     third_vanishing_lines =  [(line.start, line.end) for line in vl_settings.third_vanishing_lines]

#     axes_mapping = {
#         'X+': solver.types.Axis.PositiveX,
#         'Y+': solver.types.Axis.PositiveY,
#         'Z+': solver.types.Axis.PositiveZ,
#         'X-': solver.types.Axis.NegativeX,
#         'Y-': solver.types.Axis.NegativeY,
#         'Z-': solver.types.Axis.NegativeZ
#     }

#     new_line_sets = solver.utils.adjust_vanishing_lines_to_camera_orientation(
#         first_vanishing_lines,
#         second_vanishing_lines,
#         third_vanishing_lines,
#         axes_mapping[vl_settings.first_axis],
#         axes_mapping[vl_settings.second_axis],
#         glm.mat3(view_matrix),
#         projection_matrix,
#     )

#     # update vl_settings lines
#     for vl_setting_lines, new_lines in zip(
#         [
#             vl_settings.first_vanishing_lines, 
#             vl_settings.second_vanishing_lines, 
#             vl_settings.third_vanishing_lines
#         ],
#         new_line_sets
#     ):
#         for i in range(len(vl_setting_lines)):
#             vl_setting_lines[i].start = new_lines[i][0]
#             vl_setting_lines[i].end =   new_lines[i][1]


# -- COORDINATES --

def _get_view3d_zoom_to_fac(camzoom: float) -> float:
    """Blender internal zoom conversion
    this is some magic formula apparently used by Blender to convert the 3D view zoom level
    """
    return ((math.sqrt(2.0) + camzoom / 50.0) ** 2) / 4.0

def _map_output_to_region(
        fit_mode: Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
        output_size: Tuple[float, float],
        region_size: Tuple[float, float],
        view_camera_zoom: float,
        view_camera_offset: Tuple[float, float],
        output_coords: Tuple[float, float]
    ) -> Tuple[float, float]:
    """Convert output frame coordinates to region space using cached viewport state"""
    x, y = output_coords
    assert isinstance(x, (int, float)), f"got: {x}"
    assert isinstance(y, (int, float)), f"got: {y}"

    resolution_x = output_size[0]
    resolution_y = output_size[1]
    
    # Convert image pixels to centered NDC (-1..1)
    x = (x / resolution_x - 0.5) * 2.0
    y = (y / resolution_y - 0.5) * 2.0
    
    # Apply zoom
    zoom_fac = _get_view3d_zoom_to_fac(view_camera_zoom)
    x *= zoom_fac
    y *= zoom_fac
    
    # Correct aspect ratio mismatch between region and render
    region_aspect = region_size[0] / region_size[1]
    render_aspect = resolution_x / resolution_y


    y *= region_aspect / render_aspect
    if render_aspect < 1.0:
        x *= render_aspect
        y *= render_aspect

    match fit_mode:
        case 'HORIZONTAL':
            if render_aspect < 1.0:   
                x /= render_aspect
                y /= render_aspect

        case 'VERTICAL':
            if render_aspect<1.0:
                x /= region_aspect
                y /= region_aspect
            else:
                x *= render_aspect/region_aspect
                y *= render_aspect/region_aspect
                
        case 'AUTO':
            if region_aspect < 1.0:
                # scale = 1/region_aspect
                x /= region_aspect
                y /= region_aspect
    
    # Apply camera pan
    offset_x, offset_y = view_camera_offset
    x -= offset_x * 4.0 * zoom_fac
    y -= offset_y * 4.0 * zoom_fac
    
    # Convert NDC to region pixels
    x = (x / 2.0 + 0.5) * region_size[0]
    y = (y / 2.0 + 0.5) * region_size[1]
    
    return x, y

def _map_region_to_output(
        fit_mode: Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
        output_size: Tuple[float, float],
        region_size: Tuple[float, float],
        view_camera_zoom: float,
        view_camera_offset: Tuple[float, float],
        region_coords: Tuple[float, float]) -> Tuple[float, float]:
    """Convert region coordinates to output frame space using cached viewport state"""
    x, y = region_coords
    assert isinstance(x, (int, float)), f"got: {x}"
    assert isinstance(y, (int, float)), f"got: {y}"

    resolution_x = output_size[0]
    resolution_y = output_size[1]
    
    # Convert region pixels to NDC (-1..1)
    x = (x / region_size[0] - 0.5) * 2.0
    y = (y / region_size[1] - 0.5) * 2.0
    
    # Unapply camera pan
    zoom_fac = _get_view3d_zoom_to_fac(view_camera_zoom)
    offset_x, offset_y = view_camera_offset
    x += offset_x * 4.0 * zoom_fac
    y += offset_y * 4.0 * zoom_fac
    
    # Unapply aspect ratio correction and sensor fit
    region_aspect = region_size[0] / region_size[1]
    render_aspect = resolution_x / resolution_y
    
    match fit_mode:
        case 'HORIZONTAL':
            if render_aspect < 1.0:   
                x *= render_aspect
                y *= render_aspect

        case 'VERTICAL':
            if render_aspect<1.0:
                x *= region_aspect
                y *= region_aspect
            else:
                x /= render_aspect/region_aspect
                y /= render_aspect/region_aspect
                
        case 'AUTO':
            if region_aspect < 1.0:
                scale = 1/region_aspect
                x /= scale
                y /= scale
    
    y /= region_aspect / render_aspect

    if render_aspect < 1.0:
        scale = 1/render_aspect
        x *= scale
        y *= scale
    
    # Unapply zoom
    x /= zoom_fac
    y /= zoom_fac
    
    # Convert NDC to image pixels
    x = (x / 2.0 + 0.5) * resolution_x
    y = (y / 2.0 + 0.5) * resolution_y
    
    return x, y

def get_camera_frame(context)->Tuple[float, float, float, float]|None:
    """return the camera view frame rectangle in region space.
    if the view is not in camera mode, return None."""
    if not context.space_data.region_3d.view_perspective == 'CAMERA':
        return None
    
    view_camera_zoom =   context.space_data.region_3d.view_camera_zoom
    view_camera_offset = context.space_data.region_3d.view_camera_offset
    sensor_fit =         context.space_data.camera.data.sensor_fit  # get the camera associated with the viewport
    output_size =        context.scene.render.resolution_x, context.scene.render.resolution_y
    region_size =        context.region.width, context.region.height

    x_min, y_min = _map_output_to_region(
        fit_mode = sensor_fit,
        output_size = output_size,
        region_size = region_size,
        view_camera_zoom = view_camera_zoom,
        view_camera_offset = view_camera_offset,
        output_coords = (0,0))
    
    x_max, y_max = _map_output_to_region(
        fit_mode = sensor_fit,
        output_size = output_size,
        region_size = region_size,
        view_camera_zoom = view_camera_zoom,
        view_camera_offset = view_camera_offset,
        output_coords = output_size)

    w, h = x_max-x_min, y_max-y_min
    return x_min, y_min, w, h


# -- CONVERSION BETWEEN THE SOLVER AND BLENDER datatypes --

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
    flattened = [x for xs in blender_mat.transposed() for x in xs]
    return glm.mat4(*flatten())

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

def from_solver_mode(mode:'solver.types.SolverMode') -> str:
    """Convert solver mode to VLProps mode string."""
    match mode:
        case solver.types.SolverMode.OneVP:
            return 'ONE_POINT'
        case solver.types.SolverMode.TwoVP:
            return 'TWO_POINT'
        case solver.types.SolverMode.ThreeVP:
            return 'THREE_POINT'
        case _:
            raise ValueError(f"Unknown solver mode: {mode}")
        
def to_solver_mode(mode_str:str) -> 'solver.types.SolverMode':
    """Convert VLProps mode string to solver mode."""
    match mode_str:
        case 'ONE_POINT':
            return solver.types.SolverMode.OneVP
        case 'TWO_POINT':
            return solver.types.SolverMode.TwoVP
        case 'THREE_POINT':
            return solver.types.SolverMode.ThreeVP
        case _:
            raise ValueError(f"Unknown mode string: {mode_str}")
        
def to_solver_axis(axis_str:str, axis_sign:str) -> 'solver.types.Axis':
    """Convert VLProps axis string to solver axis enum."""
    match axis_str, axis_sign:
        case 'X', 'POSITIVE':
            return solver.types.Axis.PositiveX
        case 'Y', 'POSITIVE':
            return solver.types.Axis.PositiveY
        case 'Z', 'POSITIVE':
            return solver.types.Axis.PositiveZ
        case 'X', 'NEGATIVE':
            return solver.types.Axis.NegativeX
        case 'Y', 'NEGATIVE':
            return solver.types.Axis.NegativeY
        case 'Z', 'NEGATIVE':
            return solver.types.Axis.NegativeZ
        case _:
            raise ValueError(f"Unknown axis string: {axis_str}")
        
def from_solver_axis(axis:'solver.types.Axis') -> Tuple[str, str]:
    """Convert solver axis enum to VLProps axis string."""
    match axis:
        case solver.types.Axis.PositiveX:
            return 'X', 'POSITIVE'
        case solver.types.Axis.PositiveY:
            return 'Y', 'POSITIVE'
        case solver.types.Axis.PositiveZ:
            return 'Z', 'POSITIVE'
        case solver.types.Axis.NegativeX:
            return 'X', 'NEGATIVE'
        case solver.types.Axis.NegativeY:
            return 'Y', 'NEGATIVE'
        case solver.types.Axis.NegativeZ:
            return 'Z', 'NEGATIVE'
        case _:
            raise ValueError(f"Unknown solver axis: {axis}")

def to_solver_reference_axis(axis_str:Literal['ANCHOR', 'SCREEN', 'X_AXIS', 'Y_AXIS', 'Z_AXIS']) -> 'solver.types.ReferenceAxis':
    """Convert VLProps reference axis string to solver reference axis enum."""
    match axis_str:
        case 'ANCHOR':
            return None
        case 'SCREEN':
            return solver.types.ReferenceAxis.Screen
        case 'X_AXIS':
            return solver.types.ReferenceAxis.X_Axis
        case 'Y_AXIS':
            return solver.types.ReferenceAxis.Y_Axis
        case 'Z_AXIS':
            return solver.types.ReferenceAxis.Z_Axis
        case _:
            raise ValueError(f"Unknown reference axis string: {axis_str}")
