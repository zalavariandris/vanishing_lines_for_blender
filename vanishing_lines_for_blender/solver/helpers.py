from typing import Tuple, Literal, List
import math
from . import utils
from . types import Axis, Rect
import glm

from . types import Line2
import warnings
from . constants import EPSILON, MAX_VANISHING_POINT_DISTANCE

from . exceptions import VanishingLinesError

import warnings
import functools

def deprecated(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):   
        print(f"Deprecated: '{func.__name__}' is deprecated and will be removed in future versions.")
        result = func(*args, **kwargs)
        return result
    return wrapper

#################
# Solve Helpers #
#################

def create_roll_matrix(
        second_vanishing_line:Line2,
        view_matrix:glm.mat4,
        projection_matrix:glm.mat4,
        viewport: Rect,
        first_axis: Axis=Axis.PositiveX,
        second_axis: Axis=Axis.PositiveY
)->glm.mat4:
    """
    Apply a roll correction matrix to the viewmatrix
    to align the horizon based on the second vanishing lines.

    Note: first_axis/second_axis default to canonical space axes (PositiveX/PositiveY).
    The roll is computed in canonical space; user axis assignment is applied
    separately by adjust_axis_assignment() afterward.
    
    """
    # Get the second vanishing line in screen space
    A, B = glm.vec2(*second_vanishing_line[0]), glm.vec2(*second_vanishing_line[1])
    
    # Now unproject to 3D to compute the roll angle
    A_ray = utils.cast_ray(A, view_matrix, projection_matrix, glm.vec4(*viewport))
    B_ray = utils.cast_ray(B, view_matrix, projection_matrix, glm.vec4(*viewport))

    # define the plane coordinate system (the plane facing against the camera screen, oriented by the first axis)
    view_origin = glm.vec3(view_matrix[3])
    forward = glm.normalize(glm.vec3(view_matrix[0][2], view_matrix[1][2], view_matrix[2][2]))

    plane_origin = view_origin + forward * 0.01 # glm.vec3(0, 0, 0) TODO: the computation is dependent on the plane position. Consider removing this dependency from the algorithm.
    plane_normal = axis_positive_vector(first_axis)
    
    plane_y_axis = glm.cross(plane_normal, third_axis_vector(first_axis, second_axis)) # along the line
    plane_x_axis = glm.cross(plane_normal, plane_y_axis)  # perpendicular in the plane

    # Intersect rays with facing plane
    A_on_plane = utils.intersect_ray_with_plane(A_ray, plane_origin, plane_normal)
    B_on_plane = utils.intersect_ray_with_plane(B_ray, plane_origin, plane_normal)

    v = B_on_plane - A_on_plane # vector along the line on the plane
    v_proj = v - glm.dot(v, plane_normal) * plane_normal # project vector onto plane

    flip_to_secondary_axis = False
    if flip_to_secondary_axis:
        # Note: this is an old code, that was matching the 2vp solver.
        #       previously, the vp2 solver axes signs were pointing to the vanishing point. 
        #       now, only the primary points to the sign, the secondary axes always points to the right. 
        #       It feels more predictabble, because it wont flip.
        x_on_plane = glm.dot(v_proj, plane_y_axis)  
        y_on_plane = glm.dot(v_proj, plane_x_axis)
        angle = math.atan2(y_on_plane, x_on_plane) # Compute angle using atan2, normalized to (-π/2, π/2) range ---

        # respect the second axis sign
        # - note: to determinte the sign, we need to check the angle of the line to the first axis in screen space
        O_screen =   glm.project(plane_origin, view_matrix, projection_matrix, glm.vec4(*viewport)).xy
        vp1_screen = glm.project(plane_origin + plane_normal, view_matrix, projection_matrix, glm.vec4(*viewport)).xy
        vp1_dir_screen = glm.normalize(vp1_screen - O_screen)
        
        # flip the angle to match vp2 orientation
        line_dir_screen = glm.normalize(B - A)
        dot = glm.dot(vp1_dir_screen, line_dir_screen)
        if dot> 0: # if the line is more aligned with the negative direction of the first axis, we consider it as a negative second axis
            angle = angle + math.pi
    else:
        x_on_plane = glm.dot(v_proj, plane_y_axis)  
        y_on_plane = glm.dot(v_proj, plane_x_axis)
        angle = math.atan(y_on_plane/x_on_plane) # Compute angle using atan2, normalized to (-π/2, π/2) range ---


    
    roll_axis = plane_normal # plane normal
    roll_matrix: glm.mat4 = glm.rotate(glm.mat4(1.0), angle, roll_axis)  # type: ignore[attr-defined]
    return roll_matrix

@deprecated
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
    if glm.distance(Fu, P) < EPSILON:
        raise VanishingLinesError(" Cannot compute second vanishing point; first vanishing point overlaps principal point.")

    Fu_P = Fu - P

    k = -(glm.dot(Fu_P, Fu_P) + f * f) / glm.dot(Fu_P, horizonDir)
    Fv = Fu_P + k * horizonDir + P

    return Fv

def calc_focal_length_from_vanishing_points(
        Fu:glm.vec2, # first vanishing point
        Fv:glm.vec2, # second vanishing point
        P: glm.vec2   # principal point
    )-> float:
    """
    Computes the focal length from two orthogonal vanishing points using the cross-ratio formula.
    Enhanced with numerical stability improvements for distant vanishing points.
    """

    
    # Check for degenerate cases
    Fu_Fv_distance = glm.distance(Fu, Fv)
    if Fu_Fv_distance < EPSILON:
        raise VanishingLinesError("Focal length cannot be computed; vanishing points overlap.")
    
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
        
        raise VanishingLinesError(f"Invalid vanishing point configuration: cannot compute focal length.\n")
    
    focal_length = math.sqrt(focal_length_squared)
    return focal_length


################
# AXIS helpers #
################

def vector_from_axis(axis: Axis)->glm.vec3:
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
        
def axis_positive_vector(axis: Axis)->glm.vec3:
    """Return the positive unit vector for the given axis, ignoring sign."""
    match axis:
        case Axis.PositiveX | Axis.NegativeX:
            return glm.vec3(1, 0, 0)
        case Axis.PositiveY | Axis.NegativeY:
            return glm.vec3(0, 1, 0)
        case Axis.PositiveZ | Axis.NegativeZ:
            return glm.vec3(0, 0, 1)
        
def third_axis_vector(axis1:Axis, axis2:Axis, handedness:Literal["left-handed", "right-handed"]="right-handed")->glm.vec3:
    """get the vector of the third, perpendicular axis given two axes"""
    vec1 = vector_from_axis(axis1)
    vec2 = vector_from_axis(axis2)
    return glm.normalize(glm.cross(vec1, vec2)) if handedness=="right-handed" else glm.normalize(glm.cross(vec2, vec1))

def third_axis(axis1:Axis, axis2:Axis, handedness:Literal["left-handed", "right-handed"]="right-handed")->Axis:
    """Get the primary axis enum of the third, perpendicular axis given two axes.
    
    Args:
        axis1: First axis
        axis2: Second axis
        handedness: Coordinate system handedness ('right' or 'left')
    
    Returns:
        The perpendicular axis as an Axis enum
    """
    vec = third_axis_vector(axis1, axis2, handedness)
    return primary_axis_from_vector(vec)

def primary_axis_from_vector(vector: glm.vec3) -> Axis:
    """Determine the primary axis (positive or negative) that best aligns with the given vector.
    
    Finds the axis with the largest absolute component and returns the corresponding
    positive or negative Axis enum based on the vector's direction.
    
    Args:
        vector: A 3D vector
    
    Returns:
        The Axis enum that best represents the vector's direction
    """
    # 1. Find the index (0, 1, or 2) of the largest absolute component
    abs_v = glm.abs(vector)
    # Using a list allows us to find the index of the max value
    components = [abs_v.x, abs_v.y, abs_v.z]
    major_axis_index = components.index(max(components))
    
    # 2. Use a simple lookup to return the correct Enum
    is_positive = vector[major_axis_index] > 0
    
    lookup = {
        0: (Axis.PositiveX, Axis.NegativeX),
        1: (Axis.PositiveY, Axis.NegativeY),
        2: (Axis.PositiveZ, Axis.NegativeZ)
    }
    
    return lookup[major_axis_index][0 if is_positive else 1]


##########################
# Vanishing Line helpers #
##########################

@deprecated
def adjust_vanishing_lines(
        old_vp:glm.vec2, 
        new_vp:glm.vec2, 
        vanishing_lines:List[Tuple[glm.vec2, glm.vec2]]
    ) -> List[Tuple[glm.vec2, glm.vec2]]:
    """Adjust vanishing lines when their vanishing point moves.
    
    When a vanishing point moves, this function adjusts the vanishing lines by moving
    only the closest endpoint of each line proportionally to maintain perspective.
    
    Args:
        old_vp: Previous position of the vanishing point
        new_vp: New position of the vanishing point
        vanishing_lines: List of vanishing lines as (start, end) point tuples
    
    Returns:
        Updated list of vanishing lines with adjusted endpoints
    """
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

@deprecated
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

@deprecated
def vanishing_points_from_camera(projection: glm.mat4, view: glm.mat4) -> Tuple[glm.vec2, glm.vec2, glm.vec2]:
    """Extract vanishing points from camera projection and view matrices.
    
    Vanishing points are where parallel lines in world space converge in the image.
    For each world axis, we project a point at a very large distance along that axis.
    """
    # Use a very large but finite value to represent "infinity"
    MAX_DIST = 1e10
    
    # World space basis vectors (X, Y, Z directions)
    # These are points at very large distances along each axis
    far_points = [
        glm.vec3(MAX_DIST, 0, 0), # X-axis
        glm.vec3(0, MAX_DIST, 0), # Y-axis
        glm.vec3(0, 0, MAX_DIST)  # Z-axis
    ]
    
    vanishing_points = []
    
    for far_point in far_points:
        # Transform to clip space: P * V * point
        vp_clip = projection * view * glm.vec4(far_point, 1.0)
        
        # Check for degenerate case (direction parallel to image plane)
        if abs(vp_clip.w) < EPSILON:
            # Point at infinity - use a very large NDC value
            vanishing_points.append(glm.vec2(vp_clip.x * 1e6, vp_clip.y * 1e6))
        else:
            # Perspective divide to get NDC coordinates (normalized device coordinates)
            # These are in the range [-1, 1] for the viewport
            ndc = glm.vec2(vp_clip.x / vp_clip.w, vp_clip.y / vp_clip.w)
            vanishing_points.append(ndc)
    
    return tuple(vanishing_points)