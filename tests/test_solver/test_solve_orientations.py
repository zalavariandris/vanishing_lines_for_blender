import pytest
from pyglm import glm
import numpy as np
import sys
from pathlib import Path
from typing import Literal
from vanishing_lines_for_blender import solver


##############################
# test orientation functions #
##############################

def test_orientation_with_one_vp():
    first_vanishing_lines=[
        ((50,260), (850,500)),
        ((740,30), (1050,400)),
    ]
    vp1 = solver.core.compute_vanishing_point(first_vanishing_lines)

    projection, view = solver.core.orientation_from_one_vanishing_point(
        viewport=solver.types.Rect(0,0, 1280,720),
        vp1=vp1,
        second_line=((100,650), (1180,650)),
        f=720,
        P=(640,360)
    )

    # print("View Matrix:\n", glm.transpose(view))
    # print("Projection Matrix:\n", glm.transpose(projection))

    view_expected = glm.mat4(
         0.610905,     0.263127, -0.746699, 0,
        -0.791416,     0.22838,  -0.567012, 0,
         0.021335,     0.93734,   0.347761, 0,
         0.0,          0.0,       0.0,     1 
    )

    assert np.allclose(np.array(view), np.array(view_expected)),\
        f"View matrix does not match expected."\
        f"\nGot:\n{view}\nExpected:\n{view_expected}"
    
    projection_expected = glm.mat4(
        1.125, 0,       0,  0,
            0, 2,       0,  0,
            0, 0,  -1.002, -1,
            0, 0, -0.2002,  0
    )
    assert np.allclose(np.array(projection), np.array(projection_expected)),\
        f"Projection matrix does not match expected."\
        f"\nGot:\n{projection}\nExpected:\n{projection_expected}"
    
def test_orientation_with_two_vp():
    # projection, view = solver.core.solve(
    #     mode = solver.types.SolverMode.TwoVP,
    #     viewport = solver.types.Rect(0,0, 1280,720),

    #     first_vanishing_lines=[
    #         ((870,70), (140,460)),
    #         ((1220,300), (300,550)),
    #     ],
    #     second_vanishing_lines=[
    #         ((400,60), (1210,460)),
    #         ((140,330), (1060,560))
    #     ],
    #     third_vanishing_lines=[],

    #     f=720,
    #     P=(640,360),
    #     O=(640,280),

    #     reference_axis=solver.types.ReferenceAxis.X_Axis,
    #     reference_distance_segment=(0,100),
    #     reference_world_size=1.0,

    #     first_axis = solver.types.Axis.NegativeX,
    #     second_axis = solver.types.Axis.PositiveY,
    # )
    first_vanishing_lines=[
        ((870,70), (140,460)),
        ((1220,300), (300,550)),
    ]
    second_vanishing_lines=[
        ((400,60), (1210,460)),
        ((140,330), (1060,560))
    ]
    vp1 = solver.core.compute_vanishing_point(first_vanishing_lines)
    vp2 = solver.core.compute_vanishing_point(second_vanishing_lines)

    projection, view = solver.core.orientation_from_two_vanishing_points(
        viewport=solver.types.Rect(0,0, 1280,720),
        vp1=vp1,
        vp2=vp2,
        P=(640,360)
    )

    view_expected = glm.mat4( 
        -0.686495,    0.252992, -0.681703, 0, 
         0.727128,    0.242701, -0.642169, 0, 
         0.00298585, -0.936532, -0.350571, 0, 
         0.0,         0.0,       0.0,      1)

    assert np.allclose(np.array(view), np.array(view_expected)),\
        f"View matrix does not match expected."\
        f"\nGot:\n{view}\nExpected:\n{view_expected}"
    
    projection_expected = glm.mat4(
        1.56474,      0,       0,  0,
              0,2.78176,       0,  0,
              0,      0,  -1.002, -1,
              0,      0, -0.2002,  0,
    )
    assert np.allclose(np.array(projection), np.array(projection_expected)),\
        f"Projection matrix does not match expected."\
        f"\nGot:\n{projection}\nExpected:\n{projection_expected}"
    
def test_orientation_with_three_vp():
    """ Test the solver with three vanishing points."""
    # projection, view = solver.core.solve(
    #     mode = solver.types.SolverMode.ThreeVP,
    #     viewport = solver.types.Rect(0,0, 1757,2040),

    #     first_vanishing_lines=[
    #         ((1008, 61),  (-38,901)),
    #         ((1562,1467), (282,1872)),
    #     ],
    #     second_vanishing_lines=[
    #         ((870,829),  (1327,1505)),
    #         ((-49,1045), (986,1849))
    #     ],
    #     third_vanishing_lines=[
    #         ((261,327), (-45,1919)),
    #         ((1454,601), (1670,1915)),
    #     ],

    #     f=720, # unnecessary in 3VP mode
    #     P=(640,360), # unnecessary in 3VP mode
    #     O=(873,491),

    #     reference_axis=solver.types.ReferenceAxis.X_Axis,
    #     reference_distance_segment=(0,100),
    #     reference_world_size=1.0,

    #     first_axis = solver.types.Axis.NegativeX,
    #     second_axis = solver.types.Axis.PositiveY,
    # )

    first_vanishing_lines=[
        ((1008, 61),  (-38,901)),
        ((1562,1467), (282,1872)),
    ]
    second_vanishing_lines=[
        ((870,829),  (1327,1505)),
        ((-49,1045), (986,1849))
    ]
    third_vanishing_lines=[
        ((261,327), (-45,1919)),
        ((1454,601), (1670,1915)),
    ]

    vp1 = solver.core.compute_vanishing_point(first_vanishing_lines)
    vp2 = solver.core.compute_vanishing_point(second_vanishing_lines)
    vp3 = solver.core.compute_vanishing_point(third_vanishing_lines)

    projection, view = solver.core.orientation_from_three_vanishing_points(
        solver.types.Rect(0,0, 1757,2040),
        vp1=vp1,
        vp2=vp2,
        vp3=vp3
    )

    expected_view = glm.mat4(
        -0.823959,   0.190644, -0.533617, 0,
         0.566121,   0.31764,  -0.760666, 0,
         0.0244815, -0.928849, -0.36965,  0,
         0.0,        0.0,       0.0,      1
    )

    assert np.allclose(np.array(view), np.array(expected_view)),\
        f"View matrix does not match expected."\
        f"\nGot:\n{view}\nExpected:\n{expected_view}"

    expected_projection = glm.mat4(
        2.20622,   0,          0,      0,
        0,         1.90016,    0,      0,
        0.144669, -0.939165,  -1.002, -1,
        0,         0,         -0.2002, 0
    )

    assert np.allclose(np.array(expected_projection), np.array(expected_projection)),\
        f"View matrix does not match expected."\
        f"\nGot:\n{projection}\nExpected:\n{expected_view}"

