import unittest
import numpy as np
from fingertip_probability import circle_distribution, density_grid, CHI2_95


class ProbabilityTests(unittest.TestCase):
    def test_affine_covariance_and_mass(self):
        matrix = np.diag([2., 3., 1.])
        result = circle_distribution([50, 30], 6, matrix)
        np.testing.assert_allclose(result['flat_mean'], [100, 90])
        np.testing.assert_allclose(result['flat_covariance'], np.diag([4., 9.])*36/CHI2_95)
        self.assertAlmostEqual(density_grid(result, 220, 200).sum(), 1., places=6)

    def test_exact_projective_conic(self):
        result = circle_distribution([50, 30], 6, np.array([[2., .1, 5], [.2, 3, 4], [.002, .001, 1]]))
        boundary = np.c_[result['exact_boundary'], np.ones(361)]
        values = np.einsum('ni,ij,nj->n', boundary, result['flat_exact_conic_matrix'], boundary)
        np.testing.assert_allclose(values, 0, atol=1e-10)

    def test_horizon_and_invalid_radius(self):
        self.assertEqual(circle_distribution([0, 0], 6, np.array([[1., 0, 0], [0, 1, 0], [1, 0, 1]]))['status'],
                         'circle_crosses_projective_horizon')
        with self.assertRaises(ValueError):
            circle_distribution([0, 0], 0, np.eye(3))


if __name__ == '__main__':
    unittest.main()
