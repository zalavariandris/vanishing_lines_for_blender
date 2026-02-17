import pytest
import glm
import numpy as np
import sys
from pathlib import Path
from typing import Literal
from vanishing_lines_for_blender import solver

def test_unsolve_with_two_vp():
    viewport = solver.types.Rect(0,0, 1280,720)
    anchor_screen = glm.vec2(640,280)
    anchor_world = glm.vec3(0,0,0)
    reference_axis = solver.types.ReferenceAxis.Screen
    reference_screen_measurement = solver.types.ScreenMeasurement(offset=0, length=100)
    referende_scene_scale = 1.0
    first_axis = solver.types.Axis.NegativeX
    second_axis = solver.types.Axis.PositiveY
    
    first_vanishing_lines=[
        (glm.vec2(870,70), glm.vec2(140,460)),
        (glm.vec2(1220,300), glm.vec2(300,550))
    ]

    second_vanishing_lines=[
        (glm.vec2(400,60), glm.vec2(1210,460)),
        (glm.vec2(140,330), glm.vec2(1060,560))
    ]

    solve_result = solver.core.solve(
        mode = solver.types.SolverMode.TwoVP,
        viewport = viewport,

        first_vanishing_lines=first_vanishing_lines,
        second_vanishing_lines=second_vanishing_lines,
        third_vanishing_lines=[],

        f=720,
        P=glm.vec2(640,360),
        anchor_screen=glm.vec2(640,280),
        anchor_world=anchor_world,

        reference_axis=reference_axis,
        reference_screen_measurement=reference_screen_measurement,
        reference_world_size=referende_scene_scale,

        first_axis =  first_axis,
        second_axis = second_axis,
    )

    unsolve_result = solver.core.unsolve(
        viewport=viewport,
        projection=solve_result.projection,
        view=solve_result.view,
        anchor_world=anchor_world,
        reference_axis=reference_axis,
        reference_screen_measurement=reference_screen_measurement,
        first_axis=first_axis,
        second_axis=second_axis
    )

    # assert pytest.approx(tuple(unsolve_result.vp1)) == tuple(vp1), f"VP1 does not match expected.\nGot: {unsolve_result.vp1}\nExpected: {vp1}"
    # assert pytest.approx(tuple(unsolve_result.vp2)) == tuple(vp2), f"VP1 does not match expected.\nGot: {unsolve_result.vp1}\nExpected: {vp1}"
    assert pytest.approx(tuple(unsolve_result.anchor_screen)) == anchor_screen, f"Anchor screen does not match expected.\nGot: {unsolve_result.anchor_screen}\nExpected: {anchor_screen}"
    assert pytest.approx(unsolve_result.reference_scene_scale, rel=1e-3) == referende_scene_scale, f"Reference world size does not match expected.\nGot: {unsolve_result.reference_scene_scale}\nExpected: {referende_scene_scale}"

def test_unsolve_scene_scale_with_anchor_world():
    anchor_world = glm.vec3(3,2,1)
    anchor_screen = glm.vec2(240,100)

    viewport = solver.types.Rect(0,0, 1280,720)
    reference_axis = solver.types.ReferenceAxis.Screen
    reference_screen_measurement = solver.types.ScreenMeasurement(offset=0, length=100)
    referende_scene_scale = 1.0
    first_axis = solver.types.Axis.PositiveY
    second_axis = solver.types.Axis.PositiveX
    
    first_vanishing_lines=[
        (glm.vec2(870,70), glm.vec2(140,460)),
        (glm.vec2(1220,300), glm.vec2(300,550))
    ]

    second_vanishing_lines=[
        (glm.vec2(400,60), glm.vec2(1210,460)),
        (glm.vec2(140,330), glm.vec2(1060,560))
    ]

    solve_result = solver.core.solve(
        mode = solver.types.SolverMode.TwoVP,
        viewport = viewport,

        first_vanishing_lines=first_vanishing_lines,
        second_vanishing_lines=second_vanishing_lines,
        third_vanishing_lines=[],

        f=720,
        P=glm.vec2(640,360),
        anchor_screen=anchor_screen,
        anchor_world=anchor_world,

        reference_axis=reference_axis,
        reference_screen_measurement=reference_screen_measurement,
        reference_world_size=referende_scene_scale,

        first_axis =  first_axis,
        second_axis = second_axis,
    )

    unsolve_result = solver.core.unsolve(
        viewport=viewport,
        projection=solve_result.projection,
        view=solve_result.view,
        anchor_world=anchor_world,
        reference_axis=reference_axis,
        reference_screen_measurement=reference_screen_measurement,
        first_axis=first_axis,
        second_axis=second_axis
    )

    # assert pytest.approx(tuple(unsolve_result.vp1)) == tuple(vp1), f"VP1 does not match expected.\nGot: {unsolve_result.vp1}\nExpected: {vp1}"
    # assert pytest.approx(tuple(unsolve_result.vp2)) == tuple(vp2), f"VP1 does not match expected.\nGot: {unsolve_result.vp1}\nExpected: {vp1}"
    assert pytest.approx(tuple(unsolve_result.anchor_screen)) == anchor_screen, f"Anchor screen does not match expected.\nGot: {unsolve_result.anchor_screen}\nExpected: {anchor_screen}"
    assert pytest.approx(unsolve_result.reference_scene_scale, rel=1e-3) == referende_scene_scale, f"Reference world size does not match expected.\nGot: {unsolve_result.reference_scene_scale}\nExpected: {referende_scene_scale}"

def test_unsolve_anchor_mode_with_anchor_world():
    """Test unsolve with reference_axis=None (ANCHOR mode) and non-zero anchor_world.
    This catches the bug where decompose_extrinsics returned the view matrix translation
    column instead of the actual camera world position."""
    anchor_world = glm.vec3(3,2,1)
    anchor_screen = glm.vec2(240,100)

    viewport = solver.types.Rect(0,0, 1280,720)
    reference_axis = None  # ANCHOR mode
    reference_screen_measurement = solver.types.ScreenMeasurement(offset=0, length=100)
    referende_scene_scale = 10.0
    first_axis = solver.types.Axis.PositiveY
    second_axis = solver.types.Axis.PositiveX
    
    first_vanishing_lines=[
        (glm.vec2(870,70), glm.vec2(140,460)),
        (glm.vec2(1220,300), glm.vec2(300,550))
    ]

    second_vanishing_lines=[
        (glm.vec2(400,60), glm.vec2(1210,460)),
        (glm.vec2(140,330), glm.vec2(1060,560))
    ]

    solve_result = solver.core.solve(
        mode = solver.types.SolverMode.TwoVP,
        viewport = viewport,

        first_vanishing_lines=first_vanishing_lines,
        second_vanishing_lines=second_vanishing_lines,
        third_vanishing_lines=[],

        f=720,
        P=glm.vec2(640,360),
        anchor_screen=anchor_screen,
        anchor_world=anchor_world,

        reference_axis=reference_axis,
        reference_screen_measurement=reference_screen_measurement,
        reference_world_size=referende_scene_scale,

        first_axis =  first_axis,
        second_axis = second_axis,
    )

    unsolve_result = solver.core.unsolve(
        viewport=viewport,
        projection=solve_result.projection,
        view=solve_result.view,
        anchor_world=anchor_world,
        reference_axis=reference_axis,
        reference_screen_measurement=reference_screen_measurement,
        first_axis=first_axis,
        second_axis=second_axis
    )

    assert pytest.approx(tuple(unsolve_result.anchor_screen)) == anchor_screen, f"Anchor screen does not match expected.\nGot: {unsolve_result.anchor_screen}\nExpected: {anchor_screen}"
    assert pytest.approx(unsolve_result.reference_scene_scale, rel=1e-3) == referende_scene_scale, f"Reference world size does not match expected.\nGot: {unsolve_result.reference_scene_scale}\nExpected: {referende_scene_scale}"