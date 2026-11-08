"""Fast synthetic tests for the semester planner's weekly balancing policy."""
import unittest

from backend.app.learning.schedule_policy import select_balanced_week


class SemesterPlannerSchedulingTests(unittest.TestCase):
    def make_weeks(self, count):
        return {i: {"planned_hours": 0.0, "activities": []} for i in range(1, count + 1)}

    def test_ten_topics_spread_across_four_week_unit_window(self):
        weeks = self.make_weeks(4)
        assignments = []
        for _ in range(10):
            w = select_balanced_week([1, 2, 3, 4], weeks, 15, 1.5, 1, 4)
            assignments.append(w)
            weeks[w]["planned_hours"] += 1.5
            weeks[w]["activities"].append({"schedule_type": "required"})
        counts = [assignments.count(i) for i in range(1, 5)]
        self.assertLessEqual(max(counts) - min(counts), 1)

    def test_global_load_balancing_across_overlapping_courses(self):
        weeks = self.make_weeks(4)
        assignments = []
        # Two courses, each with six topics in the same baseline window.
        for _ in range(12):
            w = select_balanced_week([1, 2, 3, 4], weeks, 15, 1.5, 1, 4)
            assignments.append(w)
            weeks[w]["planned_hours"] += 1.5
            weeks[w]["activities"].append({"schedule_type": "required"})
        loads = [weeks[i]["planned_hours"] for i in range(1, 5)]
        self.assertLessEqual(max(loads) - min(loads), 1.5)

    def test_capacity_is_respected_when_feasible(self):
        weeks = self.make_weeks(3)
        for _ in range(6):
            w = select_balanced_week([1, 2, 3], weeks, 3, 1.5, 1, 3)
            weeks[w]["planned_hours"] += 1.5
            weeks[w]["activities"].append({"schedule_type": "required"})
        self.assertTrue(all(v["planned_hours"] <= 3 for v in weeks.values()))

    def test_overflow_still_places_topic_instead_of_dropping_it(self):
        weeks = self.make_weeks(2)
        weeks[1]["planned_hours"] = weeks[2]["planned_hours"] = 3
        chosen = select_balanced_week([1, 2], weeks, 3, 1.5, 1, 2)
        self.assertIn(chosen, (1, 2))


if __name__ == "__main__":
    unittest.main()
