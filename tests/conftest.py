
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api.auth import get_current_user


STUDENT_USER = {
    "user_id": "test-student-001",
    "email": "student@test.com",
    "role": "student",
    "is_active": True,
}

PROFESSOR_USER = {
    "user_id": "test-professor-001",
    "email": "professor@test.com",
    "role": "professor",
    "is_active": True,
}


@pytest.fixture
def student_client():
    app.dependency_overrides[get_current_user] = lambda: STUDENT_USER

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def professor_client():
    app.dependency_overrides[get_current_user] = lambda: PROFESSOR_USER

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)
