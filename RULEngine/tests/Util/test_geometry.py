# Under MIT License, see LICENSE.txt

import unittest
import math as m
import RULEngine.Util.geometry

__author__ = 'RoboCupULaval'

class TestGeometry(unittest.TestCase):

    def setUp(self):
        self.position = RULEngine.Util.Position.Position()
        self.positionN = RULEngine.Util.Position.Position(0, 10000)
        self.positionNE = RULEngine.Util.Position.Position(10000, 10000)
        self.positionNO = RULEngine.Util.Position.Position(-10000, 10000)
        self.positionS = RULEngine.Util.Position.Position(0, -10000)
        self.positionSE = RULEngine.Util.Position.Position(10000, -10000)
        self.positionSO = RULEngine.Util.Position.Position(-10000, -10000)

    def test_get_distance(self):
        dist = RULEngine.Util.geometry.get_distance(self.position, self.positionN)
        self.assertEqual(dist, 10000)

        approx_dist = RULEngine.Util.geometry.get_distance(self.positionNE, self.positionSO)
        compValue = m.sqrt(2*(20000**2))
        self.assertAlmostEqual(approx_dist, compValue) # On veut quelle précision pour geo?

    def test_get_angle(self):
        self.assertEqual(RULEngine.Util.geometry.get_angle(self.position, self.positionN), (m.pi)/2)
        self.assertEqual(RULEngine.Util.geometry.get_angle(self.position, self.positionNE), (m.pi)/4)
        self.assertEqual(RULEngine.Util.geometry.get_angle(self.position, self.positionNO), 3*(m.pi)/4)
        self.assertEqual(RULEngine.Util.geometry.get_angle(self.position, self.positionSE), -1*(m.pi)/4)
        self.assertEqual(RULEngine.Util.geometry.get_angle(self.position, self.positionSO), -3*(m.pi)/4)

    def test_get_nearest(self):
        # Cas où on a des distances égales
        # Cas normal
        list_of_positions = [self.positionNE, self.positionSE, self.positionSO, self.positionN]
        nearest = RULEngine.Util.geometry.get_nearest(self.position, list_of_positions)
        self.assertEqual(nearest[0], self.positionN)

        list_of_positions.remove(self.positionN)
        list_of_positions.append(self.positionS)
        nearest = RULEngine.Util.geometry.get_nearest(self.position, list_of_positions)
        self.assertEqual(nearest[0], self.positionS)


    def test_get_line_equation(self):
        self.assertEqual(RULEngine.Util.geometry.get_line_equation(self.positionNE, self.positionSO), (1, 0))
        self.assertEqual(RULEngine.Util.geometry.get_line_equation(self.positionNE, self.positionNO), (0, 10000))

    def test_get_closest_point_on_line(self):
        # Quand le point est nul (0, 0)
        close_null_point = RULEngine.Util.geometry.get_closest_point_on_line(self.positionNE, self.positionSE, self.positionNO)
        self.assertEqual(close_null_point, self.position)
        # Quand le point est sur une position à l'extérieure des deux points
        close_nonexistent_point = RULEngine.Util.geometry.get_closest_point_on_line(self.positionSE, self.position, self.positionN)
        self.assertEqual(close_nonexistent_point, self.positionS)
        # Point normal
        close_point = RULEngine.Util.geometry.get_closest_point_on_line(self.positionNE, self.position, self.positionN)
        self.assertEqual(close_point, self.positionN)

    # def test_get_required_kick_force(self): # simple calculation

if __name__ == '__main__':
    unittest.main()