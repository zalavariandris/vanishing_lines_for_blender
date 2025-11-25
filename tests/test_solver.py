import unittest
import glm
import math
from typing import List, Tuple
from ..src import solver


class TestVanishingPointSolver(unittest.TestCase):
    """Test suite for camera calibration from vanishing points"""
    
    def setUp(self):
        """Set up common test parameters"""
        self.width = 1920
        self.height = 1080
        self.principal_point = glm.vec2(self.width/2, self.height/2)
        self.focal_length = self.height / 2  # ~45° FOV
        
    def test_focal_length_from_orthogonal_vps(self):
        """Test focal length computation from two orthogonal vanishing points"""
        # Create two orthogonal vanishing points
        Fu = glm.vec2(1500, 540)  # Right of center
        Fv = glm.vec2(960, 200)   # Above center
        P = self.principal_point
        
        # Compute focal length
        f = solver.compute_focal_length_from_vanishing_points(Fu, Fv, P)
        
        # Focal length should be positive and reasonable
        self.assertGreater(f, 0)
        self.assertLess(f, max(self.width, self.height) * 2)
        
    def test_single_vp_solver(self):
        """Test single vanishing point solver"""
        Fu = glm.vec2(960, 300)  # VP above center
        second_line = (glm.vec2(100, 540), glm.vec2(1820, 540))  # Horizontal line
        
        camera_transform = solver.solve1vp(
            self.width, 
            self.height, 
            Fu,
            second_line,
            f=self.focal_length,
            P=self.principal_point,
            O=self.principal_point
        )
        
        # Check that we got a valid 4x4 matrix
        self.assertEqual(camera_transform.length(), 4)
        
        # Check that it's a valid transformation (det should be ±1)
        det = glm.determinant(glm.mat3(camera_transform))
        self.assertAlmostEqual(abs(det), 1.0, places=5)
        
    def test_two_vp_solver(self):
        """Test two vanishing point solver"""
        Fu = glm.vec2(1500, 540)
        Fv = glm.vec2(960, 200)
        
        fovy, camera_transform = solver.solve2vp(
            self.width,
            self.height,
            Fu,
            Fv,
            self.principal_point,
            self.principal_point
        )
        
        # Check FOV is reasonable (between 10° and 120°)
        self.assertGreater(fovy, math.radians(10))
        self.assertLess(fovy, math.radians(120))
        
        # Check matrix validity
        det = glm.determinant(glm.mat3(camera_transform))
        self.assertAlmostEqual(abs(det), 1.0, places=5)
        
    def test_least_squares_intersection(self):
        """Test vanishing point computation from multiple lines"""
        # Create lines that should intersect at (500, 300)
        vp_target = glm.vec2(500, 300)
        lines = [
            (glm.vec2(100, 100), vp_target),
            (glm.vec2(200, 500), vp_target),
            (glm.vec2(800, 200), vp_target),
            (glm.vec2(700, 600), vp_target)
        ]
        
        # Add some noise to make it realistic
        noisy_lines = []
        for p1, p2 in lines:
            # Move p2 slightly away from perfect intersection
            noise = glm.vec2(5, -3)
            noisy_lines.append((p1, p2 + noise))
        
        vp_computed = solver.least_squares_intersection_of_lines(noisy_lines)
        
        # Should be close to target
        distance = glm.distance(vp_computed, vp_target)
        self.assertLess(distance, 20)  # Within 20 pixels
        
    def test_axis_assignment(self):
        """Test axis assignment matrix creation"""        
        # Test standard assignment (should give identity-like behavior)
        mat = solver.create_axis_assignment_matrix(solver.Axis.PositiveX, solver.Axis.PositiveY)
        det = glm.determinant(mat)
        self.assertAlmostEqual(det, 1.0, places=6)
        
        # Test different assignment
        mat2 = solver.create_axis_assignment_matrix(solver.Axis.PositiveZ, solver.Axis.PositiveX)
        det2 = glm.determinant(mat2)
        self.assertAlmostEqual(abs(det2), 1.0, places=6)
        
    def test_fov_focal_length_conversion(self):
        """Test conversion between FOV and focal length"""
        fov = math.radians(60)
        f = solver.focal_length_from_fov(fov, self.height)
        fov_back = solver.fov_from_focal_length(f, self.height)
        
        self.assertAlmostEqual(fov, fov_back, places=6)
        
    def test_ray_casting(self):
        """Test ray casting from screen coordinates"""
        view_matrix = glm.mat4(1.0)
        fovy = math.radians(60)
        proj_matrix = glm.perspective(fovy, self.width/self.height, 0.1, 100)
        viewport = glm.vec4(0, 0, self.width, self.height)
        
        # Cast ray through center of screen
        center = glm.vec2(self.width/2, self.height/2)
        origin, direction = solver.cast_ray(center, view_matrix, proj_matrix, viewport)
        
        # Direction should point roughly forward (negative Z)
        self.assertLess(direction.z, 0)
        self.assertAlmostEqual(glm.length(direction), 1.0, places=5)
        
    def test_euler_extraction(self):
        """Test Euler angle extraction"""
        
        # Create a known rotation
        angle_x, angle_y, angle_z = math.radians(30), math.radians(45), math.radians(60)
        mat = glm.mat4(1.0)
        mat = glm.rotate(mat, angle_z, glm.vec3(0, 0, 1))
        mat = glm.rotate(mat, angle_x, glm.vec3(1, 0, 0))
        mat = glm.rotate(mat, angle_y, glm.vec3(0, 1, 0))
        
        # Extract angles
        ex, ey, ez = solver.extract_euler(glm.mat3(mat), solver.EulerOrder.ZXY)
        
        # Should be close to original (within numerical precision)
        self.assertAlmostEqual(ex, angle_x, places=4)
        self.assertAlmostEqual(ey, angle_y, places=4)
        self.assertAlmostEqual(ez, angle_z, places=4)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""
    
    def test_parallel_lines_error(self):
        """Test that parallel lines raise appropriate error"""
        parallel_lines = [
            (glm.vec2(0, 0), glm.vec2(100, 0)),
            (glm.vec2(0, 10), glm.vec2(100, 10))
        ]
        
        with self.assertRaises(ValueError):
            solver.least_squares_intersection_of_lines(parallel_lines)
            
    def test_coincident_vanishing_points(self):
        """Test error handling for coincident vanishing points"""
        Fu = glm.vec2(500, 500)
        Fv = glm.vec2(500.001, 500.001)  # Almost identical
        P = glm.vec2(400, 400)
        
        with self.assertRaises(ValueError):
            solver.compute_focal_length_from_vanishing_points(Fu, Fv, P)
            
    def test_very_distant_vanishing_points(self):
        """Test handling of very distant vanishing points"""
        Fu = glm.vec2(50000, 540)
        Fv = glm.vec2(960, 50000)
        P = glm.vec2(960, 540)
        
        # Should handle gracefully (either succeed or raise informative error)
        try:
            f = solver.compute_focal_length_from_vanishing_points(Fu, Fv, P)
            self.assertGreater(f, 0)
        except ValueError as e:
            # Should provide helpful error message
            self.assertIn("vanishing point", str(e).lower())


class TestIntegration(unittest.TestCase):
    """Integration tests with realistic scenarios"""
    
    def test_cube_reconstruction(self):
        """Test reconstructing a cube's camera parameters"""
        # Simulate a cube viewed from a typical angle
        width, height = 1920, 1080
        
        # Known camera setup
        true_fov = math.radians(60)
        true_focal = solver.focal_length_from_fov(true_fov, height)
        
        # Vanishing points for a cube (approximate)
        vp_x = glm.vec2(1600, 540)  # Right VP
        vp_y = glm.vec2(960, 200)   # Top VP
        vp_z = glm.vec2(400, 540)   # Left VP
        
        # Test 2VP solver
        P = glm.vec2(width/2, height/2)
        fovy, camera_transform = solver.solve2vp(
            width, height,
            vp_x, vp_y,
            P, P
        )
        
        # FOV should be reasonably close to true FOV
        fov_error = abs(fovy - true_fov)
        self.assertLess(fov_error, math.radians(10))
        
        # Camera should have sensible orientation
        _, rotation, translation, _, _ = solver.decompose(camera_transform)
        
        # Translation should be reasonable (not at origin, not too far)
        dist = glm.length(translation)
        self.assertGreater(dist, 0.1)
        self.assertLess(dist, 1000)


def run_visual_tests():
    """
    Optional: Visual validation tests
    Requires matplotlib and creates plots for manual inspection
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        
        print("\n=== Running Visual Tests ===")
        
        # Test 1: Plot vanishing lines and computed VP
        fig, ax = plt.subplots(1, 1, figsize=(10, 6))
        
        lines = [
            (glm.vec2(100, 400), glm.vec2(500, 300)),
            (glm.vec2(200, 500), glm.vec2(550, 280)),
            (glm.vec2(800, 450), glm.vec2(520, 310))
        ]
        
        vp = solver.least_squares_intersection_of_lines(lines)
        
        for p1, p2 in lines:
            ax.plot([p1.x, p2.x], [p1.y, p2.y], 'b-', linewidth=2)
            
        ax.plot(vp.x, vp.y, 'ro', markersize=10, label='Computed VP')
        ax.set_title('Vanishing Point from Multiple Lines')
        ax.legend()
        ax.grid(True)
        ax.axis('equal')
        
        plt.tight_layout()
        plt.savefig('test_vanishing_point.png')
        print("✓ Saved test_vanishing_point.png")
        
    except ImportError:
        print("Matplotlib not available for visual tests")


if __name__ == '__main__':
    # Run unit tests
    print("Running unit tests...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run visual tests if matplotlib available
    run_visual_tests()