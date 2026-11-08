import unittest

from backend.app.analytics.academic_risk import analyse_assessment_risk


def record(student_id, **assessments):
    return {"student_id": student_id, "assessments": assessments}


class AcademicRiskTests(unittest.TestCase):
    def test_single_low_quiz_is_not_high_alert(self):
        student = record("s1", quiz1={"name": "Quiz 1", "marks": 4, "maximum_marks": 10})
        peers = [
            student,
            record("s2", quiz1={"marks": 8, "maximum_marks": 10}),
            record("s3", quiz1={"marks": 7, "maximum_marks": 10}),
        ]
        result = analyse_assessment_risk("s1", student, peers, {}, [])
        self.assertTrue(result["available"])
        self.assertFalse(result["high_alert"])
        self.assertEqual(result["poor_assessment_count"], 1)
        self.assertEqual(result["assessments"][0]["class_average_percentage"], 63.3)

    def test_repeated_low_scores_trigger_high_alert(self):
        student = record(
            "s1",
            quiz1={"name": "Quiz 1", "marks": 3, "maximum_marks": 10},
            quiz2={"name": "Quiz 2", "marks": 4, "maximum_marks": 10},
            midsem={"name": "Midsem", "marks": 18, "maximum_marks": 50},
        )
        peers = [
            student,
            record("s2", quiz1={"marks": 8, "maximum_marks": 10},
                   quiz2={"marks": 8, "maximum_marks": 10},
                   midsem={"marks": 38, "maximum_marks": 50}),
            record("s3", quiz1={"marks": 7, "maximum_marks": 10},
                   quiz2={"marks": 7, "maximum_marks": 10},
                   midsem={"marks": 35, "maximum_marks": 50}),
        ]
        result = analyse_assessment_risk("s1", student, peers, {}, [])
        self.assertTrue(result["high_alert"])
        self.assertGreaterEqual(result["score"], 65)
        self.assertEqual(result["poor_assessment_count"], 3)

    def test_same_assessment_previous_score_is_reported(self):
        student = record("s1", quiz1={
            "name": "Quiz 1", "marks": 5, "maximum_marks": 10,
            "history": [
                {"marks": 8, "maximum_marks": 10, "recorded_at": "2026-10-01"},
                {"marks": 5, "maximum_marks": 10, "recorded_at": "2026-10-08"},
            ],
        })
        result = analyse_assessment_risk("s1", student, [student], {}, [
            {"assessment_key": "quiz1", "marks": 8, "maximum_marks": 10, "recorded_at": "2026-10-01"},
            {"assessment_key": "quiz1", "marks": 5, "maximum_marks": 10, "recorded_at": "2026-10-08"},
        ])
        item = result["assessments"][0]
        self.assertEqual(item["previous_percentage"], 80.0)
        self.assertEqual(item["change_from_previous"], -30.0)

    def test_improving_score_does_not_trigger_high_alert(self):
        student = record(
            "s1",
            quiz1={"name": "Quiz 1", "marks": 8, "maximum_marks": 10},
            quiz2={"name": "Quiz 2", "marks": 8, "maximum_marks": 10},
        )
        history = [
            {"assessment_key": "quiz1", "marks": 3, "maximum_marks": 10, "recorded_at": "2026-10-01"},
            {"assessment_key": "quiz1", "marks": 8, "maximum_marks": 10, "recorded_at": "2026-10-08"},
            {"assessment_key": "quiz2", "marks": 4, "maximum_marks": 10, "recorded_at": "2026-10-01"},
            {"assessment_key": "quiz2", "marks": 8, "maximum_marks": 10, "recorded_at": "2026-10-08"},
        ]
        result = analyse_assessment_risk("s1", student, [student], {}, history)
        self.assertFalse(result["high_alert"])
        self.assertEqual([row["change_from_previous"] for row in result["assessments"]], [50.0, 40.0])

    def test_two_isolated_low_assessments_among_many_do_not_create_consistency_alert(self):
        student = record("s1", **{
            "quiz1": {"marks": 3, "maximum_marks": 10},
            "quiz2": {"marks": 4, "maximum_marks": 10},
            "quiz3": {"marks": 8, "maximum_marks": 10},
            "quiz4": {"marks": 8, "maximum_marks": 10},
            "quiz5": {"marks": 8, "maximum_marks": 10},
        })
        result = analyse_assessment_risk("s1", student, [student], {}, [])
        self.assertFalse(result["high_alert"])
        self.assertFalse(result["assessments"] is None)
        self.assertFalse(any(item["issue"] == "Consistently low assessment performance" for item in result["evidence"]))

    def test_no_marks_returns_unavailable(self):
        result = analyse_assessment_risk("s1", record("s1"), [record("s1")], {}, [])
        self.assertFalse(result["available"])
        self.assertEqual(result["assessments"], [])

    def test_different_maximum_marks_are_normalized(self):
        student = record("s1", midsem={"name": "Midsem", "marks": 30, "maximum_marks": 50})
        peers = [student, record("s2", midsem={"marks": 40, "maximum_marks": 50})]
        result = analyse_assessment_risk("s1", student, peers, {"assessment_weights": {"midsem": 2}}, [])
        self.assertEqual(result["assessments"][0]["student_percentage"], 60.0)
        self.assertEqual(result["assessments"][0]["class_average_percentage"], 70.0)


if __name__ == "__main__":
    unittest.main()
