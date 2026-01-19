from typing import Tuple, List

from pyglm import glm
import math
import warnings

from . constants import EPSILON
from . types import Line2, Ray3, Line3, Rect, Axis


############################
# 2D-3D GEOMETRY FUNCTIONS #
############################

def dot2d(u: glm.vec2, v: glm.vec2) -> float:
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
    viewport: Rect
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
        view_matrix, projection_matrix, tuple(viewport)
)

    ray_target = glm.unProject(
        glm.vec3(P.x, P.y, 1.0),
        view_matrix, projection_matrix, tuple(viewport)
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
    ray_direction = glm.normalize(glm.vec3(ray[1]) - ray[0])
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

def intersect_ray_with_rect(P: glm.vec2, Q: glm.vec2, rect: Rect) -> glm.vec2 | None:
    """
    Intersect an infinite ray starting at P and passing through Q with a rectangle.
    """
    rect_x, rect_y, rect_w, rect_h = rect
    rect_min = glm.vec2(rect_x, rect_y)
    rect_max = glm.vec2(rect_x + rect_w, rect_y + rect_h)

    # Direction vector from P to Q
    direction = Q - P
    
    # Avoid division by zero if P and Q are the same point
    if glm.length2(direction) < 1e-12:
        return None

    # t_near: entry point into the 'slab', t_far: exit point
    t_near = -math.inf
    t_far = math.inf
    EPSILON = 1e-9

    for i in range(2):  # Check X (0) and Y (1) axes
        if abs(direction[i]) < EPSILON:
            # Ray is parallel to this axis. 
            # If P is not between the min/max of this axis, it misses entirely.
            if P[i] < rect_min[i] or P[i] > rect_max[i]:
                return None
        else:
            # Slab intersection distances
            inv_dir = 1.0 / direction[i]
            t1 = (rect_min[i] - P[i]) * inv_dir
            t2 = (rect_max[i] - P[i]) * inv_dir
            
            # Identify which is the entry and which is the exit for this specific axis
            t_entry = min(t1, t2)
            t_exit = max(t1, t2)
            
            # Shrink the overall interval to the intersection of all slabs
            t_near = max(t_near, t_entry)
            t_far = min(t_far, t_exit)

    # 1. Logic check: If t_near > t_far, the ray missed the rectangle.
    # 2. Infinite Ray check: If t_far < 0, the rectangle is behind the ray's origin.
    if t_near > t_far or t_far < 0:
        return None

    # 3. Origin check: If t_near < 0, the ray starts INSIDE the rectangle.
    # We return the first point forward (which is t_near if outside, or P if inside).
    # If you want the EXIT point when starting inside, use max(0, t_near).
    actual_t = max(0, t_near)

    return P + direction * actual_t

#####################
# UTILITY FUNCTIONS #
#####################

def calc_vanishing_points_from_camera(
        view_matrix: glm.mat3, 
        projection_matrix: glm.mat4, 
        viewport: Rect,
        first_axis: Axis = Axis.PositiveX,
        second_axis: Axis = Axis.PositiveY
    ) -> Tuple[glm.vec2, glm.vec2, glm.vec2]:
    """Calculate vanishing points for the camera, optionally ordered by axis assignment.
    
    Args:
        view_matrix: Camera view matrix (rotation only, mat3)
        projection_matrix: Camera projection matrix
        viewport: Viewport rectangle
        first_axis: Optional Axis enum for first vanishing point
        second_axis: Optional Axis enum for second vanishing point  
        third_axis: Optional Axis enum for third vanishing point
        
    Returns:
        Tuple of three vanishing points. If axes are specified, returns them in order
        (vp_for_first_axis, vp_for_second_axis, vp_for_third_axis).
        Otherwise returns (vpX, vpY, vpZ).
    """
    vpX, vpY, vpZ = _impl_calc_vanishing_points_from_camera(view_matrix, projection_matrix, viewport)
    
    # If no axis assignment provided, return in default X, Y, Z order
    if first_axis is None:
        return vpX, vpY, vpZ
    
    # Map axes to their corresponding vanishing points
    from . import types
    def get_vp_for_axis(axis: 'types.Axis') -> glm.vec2:
        """Map axis enum to corresponding vanishing point."""
        axis_type = abs(axis.value)  # Get base axis (1=X, 2=Y, 3=Z)
        if axis_type == 1:  # X axis
            return vpX
        elif axis_type == 2:  # Y axis
            return vpY
        else:  # Z axis
            return vpZ
    
    vp1 = get_vp_for_axis(first_axis)
    vp2 = get_vp_for_axis(second_axis) if second_axis else vpY
    
    # Calculate third axis from first and second
    from . import helpers
    third_axis = helpers.third_axis(first_axis, second_axis)
    vp3 = get_vp_for_axis(third_axis)
    
    return vp1, vp2, vp3

def _impl_calc_vanishing_points_from_camera(
        view_matrix: glm.mat3, 
        projection_matrix: glm.mat4, 
        viewport: Rect
    ) -> Tuple[glm.vec2, glm.vec2, glm.vec2]:
    """
    Calculate the projected vanishing points from the camera matrices.
    
    Reference implementation using large finite values (kept for comparison):
        MAX_FLOAT32 = (2 - 2**-23) * 2**127
        VPX = glm.project(glm.vec3(MAX_FLOAT32,0,0), glm.mat4(view_matrix), projection_matrix, glm.vec4(*viewport))
        VPY = glm.project(glm.vec3(0,MAX_FLOAT32,0), glm.mat4(view_matrix), projection_matrix, glm.vec4(*viewport))
        VPZ = glm.project(glm.vec3(0,0,MAX_FLOAT32), glm.mat4(view_matrix), projection_matrix, glm.vec4(*viewport))
    """

    if not isinstance(view_matrix, glm.mat3):
        raise TypeError("view_matrix must be a glm.mat3")
    if not isinstance(projection_matrix, glm.mat4):
        raise TypeError("projection_matrix must be a glm.mat4")
    
    # Vanishing points are where points at infinity project to.
    # In homogeneous coordinates, a point at infinity along direction d is (dx, dy, dz, 0)
    # We use the rotation part only (view_matrix as mat3), since translation doesn't affect directions
    
    def project_direction_to_vanishing_point(direction: glm.vec3) -> glm.vec2:
        """Project a world-space direction vector to its vanishing point in viewport space."""
        # Transform direction to view space (rotation only, w=0 for point at infinity)
        view_dir = view_matrix * direction
        
        # Apply projection matrix to the direction (as homogeneous point at infinity)
        # For a point at infinity: P * vec4(view_dir, 0)
        clip = projection_matrix * glm.vec4(view_dir, 0.0)
        
        # Perspective divide
        # If clip.w is 0, the point is at infinity in clip space (parallel to view direction)
        # In practice, clip.w should be non-zero for vanishing points
        if abs(clip.w) < EPSILON:
            # Direction is parallel to the image plane - vanishing point at infinity
            # Return a point far outside the viewport to indicate this
            return glm.vec2(float('inf'), float('inf'))
        
        # NDC coordinates
        ndc = glm.vec2(clip.x / clip.w, clip.y / clip.w)
        
        # Transform from NDC [-1,1] to viewport coordinates
        vp_x = viewport.x + viewport.width * (ndc.x + 1.0) / 2.0
        vp_y = viewport.y + viewport.height * (ndc.y + 1.0) / 2.0
        
        return glm.vec2(vp_x, vp_y)
    
    # Calculate vanishing points for each world axis
    VPX = project_direction_to_vanishing_point(glm.vec3(1, 0, 0))
    VPY = project_direction_to_vanishing_point(glm.vec3(0, 1, 0))
    VPZ = project_direction_to_vanishing_point(glm.vec3(0, 0, 1))
    
    return VPX, VPY, VPZ

def flip_coordinate_handness(mat: glm.mat4) -> glm.mat4:
    """swap left-right handed coordinate system"""
    flipZ = glm.scale(glm.vec3(1.0, 1.0, -1.0))  # type: ignore[attr-defined]
    return flipZ * mat # todo: check order

def adjust_vanishing_lines_to_camera_orientation(
        first_vanishing_lines: List[Line2],
        second_vanishing_lines: List[Line2],
        third_vanishing_lines: List[Line2],
        first_axis: Axis,
        second_axis: Axis,
        view_matrix: glm.mat3,
        projection_matrix: glm.mat4
    ) -> List[List[Line2]]:
        # Map vanishing points by axis assignment

        
        vp1, vp2, vp3 = calc_vanishing_points_from_camera(
            glm.mat3(view_matrix), 
            projection_matrix, 
            Rect(-1,-1,2,2),
            first_axis=first_axis,
            second_axis=second_axis
        )

        new_line_sets: List[List[Line2]] = []
        for lines, vp in [(first_vanishing_lines, vp1), (second_vanishing_lines, vp2), (third_vanishing_lines, vp3)]:
            new_lines = []
            for line in lines:
                start = glm.vec2(*line[0])
                end = glm.vec2(*line[1])
                center = (start + end) * 0.5
                dir = glm.normalize(vp - center)
                
                # Preserve direction: check if point is in same direction as VP
                start_vec = start - center
                end_vec = end - center
                start_dist = glm.length(start_vec) * glm.sign(glm.dot(start_vec, dir))
                end_dist = glm.length(end_vec) * glm.sign(glm.dot(end_vec, dir))

                new_start = center + dir * start_dist
                new_end =   center + dir * end_dist
                new_line = new_start, new_end
                new_lines.append(new_line)
            new_line_sets.append(new_lines)

        return new_line_sets


##################
# GLM EXTENSIONS #
##################
def mat3_to_euler_zxy(M: glm.mat3) -> glm.vec3:
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

    return glm.vec3(z, x, y)  # Z, X, Y order

def extract_euler_XYZ(M: glm.mat4|glm.mat3) -> glm.vec3:
    T1 = math.atan2(M[2][1], M[2][2])
    C2 = math.sqrt(M[0][0] * M[0][0] + M[1][0] * M[1][0])
    T2 = math.atan2(-M[2][0], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[0][2] - C1 * M[0][1], C1 * M[1][1] - S1 * M[1][2])
    return glm.vec3(-T1, -T2, -T3)

def extract_euler_YXZ(M: glm.mat4|glm.mat3) -> glm.vec3:
    T1 = math.atan2(M[2][0], M[2][2])
    C2 = math.sqrt(M[0][1] * M[0][1] + M[1][1] * M[1][1])
    T2 = math.atan2(-M[2][1], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[1][2] - C1 * M[1][0], C1 * M[0][0] - S1 * M[0][2])
    return glm.vec3(T1, T2, T3)

def extract_euler_XZY(M: glm.mat4|glm.mat3) -> glm.vec3:
    T1 = math.atan2(M[1][2], M[1][1])
    C2 = math.sqrt(M[0][0] * M[0][0] + M[2][0] * M[2][0])
    T2 = math.atan2(-M[1][0], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[0][1] - C1 * M[0][2], C1 * M[2][2] - S1 * M[2][1])
    return glm.vec3(T1, T2, T3)

def extract_euler_YZX(M: glm.mat4|glm.mat3) -> glm.vec3:
    T1 = math.atan2(-M[0][2], M[0][0])
    C2 = math.sqrt(M[1][1] * M[1][1] + M[2][1] * M[2][1])
    T2 = math.atan2(M[0][1], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[1][0] + C1 * M[1][2], S1 * M[2][0] + C1 * M[2][2])
    return glm.vec3(T1, T2, T3)

def extract_euler_ZYX(M: glm.mat4|glm.mat3) -> glm.vec3:
    T1 = math.atan2(M[0][1], M[0][0])
    C2 = math.sqrt(M[1][2] * M[1][2] + M[2][2] * M[2][2])
    T2 = math.atan2(-M[0][2], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(S1 * M[2][0] - C1 * M[2][1], C1 * M[1][1] - S1 * M[1][0])
    return glm.vec3(T1, T2, T3)

def extract_euler_ZXY(M: glm.mat4|glm.mat3) -> glm.vec3:
    T1 = math.atan2(-M[1][0], M[1][1])
    C2 = math.sqrt(M[0][2] * M[0][2] + M[2][2] * M[2][2])
    T2 = math.atan2(M[1][2], C2)
    S1 = math.sin(T1)
    C1 = math.cos(T1)
    T3 = math.atan2(C1 * M[2][0] + S1 * M[2][1], C1 * M[0][0] + S1 * M[0][1])
    return glm.vec3(T1, T2, T3)

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



def decompose_perspective(P: glm.mat4)->Tuple[float, float, float, float]:
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

def decompose_perspective_tiltshift(P: glm.mat4)->Tuple[float, float, float, float, float, float]:
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

def decompose_frustum(P: glm.mat4)->Tuple[float, float, float, float, float, float]:
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

def decompose_intrinsics(viewport:Rect, projection:glm.mat4)->Tuple[glm.vec2, float]:
    """
    Decomposes the projection matrix to retreive principal point, focal length and shift.
    
    :param viewport:   Description
    :param projection: Description

    :return: P, f, shift
    :rtype: Tuple[Any, float, Any]
    
    """ 
    left, right, top, bottom, near, far = decompose_frustum(projection)
    Ppx = ((right + left) / (right - left)) * near
    Ppy = ((top + bottom) / (top - bottom)) * near
    P = glm.vec2(
        viewport.center[0] - (Ppx / near) * (viewport.height / 2),
        viewport.center[1] + (Ppy / near) * (viewport.height / 2)
    )
    f = near/(bottom-top) * viewport.height
    return P, f

# def decompose_intrinsics(viewport: Rect, projection: glm.mat4):
#     # m00 = 2n / (r-l)
#     # m11 = 2n / (t-b)
#     # m20 = (r+l) / (r-l)  <- This is the X-shift (asymmetry)
#     # m21 = (t+b) / (t-b)  <- This is the Y-shift (asymmetry)
    
#     # Focal length in pixels (standardized to height)
#     f = (projection[1][1] * viewport.height) / 2.0
    
#     # Principal Point in pixels
#     # We map the NDC shift (m20, m21) back to pixel offsets
#     px = viewport.center[0] + (projection[2][0] * (viewport.width / 2.0))
#     # Note: Subtract for Y if viewport is Top-Left, Add if Bottom-Left
#     py = viewport.center[1] - (projection[2][1] * (viewport.height / 2.0))
    
#     return glm.vec2(px, py), f

# def compose_intrinsics(viewport: Rect, f: float, P: glm.vec2, near: float, far: float):
#     P = glm.vec2(*P)
#     # Calculate NDC shift
#     shift_x = (P.x - viewport.center[0]) / (viewport.width / 2.0)
#     shift_y = (viewport.center[1] - P.y) / (viewport.height / 2.0)
    
#     # Standard symmetric bounds based on focal length
#     aspect = viewport.width / viewport.height
#     h_at_near = near / (f / viewport.height) 
#     top = h_at_near / 2.0
#     right = top * aspect
    
#     # Apply asymmetry (The shift)
#     # This creates the off-axis projection matrix
#     l = -right + (shift_x * right)
#     r =  right + (shift_x * right)
#     b = -top   + (shift_y * top)
#     t =  top   + (shift_y * top)
    
#     return glm.frustum(l, r, b, t, near, far)

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


