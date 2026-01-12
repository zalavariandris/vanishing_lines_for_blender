import pytest
from pyglm import glm
import numpy as np
import sys
from pathlib import Path
from typing import Literal
from vanishing_lines_for_blender import solver

#########################
# test adjust functions #
#########################
def test_position_by_origin():
    """ Test adjusting the view matrix to set the origin distance."""
    # note that projection and view are arbitrary here
    # todo: some other values for the _view_ are not working. why?
    projection = glm.perspective(glm.radians(60), 1.0, solver.constants.DEFAULT_NEAR_PLANE, solver.constants.DEFAULT_FAR_PLANE)
    view = glm.lookAt(glm.vec3(0,0,0), glm.vec3(1, -2, 3), glm.vec3(0,0,1))

    O = (0.25, 0.5)
    CAMERA_DISTANCE = 2.0
    adjusted_view = solver.core.adjust_position_to_origin(
        viewport=solver.types.Rect(-1,-1,2,2),
        projection=projection,
        O=O,
        view=view,
        distance=CAMERA_DISTANCE
    )

    O1 = glm.project(glm.vec3(0,0,0), adjusted_view, projection, glm.vec4(-1,-1,2,2))

    assert pytest.approx(O1.x, rel=1e-3) == O[0]
    assert pytest.approx(O1.y, rel=1e-3) == O[1]
    transform = glm.inverse(adjusted_view)
    scale = glm.vec3()
    rotation = glm.quat()
    translation = glm.vec3()
    skew = glm.vec3()
    perspective = glm.vec4()
    glm.decompose(transform, scale, rotation, translation, skew, perspective)
    distance_to_origin = glm.distance(glm.vec3(0,0,0), translation)
    forward = -glm.normalize(glm.mat3(adjusted_view)[2])
    
    assert pytest.approx(distance_to_origin, rel=1e-3) == CAMERA_DISTANCE, "Camera is not at the correct distance from the origin"
    assert glm.dot(forward, -glm.normalize(translation)) > 0, "Camera is not looking towards the origin"

@pytest.mark.parametrize("axis", ['X_Axis', 'Y_Axis', 'Z_Axis'])
def test_scale_by_reference_axes(axis: Literal['X_Axis', 'Y_Axis', 'Z_Axis']):
    """ Test different reference axis settings in the solver."""
    projection = glm.perspective(glm.radians(60), 1.0, 0.1, 100)
    view = glm.lookAt(glm.vec3(-1, 2, -3), glm.vec3(0,0,0), glm.vec3(0,1,0))

    reference_axis = {
        'X_Axis': solver.types.ReferenceAxis.X_Axis,
        'Y_Axis': solver.types.ReferenceAxis.Y_Axis,
        'Z_Axis': solver.types.ReferenceAxis.Z_Axis,
    }[axis]

    axis_vector = {
        'X_Axis': glm.vec3(1,0,0),
        'Y_Axis': glm.vec3(0,1,0),
        'Z_Axis': glm.vec3(0,0,1),
    }[axis]

    adjusted_view = solver.core.adjust_scale_to_reference_distance(
        viewport=solver.types.Rect(-1,-1,2,2),
        projection=projection,
        reference_world_size=1.0,
        reference_axis=reference_axis,
        reference_distance_segment=(0, 0.25),
        view=view
    )

    P = glm.project(glm.vec3(0,0,0), adjusted_view, projection, glm.vec4(-1,-1,2,2))
    R = glm.project(axis_vector,     adjusted_view, projection, glm.vec4(-1,-1,2,2))

    projected_distance = glm.distance(P, R)

    assert pytest.approx(projected_distance, rel=1e-3) == 0.25

def test_scale_by_screen():
    """ Test adjusting the scale based on screen plane distance."""
    projection = glm.perspective(glm.radians(60), 1.0, 0.1, 100)
    view = glm.lookAt(glm.vec3(-1, 2, -3), glm.vec3(0,0,0), glm.vec3(0,1,0))
    right = glm.mat3(glm.inverse(view))[0]

    adjusted_view = solver.core.adjust_scale_to_reference_distance(
        viewport=solver.types.Rect(-1,-1,2,2),
        projection=projection,
        reference_world_size=1.0,
        reference_axis=solver.types.ReferenceAxis.Screen,
        reference_distance_segment=(0, 0.5),
        view=view
    )

    P = glm.project(glm.vec3(0,0,0), adjusted_view, projection, glm.vec4(-1,-1,2,2))
    R = glm.project(right, adjusted_view, projection, glm.vec4(-1,-1,2,2))

    projected_distance = glm.distance(P, R)

    assert pytest.approx(projected_distance, rel=1e-3) == 0.5
    



