import unittest
from datetime import date

from backend.app.learning.schedule_policy import (
    adaptive_course_allocations,
    calculate_current_week,
    is_carry_forward,
    revision_week_after_assessment,
)


class AdaptiveSemesterPolicyTests(unittest.TestCase):
    def test_week_number_advances_every_seven_days(self):
        start = date(2026, 10, 1)
        self.assertEqual(calculate_current_week(start, date(2026, 10, 1), 16), 1)
        self.assertEqual(calculate_current_week(start, date(2026, 10, 7), 16), 1)
        self.assertEqual(calculate_current_week(start, date(2026, 10, 8), 16), 2)

    def test_past_required_topic_is_carried_into_current_week(self):
        self.assertTrue(is_carry_forward(2, 4, 3))
        self.assertTrue(is_carry_forward(None, 2, 3))
        self.assertFalse(is_carry_forward(3, 5, 3))

    def test_poor_assessment_moves_revision_to_following_week(self):
        self.assertEqual(revision_week_after_assessment(3, 3, 16), 4)
        self.assertEqual(revision_week_after_assessment(2, 4, 16), 4)
        self.assertEqual(revision_week_after_assessment(16, 16, 16), 16)

    def test_low_mastery_course_receives_more_hours_than_strong_course(self):
        topics = [
            {"course_id": "a", "course_name": "Course A", "coverage_status": "not_covered",
             "estimated_effort_hours": 4, "mastery_score": 90},
            {"course_id": "a", "course_name": "Course A", "coverage_status": "mastered",
             "estimated_effort_hours": 1, "mastery_score": 90},
            {"course_id": "b", "course_name": "Course B", "coverage_status": "revision_required",
             "estimated_effort_hours": 4, "mastery_score": 35},
            {"course_id": "b", "course_name": "Course B", "coverage_status": "revision_required",
             "estimated_effort_hours": 4, "mastery_score": 40},
        ]
        allocations = {row["course_id"]: row for row in adaptive_course_allocations(topics, 15)}
        self.assertGreater(allocations["b"]["weekly_hours"], allocations["a"]["weekly_hours"])
        self.assertAlmostEqual(sum(row["weekly_hours"] for row in allocations.values()), 15, places=1)

    def test_all_courses_mastered_reserves_time_for_enrichment(self):
        topics = [
            {"course_id": "a", "course_name": "Course A", "coverage_status": "mastered",
             "estimated_effort_hours": 2, "mastery_score": 95},
            {"course_id": "b", "course_name": "Course B", "coverage_status": "mastered",
             "estimated_effort_hours": 3, "mastery_score": 92},
        ]
        allocations = {row["course_id"]: row for row in adaptive_course_allocations(topics, 10)}
        self.assertAlmostEqual(allocations["a"]["weekly_hours"], 5.0, places=1)
        self.assertAlmostEqual(allocations["b"]["weekly_hours"], 5.0, places=1)

    def test_mastered_course_releases_time_to_courses_with_remaining_work(self):
        topics = [
            {"course_id": "a", "course_name": "Course A", "coverage_status": "mastered",
             "estimated_effort_hours": 2, "mastery_score": 95},
            {"course_id": "b", "course_name": "Course B", "coverage_status": "not_covered",
             "estimated_effort_hours": 5, "mastery_score": None},
        ]
        allocations = {row["course_id"]: row for row in adaptive_course_allocations(topics, 12)}
        self.assertEqual(allocations["a"]["weekly_hours"], 0)
        self.assertEqual(allocations["b"]["weekly_hours"], 12)


if __name__ == "__main__":
    unittest.main()
