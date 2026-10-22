
import pandas as pd
import pytest

from backend.app.analytics.academic_analysis import (
    analyze_marks,
    load_marks_file,
)


def sample_marks():
    return pd.DataFrame({
        "Student ID": ["S001", "S002", "S003"],
        "Quiz 1": [8, 3, 7],
        "Assignment": [17, 9, None],
        "Midsem": [40, 18, 35],
    })


def test_analyzes_multiple_assessments():
    report = analyze_marks(
        sample_marks(),
        assessment_max_marks={
            "Quiz 1": 10,
            "Assignment": 20,
            "Midsem": 50,
        },
    )

    assert report["number_of_students"] == 3
    assert report["number_of_assessments"] == 3
    assert report["class_assessments"]["Quiz 1"]["mean_percentage"] == 60.0
    assert report["class_assessments"]["Assignment"]["missing_marks"] == 1


def test_missing_marks_are_not_treated_as_zero():
    report = analyze_marks(
        sample_marks(),
        assessment_max_marks={
            "Quiz 1": 10,
            "Assignment": 20,
            "Midsem": 50,
        },
    )

    student = next(
        s for s in report["student_summaries"]
        if s["student_id"] == "S003"
    )

    assert student["assessments"]["Assignment"]["marks"] is None
    assert student["descriptive_average_percentage"] == 70.0


def test_unknown_max_marks_do_not_create_percentages():
    report = analyze_marks(sample_marks())

    assert report["class_assessments"]["Quiz 1"]["mean_raw_marks"] == 6.0
    assert "mean_percentage" not in report["class_assessments"]["Quiz 1"]


def test_rejects_duplicate_student_ids():
    df = sample_marks()
    df.loc[1, "Student ID"] = "S001"

    with pytest.raises(ValueError, match="Duplicate student IDs"):
        analyze_marks(df)


def test_rejects_marks_above_maximum():
    df = sample_marks()
    df.loc[0, "Quiz 1"] = 11

    with pytest.raises(ValueError, match="exceed its maximum"):
        analyze_marks(
            df,
            assessment_max_marks={"Quiz 1": 10},
        )



def test_rejects_non_numeric_marks():
    df = sample_marks()
    df["Quiz 1"] = df["Quiz 1"].astype(object)
    df.loc[0, "Quiz 1"] = "not a mark"

    with pytest.raises(ValueError, match="non-numeric"):
        analyze_marks(df)


def test_loads_csv(tmp_path):
    path = tmp_path / "marks.csv"
    sample_marks().to_csv(path, index=False)

    loaded = load_marks_file(path)

    assert len(loaded) == 3
    assert "Student ID" in loaded.columns


def test_loads_excel(tmp_path):
    path = tmp_path / "marks.xlsx"
    sample_marks().to_excel(path, index=False)

    loaded = load_marks_file(path)

    assert len(loaded) == 3
    assert "Student ID" in loaded.columns


def test_rejects_missing_student_id():
    df = sample_marks()
    df.loc[0, "Student ID"] = None

    with pytest.raises(ValueError, match="Every row must have a student ID"):
        analyze_marks(df)


def test_rejects_unknown_assessment_maximum():
    with pytest.raises(ValueError, match="unknown assessments"):
        analyze_marks(
            sample_marks(),
            assessment_max_marks={"Final Exam": 100},
        )


def test_relative_performance_is_not_an_official_grade():
    report = analyze_marks(
        sample_marks(),
        assessment_max_marks={
            "Quiz 1": 10,
            "Assignment": 20,
            "Midsem": 50,
        },
    )

    assert "official_grades" not in report
    assert any(
        "not official grades" in note
        for note in report["interpretation_notes"]
    )
