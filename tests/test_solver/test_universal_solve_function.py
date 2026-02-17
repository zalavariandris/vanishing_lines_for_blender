import pytest
import glm
import numpy as np
import sys
from pathlib import Path
from typing import Literal
from vanishing_lines_for_blender import solver


############################
# test main solve function #
############################

def test_solve_with_one_vp():
    solve_result = solver.core.solve(
        mode = solver.types.SolverMode.OneVP,
        viewport = solver.types.Rect(0,0, 1280,720),

        first_vanishing_lines=[
            (glm.vec2(50,260), glm.vec2(850,500)),
            (glm.vec2(740,30), glm.vec2(1050,400)),
        ],
        second_vanishing_lines=[
            (glm.vec2(100,650), glm.vec2(1180,650))
        ],
        third_vanishing_lines=[],

        f=720,
        P=glm.vec2(640,360),
        anchor_screen=glm.vec2(640,200),
        anchor_world=glm.vec3(0,0,0),

        reference_axis=solver.types.ReferenceAxis.X_Axis,
        reference_screen_measurement=solver.types.ScreenMeasurement(offset=0, length=100),
        reference_world_size=1.0,

        first_axis = solver.types.Axis.NegativeX,
        second_axis = solver.types.Axis.PositiveY,
    )

    # print("View Matrix:\n", glm.transpose(solve_result.view))
    # print("Projection Matrix:\n", glm.transpose(projection))

    view_expected = glm.mat4(
        -0.610905,    -0.263127, 0.746699, 0,
        -0.791416,     0.22838, -0.567012, 0,
        -0.021335,    -0.93734, -0.347761, 0,
         3.72529e-08, -1.0285, -4.62827,  1 
    )

    assert np.allclose(np.array(solve_result.view), np.array(view_expected)),\
        f"View matrix does not match expected."\
        f"\nGot:\n{solve_result.view}\nExpected:\n{view_expected}"
    
    projection_expected = glm.mat4(
        1.125, 0,       0,  0,
            0, 2,       0,  0,
            0, 0,  -1.002, -1,
            0, 0, -0.2002,  0
    )
    assert np.allclose(np.array(solve_result.projection), np.array(projection_expected)),\
        f"Projection matrix does not match expected."\
        f"\nGot:\n{solve_result.projection}\nExpected:\n{projection_expected}"
    
def test_solve_with_two_vp():
    solve_result = solver.core.solve(
        mode = solver.types.SolverMode.TwoVP,
        viewport = solver.types.Rect(0,0, 1280,720),

        first_vanishing_lines=[
            (glm.vec2(870,70), glm.vec2(140,460)),
            (glm.vec2(1220,300), glm.vec2(300,550)),
        ],
        second_vanishing_lines=[
            (glm.vec2(400,60), glm.vec2(1210,460)),
            (glm.vec2(140,330), glm.vec2(1060,560))
        ],
        third_vanishing_lines=[],

        f=720,
        P=glm.vec2(640,360),
        anchor_screen=glm.vec2(640,280),
        anchor_world=glm.vec3(0,0,0),

        reference_axis=solver.types.ReferenceAxis.X_Axis,
        reference_screen_measurement=solver.types.ScreenMeasurement(offset=0, length=100),
        reference_world_size=1.0,

        first_axis = solver.types.Axis.NegativeX,
        second_axis = solver.types.Axis.PositiveY,
    )

    view_expected = glm.mat4( 
        0.686495,    -0.252992, 0.681703,  0, 
        0.727128,     0.242701, -0.642169, 0, 
       -0.00298585,   0.936532, 0.350571,  0, 
       -1.21072e-08, -0.5473, -6.85105,  1)


    assert np.allclose(np.array(solve_result.view), np.array(view_expected)),\
        f"View matrix does not match expected."\
        f"\nGot:\n{solve_result.view}\nExpected:\n{view_expected}"
    
    projection_expected = glm.mat4(
        1.56474,      0,       0,  0,
              0,2.78176,       0,  0,
              0,      0,  -1.002, -1,
              0,      0, -0.2002,  0,
    )
    assert np.allclose(np.array(solve_result.projection), np.array(projection_expected)),\
        f"Projection matrix does not match expected."\
        f"\nGot:\n{solve_result.projection}\nExpected:\n{projection_expected}"
    
def test_solve_with_three_vp():
    """ Test the solver with three vanishing points."""
    solve_result = solver.core.solve(
        mode = solver.types.SolverMode.ThreeVP,
        viewport = solver.types.Rect(0,0, 1757,2040),

        first_vanishing_lines=[
            (glm.vec2(1008, 61),  glm.vec2(-38,901)),
            (glm.vec2(1562,1467), glm.vec2(282,1872)),
        ],
        second_vanishing_lines=[
            (glm.vec2(870,829),  glm.vec2(1327,1505)),
            (glm.vec2(-49,1045), glm.vec2(986,1849))
        ],
        third_vanishing_lines=[
            (glm.vec2(261,327), glm.vec2(-45,1919)),
            (glm.vec2(1454,601), glm.vec2(1670,1915)),
        ],

        f=720, # unnecessary in 3VP mode
        P=glm.vec2(640,360), # unnecessary in 3VP mode
        anchor_screen=glm.vec2(873,491),
        anchor_world=glm.vec3(0,0,0),

        reference_axis=solver.types.ReferenceAxis.X_Axis,
        reference_screen_measurement=solver.types.ScreenMeasurement(offset=0, length=100),
        reference_world_size=1.0,

        first_axis = solver.types.Axis.NegativeX,
        second_axis = solver.types.Axis.PositiveY,
    )

    expected_view = glm.mat4(
         0.823959,   -0.190644,  0.533617, 0,
         0.566121,    0.31764,  -0.760666, 0,
        -0.0244815,   0.928849,  0.36965,  0,
         1.23902,   -15.152,  -19.7499,   1
    )

    assert np.allclose(np.array(solve_result.view), np.array(expected_view)),\
        f"View matrix does not match expected."\
        f"\nGot:\n{solve_result.view}\nExpected:\n{expected_view}"

    expected_projection = glm.mat4(
        2.20622,   0,          0,      0,
        0,         1.90016,    0,      0,
        0.144669, -0.939165,  -1.002, -1,
        0,         0,         -0.2002, 0
    )

    assert np.allclose(np.array(solve_result.projection), np.array(expected_projection)),\
        f"Projection matrix does not match expected."\
        f"\nGot:\n{solve_result.projection}\nExpected:\n{expected_projection}"

def test_solve_with_no_reference_axis():
    ORIGIN_DISTANCE = 7.0
    solve_result = solver.core.solve(
        mode = solver.types.SolverMode.TwoVP,
        viewport = solver.types.Rect(0,0, 1280,720),

        first_vanishing_lines=[
            (glm.vec2(870,70),   glm.vec2(140,460)),
            (glm.vec2(1220,300), glm.vec2(300,550)),
        ],
        second_vanishing_lines=[
            (glm.vec2(400,60), glm.vec2(1210,460)),
            (glm.vec2(140,330), glm.vec2(1060,560))
        ],
        third_vanishing_lines=[],

        f=720,
        P=glm.vec2(640,360),
        anchor_screen=glm.vec2(640,280),
        anchor_world=glm.vec3(0,0,0),

        reference_axis=None,
        reference_screen_measurement=solver.types.ScreenMeasurement(offset=0, length=100),
        reference_world_size=ORIGIN_DISTANCE,

        first_axis = solver.types.Axis.NegativeX,
        second_axis = solver.types.Axis.PositiveY,
    )

    camera_position = glm.inverse(solve_result.view)[3]
    camera_distance = glm.length(glm.vec3(camera_position))

    assert pytest.approx(camera_distance, rel=1e-3) == ORIGIN_DISTANCE

##########################
# test solver components #
##########################

if __name__ == "__main__":
    pytest.main([
        __file__, 
        # "-v", # verbose
        "-s" # to show print statements
    ])

# import unittest
# import glm
# import math
# from typing import List, Tuple
# from .. vanishing_lines_for_blender.core import solver_functional as solver


# class TestVanishingPointSolver(unittest.TestCase):
#     """Test suite for camera calibration from vanishing points"""
    
#     def setUp(self):
#         """Set up common test parameters"""
#         self.width = 1920
#         self.height = 1080
#         self.principal_point = glm.vec2(self.width/2, self.height/2)
#         self.focal_length = self.height / 2  # ~45° FOV
        
#     def test_focal_length_from_orthogonal_vps(self):
#         """Test focal length computation from two orthogonal vanishing points"""
#         # Create two orthogonal vanishing points
#         Fu = glm.vec2(1500, 540)  # Right of center
#         Fv = glm.vec2(960, 200)   # Above center
#         P = self.principal_point
        
#         # Compute focal length
#         f = solver.compute_focal_length_from_vanishing_points(Fu, Fv, P)
        
#         # Focal length should be positive and reasonable
#         self.assertGreater(f, 0)
#         self.assertLess(f, max(self.width, self.height) * 2)
        
        

#     def test_axis_assignment(self):
#         """Test axis assignment matrix creation"""        
#         # Test standard assignment (should give identity-like behavior)
#         mat = solver.create_axis_assignment_matrix(solver.Axis.PositiveX, solver.Axis.PositiveY)
#         det = glm.determinant(mat)
#         self.assertAlmostEqual(det, 1.0, places=6)
        
#         # Test different assignment
#         mat2 = solver.create_axis_assignment_matrix(solver.Axis.PositiveZ, solver.Axis.PositiveX)
#         det2 = glm.determinant(mat2)
#         self.assertAlmostEqual(abs(det2), 1.0, places=6)
        

# class TestEdgeCases(unittest.TestCase):
#     """Test edge cases and error handling"""
    
#     def test_parallel_lines_error(self):
#         """Test that parallel lines raise appropriate error"""
#         parallel_lines = [
#             (glm.vec2(0, 0), glm.vec2(100, 0)),
#             (glm.vec2(0, 10), glm.vec2(100, 10))
#         ]
        
#         with self.assertRaises(ValueError):
#             solver.least_squares_intersection_of_lines(parallel_lines)
            
#     def test_coincident_vanishing_points(self):
#         """Test error handling for coincident vanishing points"""
#         Fu = glm.vec2(500, 500)
#         Fv = glm.vec2(500.001, 500.001)  # Almost identical
#         P = glm.vec2(400, 400)
        
#         with self.assertRaises(ValueError):
#             solver.compute_focal_length_from_vanishing_points(Fu, Fv, P)
            
#     def test_very_distant_vanishing_points(self):
#         """Test handling of very distant vanishing points"""
#         Fu = glm.vec2(50000, 540)
#         Fv = glm.vec2(960, 50000)
#         P = glm.vec2(960, 540)
        
#         # Should handle gracefully (either succeed or raise informative error)
#         try:
#             f = solver.compute_focal_length_from_vanishing_points(Fu, Fv, P)
#             self.assertGreater(f, 0)
#         except ValueError as e:
#             # Should provide helpful error message
#             self.assertIn("vanishing point", str(e).lower())


# class TestIntegration(unittest.TestCase):
#     """Integration tests with realistic scenarios"""
    
#     def test_cube_reconstruction(self):
#         """Test reconstructing a cube's camera parameters"""
#         # Simulate a cube viewed from a typical angle
#         width, height = 1920, 1080
        
#         # Known camera setup
#         true_fov = math.radians(60)
#         true_focal = solver.focal_length_from_fov(true_fov, height)
        
#         # Vanishing points for a cube (approximate)
#         vp_x = glm.vec2(1600, 540)  # Right VP
#         vp_y = glm.vec2(960, 200)   # Top VP
#         vp_z = glm.vec2(400, 540)   # Left VP
        
#         # Test 2VP solver
#         P = glm.vec2(width/2, height/2)
#         fovy, camera_transform = solver.solve2vp(
#             width, height,
#             vp_x, vp_y,
#             P, P
#         )
        
#         # FOV should be reasonably close to true FOV
#         fov_error = abs(fovy - true_fov)
#         self.assertLess(fov_error, math.radians(10))
        
#         # Camera should have sensible orientation
#         _, rotation, translation, _, _ = solver.decompose(camera_transform)
        
#         # Translation should be reasonable (not at origin, not too far)
#         dist = glm.length(translation)
#         self.assertGreater(dist, 0.1)
#         self.assertLess(dist, 1000)


# def run_visual_tests():
#     """
#     Optional: Visual validation tests
#     Requires matplotlib and creates plots for manual inspection
#     """
#     try:
#         import matplotlib.pyplot as plt
#         import numpy as np
        
#         print("\n=== Running Visual Tests ===")
        
#         # Test 1: Plot vanishing lines and computed VP
#         fig, ax = plt.subplots(1, 1, figsize=(10, 6))
        
#         lines = [
#             (glm.vec2(100, 400), glm.vec2(500, 300)),
#             (glm.vec2(200, 500), glm.vec2(550, 280)),
#             (glm.vec2(800, 450), glm.vec2(520, 310))
#         ]
        
#         vp = solver.least_squares_intersection_of_lines(lines)
        
#         for p1, p2 in lines:
#             ax.plot([p1.x, p2.x], [p1.y, p2.y], 'b-', linewidth=2)
            
#         ax.plot(vp.x, vp.y, 'ro', markersize=10, label='Computed VP')
#         ax.set_title('Vanishing Point from Multiple Lines')
#         ax.legend()
#         ax.grid(True)
#         ax.axis('equal')
        
#         plt.tight_layout()
#         plt.savefig('test_vanishing_point.png')
#         print("✓ Saved test_vanishing_point.png")
        
#     except ImportError:
#         print("Matplotlib not available for visual tests")


# if __name__ == '__main__':
#     # Run unit tests
#     print("Running unit tests...")
#     unittest.main(argv=[''], exit=False, verbosity=2)
    
#     # Run visual tests if matplotlib available
#     run_visual_tests()