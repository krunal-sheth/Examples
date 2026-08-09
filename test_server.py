import os
import tempfile
import unittest
from datetime import date

with tempfile.TemporaryDirectory() as _dir:
    os.environ["DATABASE_PATH"] = f"{_dir}/test.db"
    import server


class JyotishTests(unittest.TestCase):
    def test_password_hashes_are_salted_and_verifiable(self):
        first = server.password_hash("a-secure-password")
        second = server.password_hash("a-secure-password")
        self.assertNotEqual(first, second)
        self.assertTrue(server.verify_password("a-secure-password", first))
        self.assertFalse(server.verify_password("wrong-password", first))

    def test_kundli_contains_required_vedic_fields(self):
        chart = server.calculate_kundli("1992-11-19", "07:42", 18.5204, 73.8567, 5.5)
        self.assertIn(chart["ascendant"]["sign"], server.SIGNS)
        self.assertIn(chart["moon_sign"], server.SIGNS)
        self.assertIn(chart["nakshatra"], server.NAKSHATRAS)
        self.assertIn(chart["pada"], range(1, 5))
        self.assertEqual(set(chart["planets"]), {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"})

    def test_daily_reading_is_stable_for_a_date(self):
        chart = server.calculate_kundli("1992-11-19", "07:42", 18.5204, 73.8567, 5.5)
        first = server.daily_prediction(chart, date.today().isoformat())
        second = server.daily_prediction(chart, date.today().isoformat())
        self.assertEqual(first, second)
        self.assertGreaterEqual(first["score"], 0)
        self.assertLessEqual(first["score"], 100)


if __name__ == "__main__":
    unittest.main()
