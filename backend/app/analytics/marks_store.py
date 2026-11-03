"""Course-scoped incremental marks register. No grading policy or final grading."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
import re

import pandas as pd
from pymongo import ASCENDING

from backend.app.database.mongodb import get_mongodb_database


def _key(value: object) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"(?:[_\-\s])*(?:marks?|scores?)$", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


def _max_column(value: object) -> tuple[str, bool]:
    raw = str(value).strip()
    match = re.search(r"(?:[_\-\s])*(?:max|maximum)(?:[_\-\s]*(?:marks?|scores?))?$", raw, re.I)
    return (raw[:match.start()], True) if match else (raw, False)


def get_marks_collection():
    col = get_mongodb_database()["academic_marks"]
    col.create_index([("course_id", ASCENDING), ("student_id", ASCENDING)], unique=True)
    return col


def _collection():
    return get_marks_collection()


def _uploads():
    col = get_mongodb_database()["academic_marks_uploads"]
    col.create_index([("course_id", ASCENDING), ("uploaded_at", -1)])
    col.create_index([("upload_id", ASCENDING)], unique=True)
    return col


def _resolve_enrolled_students(course_id: str) -> tuple[dict[str, str], set[str]]:
    """Resolve active enrollment IDs to canonical user IDs and roll numbers.

    Some legacy enrollment documents store a roll number instead of the user UUID;
    support both formats while preferring the canonical user UUID when available.
    """
    db = get_mongodb_database()
    enrollment_rows = list(db["course_enrollments"].find(
        {"course_id": course_id, "status": "active"}, {"_id": 0, "student_id": 1}
    ))
    enrolled_ids = {str(row.get("student_id", "")).strip() for row in enrollment_rows if row.get("student_id")}
    if not enrolled_ids:
        return {}, set()

    users = list(db["users"].find(
        {"$or": [{"user_id": {"$in": list(enrolled_ids)}}, {"roll_number": {"$in": list(enrolled_ids)}}]},
        {"_id": 0, "user_id": 1, "roll_number": 1},
    ))
    lookup: dict[str, str] = {}
    canonical_ids: set[str] = set()
    for user in users:
        uid = str(user.get("user_id", "")).strip()
        roll = str(user.get("roll_number", "")).strip()
        if uid:
            canonical_ids.add(uid)
            lookup[uid.casefold()] = uid
            if roll:
                lookup[roll.casefold()] = uid
    # Legacy enrollment records may directly contain a roll number and may not
    # have a corresponding user document. Keep that identifier usable.
    for enrolled_id in enrolled_ids:
        if enrolled_id.casefold() not in lookup:
            lookup[enrolled_id.casefold()] = enrolled_id
            canonical_ids.add(enrolled_id)
    return lookup, canonical_ids


def merge_marks(course_id: str, frame: pd.DataFrame, uploaded_by: str = "", filename: str | None = None) -> dict[str, Any]:
    """Validate and atomically prepare an upload, then merge its assessments.

    A grading policy is deliberately never read. Maximum marks come only from the
    upload or a previously stored value for that student/assessment.
    """
    frame = frame.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    if frame.empty or len(frame.columns) < 2:
        raise ValueError("The marks file must contain a student ID column and at least one assessment column.")
    if not frame.columns.is_unique:
        raise ValueError("The file contains duplicate column names.")

    id_candidates = [column for column in frame.columns if _key(column) in {
        "studentid", "rollnumber", "rollno", "registrationnumber", "studentrollnumber"
    }]
    if len(id_candidates) != 1:
        raise ValueError("Include exactly one student identifier column (student_id or roll_number).")
    id_col = id_candidates[0]

    marks_cols: dict[str, str] = {}
    max_cols: dict[str, str] = {}
    global_max_col: str | None = None
    display_names: dict[str, str] = {}
    for column in frame.columns:
        if column == id_col:
            continue
        compact = re.sub(r"[^a-z0-9]", "", column.lower())
        if compact in {"maxmarks", "maximum", "maximummarks"}:
            if global_max_col:
                raise ValueError("The file contains more than one global maximum-marks column.")
            global_max_col = column
            continue
        base, is_max = _max_column(column)
        key = _key(base)
        if not key:
            raise ValueError(f"Invalid assessment column: {column}")
        target = max_cols if is_max else marks_cols
        if key in target:
            raise ValueError(f"Duplicate assessment column after normalization: {column}")
        target[key] = column
        if not is_max:
            display_names[key] = base.strip()
    if not marks_cols:
        raise ValueError("The marks file does not contain any assessment columns.")
    if global_max_col:
        if len(marks_cols) != 1:
            raise ValueError("A global maximum_marks column can only be used with one assessment column.")
        key = next(iter(marks_cols))
        if key in max_cols:
            raise ValueError("Provide either an assessment-specific maximum column or maximum_marks, not both.")
        max_cols[key] = global_max_col

    lookup, enrolled_ids = _resolve_enrolled_students(course_id)
    # Normalise resolver keys too; this also makes legacy uppercase roll numbers
    # and deterministic test fixtures behave consistently.
    lookup = {str(key).strip().casefold(): str(value).strip() for key, value in lookup.items()}
    enrolled_ids = {str(value).strip() for value in enrolled_ids}
    if not enrolled_ids:
        raise ValueError("There are no actively enrolled students in this course. Marks cannot be uploaded.")

    collection = _collection()
    now = datetime.now(timezone.utc)
    upload_id = str(uuid4())
    prepared: list[dict[str, Any]] = []
    unknown: list[str] = []
    seen: set[str] = set()

    for _, row in frame.iterrows():
        submitted = str(row[id_col]).strip()
        if not submitted or submitted.lower() == "nan":
            raise ValueError("Student identifiers cannot be empty.")
        student_id = lookup.get(submitted.casefold())
        if not student_id or student_id not in enrolled_ids:
            unknown.append(submitted)
            continue
        if student_id in seen:
            raise ValueError(f"Duplicate student '{submitted}' appears more than once in the uploaded file.")
        seen.add(student_id)
        assessment_updates: dict[str, Any] = {}
        for key, source_column in marks_cols.items():
            raw_marks = row[source_column]
            if pd.isna(raw_marks) or str(raw_marks).strip() == "":
                marks = None
            else:
                try:
                    marks = float(raw_marks)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Non-numeric marks found in column '{source_column}'.") from exc
                if marks < 0:
                    raise ValueError(f"Marks cannot be negative in column '{source_column}'.")

            maximum = None
            if key in max_cols:
                raw_max = row[max_cols[key]]
                if pd.notna(raw_max) and str(raw_max).strip():
                    try:
                        maximum = float(raw_max)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"Invalid maximum marks in column '{max_cols[key]}'.") from exc
                    if maximum <= 0:
                        raise ValueError(f"Maximum marks must be positive in column '{max_cols[key]}'.")
            if maximum is None:
                finder = getattr(collection, "find_one", None)
                existing = finder(
                    {"course_id": course_id, "student_id": student_id},
                    {"_id": 0, f"assessments.{key}.maximum_marks": 1},
                ) if finder else None
                existing = existing or {}
                maximum = (existing.get("assessments", {}).get(key, {}) or {}).get("maximum_marks")
            if marks is not None and maximum is not None and marks > float(maximum):
                raise ValueError(f"Marks in '{source_column}' must be between 0 and {maximum}.")
            assessment_updates[key] = {
                "name": display_names[key], "marks": marks, "maximum_marks": maximum,
                "updated_at": now, "source_file_id": upload_id,
            }
        prepared.append({"student_id": student_id, "submitted_identifier": submitted, "assessments": assessment_updates})

    if unknown:
        preview = ", ".join(unknown[:10])
        extra = f" (and {len(unknown) - 10} more)" if len(unknown) > 10 else ""
        raise ValueError(f"These students are not actively enrolled in this course: {preview}{extra}. No marks were saved.")
    if not prepared:
        raise ValueError("No enrolled student rows were found in the uploaded file.")

    # All rows are validated before any write, preventing partial imports.
    for item in prepared:
        fields = {"course_id": course_id, "student_id": item["student_id"], "updated_at": now}
        for key, value in item["assessments"].items():
            fields[f"assessments.{key}"] = value
        collection.update_one(
            {"course_id": course_id, "student_id": item["student_id"]},
            {"$set": fields, "$setOnInsert": {"created_at": now, "uploaded_by": uploaded_by}},
            upsert=True,
        )

    file_doc = {
        "upload_id": upload_id, "course_id": course_id,
        "filename": filename or "marks-upload.csv", "uploaded_by": uploaded_by,
        "uploaded_at": now, "student_count": len(prepared),
        "assessment_names": display_names, "assessment_keys": list(marks_cols),
        "rows": [{"student_id": item["student_id"], "assessments": item["assessments"]} for item in prepared],
        "status": "active",
    }
    _uploads().insert_one(file_doc)
    return {
        "course_id": course_id, "upload_id": upload_id, "filename": file_doc["filename"],
        "students_updated": len(prepared), "assessments_uploaded": list(marks_cols),
        "assessment_names": display_names,
        "message": "Marks uploaded and merged successfully.",
    }


def merge_marks_upload(course_id: str, frame: pd.DataFrame, uploaded_by: str = "test-professor", filename: str | None = None) -> dict[str, Any]:
    return merge_marks(course_id, frame, uploaded_by, filename)


def list_marks_uploads(course_id: str) -> dict[str, Any]:
    docs = list(_uploads().find({"course_id": course_id, "status": "active"}, {"_id": 0, "rows": 0}).sort("uploaded_at", -1))
    return {"course_id": course_id, "uploads": docs, "total_uploads": len(docs)}


def delete_marks_upload(course_id: str, upload_id: str) -> dict[str, Any] | None:
    upload = _uploads().find_one({"course_id": course_id, "upload_id": upload_id, "status": "active"})
    if not upload:
        return None
    marks = _collection()
    fallback = list(_uploads().find(
        {"course_id": course_id, "status": "active", "upload_id": {"$ne": upload_id}}, {"_id": 0}
    ).sort("uploaded_at", -1))
    for row in upload.get("rows", []):
        record = marks.find_one({"course_id": course_id, "student_id": row["student_id"]})
        if not record:
            continue
        set_fields, unset_fields = {}, {}
        for key in upload.get("assessment_keys", []):
            current = record.get("assessments", {}).get(key, {})
            if current.get("source_file_id") != upload_id:
                continue
            replacement = None
            for candidate in fallback:
                candidate_row = next((r for r in candidate.get("rows", []) if r.get("student_id") == row["student_id"]), None)
                if candidate_row and key in candidate_row.get("assessments", {}):
                    replacement = candidate_row["assessments"][key]
                    break
            if replacement is not None:
                set_fields[f"assessments.{key}"] = replacement
            else:
                unset_fields[f"assessments.{key}"] = ""
        update = {}
        if set_fields:
            update["$set"] = set_fields
        if unset_fields:
            update["$unset"] = unset_fields
        if update:
            marks.update_one({"course_id": course_id, "student_id": row["student_id"]}, update)
    _uploads().update_one({"upload_id": upload_id}, {"$set": {"status": "deleted", "deleted_at": datetime.now(timezone.utc)}})
    return {"upload_id": upload_id, "message": "Upload deleted. Marks from newer uploads and manual edits were preserved."}


def edit_student_mark(course_id: str, student_identifier: str, assessment_key: str, marks_value: float | None) -> dict[str, Any] | None:
    lookup, enrolled_ids = _resolve_enrolled_students(course_id)
    lookup = {str(key).strip().casefold(): str(value).strip() for key, value in lookup.items()}
    student_id = lookup.get(student_identifier.strip().casefold())
    if not student_id or student_id not in enrolled_ids:
        raise ValueError("Student is not actively enrolled in this course.")
    key = _key(assessment_key)
    record = _collection().find_one({"course_id": course_id, "student_id": student_id})
    if not record or key not in record.get("assessments", {}):
        return None
    current = record["assessments"][key]
    maximum = current.get("maximum_marks")
    if marks_value is not None:
        if marks_value < 0:
            raise ValueError("Marks cannot be negative.")
        if maximum is not None and marks_value > float(maximum):
            raise ValueError(f"Marks cannot exceed the maximum of {maximum}.")
    updated = {**current, "marks": marks_value, "updated_at": datetime.now(timezone.utc), "source_file_id": None, "manually_edited": True}
    _collection().update_one({"course_id": course_id, "student_id": student_id}, {"$set": {f"assessments.{key}": updated, "updated_at": datetime.now(timezone.utc)}})
    return {"student_id": student_id, "assessment": key, "marks": marks_value, "message": "Marks updated."}


def get_marks_register(course_id: str) -> dict[str, Any]:
    _, enrolled_ids = _resolve_enrolled_students(course_id)
    db = get_mongodb_database()
    records = list(_collection().find({"course_id": course_id, "student_id": {"$in": list(enrolled_ids)}}, {"_id": 0}).sort("student_id", ASCENDING))
    users = list(db["users"].find({"user_id": {"$in": list(enrolled_ids)}}, {"_id": 0, "user_id": 1, "roll_number": 1}))
    roll_by_id = {str(user["user_id"]): str(user.get("roll_number") or user["user_id"]) for user in users}
    # Legacy enrollment records whose student_id is itself a roll number.
    for student_id in enrolled_ids:
        roll_by_id.setdefault(student_id, student_id)
    names: dict[str, str] = {}
    records_by_id = {record["student_id"]: record for record in records}
    for record in records:
        for key, value in record.get("assessments", {}).items():
            names[key] = value.get("name", key)
    students = []
    for student_id in sorted(enrolled_ids, key=lambda value: roll_by_id.get(value, value).casefold()):
        record = records_by_id.get(student_id, {})
        assessments = record.get("assessments", {})
        students.append({
            "student_id": student_id,
            "display_id": roll_by_id.get(student_id, student_id),
            "assessments": {key: assessments.get(key, {}).get("marks") for key in names},
            "assessment_maximums": {key: assessments.get(key, {}).get("maximum_marks") for key in names},
        })
    return {"course_id": course_id, "number_of_students": len(students), "assessment_names": names, "students": students}


def cleanup_unenrolled_marks(course_id: str) -> dict[str, Any]:
    _, enrolled_ids = _resolve_enrolled_students(course_id)
    result = _collection().delete_many({"course_id": course_id, "student_id": {"$nin": list(enrolled_ids)}})
    return {"course_id": course_id, "deleted_records": int(result.deleted_count), "message": "Removed legacy marks records for students who are not actively enrolled in this course."}


def get_student_marks(course_id: str, student_identifiers: list[str]) -> dict[str, Any]:
    record = _collection().find_one({"course_id": course_id, "student_id": {"$in": student_identifiers}}, {"_id": 0})
    if not record:
        return {"course_id": course_id, "assessments": {}}
    return {"course_id": course_id, "assessments": record.get("assessments", {})}
