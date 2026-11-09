from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING

from backend.app.api.auth import get_current_user, require_role
from backend.app.database.mongodb import get_mongodb_database
from backend.app.services.course_access import get_accessible_course
from backend.app.agents.project_analysis_agent import analyse_project_submission
from backend.app.storage.file_storage import save_file, read_file_record

router = APIRouter(prefix="/project-tracker", tags=["Project Tracker"])
BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_UPLOADS = BACKEND_ROOT / "data" / "project_uploads"
MAX_FILE_BYTES = 30 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".md", ".zip", ".png", ".jpg", ".jpeg", ".webp", ".csv", ".py", ".js", ".ts", ".ipynb"}


def _db():
    return get_mongodb_database()


def _now():
    return datetime.now(timezone.utc)


def _ensure_indexes():
    _db()["course_projects"].create_index([("project_id", ASCENDING)], unique=True)
    _db()["course_projects"].create_index([("course_id", ASCENDING), ("created_at", DESCENDING)])
    _db()["student_projects"].create_index([("student_project_id", ASCENDING)], unique=True)
    _db()["student_projects"].create_index([("course_project_id", ASCENDING), ("student_id", ASCENDING)], unique=True)
    _db()["student_projects"].create_index([("student_id", ASCENDING), ("updated_at", DESCENDING)])
    _db()["project_milestones"].create_index([("milestone_id", ASCENDING)], unique=True)
    _db()["project_milestones"].create_index([("course_project_id", ASCENDING), ("due_date", ASCENDING)])
    _db()["project_submissions"].create_index([("submission_id", ASCENDING)], unique=True)
    _db()["project_submissions"].create_index([("student_project_id", ASCENDING), ("created_at", DESCENDING)])
    _db()["project_reviews"].create_index([("review_id", ASCENDING)], unique=True)
    _db()["project_activity"].create_index([("student_project_id", ASCENDING), ("created_at", DESCENDING)])
    _db()["project_analyses"].create_index([("analysis_id", ASCENDING)], unique=True)
    _db()["project_analyses"].create_index([("submission_id", ASCENDING), ("created_at", DESCENDING)])


class CourseProjectCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=10, max_length=6000)
    objectives: list[str] = Field(default_factory=list, max_length=30)
    requirements: list[str] = Field(default_factory=list, max_length=50)
    publish: bool = True


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=4000)
    due_date: datetime
    is_mandatory: bool = True


class MilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=4000)
    due_date: datetime | None = None
    is_mandatory: bool | None = None


class ReviewCreate(BaseModel):
    decision: str = Field(pattern="^(approved|revision_requested|rejected|needs_clarification)$")
    feedback: str = Field(min_length=1, max_length=6000)


def _course_project_or_404(project_id: str) -> dict:
    item = _db()["course_projects"].find_one({"project_id": project_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Course project not found.")
    return item


def _student_project_or_404(student_project_id: str) -> dict:
    item = _db()["student_projects"].find_one({"student_project_id": student_project_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Student project not found.")
    return item


def _require_project_owner(course_project: dict, user: dict):
    if course_project.get("professor_id") != user.get("user_id"):
        raise HTTPException(status_code=403, detail="You do not own this course project.")
    get_accessible_course(course_project["course_id"], user)


def _require_student_project_access(student_project: dict, user: dict):
    if student_project.get("status") == "archived":
        raise HTTPException(status_code=410, detail="This project has been archived by the professor.")
    if user.get("role") == "student":
        if student_project.get("student_id") != user.get("user_id"):
            raise HTTPException(status_code=404, detail="Project not found.")
        get_accessible_course(student_project["course_id"], user)
    elif user.get("role") == "professor":
        project = _course_project_or_404(student_project["course_project_id"])
        _require_project_owner(project, user)
    else:
        raise HTTPException(status_code=403, detail="Access denied.")


def _sync_project_assignments(project: dict):
    """Create individual workspaces for active course members not yet assigned."""
    if project.get("status") != "published":
        return
    enrollments = list(_db()["course_enrollments"].find(
        {"course_id": project["course_id"], "status": "active"}, {"_id": 0, "student_id": 1}
    ))
    existing = {row["student_id"] for row in _db()["student_projects"].find(
        {"course_project_id": project["project_id"]}, {"_id": 0, "student_id": 1}
    )}
    missing = [row["student_id"] for row in enrollments if row.get("student_id") not in existing]
    if not missing:
        return
    identities = list(_db()["users"].find(
        {"user_id": {"$in": missing}, "role": "student", "is_active": True},
        {"_id": 0, "user_id": 1, "email": 1, "roll_number": 1}
    ))
    identity_map = {row["user_id"]: row for row in identities}
    for student_id in missing:
        identity = identity_map.get(student_id)
        if not identity:
            continue
        now = _now()
        record = {
            "student_project_id": str(uuid4()), "course_project_id": project["project_id"],
            "course_id": project["course_id"], "course_name": project.get("course_name"),
            "student_id": student_id, "student_email": identity.get("email"),
            "roll_number": identity.get("roll_number"), "professor_id": project["professor_id"],
            "title": project["title"], "status": "proposal_pending",
            "proposal_status": "not_submitted", "created_at": now, "updated_at": now,
        }
        _db()["student_projects"].update_one(
            {"course_project_id": project["project_id"], "student_id": student_id},
            {"$setOnInsert": record}, upsert=True,
        )
    count = _db()["student_projects"].count_documents({"course_project_id": project["project_id"]})
    _db()["course_projects"].update_one({"project_id": project["project_id"]}, {"$set": {"assigned_student_count": count}})


def _public_file(file_record: dict | None):
    if not file_record:
        return None
    return {key: file_record.get(key) for key in ("file_id", "filename", "file_type", "file_size", "uploaded_at")}


def _log(student_project_id: str, course_project_id: str, course_id: str, actor: dict, action: str, details: str = ""):
    _db()["project_activity"].insert_one({
        "activity_id": str(uuid4()), "student_project_id": student_project_id,
        "course_project_id": course_project_id, "course_id": course_id,
        "actor_id": actor["user_id"], "actor_role": actor["role"],
        "action": action, "details": details, "created_at": _now(),
    })


@router.post("/courses/{course_id}/projects", status_code=201)
def create_course_project(course_id: str, request: CourseProjectCreate, user: dict = Depends(require_role("professor"))):
    _ensure_indexes()
    course = get_accessible_course(course_id, user)
    title = request.title.strip()
    description = request.description.strip()
    if not title or not description:
        raise HTTPException(status_code=422, detail="Title and description cannot be blank.")

    # Reuse the existing course_enrollments and users collections as the source of truth.
    enrollments = list(_db()["course_enrollments"].find(
        {"course_id": course_id, "status": "active"},
        {"_id": 0, "student_id": 1},
    ))
    student_ids = list(dict.fromkeys(row["student_id"] for row in enrollments))
    users = list(_db()["users"].find(
        {"user_id": {"$in": student_ids}, "role": "student", "is_active": True},
        {"_id": 0, "user_id": 1, "email": 1, "roll_number": 1},
    ))
    user_map = {item["user_id"]: item for item in users}

    now = _now()
    project_id = str(uuid4())
    project = {
        "project_id": project_id, "course_id": course_id,
        "course_name": course.get("name"), "professor_id": user["user_id"],
        "title": title, "description": description,
        "objectives": [item.strip() for item in request.objectives if item.strip()],
        "requirements": [item.strip() for item in request.requirements if item.strip()],
        "status": "published" if request.publish else "draft",
        "assigned_student_count": 0, "created_at": now, "updated_at": now,
    }
    _db()["course_projects"].insert_one(project)
    project.pop("_id", None)

    created = []
    if request.publish:
        for student_id in student_ids:
            identity = user_map.get(student_id, {})
            record = {
                "student_project_id": str(uuid4()), "course_project_id": project_id,
                "course_id": course_id, "course_name": course.get("name"),
                "student_id": student_id, "student_email": identity.get("email"),
                "roll_number": identity.get("roll_number"),
                "professor_id": user["user_id"], "title": title,
                "status": "proposal_pending", "proposal_status": "not_submitted",
                "created_at": now, "updated_at": now,
            }
            _db()["student_projects"].insert_one(record)
            created.append(record["student_project_id"])
            _log(record["student_project_id"], project_id, course_id, user, "project_assigned", "Course project published to enrolled class")
        _db()["course_projects"].update_one({"project_id": project_id}, {"$set": {"assigned_student_count": len(created)}})

    project["assigned_student_count"] = len(created)
    return {"message": "Course project created and assigned to enrolled students.", "project": project, "assigned_students": len(created)}


@router.post("/projects/{project_id}/brief", status_code=201)
async def upload_course_project_brief(project_id: str, file: UploadFile = File(...), user: dict = Depends(require_role("professor"))):
    _ensure_indexes()
    project = _course_project_or_404(project_id)
    _require_project_owner(project, user)
    if Path(file.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="The course project brief must be a PDF.")
    stored = await _save_upload(file, user)
    _db()["course_projects"].update_one({"project_id": project_id}, {"$set": {"brief_file": stored, "updated_at": _now()}})
    return {"message": "Course project brief uploaded.", "brief_file": _public_file(stored)}


@router.get("/courses/{course_id}/projects")
def list_course_projects(course_id: str, user: dict = Depends(require_role("professor"))):
    _ensure_indexes()
    get_accessible_course(course_id, user)
    projects = list(_db()["course_projects"].find(
        {"course_id": course_id, "professor_id": user["user_id"], "is_deleted": {"$ne": True}}, {"_id": 0}
    ).sort("created_at", DESCENDING))
    for project in projects:
        _sync_project_assignments(project)
        if project.get("brief_file"):
            project["brief_file"] = _public_file(project["brief_file"])
        instances = list(_db()["student_projects"].find(
            {"course_project_id": project["project_id"]},
            {"_id": 0, "student_project_id": 1, "student_id": 1, "roll_number": 1, "student_email": 1, "status": 1, "proposal_status": 1, "updated_at": 1},
        ).sort("roll_number", ASCENDING))
        project["students"] = instances
        project["assigned_student_count"] = len(instances)
    return {"course_id": course_id, "projects": projects}


@router.delete("/projects/{project_id}")
def archive_course_project(project_id: str, user: dict = Depends(require_role("professor"))):
    """Soft-delete a course project while retaining submissions and audit history."""
    project = _course_project_or_404(project_id)
    _require_project_owner(project, user)
    if project.get("is_deleted"):
        return {"message": "Project is already deleted."}
    now = _now()
    _db()["course_projects"].update_one(
        {"project_id": project_id},
        {"$set": {"status": "archived", "is_deleted": True, "deleted_at": now,
                  "deleted_by": user["user_id"], "updated_at": now}},
    )
    instances = list(_db()["student_projects"].find(
        {"course_project_id": project_id}, {"_id": 0, "student_project_id": 1, "course_id": 1}
    ))
    for instance in instances:
        _db()["student_projects"].update_one(
            {"student_project_id": instance["student_project_id"]},
            {"$set": {"status": "archived", "updated_at": now}},
        )
        _log(instance["student_project_id"], project_id, instance["course_id"], user,
             "project_archived", "Professor archived the course project")
    return {"message": "Project deleted from active tracking. Submission and activity history were retained."}


@router.get("/mine")
def list_my_projects(user: dict = Depends(require_role("student"))):
    _ensure_indexes()
    # Late enrollees receive any already-published course projects automatically.
    enrollments = list(_db()["course_enrollments"].find({"student_id": user["user_id"], "status": "active"}, {"_id": 0, "course_id": 1}))
    course_ids = [row["course_id"] for row in enrollments]
    for course_project in _db()["course_projects"].find({"course_id": {"$in": course_ids}, "status": "published"}, {"_id": 0}):
        _sync_project_assignments(course_project)
    projects = list(_db()["student_projects"].find({"student_id": user["user_id"], "status": {"$ne": "archived"}}, {"_id": 0}).sort("updated_at", DESCENDING))
    for item in projects:
        item["course_project"] = _db()["course_projects"].find_one({"project_id": item["course_project_id"]}, {"_id": 0, "objectives": 1, "requirements": 1, "description": 1, "status": 1, "brief_file": 1})
        if item.get("course_project") and item["course_project"].get("brief_file"):
            item["course_project"]["brief_file"] = _public_file(item["course_project"]["brief_file"])
        item["milestones"] = list(_db()["project_milestones"].find({"course_project_id": item["course_project_id"], "is_deleted": {"$ne": True}}, {"_id": 0}).sort("due_date", ASCENDING))
        item["submissions"] = list(_db()["project_submissions"].find({"student_project_id": item["student_project_id"]}, {"_id": 0, "file.file_path": 0}).sort("created_at", DESCENDING))
        for submission in item["submissions"]:
            submission["file"] = _public_file(submission.get("file"))
            submission["files"] = [_public_file(item) for item in submission.get("files", [])] or ([submission["file"]] if submission.get("file") else [])
        item["latest_submission"] = item["submissions"][0] if item["submissions"] else None
        item["reviews"] = list(_db()["project_reviews"].find({"student_project_id": item["student_project_id"]}, {"_id": 0}).sort("created_at", DESCENDING))
    return {"projects": projects}


@router.get("/projects/{project_id}/students")
def list_project_students(project_id: str, user: dict = Depends(require_role("professor"))):
    _ensure_indexes()
    project = _course_project_or_404(project_id)
    _require_project_owner(project, user)
    instances = list(_db()["student_projects"].find({"course_project_id": project_id}, {"_id": 0}).sort("roll_number", ASCENDING))
    for instance in instances:
        instance["submissions"] = list(_db()["project_submissions"].find({"student_project_id": instance["student_project_id"]}, {"_id": 0, "file.file_path": 0, "files.file_path": 0}).sort("created_at", DESCENDING))
        for submission in instance["submissions"]:
            submission["file"] = _public_file(submission.get("file"))
            submission["files"] = [_public_file(item) for item in submission.get("files", [])] or ([submission["file"]] if submission.get("file") else [])
        instance["reviews"] = list(_db()["project_reviews"].find({"student_project_id": instance["student_project_id"]}, {"_id": 0}).sort("created_at", ASCENDING))
    milestones = list(_db()["project_milestones"].find(
        {"course_project_id": project_id, "is_deleted": {"$ne": True}}, {"_id": 0}
    ).sort("due_date", ASCENDING))
    return {"project": project, "students": instances, "milestones": milestones}


@router.post("/projects/{project_id}/milestones", status_code=201)
def create_milestone(project_id: str, request: MilestoneCreate, user: dict = Depends(require_role("professor"))):
    _ensure_indexes()
    project = _course_project_or_404(project_id)
    _require_project_owner(project, user)
    milestone = {
        "milestone_id": str(uuid4()), "course_project_id": project_id,
        "course_id": project["course_id"], "title": request.title.strip(),
        "description": request.description.strip(), "due_date": request.due_date,
        "is_mandatory": request.is_mandatory, "created_by": user["user_id"],
        "created_at": _now(),
    }
    _db()["project_milestones"].insert_one(milestone)
    milestone.pop("_id", None)
    instances = list(_db()["student_projects"].find({"course_project_id": project_id}, {"_id": 0, "student_project_id": 1}))
    for instance in instances:
        _db()["student_projects"].update_one({"student_project_id": instance["student_project_id"]}, {"$set": {"updated_at": _now()}})
        _log(instance["student_project_id"], project_id, project["course_id"], user, "milestone_added", request.title.strip())
    return {"message": "Milestone added for the course project.", "milestone": milestone}


@router.put("/milestones/{milestone_id}")
def update_milestone(milestone_id: str, request: MilestoneUpdate, user: dict = Depends(require_role("professor"))):
    _ensure_indexes()
    milestone = _db()["project_milestones"].find_one({"milestone_id": milestone_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not milestone:
        raise HTTPException(status_code=404, detail="Checkpoint not found.")
    project = _course_project_or_404(milestone["course_project_id"])
    _require_project_owner(project, user)
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one checkpoint field to update.")
    if "title" in updates:
        if updates["title"] is None:
            raise HTTPException(status_code=422, detail="Checkpoint title cannot be null.")
        updates["title"] = updates["title"].strip()
        if not updates["title"]:
            raise HTTPException(status_code=422, detail="Checkpoint title cannot be blank.")
    if "description" in updates:
        updates["description"] = (updates["description"] or "").strip()
    if "due_date" in updates and updates["due_date"] is None:
        raise HTTPException(status_code=422, detail="Checkpoint deadline cannot be null.")
    if "is_mandatory" in updates and updates["is_mandatory"] is None:
        raise HTTPException(status_code=422, detail="Mandatory flag cannot be null.")
    updates.update({"updated_at": _now(), "updated_by": user["user_id"]})
    _db()["project_milestones"].update_one({"milestone_id": milestone_id}, {"$set": updates})
    updated = _db()["project_milestones"].find_one({"milestone_id": milestone_id}, {"_id": 0})
    instances = list(_db()["student_projects"].find({"course_project_id": project["project_id"]}, {"_id": 0, "student_project_id": 1}))
    for instance in instances:
        _log(instance["student_project_id"], project["project_id"], project["course_id"], user, "milestone_updated", updated.get("title", milestone["title"]))
    return {"message": "Checkpoint updated.", "milestone": updated}


@router.delete("/milestones/{milestone_id}")
def delete_milestone(milestone_id: str, user: dict = Depends(require_role("professor"))):
    """Soft-delete a checkpoint so existing submissions retain their milestone reference."""
    _ensure_indexes()
    milestone = _db()["project_milestones"].find_one({"milestone_id": milestone_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not milestone:
        raise HTTPException(status_code=404, detail="Checkpoint not found.")
    project = _course_project_or_404(milestone["course_project_id"])
    _require_project_owner(project, user)
    _db()["project_milestones"].update_one(
        {"milestone_id": milestone_id},
        {"$set": {"is_deleted": True, "deleted_at": _now(), "deleted_by": user["user_id"]}},
    )
    instances = list(_db()["student_projects"].find({"course_project_id": project["project_id"]}, {"_id": 0, "student_project_id": 1}))
    for instance in instances:
        _log(instance["student_project_id"], project["project_id"], project["course_id"], user, "milestone_deleted", milestone["title"])
    return {"message": "Checkpoint deleted."}


@router.get("/projects/{project_id}/milestones")
def list_milestones(project_id: str, user: dict = Depends(get_current_user)):
    _ensure_indexes()
    project = _course_project_or_404(project_id)
    if user.get("role") == "professor":
        _require_project_owner(project, user)
    else:
        get_accessible_course(project["course_id"], user)
    milestones = list(_db()["project_milestones"].find({"course_project_id": project_id, "is_deleted": {"$ne": True}}, {"_id": 0}).sort("due_date", ASCENDING))
    return {"milestones": milestones}


async def _save_upload(file: UploadFile, actor: dict) -> dict:
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix or 'no extension'}.")
    data = await file.read(MAX_FILE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Maximum upload size is 30 MB.")
    file_id = str(uuid4())
    save_file(
        file_id,
        filename,
        data,
        metadata={"file_id": file_id, "uploaded_by": actor["user_id"], "file_type": suffix.lstrip(".")},
    )
    return {
        "file_id": file_id,
        "storage_file_id": file_id,
        "storage_provider": "gridfs",
        "filename": filename,
        "file_type": suffix.lstrip("."),
        "file_size": len(data),
        "uploaded_by": actor["user_id"],
        "uploaded_at": _now(),
    }


@router.post("/student-projects/{student_project_id}/proposal", status_code=201)
async def submit_proposal(student_project_id: str, description: str = Form(default=""), file: UploadFile = File(...), user: dict = Depends(require_role("student"))):
    _ensure_indexes()
    instance = _student_project_or_404(student_project_id)
    _require_student_project_access(instance, user)
    if instance.get("proposal_status") == "approved":
        raise HTTPException(status_code=409, detail="The proposal is already approved. Contact your professor if a scope change is needed.")
    stored = await _save_upload(file, user)
    version = _db()["project_submissions"].count_documents({
        "student_project_id": student_project_id, "submission_type": "proposal"
    }) + 1
    submission = {
        "submission_id": str(uuid4()), "student_project_id": student_project_id,
        "course_project_id": instance["course_project_id"], "course_id": instance["course_id"],
        "student_id": user["user_id"], "milestone_id": None, "submission_type": "proposal",
        "version": version, "description": description.strip(), "file": stored,
        "status": "submitted", "created_at": _now(),
    }
    _db()["project_submissions"].insert_one(submission)
    submission.pop("_id", None)
    _db()["student_projects"].update_one({"student_project_id": student_project_id}, {"$set": {"proposal_status": "submitted", "status": "proposal_under_review", "updated_at": _now()}})
    _log(student_project_id, instance["course_project_id"], instance["course_id"], user, "proposal_submitted", stored["filename"])
    return {"message": "Proposal submitted successfully.", "submission": {**submission, "file": _public_file(stored)}}


@router.post("/student-projects/{student_project_id}/submissions", status_code=201)
async def submit_deliverable(student_project_id: str, description: str = Form(default=""), milestone_id: str | None = Form(default=None), files: list[UploadFile] = File(default=[]), file: UploadFile | None = File(default=None), user: dict = Depends(require_role("student"))):
    _ensure_indexes()
    instance = _student_project_or_404(student_project_id)
    _require_student_project_access(instance, user)
    if instance.get("proposal_status") != "approved":
        raise HTTPException(status_code=409, detail="Your proposal must be approved before submitting project progress.")
    if milestone_id:
        milestone = _db()["project_milestones"].find_one({"milestone_id": milestone_id, "course_project_id": instance["course_project_id"]})
        if not milestone:
            raise HTTPException(status_code=404, detail="Milestone not found for this project.")
    uploads = list(files or [])
    if file is not None:
        uploads.append(file)
    if not uploads:
        raise HTTPException(status_code=400, detail="Choose at least one deliverable file.")
    if len(uploads) > 10:
        raise HTTPException(status_code=400, detail="You can submit up to 10 files at a time.")
    stored_files = [await _save_upload(upload, user) for upload in uploads]
    stored = stored_files[0]
    version_query = {
        "student_project_id": student_project_id, "submission_type": "progress",
        "milestone_id": milestone_id,
    }
    version = _db()["project_submissions"].count_documents(version_query) + 1
    submission = {
        "submission_id": str(uuid4()), "student_project_id": student_project_id,
        "course_project_id": instance["course_project_id"], "course_id": instance["course_id"],
        "student_id": user["user_id"], "milestone_id": milestone_id,
        "submission_type": "progress", "version": version, "description": description.strip(),
        "file": stored, "files": stored_files, "status": "submitted", "created_at": _now(),
    }
    _db()["project_submissions"].insert_one(submission)
    submission.pop("_id", None)
    _db()["student_projects"].update_one({"student_project_id": student_project_id}, {"$set": {"status": "submission_under_review", "updated_at": _now()}})
    _log(student_project_id, instance["course_project_id"], instance["course_id"], user, "progress_submitted", stored["filename"])
    return {"message": "Project deliverable submitted successfully.", "submission": {**submission, "file": _public_file(stored), "files": [_public_file(item) for item in stored_files]}}


@router.get("/student-projects/{student_project_id}/submissions")
def list_submissions(student_project_id: str, user: dict = Depends(get_current_user)):
    _ensure_indexes()
    instance = _student_project_or_404(student_project_id)
    _require_student_project_access(instance, user)
    records = list(_db()["project_submissions"].find({"student_project_id": student_project_id}, {"_id": 0, "file.file_path": 0}).sort("created_at", DESCENDING))
    for record in records:
        record["file"] = _public_file(record.get("file"))
        record["files"] = [_public_file(item) for item in record.get("files", [])] or ([record["file"]] if record.get("file") else [])
    return {"submissions": records}


@router.post("/submissions/{submission_id}/review", status_code=201)
def review_submission(submission_id: str, request: ReviewCreate, user: dict = Depends(require_role("professor"))):
    _ensure_indexes()
    submission = _db()["project_submissions"].find_one({"submission_id": submission_id}, {"_id": 0})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found.")
    instance = _student_project_or_404(submission["student_project_id"])
    project = _course_project_or_404(instance["course_project_id"])
    _require_project_owner(project, user)
    review = {
        "review_id": str(uuid4()), "submission_id": submission_id,
        "student_project_id": instance["student_project_id"],
        "course_project_id": project["project_id"], "course_id": project["course_id"],
        "student_id": instance["student_id"], "professor_id": user["user_id"],
        "decision": request.decision, "feedback": request.feedback.strip(), "created_at": _now(),
    }
    _db()["project_reviews"].insert_one(review)
    review.pop("_id", None)
    if submission["submission_type"] == "proposal":
        proposal_status = "approved" if request.decision == "approved" else "revision_requested" if request.decision == "revision_requested" else request.decision
        status_value = "active" if request.decision == "approved" else "proposal_revision_requested" if request.decision == "revision_requested" else "proposal_under_review"
        _db()["student_projects"].update_one({"student_project_id": instance["student_project_id"]}, {"$set": {"proposal_status": proposal_status, "status": status_value, "updated_at": _now()}})
    else:
        _db()["project_submissions"].update_one({"submission_id": submission_id}, {"$set": {"status": request.decision}})
        _db()["student_projects"].update_one({"student_project_id": instance["student_project_id"]}, {"$set": {"status": "active" if request.decision == "approved" else "changes_requested" if request.decision == "revision_requested" else "active", "updated_at": _now()}})
    _log(instance["student_project_id"], project["project_id"], project["course_id"], user, "submission_reviewed", request.decision)
    return {"message": "Review recorded.", "review": review}


@router.post("/submissions/{submission_id}/analysis")
def analyse_submission(submission_id: str, user: dict = Depends(require_role("professor"))):
    """Run AI comparison for a submitted checkpoint and persist its advisory report."""
    _ensure_indexes()
    submission = _db()["project_submissions"].find_one({"submission_id": submission_id}, {"_id": 0})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found.")
    if submission.get("submission_type") != "progress":
        raise HTTPException(status_code=400, detail="AI alignment analysis is available for progress submissions after proposal approval.")
    instance = _student_project_or_404(submission["student_project_id"])
    project = _course_project_or_404(instance["course_project_id"])
    _require_project_owner(project, user)
    if instance.get("proposal_status") != "approved":
        raise HTTPException(status_code=409, detail="The student's proposal must be approved before alignment analysis.")
    proposal_candidates = list(_db()["project_submissions"].find(
        {"student_project_id": instance["student_project_id"], "submission_type": "proposal"},
        {"_id": 0},
    ).sort("created_at", DESCENDING))
    approved_proposal = None
    for candidate in proposal_candidates:
        approved_review = _db()["project_reviews"].find_one(
            {"submission_id": candidate["submission_id"], "decision": "approved"}, {"_id": 0}
        )
        if approved_review:
            approved_proposal = candidate
            break
    proposal = approved_proposal or (proposal_candidates[0] if proposal_candidates else None)
    if not proposal:
        raise HTTPException(status_code=409, detail="No submitted proposal was found for comparison.")
    milestone = None
    if submission.get("milestone_id"):
        milestone = _db()["project_milestones"].find_one(
            {"milestone_id": submission["milestone_id"]}, {"_id": 0}
        )
    previous_reviews = list(_db()["project_reviews"].find(
        {"student_project_id": instance["student_project_id"], "submission_id": {"$ne": submission_id}},
        {"_id": 0},
    ).sort("created_at", ASCENDING))
    try:
        report = analyse_project_submission(
            project=project, proposal_submission=proposal, submission=submission,
            milestone=milestone, previous_reviews=previous_reviews,
        )
    except (RuntimeError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail=f"Project analysis unavailable: {exc}") from exc
    report.update({"analysis_id": str(uuid4()), "submission_id": submission_id,
                   "student_project_id": instance["student_project_id"],
                   "course_project_id": project["project_id"], "course_id": project["course_id"],
                   "student_id": instance["student_id"], "created_at": _now(),
                   "analysed_by": user["user_id"]})
    _db()["project_analyses"].insert_one(report)
    report.pop("_id", None)
    _db()["project_submissions"].update_one({"submission_id": submission_id}, {"$set": {"analysis": report}})
    _log(instance["student_project_id"], project["project_id"], project["course_id"], user, "ai_analysis_completed", submission.get("file", {}).get("filename", "submission"))
    return {"analysis": report}


@router.get("/student-projects/{student_project_id}/activity")
def list_activity(student_project_id: str, user: dict = Depends(get_current_user)):
    _ensure_indexes()
    instance = _student_project_or_404(student_project_id)
    _require_student_project_access(instance, user)
    activity = list(_db()["project_activity"].find({"student_project_id": student_project_id}, {"_id": 0}).sort("created_at", DESCENDING))
    return {"activity": activity}


@router.get("/files/{file_id}")
def download_project_file(file_id: str, user: dict = Depends(get_current_user)):
    _ensure_indexes()
    submission = _db()["project_submissions"].find_one(
        {"$or": [{"file.file_id": file_id}, {"files.file_id": file_id}]}, {"_id": 0}
    )
    if submission:
        instance = _student_project_or_404(submission["student_project_id"])
        _require_student_project_access(instance, user)
        file_record = next((item for item in submission.get("files", []) if item.get("file_id") == file_id), None)
        if file_record is None and submission.get("file", {}).get("file_id") == file_id:
            file_record = submission["file"]
        if file_record is None:
            raise HTTPException(status_code=404, detail="File not found.")
    else:
        project = _db()["course_projects"].find_one({"brief_file.file_id": file_id}, {"_id": 0})
        if not project:
            raise HTTPException(status_code=404, detail="File not found.")
        get_accessible_course(project["course_id"], user)
        file_record = project["brief_file"]
    try:
        data = read_file_record(file_record)
    except (FileNotFoundError, OSError, RuntimeError):
        raise HTTPException(status_code=404, detail="Stored file is unavailable.")
    from urllib.parse import quote
    filename = file_record.get("filename", "project-file")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/student-projects/{student_project_id}/reviews")
def list_reviews(student_project_id: str, user: dict = Depends(get_current_user)):
    _ensure_indexes()
    instance = _student_project_or_404(student_project_id)
    _require_student_project_access(instance, user)
    reviews = list(_db()["project_reviews"].find({"student_project_id": student_project_id}, {"_id": 0}).sort("created_at", DESCENDING))
    return {"reviews": reviews}
