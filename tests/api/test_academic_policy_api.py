
import uuid

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.analytics.policy_store import get_policy_collection


client = TestClient(app)


def test_academic_policy_api_crud_and_validation():
    course_id = f"API_TEST_{uuid.uuid4().hex[:12]}"
    base_url = "/academic-policies"

    policy = {
        "course_id": course_id,
        "assessment_weights": {
            "quiz": 20,
            "assignment": 30,
            "final_exam": 50,
        },
        "assessment_max_marks": {
            "quiz": 10,
            "assignment": 20,
            "final_exam": 100,
        },
        "pass_percentage": 40,
        "missing_marks_policy": "exclude",
    }

    collection = get_policy_collection()

    try:
        # Create a policy
        response = client.post(base_url, json=policy)
        assert response.status_code == 201
        assert response.json()["course_id"] == course_id

        # Retrieve the saved policy
        response = client.get(f"{base_url}/{course_id}")
        assert response.status_code == 200
        assert response.json()["assessment_weights"] == policy[
            "assessment_weights"
        ]

        # Update the policy
        updated_policy = {
            "assessment_weights": {
                "quiz": 25,
                "assignment": 25,
                "final_exam": 50,
            },
            "assessment_max_marks": policy["assessment_max_marks"],
            "pass_percentage": 45,
            "missing_marks_policy": "zero",
        }

        response = client.put(
            f"{base_url}/{course_id}",
            json=updated_policy,
        )
        assert response.status_code == 200
        assert response.json()["pass_percentage"] == 45

        # Reject a duplicate course policy
        response = client.post(base_url, json=policy)
        assert response.status_code == 422

        # Reject weights that do not total 100
        invalid_policy = {
            **policy,
            "course_id": f"{course_id}_INVALID",
            "assessment_weights": {
                "quiz": 20,
                "assignment": 20,
                "final_exam": 50,
            },
        }
        response = client.post(base_url, json=invalid_policy)
        assert response.status_code == 422

        # A missing course policy should return 404
        response = client.get(
            f"{base_url}/MISSING_{uuid.uuid4().hex}"
        )
        assert response.status_code == 404

        # Updating a missing course should return 404
        response = client.put(
            f"{base_url}/MISSING_{uuid.uuid4().hex}",
            json=updated_policy,
        )
        assert response.status_code == 404

    finally:
        # Remove the temporary test record
        collection.delete_one({"course_id": course_id})
