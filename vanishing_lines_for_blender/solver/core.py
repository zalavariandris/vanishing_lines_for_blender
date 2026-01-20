# standard library
from typing import List, Tuple, Literal
import warnings

# third party library
from pyglm import glm

from dataclasses import dataclass

# local imports
from .constants import (
    EPSILON, 
    DEFAULT_NEAR_PLANE, 
    DEFAULT_FAR_PLANE, 
    MAX_VANISHING_POINT_DISTANCE
)

from . import utils
from . types import (
    Line2, 
    Rect, 
    SolverMode, 
    Axis, 
    ReferenceAxis
)

from . exceptions import (
    VanishingLinesError,
    AxisAssignmentError
)

from . import helpers


#########################
# MAIN SOLVER FUNCTIONS #
#########################

def solve(
        mode:SolverMode, 
        viewport: Rect,
        first_vanishing_lines:  List[Line2],
        second_vanishing_lines: List[Line2],
        third_vanishing_lines:  List[Line2],

        f:float, # focal length (in height units)
        P:glm.vec2|None,
        anchor_screen:glm.vec2,
        anchor_world:glm.vec3,

        reference_axis:ReferenceAxis|None,
        reference_distance_segment:Tuple[float, float], # 2D distance from origin to camera
        reference_world_size:float,

        first_axis:Axis,
        second_axis:Axis,
        handedness:Literal['right-handed', 'left-handed']="right-handed" 
    )->Tuple[glm.mat4, glm.mat4]:

    print(f"Solve")
    print(f" Mode: {mode}")
    print(f" Focal Length: {f}")
    print(f" P: {P}")
    print(f" A: {anchor_screen}")
    print(f" Reference Axis: {reference_axis}")
    print(f" reference_world_size: {reference_world_size}")
    

    match mode:
        case SolverMode.OneVP:
            vp1 = compute_vanishing_point(first_vanishing_lines)
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
            vp1 = compute_vanishing_point(first_vanishing_lines)
            vp2 = compute_vanishing_point(second_vanishing_lines)
            vp3 = None
            projection, view = orientation_from_two_vanishing_points(
                viewport,
                vp1=vp1,
                vp2=vp2,
                P=P
            )

        case SolverMode.ThreeVP:
            vp1 = compute_vanishing_point(first_vanishing_lines)
            vp2 = compute_vanishing_point(second_vanishing_lines)
            vp3 = compute_vanishing_point(third_vanishing_lines)

            projection, view = orientation_from_three_vanishing_points(
                viewport,
                vp1=vp1,
                vp2=vp2,
                vp3=vp3
            )

    # validate if matrix is a purely rotational matrix
    if utils.validate_orthogonality(glm.mat3(view)) is False:
        view = glm.mat4(utils.apply_gram_schmidt_orthogonalization(glm.mat3(view))) # note this will remove scaling and translation
        warnings.warn('Warning: Invalid vanishing point configuration.\n'+"View orientation matrix was not orthogonal, applied Gram-Schmidt orthogonalization")

    

    view = adjust_axis_assignment(
        first_axis,
        second_axis,
        view,
        handedness
    )

    view = adjust_position_to_anchor(
        viewport, 
        projection, 
        anchor_screen, 
        anchor_world,
        view,
        distance=reference_world_size
    )
    
    # if reference_axis is not None:
    #     view = adjust_scale_to_reference_distance(
    #         viewport, 
    #         projection, 
    #         anchor_world,
    #         reference_world_size, 
    #         reference_axis, 
    #         reference_distance_segment, 
    #         view
    #     )

    return projection, view


@dataclass
class UnsolveResults:
    vp1:glm.vec2
    vp2:glm.vec2
    vp3:glm.vec2
    anchor: glm.vec2
    anchor_distance: float

def unsolve(
        viewport:Rect, 
        projection:glm.mat4, 
        view:glm.mat4, 
        anchor_world:glm.vec3,
        first_axis:Axis, 
        second_axis:Axis, 
        handedness:Literal['right-handed', 'left-handed']="right-handed")->UnsolveResults:
    vp1, vp2, vp3 = utils.calc_vanishing_points_from_camera(
        glm.mat3(view), 
        projection, 
        viewport, 
        first_axis=first_axis, 
        second_axis=second_axis
    )
    
    anchor_screen = glm.project(anchor_world, view, projection, tuple(viewport)).xy
    
    anchor_camera_space = view * glm.vec4(anchor_world, 1.0)
    is_behind_camera = anchor_camera_space.z > 0
    anchor_distance = glm.length(glm.vec3(anchor_camera_space))
    if is_behind_camera:
        # flip anchor around the rectangle center if distance is negative
        rect_center = glm.vec2(viewport.x + viewport.width / 2, viewport.y + viewport.height / 2)
        anchor_screen = rect_center * 2.0 - anchor_screen
        anchor_distance = -anchor_distance

    return UnsolveResults(
        vp1=vp1,
        vp2=vp2,
        vp3=vp3,
        anchor=anchor_screen,
        anchor_distance=anchor_distance
    )

#####################
# SOLVER COMPONENTS #
#####################

def compute_vanishing_point(lines: List[Line2], EPSILON: float = 1e-6) -> glm.vec2:
    """
    Compute the least-squares intersection of 2D lines.
    
    Returns:
        glm.vec2: (The intersection point, The total squared error)
    """
    if len(lines) < 2:
        raise VanishingLinesError("At least two lines are required.")

    # 1. Accumulate normal equation components
    S_aa = S_ab = S_bb = S_ac = S_bc = S_cc = 0.0

    for (px, py), (qx, qy) in lines:
        # Check for degenerate lines (zero length)
        dx, dy = qx - px, qy - py
        length_sq = dx*dx + dy*dy
        if length_sq < EPSILON:
            raise VanishingLinesError("Line of zero length.") 

        # Coefficients for ax + by + c = 0
        a = py - qy
        b = qx - px
        c = px * qy - qx * py

        # # Optionally normalize coefficients so the error is actual Euclidean distance
        # norm = 1.0 / glm.sqrt(a*a + b*b)
        # a *= norm
        # b *= norm
        # c *= norm

        S_aa += a * a
        S_ab += a * b
        S_bb += b * b
        S_ac += a * c
        S_bc += b * c
        S_cc += c * c

    # 2. Analyze the Determinant
    det = S_aa * S_bb - S_ab * S_ab
    
    if abs(det) < EPSILON**2:
        p1_x, p1_y = lines[0][0]
        residual = abs(S_aa * p1_x + S_ab * p1_y + S_ac)
        
        if residual < EPSILON**2:
            raise VanishingLinesError("All Lines are collinear.")
        else:
            raise VanishingLinesError("All lines are parallel.")

    # 3. Solve the system using Cramer's Rule
    # [S_aa S_ab][x] = [-S_ac]
    # [S_ab S_bb][y] = [-S_bc]
    x = ((-S_ac) * S_bb - S_ab * (-S_bc)) / det
    y = (S_aa * (-S_bc) - (-S_ac) * S_ab) / det
    
    vp = glm.vec2(x, y)

    # # Optionally Compute Total Squared Error and raise an Exception
    # #                    (Residual Sum of Squares)
    # # This is the expansion of sum((a*x + b*y + c)^2)
    # total_error = (x*x * S_aa + 
    #                y*y * S_bb + 
    #                2*x*y * S_ab + 
    #                2*x * S_ac + 
    #                2*y * S_bc + 
    #                S_cc)

    return glm.vec2(vp.x, vp.y)

def orientation_from_one_vanishing_point(
        viewport:Rect, 
        vp1:glm.vec2, 
        second_line:Line2, 
        f:float, 
        P:glm.vec2
    )->Tuple[glm.mat4, glm.mat4]:
    # compute projection
    projection = utils.compose_intrinsics(viewport, f, P, DEFAULT_NEAR_PLANE, DEFAULT_FAR_PLANE)

    # compute orientation
    view:glm.mat4x4 = glm.mat4(_impl_compute_orientation_from_single_vanishing_point(
        Fu=vp1,
        P=P,
        f=f,
        horizon_direction=glm.vec2(1,0)
    ))

    # validate if matrix is a purely rotational matrix
    if utils.validate_orthogonality(glm.mat3(view)) is False:
        raise VanishingLinesError("Invalid vanishing point configuration: computed view orientation matrix is not orthogonal.")
        view = glm.mat4(utils.apply_gram_schmidt_orthogonalization(glm.mat3(view))) # note this will remove scaling and translation
        # warnings.warn('Warning: Invalid vanishing point configuration.\n'+"View orientation matrix was not orthogonal, applied Gram-Schmidt orthogonalization")
    

    # Adjust Camera Roll to match second vanishing line
    view:glm.mat4 = view * helpers.compute_roll_matrix(
        second_line, # Roll the camera based on the horizon line projected to 3D
        view,
        projection,
        viewport
    )  # type: ignore[assignment] # PyGLM type stubs incorrectly infer mat4x2

    return projection, view

def orientation_from_two_vanishing_points(
        viewport:Rect, 
        vp1:glm.vec2, 
        vp2:glm.vec2, 
        P:glm.vec2
    )->Tuple[glm.mat4, glm.mat4]:
    """"""
    vp1 = glm.vec2(*vp1)
    vp2 = glm.vec2(*vp2)

    f = helpers.compute_focal_length_from_vanishing_points(Fu=vp1,Fv=vp2,P=P)

    # compute projection
    projection = utils.compose_intrinsics(viewport, f, P, DEFAULT_NEAR_PLANE, DEFAULT_FAR_PLANE)

    # compute orientation
    view:glm.mat4 = glm.mat4(_impl_compute_orientation_from_two_vanishing_points(
        Fu=vp1,
        Fv=vp2,
        P=P,
        f=f
    ))
        
    # validate if matrix is a purely rotational matrix
    if utils.validate_orthogonality(glm.mat3(view)) is False:
        raise VanishingLinesError("Invalid vanishing point configuration: computed view orientation matrix is not orthogonal.")
        view = glm.mat4(utils.apply_gram_schmidt_orthogonalization(glm.mat3(view))) # note this will remove scaling and translation
        # warnings.warn('Warning: Invalid vanishing point configuration.\n'+"View orientation matrix was not orthogonal, applied Gram-Schmidt orthogonalization")
    

    return projection, view

def orientation_from_three_vanishing_points(
        viewport:Rect, 
        vp1:glm.vec2, 
        vp2:glm.vec2, 
        vp3:glm.vec2
    )->Tuple[glm.mat4, glm.mat4]:
    """"""

    vp1 = glm.vec2(*vp1)
    vp2 = glm.vec2(*vp2)
    vp3 = glm.vec2(*vp3)

    P = utils.triangle_orthocenter(vp1, vp2, vp3)
    f = helpers.compute_focal_length_from_vanishing_points(Fu=vp1,Fv=vp2,P=P)

    # compute projection
    projection = utils.compose_intrinsics(viewport, f, P, DEFAULT_NEAR_PLANE, DEFAULT_FAR_PLANE)

    # compute orientation
    view:glm.mat4 = glm.mat4(_impl_compute_orientation_from_two_vanishing_points(
        Fu=vp1,
        Fv=vp2,
        P=P,
        f=f
    ))

        
    # validate if matrix is a purely rotational matrix
    if utils.validate_orthogonality(glm.mat3(view)) is False:
        raise VanishingLinesError("Invalid vanishing point configuration: computed view orientation matrix is not orthogonal.")
        view = glm.mat4(utils.apply_gram_schmidt_orthogonalization(glm.mat3(view))) # note this will remove scaling and translation
        # warnings.warn('Warning: Invalid vanishing point configuration.\n'+"View orientation matrix was not orthogonal, applied Gram-Schmidt orthogonalization")

    return projection, view

def _impl_compute_orientation_from_single_vanishing_point(
        Fu:glm.vec2, 
        P:glm.vec2, 
        f:float, 
        horizon_direction:glm.vec2
    )->glm.mat3:
    """
    Computes the camera orientation matrix from a single vanishing point.
    """
    Fu = glm.vec2(*Fu)
    P = glm.vec2(*P)
    horizon_direction = glm.vec2(*horizon_direction)
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

    Fu = glm.vec2(*Fu)
    Fv = glm.vec2(*Fv)
    P =  glm.vec2(*P)


    forward = glm.normalize(glm.vec3(Fu-P, -f))
    right =   glm.normalize(glm.vec3(Fv-P, -f))
    up =      glm.cross(forward, right)

    orientation = glm.mat3(forward, right, up)

    return orientation

###########################
# ADJUST CAMERA FUNCTIONS #
###########################
import math
def adjust_position_to_anchor(
        viewport:Rect,
        projection:glm.mat4, 
        anchor_screen:glm.vec2, 
        anchor_world:glm.vec3,
        view:glm.mat4,
        distance:float=1.0
    )->glm.mat4:

    print("anchor_world:", anchor_world)
    is_behind_camera = distance < 0
    if is_behind_camera:
        # flip origin around the rectangle center if distance is negative
        rect_center = glm.vec2(viewport.x + viewport.width / 2, viewport.y + viewport.height / 2)
        anchor_screen = rect_center * 2.0 - anchor_screen



    ray_origin, ray_target = utils.cast_ray(anchor_screen, view, projection, viewport)  # to validate unprojection
    ray_direction = glm.normalize(ray_target - ray_origin)
    point_on_ray = ray_direction * distance
    camera_position = point_on_ray
    view = glm.translate(view, camera_position-anchor_world)
    
    # print(f"anchor_world: {anchor_world}")
    # trans_mat = glm.translate(glm.mat4(1.0), -anchor_world)
    # view = view * trans_mat

    # move camera location in world space to match anchor_world
    return view



def adjust_scale_to_reference_distance(
        viewport:Rect,
        projection:glm.mat4,
        anchor_world:glm.vec3,
        reference_world_size:float, 
        reference_axis:ReferenceAxis,
        reference_distance_segment:Tuple[float, float],
        view:glm.mat4, 
    )->glm.mat4:
    """ Calculate the world distance from origin based on the reference distance mode and value."""
    reference_offset, reference_length = reference_distance_segment

    # Determine the reference axis vector in world space
    match reference_axis:
        case ReferenceAxis.X_Axis:
            reference_axis_vector = glm.vec3(1, 0, 0)

        case ReferenceAxis.Y_Axis:
            reference_axis_vector = glm.vec3(0, 1, 0)

        case ReferenceAxis.Z_Axis:
            reference_axis_vector = glm.vec3(0, 0, 1)

        case ReferenceAxis.Screen | _:
            # use camera right vector as reference axis
            right = glm.mat3(glm.inverse(view))[0]   # right vector is +X in view space
            reference_axis_vector = right

    # find reference axis in screen space
    O_screen = glm.project(glm.vec3(0,0,0), view, projection, tuple(viewport)).xy
    V_screen = glm.project(reference_axis_vector, view, projection, tuple(viewport)).xy
    dir_screen = glm.normalize(glm.vec2(V_screen.x - O_screen.x, V_screen.y - O_screen.y))

    # cast rayt from reference points in screen space to intersect with reference axis in world space
    reference_start_point_screen = O_screen + dir_screen * reference_offset
    reference_start_ray = utils.cast_ray(reference_start_point_screen, view, projection, viewport)
    reference_start_point_world = utils.closest_point_between_lines(
        (glm.vec3(0,0,0), reference_axis_vector), 
        reference_start_ray
    )

    reference_end_point_screen = O_screen + dir_screen * (reference_offset + reference_length)
    reference_end_ray = utils.cast_ray(reference_end_point_screen, view, projection, viewport)
    reference_end_point_world = utils.closest_point_between_lines(
        (glm.vec3(0,0,0), reference_axis_vector), 
        reference_end_ray
    )

    # compute the world distance between the two reference points
    reference_world_length = glm.distance(reference_start_point_world, reference_end_point_world)

    # compute scale factor to match desired distance 
    scale_factor = reference_world_length / reference_world_size

    # apply to view matrix
    view = glm.mat4(view) # make a copy
    view_position = glm.vec3(view[3])
    new_view_position = view_position / scale_factor
    view[3] = glm.vec4(new_view_position, 1.0)
    return view

def adjust_axis_assignment(
        first_axis: Axis, 
        second_axis: Axis,
        view_matrix:glm.mat4,
        handedness:Literal['right-handed', 'left-handed']='right-handed'
    )->glm.mat4:
    """adjust a view matrix to match user-specified axis assignment. when used as a trasform matrix.
    create_axis_assignment_matrix crates a native transform matrix"""
    return view_matrix * glm.inverse(glm.mat4(create_axis_assignment_matrix(first_axis, second_axis, handedness))) # type: ignore[return-value] # PyGLM type stubs incorrectly infer mat4x2

def create_axis_assignment_matrix(first_axis: Axis, second_axis: Axis, handedness:Literal['right-handed', 'left-handed']='right-handed') -> glm.mat3:
    """
    Creates an axis assignment matrix that maps vanishing point directions to user-specified world axes.
    
    Args:
        firstVanishingPointAxis: The world axis that the first vanishing point should represent
        secondVanishingPointAxis: The world axis that the second vanishing point should represent
    
    Returns:
        A 3x3 rotation matrix that transforms from vanishing point space to world space
    
    Raises:
        AxisAssignmentError: If the axis assignment creates an invalid (non-orthogonal) matrix

    Usage:
        M_with_axis_shuffled = m * create_axis_assignment_matrix(
            firstVanishingPointAxis=Axis.PositiveX,
            secondVanishingPointAxis=Axis.PositiveY
        )

    Note:
        Identity if:
        - if First vanishing point naturally points along the world's +X direction
        - Second vanishing point naturally points along the world's +Y direction
        - Third direction (computed via cross product) naturally points along the world's +Z direction
    """

    # validate that all three axes are distinct and orthogonal
    def get_axis(axis: Axis) -> glm.vec3:
        match axis:
            case Axis.PositiveX | Axis.NegativeX:
                return "X"
            case Axis.PositiveY | Axis.NegativeY:
                return "Y"
            case Axis.PositiveZ | Axis.NegativeZ:
                return "Z"
            
    if get_axis(first_axis) == get_axis(second_axis):
        raise AxisAssignmentError("Invalid axis assignment: axes must be distinct")
    
    # Get the unit vectors for the specified axes
    forward = helpers.vector_from_axis(first_axis)
    right = helpers.vector_from_axis(second_axis)
    up = helpers.third_axis_vector(first_axis, second_axis, handedness=handedness) # Todo: make sure this is correct
    
    # Build the matrix with each row representing the target world axis
    axis_assignment_matrix = glm.mat3( # Note: this is the inverse of the mat3_from_directions
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
    # assert math.fabs(1 - glm.determinant(axis_assignment_matrix)) < EPSILON, "Invalid axis assignment: axes must be orthogonal"
    return axis_assignment_matrix
