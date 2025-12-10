# standard library
from collections import namedtuple
from typing import Dict, List, Tuple, Literal, Final, Iterable
from enum import IntEnum
import math
from dataclasses import dataclass
from textwrap import dedent
from abc import ABC, abstractmethod

# third party library
import glm
import numpy as np

import warnings

from . constants import (
    EPSILON, 
    DEFAULT_NEAR_PLANE, 
    DEFAULT_FAR_PLANE, 
    MAX_VANISHING_POINT_DISTANCE
)

from . import utils
from . types import *


#########################
# MAIN SOLVER FUNCTIONS #
#########################
def solve(
        mode:SolverMode, 
        viewport: Rect,
        first_vanishing_lines: List[Tuple[glm.vec2, glm.vec2]],
        second_vanishing_lines: List[Tuple[glm.vec2, glm.vec2]],
        third_vanishing_lines: List[Tuple[glm.vec2, glm.vec2]],

        f:float, # focal length (in height units)
        P:glm.vec2,
        O:glm.vec2,

        reference_axis:ReferenceAxis,
        reference_distance_segment:Tuple[float, float], # 2D distance from origin to camera
        reference_world_size:float,

        first_axis:Axis,
        second_axis:Axis
    )->Dict:
        """
        Main solver function.
        
        :param mode: Description
        :type mode: SolverMode
        
        :param viewport: Description
        :type viewport: Rect (x, y, w, h)
        :param first_vanishing_lines: Description
        :type first_vanishing_lines: List[Tuple[glm.vec2, glm.vec2]]
        :param second_vanishing_lines: Description
        :type second_vanishing_lines: List[Tuple[glm.vec2, glm.vec2]]
        :param third_vanishing_lines: Description
        :type third_vanishing_lines: List[Tuple[glm.vec2, glm.vec2]]
        :param f: focal length (in the same units as viewport rect)
        :type f: float
        :param P: Principal point, in the same coordinate system as viewport
        :type P: glm.vec2
        :param O: Description
        :type O: glm.vec2
        :param reference_axis: Description
        :type reference_axis: ReferenceAxis
        :param reference_distance_segment: Description
        :type reference_distance_segment: Tuple[float, float]
        :param reference_world_size: Description
        :type reference_world_size: float
        :param first_axis: Description
        :type first_axis: Axis
        :param second_axis: Description
        :type second_axis: Axis
        :return: Description
        :rtype: Dict
        
        """
        return _solve_functional_impl_v1(
            mode,
            viewport,
            first_vanishing_lines,
            second_vanishing_lines,
            third_vanishing_lines,

            f,
            P,
            O,

            reference_axis,
            reference_distance_segment,
            reference_world_size,

            first_axis,
            second_axis
        )

def _solve_functional_impl_v1(
        mode:SolverMode, 
        viewport: Rect,
        first_vanishing_lines: List[Tuple[glm.vec2, glm.vec2]],
        second_vanishing_lines: List[Tuple[glm.vec2, glm.vec2]],
        third_vanishing_lines: List[Tuple[glm.vec2, glm.vec2]],

        f:float, # focal length (in height units)
        P:glm.vec2,
        O:glm.vec2,

        reference_axis:ReferenceAxis,
        reference_distance_segment:Tuple[float, float], # 2D distance from origin to camera
        reference_world_size:float,

        first_axis:Axis,
        second_axis:Axis
    ):
    
    match mode:
        case SolverMode.OneVP:
            vp1 = utils.least_squares_intersection_of_lines(first_vanishing_lines)
            vp2 = None
            vp3 = None
            projection, view = orientation_from_one_vanishing_point(
                viewport,
                vp1=vp1,
                second_line=second_vanishing_lines[0],
                f=f,
                P=P
            )

        case SolverMode.TwoVP:
            vp1 = utils.least_squares_intersection_of_lines(first_vanishing_lines)
            vp2 = utils.least_squares_intersection_of_lines(second_vanishing_lines)
            vp3 = None
            projection, view = orientation_from_two_vanishing_points(
                viewport,
                vp1=vp1,
                vp2=vp2,
                P=P
            )

        case SolverMode.ThreeVP:
            vp1 = utils.least_squares_intersection_of_lines(first_vanishing_lines)
            vp2 = utils.least_squares_intersection_of_lines(second_vanishing_lines)
            vp3 = utils.least_squares_intersection_of_lines(third_vanishing_lines)

            projection, view = orientation_from_three_vanishing_points(
                viewport,
                vp1=vp1,
                vp2=vp2,
                vp3=vp3
            )

    # validate if matrix is a purely rotational matrix
    if validate_orthogonality(glm.mat3(view)) is False:
        view = glm.mat4(utils.apply_gram_schmidt_orthogonalization(glm.mat3(view))) # note this will remove scaling and translation
        warnings.warn('Warning: Invalid vanishing point configuration.\n'+"View orientation matrix was not orthogonal, applied Gram-Schmidt orthogonalization")
    
    view = adjust_position_to_origin(
        viewport, 
        projection, 
        O, 
        view
    )

    view = adjust_scale_to_reference_distance(
        viewport, 
        projection, 
        reference_world_size, 
        reference_axis, 
        reference_distance_segment, 
        view
    )

    view = adjust_axis_assignment(
        first_axis,
        second_axis,
        view
    )

    return {
        # initial parameters
        'viewport': viewport,

        # vanishing points
        'first_vanishing_point':  vp1,
        'second_vanishing_point': vp2,
        'third_vanishing_point':  vp3,
        
        # projection
        'projection':   projection,

        # position
        'view': view
    }


#####################
# SOLVER COMPONENTS #
#####################
def orientation_from_one_vanishing_point(viewport, vp1, second_line, f, P)->Tuple[glm.mat4, glm.mat4]:
    # compute projection
    projection = compose_intrinsics(viewport, f, P)

    # compute orientation
    view_matrix:glm.mat4x4 = glm.mat4(_impl_compute_orientation_from_single_vanishing_point(
        Fu=vp1,
        P=P,
        f=f,
        horizon_direction=glm.vec2(1,0)
    ))

    # Adjust Camera Roll to match second vanishing line
    view_matrix:glm.mat4 = view_matrix * compute_roll_matrix(
        second_line, # Roll the camera based on the horizon line projected to 3D
        view_matrix,
        projection,
        viewport
    )  # type: ignore[assignment] # PyGLM type stubs incorrectly infer mat4x2

    return projection, view_matrix

def orientation_from_two_vanishing_points(viewport, vp1, vp2, P)->Tuple[glm.mat4, glm.mat4]:
    f = compute_focal_length_from_vanishing_points(Fu=vp1,Fv=vp2,P=P)

    # compute projection
    projection = compose_intrinsics(viewport, f, P)

    # compute orientation
    view_matrix:glm.mat4 = glm.mat4(_impl_compute_orientation_from_two_vanishing_points(
        Fu=vp1,
        Fv=vp2,
        P=P,
        f=f
    ))

    return projection, view_matrix

def orientation_from_three_vanishing_points(viewport, vp1, vp2, vp3)->Tuple[glm.mat4, glm.mat4]:
    P = utils.triangle_orthocenter(vp1,vp2,vp3)
    f = compute_focal_length_from_vanishing_points(Fu=vp1,Fv=vp2,P=P)

    # compute projection
    projection = compose_intrinsics(viewport, f, P)

    # compute orientation
    view_matrix:glm.mat4 = glm.mat4(_impl_compute_orientation_from_two_vanishing_points(
        Fu=vp1,
        Fv=vp2,
        P=P,
        f=f
    ))

    return projection, view_matrix

def _impl_compute_orientation_from_single_vanishing_point(
        Fu:glm.vec2,
        P:glm.vec2,
        f:float,
        horizon_direction:glm.vec2
    )->glm.mat3:
    """
    Computes the camera orientation matrix from a single vanishing point.
    """

    # Direction from principal point to vanishing point
    forward = glm.normalize( glm.vec3(Fu-P, -f))
    up =      glm.normalize( glm.cross(glm.vec3(horizon_direction, 0), forward))
    right =   glm.normalize( glm.cross(up, forward))

    #
    orientation = glm.mat3(forward, right, up)

    return orientation

def _impl_compute_orientation_from_two_vanishing_points(
        Fu:glm.vec2, # first vanishing point
        Fv:glm.vec2, # second vanishing point
        P:glm.vec2,
        f:float
    )->glm.mat3:

    forward = glm.normalize(glm.vec3(Fu-P, -f))
    right =   glm.normalize(glm.vec3(Fv-P, -f))
    up =      glm.cross(forward, right)

    orientation = glm.mat3(forward, right, up)

    return orientation

def validate_orthogonality(mat: glm.mat3) -> bool:
    """ Validates if the given matrix is orthogonal (i.e., its transpose equals its inverse)."""
    identity = glm.mat3(1.0)
    should_be_identity = mat * glm.transpose(mat)
    return glm.all(glm.equal(should_be_identity, identity, glm.vec3(EPSILON)))

def adjust_position_to_origin(
        viewport, 
        projection:glm.mat4, 
        O:glm.vec2, 
        view:glm.mat4
    )->glm.mat4:
    
    # Convert world distance 1.0 to NDC z-coordinate
    distance = 1.0
    near = DEFAULT_NEAR_PLANE
    far = DEFAULT_FAR_PLANE
    
    # Perspective-correct depth calculation
    ndc_z = (far + near) / (far - near) + (2 * far * near) / ((far - near) * distance)
    ndc_z = (ndc_z + 1) / 2  # Convert from [-1, 1] to [0, 1]
    
    # Unproject the origin point at distance 1.0
    viewport_tuple = (
        viewport.x, 
        viewport.y, 
        viewport.width, 
        viewport.height
    )
    origin_3d = glm.unProject(
        glm.vec3(O.x, O.y, ndc_z),
        view,
        projection,
        viewport_tuple
    )
    
    # Move camera so this point becomes the world origin
    camera_position = -origin_3d
    
    view = glm.translate(view, camera_position)  # type: ignore[attr-defined]

    return view

def adjust_scale_to_reference_distance(
        viewport, 
        projection:glm.mat4,
        reference_world_size:float, 
        reference_axis:ReferenceAxis,
        reference_distance_segment:Tuple[float, float],
        view:glm.mat4, 
    )->glm.mat4:

    return apply_reference_world_distance(
        reference_axis, 
        reference_distance_segment, 
        reference_world_size,
        view, 
        projection, 
        viewport
    )

def adjust_axis_assignment(
        first_axis, 
        second_axis, 
        view_matrix:glm.mat4
    )->glm.mat4:
    return view_matrix * glm.mat4(create_axis_assignment_matrix(first_axis, second_axis))  # type: ignore[return-value] # PyGLM type stubs incorrectly infer mat4x2


###########################
# ADJUST CAMERA FUNCTIONS #
###########################
def compute_roll_matrix(
        second_vanishing_line:Tuple[glm.vec2, glm.vec2],
        view_matrix:glm.mat4,
        projection_matrix:glm.mat4,
        viewport: Rect,
        first_axis:Axis=Axis.PositiveX, # TODO: are these needed?
        second_axis:Axis=Axis.PositiveY
)->glm.mat4:
    """
    Apply a roll correction matrix to the viewmatrix
    to align the horizon based on the second vanishing lines.
    """

    # Project the second vanishing line the forward plane in 3D world space
    A, B = second_vanishing_line

    # Unproject pixel coordinates to world space rays 
    A_ray = utils.cast_ray(A, view_matrix, projection_matrix, glm.vec4(*viewport))
    B_ray = utils.cast_ray(B, view_matrix, projection_matrix, glm.vec4(*viewport))

    # define the plane coordinate system (the plane facing against the camera screen, orineted by the first axis)
    view_origin = glm.vec3(view_matrix[3])
    forward = glm.normalize(glm.vec3(view_matrix[0][2], view_matrix[1][2], view_matrix[2][2]))

    plane_origin = view_origin + forward*0.01# glm.vec3(0, 0, 0) TODO: the computation is dependent on the plane position. Consider removeing this dependency from the algorithm.
    plane_normal = _axis_positive_vector(first_axis)
    plane_y_axis = glm.cross(plane_normal, _third_axis_vector(first_axis, second_axis)) # along the line
    plane_x_axis = glm.cross(plane_normal, plane_y_axis)  # perpendicular in the plane

    # Intersect rays with facing plane
    A_on_plane = utils.intersect_ray_with_plane(A_ray, plane_origin, plane_normal)
    B_on_plane = utils.intersect_ray_with_plane(B_ray, plane_origin, plane_normal)

    v = B_on_plane - A_on_plane # vector along the line on the plane
    v_proj = v - glm.dot(v, plane_normal) * plane_normal # project vector onto plane

    # --- Compute 360° angle using atan2 ---
    x_on_plane = glm.dot(v_proj, plane_y_axis)
    y_on_plane = glm.dot(v_proj, plane_x_axis)
    angle = angle = math.atan(y_on_plane / x_on_plane)
    
    roll_axis = plane_normal # plane normal
    roll_matrix: glm.mat4 = glm.rotate(glm.mat4(1.0), angle, roll_axis)  # type: ignore[attr-defined]
    return roll_matrix

def apply_reference_world_distance(
        reference_axis:ReferenceAxis, 
        reference_screen_length_segment:Tuple[float, float], # 2D distance on the specidied reference axis. Optionally use a tuple for a segment (start, end)
        reference_world_size:float,
        view_matrix, 
        projection_matrix, 
        viewport
    ):

    """ Calculate the world distance from origin based on the reference distance mode and value."""
    match reference_axis:
        case ReferenceAxis.X_Axis:
            reference_axis = glm.vec3(1, 0, 0)
        case ReferenceAxis.Y_Axis:
            reference_axis = glm.vec3(0, 1, 0)
        case ReferenceAxis.Z_Axis:
            reference_axis = glm.vec3(0, 0, 1)
        case ReferenceAxis.Screen | _:
            # use camera right vector as reference axis
            right = glm.mat3(glm.inverse(view_matrix))[0]   # right vector is +X in view space
            reference_axis = right

    O_screen = glm.project(
        glm.vec3(0, 0, 0), 
        view_matrix, 
        projection_matrix, 
        tuple(viewport)).xy
    
    V_screen = glm.project(reference_axis, view_matrix, projection_matrix, tuple(viewport)).xy
    dir_screen = glm.normalize(glm.vec2(V_screen.x - O_screen.x, V_screen.y - O_screen.y))

    reference_offset, reference_length = reference_screen_length_segment
    reference_line = (glm.vec3(0,0,0), reference_axis)

    reference_start_point_screen = O_screen + dir_screen * reference_offset
    reference_start_ray = utils.cast_ray(reference_start_point_screen, view_matrix, projection_matrix, tuple(viewport))
    reference_start_point_world = utils.closest_point_between_lines(
        reference_line, 
        reference_start_ray
    )

    reference_end_point_screen = O_screen + dir_screen * (reference_offset + reference_length)
    reference_end_ray = utils.cast_ray(reference_end_point_screen, view_matrix, projection_matrix, tuple(viewport))

    reference_end_point_world = utils.closest_point_between_lines(
        reference_line, 
        reference_end_ray
    )

    reference_world_length = glm.distance(reference_start_point_world, reference_end_point_world)

    # apply to view matrix
    view_matrix = glm.mat4(view_matrix) # make a copy
    view_position = glm.vec3(view_matrix[3])
    view_matrix[3] = glm.vec4(view_position/reference_world_length*reference_world_size, 1.0)
    return view_matrix

def create_axis_assignment_matrix(first_axis: Axis, second_axis: Axis) -> glm.mat3:
    """
    Creates an axis assignment matrix that maps vanishing point directions to user-specified world axes.
    
    Args:
        firstVanishingPointAxis: The world axis that the first vanishing point should represent
        secondVanishingPointAxis: The world axis that the second vanishing point should represent
    
    Returns:
        A 3x3 rotation matrix that transforms from vanishing point space to world space
    
    Raises:
        Exception: If the axis assignment creates an invalid (non-orthogonal) matrix

    Note:
        Identity if:
        - if First vanishing point naturally points along the world's +X direction
        - Second vanishing point naturally points along the world's +Y direction
        - Third direction (computed via cross product) naturally points along the world's +Z direction
    """
    
    # Get the unit vectors for the specified axes
    forward = _vector_from_axis(first_axis)
    right = _vector_from_axis(second_axis)
    up = glm.cross(forward, right)
    
    # Build the matrix with each row representing the target world axis
    axis_assignment_matrix = glm.mat3( # TODO: this is the inverse of the mat3_from_directions
        forward.x,
        forward.y,
        forward.z,
        right.x,
        right.y,
        right.z,
        up.x,
        up.y,
        up.z
    )
    
    # Validate that we have a proper orthogonal matrix
    assert math.fabs(1 - glm.determinant(axis_assignment_matrix)) < EPSILON, "Invalid axis assignment: axes must be orthogonal"
    return axis_assignment_matrix

def compose_intrinsics(viewport:Rect, f:float, P:glm.vec2)->glm.mat4:
    """ Composes the projection matrix from intrinsic parameters."""
    # compute projection
    shift = -(P - viewport.center) / (viewport.size / 2.0)  # Negated to match convention
    fovy = utils.fov_from_focal_length(f, viewport.height)
    aspect = viewport.width/viewport.height

    # return glm.perspective(fovy, aspect, DEFAULT_NEAR_PLANE, DEFAULT_FAR_PLANE)
    # Compute top/bottom/left/right in view space
    top = DEFAULT_NEAR_PLANE * glm.tan(fovy / 2)
    bottom = -top
    right = top * aspect
    left = -right

    # Apply shifts
    width = right - left
    height = top - bottom

    left   += shift.x * width / 2
    right  += shift.x * width / 2
    bottom += shift.y * height / 2
    top    += shift.y * height / 2

    # Create the projection matrix with lens shift
    return glm.frustum(left, right, bottom, top, DEFAULT_NEAR_PLANE, DEFAULT_FAR_PLANE)

def decompose_intrinsics(viewport, projection)->Tuple[glm.vec2, float, glm.vec2]:
    """
    Decomposes the projection matrix to retreive principal point, focal length and shift.
    
    :param viewport:   Description
    :param projection: Description

    :return: P, f, shift
    :rtype: Tuple[Any, float, Any]
    
    """ 
    left, right, top, bottom, near, far = utils.decompose_frustum(projection)
    Ppx = ((right + left) / (top - bottom)) * near
    Ppy = ((top + bottom) / (top - bottom)) * near
    P = glm.vec2(
        viewport.center.x - (Ppx / near) * (viewport.height / 2),
        viewport.center.y + (Ppy / near) * (viewport.height / 2)
    )
    f = near/(bottom-top) * viewport.height
    shift = (P - viewport.center) / (viewport.size / 2.0)
    return P, f, shift

def decompose_extrinsics(view)->Tuple[glm.vec3, glm.quat]:
    """ Decomposes the view matrix to retreive position and orientation.
    returns (position, orientation)
    
    :param viewport:   Description
    :param projection: Description

    :return: position, orientation
    :rtype: Tuple[glm.vec3, glm.quat]
    
    """
    scale = glm.vec3()
    quat = glm.quat()  # This will be our quaternion
    translation = glm.vec3()
    skew = glm.vec3()
    perspective = glm.vec4()
    success = glm.decompose(view, scale, quat, translation, skew, perspective)

    if not success:
        raise ValueError("Failed to decompose view matrix.")
    
    return translation, quat


###########
# HELPERS #
###########
def calc_second_vanishing_point_from_focal_length(
        Fu: glm.vec2, 
        f: float, 
        P: glm.vec2, 
        horizonDir: glm.vec2
    )->glm.vec2:
    """
    Computes the coordinates of the second vanishing point
    based on the first, a focal length, the center of projection and
    the desired horizon tilt angle. The equations here are derived from
    section 3.2 "Determining the focal length from a single image".

    @param Fu the first vanishing point in _image plane_ coordinates.
    @param f the relative focal length
    @param P the center of projection in _normalized image_ coordinates
    @param horizonDir The desired horizon direction
    """
    
    # find the second vanishing point
    # // TODO_ take principal point into account here
    if glm.distance(Fu, P) < EPSILON:
        raise ValueError("First vanishing point coincides with principal point, cannot compute second vanishing point.")

    Fu_P = Fu - P

    k = -(glm.dot(Fu_P, Fu_P) + f * f) / glm.dot(Fu_P, horizonDir)
    Fv = Fu_P + k * horizonDir + P

    return Fv

def compute_focal_length_from_vanishing_points(
        Fu: glm.vec2, # first vanishing point
        Fv: glm.vec2, # second vanishing point
        P: glm.vec2   # principal point
    )-> float:
    """
    Computes the focal length from two orthogonal vanishing points using the cross-ratio formula.
    Enhanced with numerical stability improvements for distant vanishing points.
    """
    # Check for degenerate cases
    Fu_Fv_distance = glm.distance(Fu, Fv)
    if Fu_Fv_distance < EPSILON:
        raise ValueError(f"Vanishing points are too close together: distance = {Fu_Fv_distance:.2e}")
    
    # Detect if vanishing points are very far away and need special handling
    max_reasonable_distance = MAX_VANISHING_POINT_DISTANCE # Configurable threshold
    Fu_distance = glm.distance(Fu, P)
    Fv_distance = glm.distance(Fv, P)
    
    # For very distant VPs, clamp them to reasonable bounds to prevent numerical issues
    if Fu_distance > max_reasonable_distance or Fv_distance > max_reasonable_distance:
        warnings.warn(f"Warning: Very distant vanishing points detected (Fu: {Fu_distance:.1f}, Fv: {Fv_distance:.1f})")
        
        # Clamp to reasonable distance while preserving direction
        if Fu_distance > max_reasonable_distance:
            direction = glm.normalize(Fu - P)
            Fu = P + direction * max_reasonable_distance
            
        if Fv_distance > max_reasonable_distance:
            direction = glm.normalize(Fv - P)
            Fv = P + direction * max_reasonable_distance

        warnings.warn(f"  Clamped vanishing points to Fu: {Fu}, Fv: {Fv}")
    
    # Use the standard cross-ratio formula with improved numerical precision
    horizon_vector = Fu - Fv
    horizon_direction = glm.normalize(horizon_vector)
    
    principal_to_fv = P - Fv
    projection_length = glm.dot(horizon_direction, principal_to_fv)
    projection_point = Fv + projection_length * horizon_direction
    
    # Use double precision for critical calculations
    distance_fv_to_proj = float(glm.distance(Fv, projection_point))
    distance_fu_to_proj = float(glm.distance(Fu, projection_point))
    distance_p_to_proj =  float(glm.distance(P, projection_point))
    
    focal_length_squared = distance_fv_to_proj * distance_fu_to_proj - distance_p_to_proj * distance_p_to_proj
    
    if focal_length_squared <= 0:
        vanishing_point_distance = glm.distance(Fu, Fv)
        angle_deg = math.degrees(math.acos(glm.clamp(
            glm.dot(glm.normalize(Fu - P), glm.normalize(Fv - P)), -1.0, 1.0
        )))
        
        raise ValueError(
            f"Invalid vanishing point configuration: cannot compute focal length.\n"
            f"  f² = {focal_length_squared:.6f} (must be > 0)\n"
            f"  Vanishing point separation: {vanishing_point_distance:.2f} pixels\n"
            f"  Angle between VP directions: {angle_deg:.1f}° (should be close to 90°)\n"
            f"  Distance Fu->projection: {distance_fu_to_proj:.2f}\n"
            f"  Distance Fv->projection: {distance_fv_to_proj:.2f}\n"
            f"  Distance P->projection: {distance_p_to_proj:.2f}\n"
            f"  Possible causes: VPs too close to principal point, VPs not orthogonal, or VPs collinear with principal point"
        )
    
    focal_length = math.sqrt(focal_length_squared)
    return focal_length


#####################
# UTILITY FUNCTIONS #
#####################
def _vector_from_axis(axis: Axis)->glm.vec3:
    match axis:
      case Axis.NegativeX:
        return glm.vec3(-1, 0, 0)
      case Axis.PositiveX:
        return glm.vec3(1, 0, 0)
      case Axis.NegativeY:
        return glm.vec3(0, -1, 0)
      case Axis.PositiveY:
        return glm.vec3(0, 1, 0)
      case Axis.NegativeZ:
        return glm.vec3(0, 0, -1)
      case Axis.PositiveZ:
        return glm.vec3(0, 0, 1)

def _axis_positive_vector(axis)->glm.vec3:
    match axis:
        case Axis.PositiveX | Axis.NegativeX:
            return glm.vec3(1, 0, 0)
        case Axis.PositiveY | Axis.NegativeY:
            return glm.vec3(0, -1, 0)
        case Axis.PositiveZ | Axis.NegativeZ:
            return glm.vec3(0, 0, 1)
        
def _third_axis_vector(axis1:Axis, axis2:Axis)->glm.vec3:
    vec1 = _vector_from_axis(axis1)
    vec2 = _vector_from_axis(axis2)
    return glm.normalize(glm.cross(vec1, vec2))

def _axis_from_vector(vector: glm.vec3)->Axis:
    if vector.x == 0 and vector.y == 0:
      return Axis.PositiveZ if vector.z > 0 else Axis.NegativeZ
    elif vector.x == 0 and vector.z == 0:
      return Axis.PositiveY if vector.y > 0 else Axis.NegativeY
    elif vector.y == 0 and vector.z == 0:
      return Axis.PositiveX if vector.x > 0 else Axis.NegativeX
    
    raise ValueError('Invalid axis vector')

def calc_vanishing_points_from_camera(
        view_matrix: glm.mat3, 
        projection_matrix: glm.mat4, 
        viewport: Rect
    ) -> Tuple[glm.vec2, glm.vec2, glm.vec2]:
    """
    Calculate the projected vanishing points from the camera matrices.
    """
    
    # Project vanishing Points
    MAX_FLOAT32 = (2 - 2**-23) * 2**127
    VPX = glm.project(glm.vec3(MAX_FLOAT32,0,0), view_matrix, projection_matrix, viewport)
    VPY = glm.project(glm.vec3(0,MAX_FLOAT32,0), view_matrix, projection_matrix, viewport)
    VPZ = glm.project(glm.vec3(0,0,MAX_FLOAT32), view_matrix, projection_matrix, viewport)

    return glm.vec2(VPX), glm.vec2(VPY), glm.vec2(VPZ)

def adjust_vanishing_lines(
        old_vp:glm.vec2, 
        new_vp:glm.vec2, 
        vanishing_lines:List[Tuple[glm.vec2, glm.vec2]]
    ) -> List[Tuple[glm.vec2, glm.vec2]]:
    # When vanishing point moves, adjust only the closest endpoint of each vanishing line
    new_vanishing_lines = vanishing_lines.copy()
    for i, (P, Q) in enumerate(vanishing_lines):
        # Find which endpoint is closer to the old vanishing point
        dist_P = glm.length(P - old_vp)  # type: ignore[attr-defined]
        dist_Q = glm.length(Q - old_vp)  # type: ignore[attr-defined]
        
        # Choose the closer endpoint and the fixed endpoint
        if dist_P < dist_Q:
            moving_point, fixed_point = P, Q
        else:
            moving_point, fixed_point = Q, P
        
        # Calculate relative position and apply to new vanishing point
        line_to_old_vp = old_vp - fixed_point
        line_to_moving = moving_point - fixed_point
        
        if glm.length(line_to_old_vp) > EPSILON:  # type: ignore[attr-defined]
            ratio = glm.length(line_to_moving) / glm.length(line_to_old_vp)  # type: ignore[attr-defined]
            new_line_to_vp = new_vp - fixed_point
            new_moving_point = fixed_point + glm.normalize(new_line_to_vp) * glm.length(new_line_to_vp) * ratio  # type: ignore[attr-defined]
            
            # Update the correct endpoint
            if dist_P < dist_Q:
                new_vanishing_lines[i] = (new_moving_point, Q)
            else:
                new_vanishing_lines[i] = (P, new_moving_point)
    return new_vanishing_lines

def adjust_vanishing_lines_by_rotation(
        old_vp: glm.vec2, 
        new_vp: glm.vec2, 
        vanishing_lines: List[Tuple[glm.vec2, glm.vec2]],
        principal_point: glm.vec2
    ) -> List[Tuple[glm.vec2, glm.vec2]]:
    """
    Adjust vanishing lines by rotating them around the principal point so they point to the new vanishing point.
    """
    
    # Apply the same rotation to all line endpoints
    new_vanishing_lines = []
    for P, Q in vanishing_lines:
        # Calculate the global rotation from old VP to new VP (relative to principal point)
        old_dir = glm.normalize(old_vp - P)
        new_dir = glm.normalize(new_vp - P)
        
        # Calculate rotation angle
        dot_product = glm.dot(old_dir, new_dir)
        dot_product = max(-1.0, min(1.0, dot_product))  # Clamp to avoid numerical errors
        rotation_angle = math.acos(dot_product)
        
        # Determine rotation direction using cross product (in 2D, this gives the z-component)
        cross_z = old_dir.x * new_dir.y - old_dir.y * new_dir.x
        if cross_z < 0:
            rotation_angle = -rotation_angle
        new_P = utils.rotate_point_around_center(P, principal_point, rotation_angle)
        new_Q = utils.rotate_point_around_center(Q, principal_point, rotation_angle)
        new_vanishing_lines.append((new_P, new_Q))
    
    return new_vanishing_lines

def flip_coordinate_handness(mat: glm.mat4) -> glm.mat4:
    """swap left-right handed coordinate system"""
    flipZ = glm.scale(glm.vec3(1.0, 1.0, -1.0))  # type: ignore[attr-defined]
    return flipZ * mat # todo: check order
