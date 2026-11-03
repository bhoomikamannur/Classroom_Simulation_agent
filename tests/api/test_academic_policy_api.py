def test_grading_policy_routes_are_disabled_for_current_marks_only_phase(professor_client):
    response = professor_client.get("/academic-policies/COURSE1")
    assert response.status_code == 404
