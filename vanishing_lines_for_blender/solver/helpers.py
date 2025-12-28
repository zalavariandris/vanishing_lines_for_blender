from typing import Tuple, Literal, List
import math
from . import utils
from . types import Axis, Rect
from pyglm import glm
import warnings
from . constants import EPSILON, MAX_VANISHING_POINT_DISTANCE

from . types import Point2

def compute_roll_matrix(
        second_vanishing_line:Tuple[Point2, Point2],
        view_matrix:glm.mat4,
        projection_matrix:glm.mat4,
        viewport: Rect,
        first_axis: Axis=Axis.PositiveX, # TODO: are these needed?
        second_axis: Axis=Axis.PositiveY
)->glm.mat4:
    """
    Apply a roll correction matrix to the viewmatrix
    to align the horizon based on the second vanishing lines.
    """

    # Project the second vanishing line the forward plane in 3D world space
    A, B = glm.vec2(*second_vanishing_line[0]), glm.vec2(*second_vanishing_line[1])

    # Unproject pixel coordinates to world space rays 
    A_ray = utils.cast_ray(A, view_matrix, projection_matrix, glm.vec4(*viewport))
    B_ray = utils.cast_ray(B, view_matrix, projection_matrix, glm.vec4(*viewport))

    # define the plane coordinate system (the plane facing against the camera screen, orineted by the first axis)
    view_origin = glm.vec3(view_matrix[3])
    forward = glm.normalize(glm.vec3(view_matrix[0][2], view_matrix[1][2], view_matrix[2][2]))

    plane_origin = view_origin + forward*0.01# glm.vec3(0, 0, 0) TODO: the computation is dependent on the plane position. Consider removeing this dependency from the algorithm.
    plane_normal = axis_positive_vector(first_axis)
    plane_y_axis = glm.cross(plane_normal, third_axis_vector(first_axis, second_axis)) # along the line
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

def axis_positive_vector(axis)->glm.vec3:
    match axis:
        case Axis.PositiveX | Axis.NegativeX:
            return glm.vec3(1, 0, 0)
        case Axis.PositiveY | Axis.NegativeY:
            return glm.vec3(0, -1, 0)
        case Axis.PositiveZ | Axis.NegativeZ:
            return glm.vec3(0, 0, 1)
        
def third_axis_vector(axis1:Axis, axis2:Axis)->glm.vec3:
    vec1 = vector_from_axis(axis1)
    vec2 = vector_from_axis(axis2)
    return glm.normalize(glm.cross(vec1, vec2))

def third_axis(axis1:Axis, axis2:Axis)->Axis:
    vec = third_axis_vector(axis1, axis2)
    return axis_from_vector(vec)

def axis_from_vector(vector: glm.vec3)->Axis:
    if vector.x == 0 and vector.y == 0:
      return Axis.PositiveZ if vector.z > 0 else Axis.NegativeZ
    elif vector.x == 0 and vector.z == 0:
      return Axis.PositiveY if vector.y > 0 else Axis.NegativeY
    elif vector.y == 0 and vector.z == 0:
      return Axis.PositiveX if vector.x > 0 else Axis.NegativeX
    
    raise ValueError('Invalid axis vector')

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
