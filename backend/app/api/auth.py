
import os
import re
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from pymongo.errors import DuplicateKeyError

from backend.app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from backend.app.database.mongodb import get_mongodb_database


router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: str = Field(pattern="^(student|professor)$")
    roll_number: str | None = Field(default=None, min_length=3, max_length=20)
    professor_registration_code: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    users = get_mongodb_database()["users"]
    user = users.find_one(
        {"user_id": payload["sub"], "is_active": True},
        {"_id": 0, "password_hash": 0},
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
        )

    return user

def require_role(required_role: str):
    def role_checker(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        if current_user.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only {required_role}s can access this resource.",
            )
        return current_user

    return role_checker

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    email = str(request.email).strip().lower()
    users = get_mongodb_database()["users"]

    # Professor registration requires a separate code from the server environment.
    if request.role == "professor":
        expected_code = os.getenv("PROFESSOR_REGISTRATION_CODE")
        if (
            not expected_code
            or not request.professor_registration_code
            or request.professor_registration_code != expected_code
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Professor registration is restricted.",
            )

    roll_number = (request.roll_number or "").strip().lower() or None
    if request.role == "student" and roll_number:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,19}", roll_number):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Roll number must contain 3-20 letters, numbers or hyphens.",
            )
        users.create_index("roll_number", unique=True, sparse=True, name="unique_student_roll_number")
        if users.find_one({"roll_number": roll_number}, {"_id": 1}):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A student with this roll number already exists.",
            )

    user = {
        "user_id": str(uuid4()),
        "email": email,
        "password_hash": hash_password(request.password),
        "role": request.role,
        **({"roll_number": roll_number} if request.role == "student" and roll_number else {}),
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }

    # The unique index prevents duplicate email accounts, including race conditions.
    try:
        users.create_index("email", unique=True)
        users.insert_one(user)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc

    return {
        "message": "Account created successfully.",
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "role": user["role"],
            "roll_number": user.get("roll_number"),
        },
    }


@router.post("/login")
def login(request: LoginRequest):
    email = str(request.email).strip().lower()
    users = get_mongodb_database()["users"]
    user = users.find_one({"email": email, "is_active": True})

    if user is None or not verify_password(
        request.password, user.get("password_hash", "")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    public_user = {
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"],
        "roll_number": user.get("roll_number"),
    }

    return {
        "access_token": create_access_token(public_user),
        "token_type": "bearer",
        "expires_in": 3600,
        "user": public_user,
    }


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "role": current_user["role"],
        "roll_number": current_user.get("roll_number"),
    }
