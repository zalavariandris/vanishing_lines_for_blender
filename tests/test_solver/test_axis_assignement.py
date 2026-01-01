import pytest
from pyglm import glm
import numpy as np
import sys
from pathlib import Path
from typing import Literal

if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    print("Project root:", project_root)
    sys.path.insert(0, str(project_root / "vanishing_lines_for_blender"))

import solver


##############################
# test orientation functions #
##############################

X = glm.vec3(1,0,0)
Y = glm.vec3(0,1,0)
Z = glm.vec3(0,0,1)
parameters = [
    (solver.types.Axis.PositiveX, solver.types.Axis.PositiveY, [X, Y]),
    (solver.types.Axis.PositiveX, solver.types.Axis.NegativeY, [X, -Y]),
    (solver.types.Axis.PositiveY, solver.types.Axis.PositiveX, [Y, X]),
    (solver.types.Axis.PositiveY, solver.types.Axis.NegativeX, [Y, -X]),
]

@pytest.mark.parametrize("first_axis, second_axis, expected", parameters)
def test_axis_assignement(first_axis, second_axis, expected):
    m = glm.mat4(1.0)

    # note the inversion. Unlike _create_axis_assignment_matrix_, 
    # the _adjust_axis_assignment_ is designed to work on the view matrix, not the camera matrix.
    # we need to invert it to get the expected results.
    adjusted_m = glm.inverse(solver.core.adjust_axis_assignment(
        first_axis=first_axis,
        second_axis=second_axis,
        view_matrix=m
    ))
    
    assert pytest.approx(adjusted_m[0])  == glm.vec4(*expected[0], 0), f"got{tuple(adjusted_m[0].xyz)}, expected {tuple(expected[0])}"
    assert pytest.approx(adjusted_m[1])  == glm.vec4(*expected[1], 0), f"got{tuple(adjusted_m[1].xyz)}, expected {tuple(expected[1])}"

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])