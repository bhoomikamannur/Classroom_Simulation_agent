from backend.app.api.learning_plans import _allocate_weeks


def test_week_allocation_covers_full_semester_without_gaps():
    units = [
        {"title": "Unit 1", "topics": ["A", "B"]},
        {"title": "Unit 2", "topics": ["C", "D", "E"]},
        {"title": "Unit 3", "topics": ["F"]},
    ]
    result = _allocate_weeks(units, 16)
    assert result[0]["start_week"] == 1
    assert result[-1]["end_week"] == 16
    assert sum(unit["duration_weeks"] for unit in result) == 16
    for previous, current in zip(result, result[1:]):
        assert current["start_week"] == previous["end_week"] + 1
    assert all(unit["duration_weeks"] >= 1 for unit in result)


def test_week_allocation_gives_more_time_to_units_with_more_topics():
    units = [
        {"title": "Small", "topics": ["A"]},
        {"title": "Large", "topics": ["B", "C", "D", "E"]},
    ]
    result = _allocate_weeks(units, 10)
    assert result[1]["duration_weeks"] > result[0]["duration_weeks"]
