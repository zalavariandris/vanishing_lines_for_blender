from typing import Tuple, List

from pyglm import glm
import math
import warnings

from . constants import EPSILON
from . types import Point2, Line2, Ray3, Line3, Rect


############################
# 2D-3D GEOMETRY FUNCTIONS #
############################

def dot2d(u: Point2, v: Point2) -> float:
    Ux, Uy = u
    Vx, Vy = v
    return Ux * Vx + Uy * Vy

def triangle_orthocenter(A: glm.vec2, B: glm.vec2, C: glm.vec2)-> glm.vec2:
    a = A.x
    b = A.y
    c = B.x
    d = B.y
    e = C.x
    f = C.y

    N = b * c + d * e + f * a - c * f - b * e - a * d
    x = ((d - f) * b * b + (f - b) * d * d + (b - d) * f * f + 
        a * b * (c - e) + c * d * (e - a) + e * f * (a - c)) / N
    y = ((e - c) * a * a + (a - e) * c * c + (c - a) * e * e + 
        a * b * (f - d) + c * d * (b - f) + e * f * (d - b)) / N

    return glm.vec2(x, y)

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

def focal_length_from_fov(fovy, size)->float:
    return (size / 2) / math.tan(fovy / 2)

def fov_from_focal_length(f, size)->float:
    return math.atan(size / 2 / f) * 2

def cast_ray(
    P: glm.vec2, 
    view_matrix: glm.mat4, 
    projection_matrix: glm.mat4, 
    viewport: glm.vec4 | Tuple[float, float, float, float]
) -> Ray3:
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
        glm.vec3(P.x, P.y, 0.0),
        view_matrix, projection_matrix, viewport
)

    ray_target = glm.unProject(
        glm.vec3(P.x, P.y, 1.0),
        view_matrix, projection_matrix, viewport
    )

    return ray_origin, ray_target

def closest_point_between_lines(AB: Line3, CD: Line3) -> glm.vec3:
    A = glm.vec3(AB[0])
    B = glm.vec3(AB[1])
    C = glm.vec3(CD[0])
    D = glm.vec3(CD[1])

    d1 = B - A
    d2 = D - C
    r  = C - A

    # The common normal vector
    n = glm.cross(d1, d2)
    denom = glm.dot(n, n)

    # If lines are parallel, the cross product is zero
    if denom < 1e-8:
        # Project r onto d1 to find the closest point to C on line AB
        t_parallel = glm.dot(r, d1) / glm.dot(d1, d1)
        return A + t_parallel * d1

    # Using the vector triple product identity to solve for t
    # t = dot(cross(r, d2), n) / dot(n, n)
    n2 = glm.cross(r, d2)
    t = glm.dot(n2, n) / denom

    return A + t * d1

def _world_depth_to_ndc_z(distance:float, near:float, far:float, clamp=False) -> float:
    """Convert world depth to NDC z-coordinate using perspective-correct mapping
    distance: The distance from the camera in world units
    near: The near clipping plane distance
    far: The far clipping plane distance
    clamp: Whether to clamp the distance between near and far, default is False
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

def intersect_ray_with_plane(ray: Ray3, plane_point: glm.vec3, plane_normal: glm.vec3) -> glm.vec3:
    """
    Intersect a ray with a plane.
    
    Args:
        ray_origin: Point where the ray starts
        ray_target: Direction vector of the ray (should be normalized)
        plane_point: Any point on the plane
        plane_normal: Normal vector of the plane (should be normalized)
    
    Returns:
        The intersection point, or raises exception if no intersection
    """
    ray_direction = glm.normalize(ray[1] - ray[0])
    denom = glm.dot(plane_normal, ray_direction)
    
    if abs(denom) < EPSILON:
        raise ValueError("Ray is parallel to the plane")
    
    t = glm.dot(plane_normal, plane_point - ray[0]) / denom
    
    # if t < 0:
    #     raise ValueError("Intersection is behind the ray origin")
    
    return ray[0] + ray_direction * t

def validate_orthogonality(mat: glm.mat3) -> bool:
    """ Validates if the given matrix is orthogonal (i.e., its transpose equals its inverse)."""
    identity = glm.mat3(1.0)
    should_be_identity = mat * glm.transpose(mat)
    return glm.all(glm.equal(should_be_identity, identity, glm.vec3(EPSILON)))

def apply_gram_schmidt_orthogonalization(matrix: glm.mat3) -> glm.mat3:
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

#####################
# UTILITY FUNCTIONS #
#####################

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

def flip_coordinate_handness(mat: glm.mat4) -> glm.mat4:
    """swap left-right handed coordinate system"""
    flipZ = glm.scale(glm.vec3(1.0, 1.0, -1.0))  # type: ignore[attr-defined]
    return flipZ * mat # todo: check order


##################
# GLM EXTENSIONS #
##################
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

def extract_euler_XYZ(M: glm.mat4|glm.mat3) -> Tuple[float, float, float]:
    T1 = math.atan2(M[2][1], M[2][2])
    C2 = math.sqrt(M[0][0] * M[0][0] + M[1][0] * M[1][0])
    T2 = math.atan2(-M[2][0], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[0][2] - C1 * M[0][1], C1 * M[1][1] - S1 * M[1][2])
    return -T1, -T2, -T3

def extract_euler_YXZ(M: glm.mat4|glm.mat3) -> Tuple[float, float, float]:
    T1 = math.atan2(M[2][0], M[2][2])
    C2 = math.sqrt(M[0][1] * M[0][1] + M[1][1] * M[1][1])
    T2 = math.atan2(-M[2][1], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[1][2] - C1 * M[1][0], C1 * M[0][0] - S1 * M[0][2])
    return T1, T2, T3

def extract_euler_XZY(M: glm.mat4|glm.mat3) -> Tuple[float, float, float]:
    T1 = math.atan2(M[1][2], M[1][1])
    C2 = math.sqrt(M[0][0] * M[0][0] + M[2][0] * M[2][0])
    T2 = math.atan2(-M[1][0], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[0][1] - C1 * M[0][2], C1 * M[2][2] - S1 * M[2][1])
    return T1, T2, T3

def extract_euler_YZX(M: glm.mat4|glm.mat3) -> Tuple[float, float, float]:
    T1 = math.atan2(-M[0][2], M[0][0])
    C2 = math.sqrt(M[1][1] * M[1][1] + M[2][1] * M[2][1])
    T2 = math.atan2(M[0][1], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[1][0] + C1 * M[1][2], S1 * M[2][0] + C1 * M[2][2])
    return T1, T2, T3

def extract_euler_ZYX(M: glm.mat4|glm.mat3) -> Tuple[float, float, float]:
    T1 = math.atan2(M[0][1], M[0][0])
    C2 = math.sqrt(M[1][2] * M[1][2] + M[2][2] * M[2][2])
    T2 = math.atan2(-M[0][2], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[2][0] - C1 * M[2][1], C1 * M[1][1] - S1 * M[1][0])
    return T1, T2, T3

def extract_euler_ZXY(M: glm.mat4|glm.mat3) -> Tuple[float, float, float]:
    T1 = math.atan2(-M[1][0], M[1][1])
    C2 = math.sqrt(M[0][2] * M[0][2] + M[2][2] * M[2][2])
    T2 = math.atan2(M[1][2], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(C1 * M[2][0] + S1 * M[2][1], C1 * M[0][0] + S1 * M[0][1])
    return T1, T2, T3

def decompose(M: glm.mat4) -> Tuple[glm.vec3, glm.quat, glm.vec3, glm.vec3, glm.vec4]:
    """glm decompose wrapper.
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

def perspective_tiltshift(fovy:float, aspect:float, near:float, far:float, shift_x:float, shift_y:float) -> glm.mat4:
    """ Create a perspective projection matrix with lens shift.
    glm.persective with lens shift support.
    params:
        fovy: field of view in y direction (radians)
        aspect: aspect ratio (width/height)
        near: near clipping plane
        far: far clipping plane
        shift_x: horizontal lens shift (-1..1, where 0 is center)
        shift_y: vertical lens shift (-1..1, where 0 is center)
    """
    # Compute top/bottom/left/right in view space
    top = near * glm.tan(fovy / 2)
    bottom = -top
    right = top * aspect
    left = -right

    # Apply shifts
    width = right - left
    height = top - bottom

    left   += shift_x * width / 2
    right  += shift_x * width / 2
    bottom += shift_y * height / 2
    top    += shift_y * height / 2

    # Create the projection matrix with lens shift
    return glm.frustum(left, right, bottom, top, near, far)

def decompose_frustum(P: glm.mat4):
    # near / far
    near = P[3][2] / (P[2][2] - 1.0)
    far  = P[3][2] / (P[2][2] + 1.0)

    # left / right
    left  =  near * (P[2][0] - 1.0) / P[0][0]
    right =  near * (P[2][0] + 1.0) / P[0][0]

    # bottom / top
    bottom = near * (P[2][1] - 1.0) / P[1][1]
    top    = near * (P[2][1] + 1.0) / P[1][1]

    return left, right, bottom, top, near, far

def decompose_perspective(P: glm.mat4):
    """
    Decompose a perspective projection matrix.
    Works for both symmetric and tilt-shift (off-center) variants.

    Returns:
        fovy (degrees)
        aspect
        near
        far
        shift_x  # principal point shift in X (0 for symmetric)
        shift_y  # principal point shift in Y (0 for symmetric)
    """

    # --- tilt-shift detection and extraction ---
    # P[2][0] = (r + l) / (r - l)
    # P[2][1] = (t + b) / (t - b)
    shift_x = P[2][0]
    shift_y = P[2][1]

    eps = 1e-6
    if abs(P[2][0]) > eps or abs(P[2][1]) > eps:
        warnings.warn(
            "Perspective matrix is not symmetric (tilt-shift / off-center projection detected). "
            "fovy and aspect will not fully describe this projection.",
            RuntimeWarning
        )

    # --- near / far ---
    near = P[3][2] / (P[2][2] - 1.0)
    far  = P[3][2] / (P[2][2] + 1.0)

    # --- fovy ---
    fovy_rad = 2.0 * math.atan(1.0 / P[1][1])
    fovy = math.degrees(fovy_rad)

    # --- aspect ---
    aspect = P[1][1] / P[0][0]



    return fovy, aspect, near, far

def decompose_perspective_tiltshift(P: glm.mat4):
    """
    Decompose a perspective projection matrix.
    Works for both symmetric and tilt-shift (off-center) variants.

    Returns:
        fovy (degrees)
        aspect
        near
        far
        shift_x  # principal point shift in X (0 for symmetric)
        shift_y  # principal point shift in Y (0 for symmetric)
    """

    # --- near / far ---
    near = P[3][2] / (P[2][2] - 1.0)
    far  = P[3][2] / (P[2][2] + 1.0)

    # --- fovy ---
    fovy_rad = 2.0 * math.atan(1.0 / P[1][1])
    fovy = math.degrees(fovy_rad)

    # --- aspect ---
    aspect = P[1][1] / P[0][0]

    # --- tilt-shift detection and extraction ---
    # P[2][0] = (r + l) / (r - l)
    # P[2][1] = (t + b) / (t - b)
    shift_x = P[2][0]
    shift_y = P[2][1]

    return fovy, aspect, near, far, shift_x, shift_y

def decompose_intrinsics(viewport:Rect, projection:glm.mat4)->Tuple[glm.vec2, float]:
    """
    Decomposes the projection matrix to retreive principal point, focal length and shift.
    
    :param viewport:   Description
    :param projection: Description

    :return: P, f, shift
    :rtype: Tuple[Any, float, Any]
    
    """ 
    left, right, top, bottom, near, far = decompose_frustum(projection)
    Ppx = ((right + left) / (top - bottom)) * near
    Ppy = ((top + bottom) / (top - bottom)) * near
    P = glm.vec2(
        viewport.center[0] - (Ppx / near) * (viewport.height / 2),
        viewport.center[1] + (Ppy / near) * (viewport.height / 2)
    )
    f = near/(bottom-top) * viewport.height
    return P, f

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

def compose_intrinsics(viewport:Rect, f:float, P:glm.vec2, near:float, far:float)->glm.mat4:
    """ Composes the projection matrix from intrinsic parameters."""
    # compute projection
    shift = -(P - glm.vec2(*viewport.center)) / (glm.vec2(*viewport.size) / 2.0)  # Negated to match convention
    fovy = fov_from_focal_length(f, viewport.height)
    aspect = viewport.width/viewport.height

    # return glm.perspective(fovy, aspect, DEFAULT_NEAR_PLANE, DEFAULT_FAR_PLANE)
    # Compute top/bottom/left/right in view space
    top = near * glm.tan(fovy / 2)
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
    return glm.frustum(left, right, bottom, top, near, far)


