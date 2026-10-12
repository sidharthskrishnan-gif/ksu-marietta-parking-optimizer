import unittest

from ksu_parking_optimizer import (
    DEFAULT_PREFERENCES,
    detect_long_gaps,
    list_buildings,
    recommend_permit,
    validate_schedule,
)


def building(fragment):
    matches = [b for b in list_buildings() if fragment.lower() in b.lower()]
    if not matches:
        raise RuntimeError(f"No building contains {fragment!r}")
    return matches[0]


class OptimizerRegressionTests(unittest.TestCase):
    def test_conflicting_classes_are_rejected(self):
        schedule = [
            {
                "day": "Monday",
                "building": building("Mathematics"),
                "start_time": "09:00",
                "end_time": "10:15",
            },
            {
                "day": "Monday",
                "building": building("Academic"),
                "start_time": "10:00",
                "end_time": "11:15",
            },
        ]
        with self.assertRaises(ValueError):
            validate_schedule(schedule)

    def test_multiple_long_gaps_are_detected(self):
        schedule = [
            {
                "day": "Monday",
                "building": building("Mathematics"),
                "start_time": "08:00",
                "end_time": "09:15",
            },
            {
                "day": "Monday",
                "building": building("Academic"),
                "start_time": "12:00",
                "end_time": "13:15",
            },
            {
                "day": "Monday",
                "building": building("Engineering Technology"),
                "start_time": "17:30",
                "end_time": "18:45",
            },
        ]
        gaps = detect_long_gaps(schedule, minimum_gap_minutes=120)
        self.assertEqual(len(gaps), 2)

    def test_recommendation_ranks_all_permits(self):
        schedule = [
            {
                "day": "Monday",
                "building": building("Mathematics"),
                "start_time": "08:00",
                "end_time": "09:15",
            },
            {
                "day": "Monday",
                "building": building("Academic"),
                "start_time": "12:00",
                "end_time": "13:15",
            },
            {
                "day": "Monday",
                "building": building("Engineering Technology"),
                "start_time": "17:30",
                "end_time": "18:45",
            },
            {
                "day": "Tuesday",
                "building": building("Joe Mack Wilson"),
                "start_time": "11:00",
                "end_time": "12:15",
            },
        ]
        result = recommend_permit(
            schedule,
            preferences={"walking": 38, "reliability": 42, "shade": 12, "price": 8},
            semester_week=1,
            leave_after={("Monday", "13:15")},
            confidence_simulations=30,
        )
        self.assertEqual(len(result["ranked_permits"]), 6)
        self.assertTrue(result["recommended_permit"])
        self.assertEqual(len(result["priority_tradeoffs"]), 4)
        self.assertEqual(len(result["sessions"]), 3)

    def test_defaults_are_stable_public_api(self):
        self.assertEqual(
            DEFAULT_PREFERENCES,
            {"walking": 50, "reliability": 35, "shade": 10, "price": 5},
        )


if __name__ == "__main__":
    unittest.main()
