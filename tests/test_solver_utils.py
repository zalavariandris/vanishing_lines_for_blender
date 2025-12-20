import pytest
import math
from typing import Final

from pyglm import glm

from core import utils
from core import solver


def test_least_squares_intersection_shape_X():
    """Test least squares intersection of lines in X shape."""
    lines = [
        (glm.vec2(0, 0), glm.vec2(1, 1)),
        (glm.vec2(0, 1), glm.vec2(1, 0)),
    ]
    vp_computed = utils.least_squares_intersection_of_lines(lines)

    assert vp_computed == glm.vec2(0.5, 0.5)

def test_fov_focal_length_conversion():
    """Test conversion between FOV and focal length"""
    height = 1080
    fov = math.radians(60)
    f = utils.focal_length_from_fov(fov, height)
    fov_back = utils.fov_from_focal_length(f, height)
    
    assert pytest.approx(fov_back) == fov
    
def test_ray_casting():
    """Test ray casting from screen coordinates"""
    width, height = 1920, 1080
    view_matrix = glm.mat4(1.0)
    fovy = math.radians(60)
    proj_matrix = glm.perspective(fovy, width/height, 0.1, 100)
    viewport = glm.vec4(0, 0, width, height)
    
    # Cast ray through center of screen
    center = glm.vec2(width/2, height/2)
    origin, target = utils.cast_ray(center, view_matrix, proj_matrix, viewport)
    
    # Direction should point roughly forward (negative Z)
    direction = glm.normalize(target - origin)
    assert direction.z < 0
    assert glm.length(direction) == pytest.approx(1.0)

def test_euler_extraction_ZXY():
    """Test Euler angle extraction"""
    x_axis:Final = glm.vec3(1, 0, 0)
    y_axis:Final = glm.vec3(0, 1, 0)
    z_axis:Final = glm.vec3(0, 0, 1)
    
    angle_x, angle_y, angle_z = math.radians(30), math.radians(45), math.radians(60)

    # ZXY order
    mat = glm.mat4(1.0)
    for angle, axis in [(angle_z, z_axis), (angle_x, x_axis), (angle_y, y_axis)]:
        mat = glm.rotate(mat, angle, axis) 

    ez, ex, ey = utils.extract_euler_ZXY(glm.mat3(mat))
    
    # Should be close to original (within numerical precision)
    assert (ex, ey, ez) == pytest.approx((angle_x, angle_y, angle_z))

@pytest.mark.parametrize("order", ['XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'])
def test_euler_extraction(order):
    """
    Test Euler angle extraction for a specific rotation order'.
    note: angles returned in the specified order.
    example: for order 'ZXY', angles are returned as (z, x, y)
    """
    extract_euler = getattr(utils, f'extract_euler_{order}')

    axes:Final =   {
        'X': glm.vec3(1, 0, 0),
        'Y': glm.vec3(0, 1, 0),
        'Z': glm.vec3(0, 0, 1)
    }

    angles:Final = {
        'X': math.radians(30), 
        'Y': math.radians(45), 
        'Z': math.radians(60)
    }

    mat = glm.mat4(1.0)
    for angle, axis_vector in [(angles[axis], axes[axis]) for axis in order]:
        mat = glm.rotate(mat, angle, axis_vector)

    euler = extract_euler(mat) # return angles expected in specified order
    expected_angles = tuple(angles[axis] for axis in order) #
    assert euler == pytest.approx(expected_angles)
