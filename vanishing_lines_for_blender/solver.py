# standard library
from typing import List, Tuple, Literal
from enum import IntEnum
import math
import logging


# third party library
import glm

# set up logger
logger = logging.getLogger(__name__)

#########
# TYPES #
#########
class Axis(IntEnum):
    PositiveX = 0
    NegativeX = 1
    PositiveY = 2
    NegativeY = 3
    PositiveZ = 4
    NegativeZ = 5

class EulerOrder(IntEnum):
    XYZ = 0
    XZY = 1
    YZX = 2
    YXZ = 3
    ZXY = 4
    ZYX = 5

#########################
# MAIN SOLVER FUNCTIONS #
#########################
def solve1vp(
        width:int,
        height:int,
        Fu: glm.vec2,
        second_vanishing_line: Tuple[glm.vec2, glm.vec2],
        f:float|None=None, # focal length (in width and height units)
        P:glm.vec2|None=None,
        O:glm.vec2|None=None,
        first_axis = Axis.PositiveZ,
        second_axis = Axis.PositiveX,
        scale:float=1.0
    )->glm.mat4:
        """
        Solve camera orientation from a single vanishing point and focal length,
        and computes the camera position from the scene origin 'O'.
        
        params:
            width: image width in pixels
            height: image height in pixels
            Fu: first vanishing point in pixel coordinates
            second_vanishing_line: used to compute camera roll
            f: focal length in pixels
            P: principal point in pixel coordinates
            O: the scene origin in pixel coordinates
            first_axis: the world axis that the first vanishing point represents
            second_axis: the world axis that the second vanishing point represents
            scale: scene scale factor

        returns:
            the camera transformation matrix.
        """
        if f is None:
            f = height / 4  # assume a reasonable focal length
        if P is None:
            P = glm.vec2(width/2, height/2)
        if O is None:
            O = glm.vec2(width/2, height/2)
        #################################
        # 3. COMPUTE Camera Orientation #
        #################################
        view_orientation_matrix = compute_orientation_from_single_vanishing_point(
            Fu,
            P,
            f
        )
  
        # convert to 4x4 matrix for transformations
        view_matrix:glm.mat4 = glm.mat4(view_orientation_matrix)

        ##############################
        # 4. COMPUTE Camera Position #
        ##############################
        camera_position = compute_camera_position(
            width, 
            height, 
            f, 
            view_matrix, 
            O, 
            scale
        )

        # apply translation
        view_matrix = glm.translate(view_matrix, camera_position)

        #########################
        # 3. Adjust Camera Roll #
        #########################
        # Roll the camera based on the horizon line projected to 3D
        if second_vanishing_line:
            fovy = fov_from_focal_length(f, height)
            roll_matrix = compute_roll_matrix(
                width, 
                height, 
                second_vanishing_line,
                projection_matrix=glm.perspective(fovy, width/height, 0.1, 100.0),
                view_matrix=view_matrix
            )

            # apply roll
            view_matrix = view_matrix * roll_matrix

        # world transform from view_matrix
        camera_transform = glm.inverse(view_matrix)

        ############################
        # 4. Apply axis assignment #
        ############################
        axis_assignment_matrix:glm.mat3 = create_axis_assignment_matrix(first_axis, second_axis)       
        camera_transform= glm.mat4(axis_assignment_matrix)*camera_transform

        return camera_transform

def solve2vp(
        width:int,
        height:int,
        Fu: glm.vec2,
        Fv: glm.vec2,
        P: glm.vec2,
        O: glm.vec2,
        first_axis = Axis.PositiveZ,
        second_axis = Axis.PositiveX,
        scale:float=1.0
    )->Tuple[float, glm.mat4]:
    """ Solve camera intrinsics and orientation from 3 orthogonal vanishing points.
    returns (fovy in radians, camera_orientation_matrix, camera_position)
    """
    ###########################
    # 2. COMPUTE Focal Length #
    ###########################
    f = compute_focal_length_from_vanishing_points(
        Fu = Fu, 
        Fv = Fv, 
        P =  P
    )
    fovy = fov_from_focal_length(f, height)

    #################################
    # 3. COMPUTE Camera Orientation #
    #################################
    view_orientation_matrix = compute_orientation_from_two_vanishing_points(
        Fu,
        Fv,
        P,
        f
    )

    view_matrix = glm.mat4(view_orientation_matrix)

    ##############################
    # 4. COMPUTE Camera Position #
    ##############################
    camera_position = compute_camera_position(
        width, 
        height, 
        f, 
        glm.mat4(view_orientation_matrix), 
        O, 
        scale
    )

    # apply translation
    view_matrix = glm.translate(view_matrix, camera_position)

    # world transform from view_matrix
    camera_transform = glm.inverse(view_matrix)

    ############################
    # 5. Apply axis assignment #
    ############################
    axis_assignment_matrix:glm.mat3 = create_axis_assignment_matrix(first_axis, second_axis)       
    camera_transform= glm.mat4(axis_assignment_matrix)*camera_transform

    return fovy, camera_transform

########################
# CORE SOLVER FUNCTIOS #
########################
def second_vanishing_point_from_focal_length(
        Fu: glm.vec2, 
        f: float, 
        P: glm.vec2, 
        horizonDir: glm.vec2
    )->glm.vec2|None:
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
    if glm.distance(Fu, P) < 1e-7:
        return None

    Fu_P = Fu - P

    k = -(glm.dot(Fu_P, Fu_P) + f * f) / glm.dot(Fu_P, horizonDir)
    Fv = Fu_P + k * horizonDir + P

    return Fv

def compute_orientation_from_single_vanishing_point(
        Fu:glm.vec2,
        P:glm.vec2,
        f:float,
        horizon_direction:glm.vec3=glm.vec3(1,0,0)
    ):
    """
    Computes the camera orientation matrix from a single vanishing point.
    """

    # Direction from principal point to vanishing point
    Fu_P = Fu-P
    forward = glm.normalize( glm.vec3(Fu_P.x, Fu_P.y,  -f))

    # 
    up =   glm.normalize( glm.cross(horizon_direction, forward))
    right =      glm.normalize( glm.cross(up, forward))

    #
    view_orientation_matrix = glm.mat3(forward, right, up)

    # validate if matrix is a purely rotational matrix
    determinant = glm.determinant(view_orientation_matrix)
    if math.fabs(determinant - 1) > 1e-6:
        view_orientation_matrix = _gram_schmidt_orthogonalization(view_orientation_matrix)
        logger.warning(f'Warning: Invalid vanishing point configuration. Rotation determinant {determinant}\n'+"View orientation matrix was not orthogonal, applied Gram-Schmidt orthogonalization")
    
    return view_orientation_matrix

def compute_orientation_from_two_vanishing_points(
        Fu:glm.vec2, # first vanishing point
        Fv:glm.vec2, # second vanishing point
        P:glm.vec2,
        f:float
    )->glm.mat3:

    forward = glm.normalize(glm.vec3(Fu-P, -f))
    right =   glm.normalize(glm.vec3(Fv-P, -f))
    up = glm.cross(forward, right)
    view_orientation_matrix = glm.mat3(forward, right, up)

    # validate if matrix is a purely rotational matrix
    determinant = glm.determinant(view_orientation_matrix)
    if math.fabs(determinant - 1) > 1e-6:
        view_orientation_matrix = _gram_schmidt_orthogonalization(view_orientation_matrix)
        logger.warning(f'Warning: Invalid vanishing point configuration. Rotation determinant {determinant}\n'+"View orientation matrix was not orthogonal, applied Gram-Schmidt orthogonalization")

    return view_orientation_matrix

def compute_camera_position(
        width:int,
        height:int,
        f:float,
        view_matrix:glm.mat4,
        O:glm.vec2,
        scale:float=1.0,
    )-> glm.vec3:
    """
    Computes the camera position in 3D space from 2D image coordinates and camera parameters.
    """
    fovy = fov_from_focal_length(f, height)
    near = 0.1
    far = 100
    projection_matrix = glm.perspective(
        fovy, # fovy in radians
        width/height, # aspect 
        near,
        far
    )

    # convert to 4x4 matrix for transformations
    origin_3D = glm.unProject(
        glm.vec3(
            O.x, 
            O.y, 
            _world_depth_to_ndc_z(scale, near, far)
        ),
        glm.mat4(view_matrix), 
        projection_matrix, 
        glm.vec4(0,0,width,height)
    )

    return -origin_3D

def compute_roll_matrix(
        width:int,
        height:int,
        second_vanishing_line:Tuple[glm.vec2, glm.vec2],
        projection_matrix:glm.mat4,
        view_matrix:glm.mat4,
        first_axis:Axis=Axis.PositiveX,
        second_axis:Axis=Axis.PositiveY
):
    """
    Compute a roll correction matrix to align the horizon based on the second vanishing lines.
    """

    # Project the second vanishing line the forward plane in 3D world space
    P, Q = second_vanishing_line

    # Unproject pixel coordinates to world space rays
    viewport = glm.vec4(0, 0, width, height)    
    P_ray_origin, P_ray_dir = cast_ray(P, view_matrix, projection_matrix, viewport)
    Q_ray_origin, Q_ray_dir = cast_ray(Q, view_matrix, projection_matrix, viewport)

    # define the plane coordinate system (the plane facing against the camera screen, orineted by the first axis)
    plane_origin = glm.vec3(0, 0, 0)
    plane_normal = _axis_positive_vector(first_axis)
    plane_y_axis = glm.cross(plane_normal, _third_axis_vector(first_axis, second_axis)) # along the line
    plane_x_axis = glm.cross(plane_normal, plane_y_axis)  # perpendicular in the plane

    # Intersect rays with facing plane
    P_on_grid = intersect_ray_with_plane(P_ray_origin, P_ray_dir, plane_origin, plane_normal)
    Q_on_grid = intersect_ray_with_plane(Q_ray_origin, Q_ray_dir, plane_origin, plane_normal)

    v = Q_on_grid - P_on_grid # vector along the line on the plane
    v_proj = v - glm.dot(v, plane_normal) * plane_normal # project vector onto plane

    # --- Compute 360° angle using atan2 ---
    x_on_plane = glm.dot(v_proj, plane_y_axis)
    y_on_plane = glm.dot(v_proj, plane_x_axis)
    angle = math.atan(y_on_plane / x_on_plane)
    
    roll_axis = plane_normal # plane normal

    return glm.rotate(glm.mat4(1.0), angle, roll_axis)

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
    if Fu_Fv_distance < 1e-6:
        raise ValueError(f"Vanishing points are too close together: distance = {Fu_Fv_distance:.2e}")
    
    # Detect if vanishing points are very far away and need special handling
    max_reasonable_distance = 1e4  # Configurable threshold
    Fu_distance = glm.distance(Fu, P)
    Fv_distance = glm.distance(Fv, P)
    
    # For very distant VPs, clamp them to reasonable bounds to prevent numerical issues
    if Fu_distance > max_reasonable_distance or Fv_distance > max_reasonable_distance:
        logger.warning(f"Warning: Very distant vanishing points detected (Fu: {Fu_distance:.1f}, Fv: {Fv_distance:.1f})")
        
        # Clamp to reasonable distance while preserving direction
        if Fu_distance > max_reasonable_distance:
            direction = glm.normalize(Fu - P)
            Fu = P + direction * max_reasonable_distance
            
        if Fv_distance > max_reasonable_distance:
            direction = glm.normalize(Fv - P)
            Fv = P + direction * max_reasonable_distance

        logger.warning(f"  Clamped vanishing points to Fu: {Fu}, Fv: {Fv}")
    
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
    
    # Sanity check the result
    min_focal = 10.0   # Minimum reasonable focal length
    max_focal = 10000.0 # Maximum reasonable focal length
    
    if focal_length < min_focal or focal_length > max_focal:
        logger.warning(f"Warning: Computed focal length {focal_length:.1f} is outside reasonable range [{min_focal}, {max_focal}]")
    
    return focal_length

def _compute_focal_length_from_vanishing_points_simple(
        Fu: glm.vec2, # first vanishing point
        Fv: glm.vec2, # second vanishing point
        P: glm.vec2   # principal point
    )-> float:
    """
    Computes the focal length from two orthogonal vanishing points using the cross-ratio formula.
    
    The formula is derived from the constraint that orthogonal directions in 3D space
    project to vanishing points that satisfy: f² = |Fv_Puv| * |Fu_Puv| - |P_Puv|²
    where Puv is the orthogonal projection of P onto the line FuFv.
    
    Args:
        Fu: First vanishing point in pixel coordinates
        Fv: Second vanishing point in pixel coordinates  
        P: Principal point in pixel coordinates
        
    Returns:
        Focal length in pixels
        
    Raises:
        ValueError: If vanishing points are too close, collinear with principal point,
                   or configuration is otherwise invalid
    """
    # Check for degenerate cases
    Fu_Fv_distance = glm.distance(Fu, Fv)
    if Fu_Fv_distance < 1e-6:
        raise ValueError(f"Vanishing points are too close together: distance = {Fu_Fv_distance:.2e}")
    
    # Compute Puv: orthogonal projection of principal point P onto line segment Fu-Fv
    horizon_vector = Fu - Fv
    horizon_direction = glm.normalize(horizon_vector)
    
    # Vector from Fv to principal point
    principal_to_fv = P - Fv
    
    # Project onto horizon line
    projection_length = glm.dot(horizon_direction, principal_to_fv)
    projection_point = Fv + projection_length * horizon_direction
    
    # Compute distances for focal length formula
    # f² = |Fv_Puv| * |Fu_Puv| - |P_Puv|²
    distance_fv_to_proj = glm.distance(Fv, projection_point)
    distance_fu_to_proj = glm.distance(Fu, projection_point)
    distance_p_to_proj = glm.distance(P, projection_point)
    
    # Apply focal length formula
    focal_length_squared = distance_fv_to_proj * distance_fu_to_proj - distance_p_to_proj * distance_p_to_proj
    
    # Validate result
    if focal_length_squared <= 0:
        # Provide detailed diagnostic information
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
    
    return math.sqrt(focal_length_squared)

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
    forward = _axis_vector(first_axis)
    right = _axis_vector(second_axis)
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
    assert math.fabs(1 - glm.determinant(axis_assignment_matrix)) < 1e-7, "Invalid axis assignment: axes must be orthogonal"
    return axis_assignment_matrix

###########################
# Solver helper functions #
###########################
def focal_length_from_fov(fovy, image_height):
    # fov = math.atan(height / 2 / f) * 2
    # fov/2 = math.atan(height / 2 / f)
    # tan(fov/2) = height / 2 / f
    # f * tan(fov/2) = height / 2
    # f = (height / 2) / tan(fov/2)

    return (image_height / 2) / math.tan(fovy / 2)

def fov_from_focal_length(focal_length_pixel, image_height):
    return math.atan(image_height / 2 / focal_length_pixel) * 2

def _axis_vector(axis: Axis)->glm.vec3:
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
        
def _third_axis_vector(axis1, axis2):
    vec1 = _axis_vector(axis1)
    vec2 = _axis_vector(axis2)
    return glm.normalize(glm.cross(vec1, vec2))

def _vectorAxis(vector: glm.vec3)->Axis:
    if vector.x == 0 and vector.y == 0:
      return Axis.PositiveZ if vector.z > 0 else Axis.NegativeZ
    elif vector.x == 0 and vector.z == 0:
      return Axis.PositiveY if vector.y > 0 else Axis.NegativeY
    elif vector.y == 0 and vector.z == 0:
      return Axis.PositiveX if vector.x > 0 else Axis.NegativeX
    
    raise ValueError('Invalid axis vector')

def flip_coordinate_handness(mat: glm.mat4) -> glm.mat4:
    """swap left-right handed coordinate system"""
    flipZ = glm.scale(glm.vec3(1.0, 1.0, -1.0))
    return flipZ * mat # todo: check order

###########################
# 2D-3D GOMETRY FUNCTIONS #
###########################
def least_squares_intersection_of_lines(line_segments: List[Tuple[glm.vec2, glm.vec2]]) -> glm.vec2:
    """
    Compute the least-squares intersection (vanishing point) of a set of 2D lines
    defined by their endpoints. Uses pure PyGLM math, no numpy.

    Args:
        line_segments: list of ((x1, y1), (x2, y2)) as glm.vec2 pairs.

    Returns:
        glm.vec2: the least-squares intersection point.
    """
    if len(line_segments) < 2:
        raise ValueError("At least two lines are required to compute a vanishing point")

    # Accumulate normal equation components
    S_aa = S_ab = S_bb = S_ac = S_bc = 0.0

    for P, Q in line_segments:
        # Line equation coefficients: a*x + b*y + c = 0
        a = P.y - Q.y
        b = Q.x - P.x
        c = P.x * Q.y - Q.x * P.y

        S_aa += a * a
        S_ab += a * b
        S_bb += b * b
        S_ac += a * c
        S_bc += b * c

    # Solve normal equations:
    # [S_aa S_ab][x] = -[S_ac]
    # [S_ab S_bb][y]   -[S_bc]
    det = S_aa * S_bb - S_ab * S_ab
    if abs(det) < 1e-12:
        raise ValueError(f"Lines are nearly parallel or determinant is zero. linesegments: {line_segments}")

    x = (-S_bb * S_ac + S_ab * S_bc) / det
    y = (-S_aa * S_bc + S_ab * S_ac) / det

    return glm.vec2(x, y)

def cast_ray(
    pos: glm.vec2, 
    view_matrix: glm.mat4, 
    projection_matrix: glm.mat4, 
    viewport: glm.vec4
) -> Tuple[glm.vec3, glm.vec3]:
    """
    Cast a ray from the camera through a pixel in screen space.
    returns the ray origin and target.
    
    Args:
        screen_x: X coordinate in pixel space
        screen_y: Y coordinate in pixel space
        view_matrix: Camera view matrix
        projection_matrix: Camera projection matrix
        viewport: Viewport (x, y, width, height)
    """

    ray_origin = glm.unProject(
        glm.vec3(pos.x, pos.y, 0.0),
        view_matrix, projection_matrix, viewport
    )

    ray_target = glm.unProject(
        glm.vec3(pos.x, pos.y, 1.0),
        view_matrix, projection_matrix, viewport
    )

    ray_direction = glm.normalize(ray_target - ray_origin)

    return ray_origin, ray_direction

def _world_depth_to_ndc_z(distance:float, near:float, far:float, clamp=False) -> float:
    """Convert world depth to NDC z-coordinate using perspective-correct mapping
    world_distance: The distance from the camera in world units
    near: The near clipping plane distance
    far: The far clipping plane distance
    returns: NDC z-coordinate in [0, 1], where 0 is near and 1 is far
    """
    # Clamp the distance between near and far
    if clamp:
        distance = max(near, min(far, distance))

    # Perspective-correct depth calculation
    # This matches how the depth buffer actually works
    ndc_z = (far + near) / (far - near) + (2 * far * near) / ((far - near) * distance)
    ndc_z = (ndc_z + 1) / 2  # Convert from [-1, 1] to [0, 1]
    return ndc_z

def intersect_ray_with_plane(
        ray_origin: glm.vec3, ray_direction: glm.vec3, 
        plane_point: glm.vec3, plane_normal: glm.vec3) -> glm.vec3:
    """
    Intersect a ray with a plane.
    
    Args:
        ray_origin: Point where the ray starts
        ray_direction: Direction vector of the ray (should be normalized)
        plane_point: Any point on the plane
        plane_normal: Normal vector of the plane (should be normalized)
    
    Returns:
        The intersection point, or raises exception if no intersection
    """
    denom = glm.dot(plane_normal, ray_direction)
    
    if abs(denom) < 1e-6:
        raise ValueError("Ray is parallel to the plane")
    
    t = glm.dot(plane_normal, plane_point - ray_origin) / denom
    
    # if t < 0:
    #     raise ValueError("Intersection is behind the ray origin")
    
    return ray_origin + t * ray_direction

def _gram_schmidt_orthogonalization(matrix: glm.mat3) -> glm.mat3:
    """
    Apply Gram-Schmidt orthogonalization to a 3x3 matrix to make it orthogonal.
    This ensures the matrix represents a valid rotation matrix.
    """
    # Extract the three column vectors
    v1 = glm.vec3(matrix[0])  # First column
    v2 = glm.vec3(matrix[1])  # Second column
    v3 = glm.vec3(matrix[2])  # Third column
    
    # Step 1: Normalize the first vector
    u1 = glm.normalize(v1)
    
    # Step 2: Make v2 orthogonal to u1
    u2 = v2 - glm.dot(v2, u1) * u1
    u2 = glm.normalize(u2)
    
    # Step 3: Make v3 orthogonal to both u1 and u2
    u3 = v3 - glm.dot(v3, u1) * u1 - glm.dot(v3, u2) * u2
    u3 = glm.normalize(u3)
    
    # Construct the orthogonal matrix
    result = glm.mat3()
    result[0] = u1  # First column
    result[1] = u2  # Second column
    result[2] = u3  # Third column
    
    return result

#############################
# Post-processing functions #
#############################
def adjust_vanishing_lines(
        old_vp:glm.vec2, 
        new_vp:glm.vec2, 
        vanishing_lines:List[Tuple[glm.vec2, glm.vec2]]
    ) -> List[Tuple[glm.vec2, glm.vec2]]:
    # When vanishing point moves, adjust only the closest endpoint of each vanishing line
    new_vanishing_lines = vanishing_lines.copy()
    for i, (P, Q) in enumerate(vanishing_lines):
        # Find which endpoint is closer to the old vanishing point
        dist_P = glm.length(P - old_vp)
        dist_Q = glm.length(Q - old_vp)
        
        # Choose the closer endpoint and the fixed endpoint
        if dist_P < dist_Q:
            moving_point, fixed_point = P, Q
        else:
            moving_point, fixed_point = Q, P
        
        # Calculate relative position and apply to new vanishing point
        line_to_old_vp = old_vp - fixed_point
        line_to_moving = moving_point - fixed_point
        
        if glm.length(line_to_old_vp) > 1e-6:
            ratio = glm.length(line_to_moving) / glm.length(line_to_old_vp)
            new_line_to_vp = new_vp - fixed_point
            new_moving_point = fixed_point + glm.normalize(new_line_to_vp) * glm.length(new_line_to_vp) * ratio
            
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
    
    # Create rotation matrix
    def rotate_point_around_center(point: glm.vec2, center: glm.vec2, rotation_angle:float) -> glm.vec2:
        # Rotation matrix components
        cos_angle = math.cos(rotation_angle)
        sin_angle = math.sin(rotation_angle)

        # Translate to origin
        translated = point - center
        # Apply rotation
        rotated_x = translated.x * cos_angle - translated.y * sin_angle
        rotated_y = translated.x * sin_angle + translated.y * cos_angle
        # Translate back
        return glm.vec2(rotated_x, rotated_y) + center
    
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
        new_P = rotate_point_around_center(P, principal_point, rotation_angle)
        new_Q = rotate_point_around_center(Q, principal_point, rotation_angle)
        new_vanishing_lines.append((new_P, new_Q))
    
    return new_vanishing_lines

def vanishing_points_from_camera(
        view_matrix: glm.mat3, 
        projection_matrix: glm.mat4, 
        viewport: glm.vec4
    ) -> Tuple[glm.vec2, glm.vec2, glm.vec2]:
    # Project vanishing Points
    MAX_FLOAT32 = (2 - 2**-23) * 2**127
    VPX = glm.project(glm.vec3(MAX_FLOAT32,0,0), view_matrix, projection_matrix, viewport)
    VPY = glm.project(glm.vec3(0,MAX_FLOAT32,0), view_matrix, projection_matrix, viewport)
    VPZ = glm.project(glm.vec3(0,0,MAX_FLOAT32), view_matrix, projection_matrix, viewport)
    return glm.vec2(VPX), glm.vec2( VPY), glm.vec2(VPZ)

def mat3_to_euler_zxy(M: glm.mat3) -> Tuple[float, float, float]:
    """
    # Assumes R is a flat list of 9 elements (col-major)
    """
    r00, r01, r02 = M[0][0], M[0][1], M[0][2]
    r10, r11, r12 = M[1][0], M[1][1], M[1][2]
    r20, r21, r22 = M[2][0], M[2][1], M[2][2]

    # ZXY order extraction
    if abs(r21) < 1.0:
        x = math.asin(r21)
        z = math.atan2(-r01, r11)
        y = math.atan2(-r20, r22)
    else:
        # Gimbal lock
        x = math.copysign(math.pi/2, r21)
        z = math.atan2(r10, r00)
        y = 0.0

    return z, x, y  # Z, X, Y order


##################
# GLM EXTENSIONS #
##################
def extract_euler_XYZ(M: glm.mat4) -> Tuple[float, float, float]:
    T1 = math.atan2(M[2][1], M[2][2])
    C2 = math.sqrt(M[0][0] * M[0][0] + M[1][0] * M[1][0])
    T2 = math.atan2(-M[2][0], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[0][2] - C1 * M[0][1], C1 * M[1][1] - S1 * M[1][2])
    return -T1, -T2, -T3

def extract_euler_YXZ(M: glm.mat4) -> Tuple[float, float, float]:
    T1 = math.atan2(M[2][0], M[2][2])
    C2 = math.sqrt(M[0][1] * M[0][1] + M[1][1] * M[1][1])
    T2 = math.atan2(-M[2][1], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[1][2] - C1 * M[1][0], C1 * M[0][0] - S1 * M[0][2])
    return T1, T2, T3

def extract_euler_XZY(M: glm.mat4) -> Tuple[float, float, float]:
    T1 = math.atan2(M[1][2], M[1][1])
    C2 = math.sqrt(M[0][0] * M[0][0] + M[2][0] * M[2][0])
    T2 = math.atan2(-M[1][0], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[0][1] - C1 * M[0][2], C1 * M[2][2] - S1 * M[2][1])
    return T1, T2, T3

def extract_euler_YZX(M: glm.mat4) -> Tuple[float, float, float]:
    T1 = math.atan2(-M[0][2], M[0][0])
    C2 = math.sqrt(M[1][1] * M[1][1] + M[2][1] * M[2][1])
    T2 = math.atan2(M[0][1], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[1][0] + C1 * M[1][2], S1 * M[2][0] + C1 * M[2][2])
    return T1, T2, T3

def extract_euler_ZYX(M: glm.mat4) -> Tuple[float, float, float]:
    T1 = math.atan2(M[0][1], M[0][0])
    C2 = math.sqrt(M[1][2] * M[1][2] + M[2][2] * M[2][2])
    T2 = math.atan2(-M[0][2], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[2][0] - C1 * M[2][1], C1 * M[1][1] - S1 * M[1][0])
    return T1, T2, T3

def extract_euler_ZXY(M: glm.mat4) -> Tuple[float, float, float]:
    T1 = math.atan2(-M[1][0], M[1][1])
    C2 = math.sqrt(M[0][2] * M[0][2] + M[2][2] * M[2][2])
    T2 = math.atan2(M[1][2], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(C1 * M[2][0] + S1 * M[2][1], C1 * M[0][0] + S1 * M[0][1])
    return T1, T2, T3

def extract_euler(M: glm.mat3, order: EulerOrder) -> Tuple[float, float, float]:
    """
    Convert a glm.mat3 rotation matrix
    to Euler angles (radians) for the specified rotation order.
    Supported orders: "XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"
    return x, y, z angles in radians.
    """
    match order:
        case EulerOrder.XYZ:
            x,y,z = extract_euler_XYZ(M)
            return x,y,z
        case EulerOrder.XZY:
            x,z,y = extract_euler_XZY(M)
            return x,y,z
        case EulerOrder.YXZ:
            y,x,z = extract_euler_YXZ(M)
            return x,y,z
        case EulerOrder.YZX:
            y,z,x = extract_euler_YZX(M)
            return x,y,z
        case EulerOrder.ZXY:
            z,x,y = extract_euler_ZXY(M)
            return x,y,z
        case EulerOrder.ZYX:
            z,y,x = extract_euler_ZYX(M)
            return x,y,z
        case _:
            raise ValueError(f"Unsupported Euler angle order: {order}")

def decompose(M: glm.mat4) -> Tuple[glm.vec3, glm.quat, glm.vec3, glm.vec3, glm.vec4]:
    """glm dedomcpose wrapper.
    returns: scale(vec3), rotation(quat), translation(vec3), skew(vec3), perspective(vec4)
    raises ValueError if decomposition fails.
    """
    scale = glm.vec3()
    quat = glm.quat()  # This will be our quaternion
    translation = glm.vec3()
    skew = glm.vec3()
    perspective = glm.vec4()

    if not glm.decompose(M, scale, quat, translation, skew, perspective):
        raise ValueError("Could not decompose matrix")
    
    return scale, quat, translation, skew, perspective