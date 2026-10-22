
from pathlib import Path
from typing import Any

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}
DEFAULT_STUDENT_ID_COLUMNS = (
    "student_id",
    "student id",
    "studentid",
    "roll_no",
    "roll no",
    "roll_number",
    "roll number",
    "id",
)


def load_marks_file(file_path: str | Path) -> pd.DataFrame:
    """Load a CSV or XLSX marks file into a DataFrame."""
    path = Path(file_path)

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Marks file not found: {path}")

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Unsupported file format. Upload a CSV or XLSX file."
        )

    if extension == ".csv":
        df = pd.read_csv(path, dtype=object)
    else:
        df = pd.read_excel(path, dtype=object, engine="openpyxl")

    if df.empty:
        raise ValueError("The uploaded marks file is empty.")

    return df


def _find_student_id_column(
    df: pd.DataFrame,
    requested_column: str | None = None,
) -> str:
    """Find the student identifier column."""
    if requested_column is not None:
        if requested_column not in df.columns:
            raise ValueError(
                f"Student ID column '{requested_column}' was not found."
            )
        return requested_column

    normalized = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for candidate in DEFAULT_STUDENT_ID_COLUMNS:
        if candidate in normalized:
            return normalized[candidate]

    raise ValueError(
        "Could not identify the student ID column. "
        "Provide student_id_column explicitly."
    )


def _prepare_marks(
    df: pd.DataFrame,
    student_id_column: str,
) -> tuple[pd.DataFrame, list[str]]:
    """Validate IDs and convert assessment columns to numeric scores."""
    df = df.copy()
    df.columns = [str(column).strip() for column in df.columns]

    if not df.columns.is_unique:
        raise ValueError(
            "The file contains duplicate column names. "
            "Rename them before uploading."
        )

    if student_id_column not in df.columns:
        raise ValueError(
            f"Student ID column '{student_id_column}' was not found."
        )

    if len(df.columns) < 2:
        raise ValueError(
            "The file must contain a student ID and at least "
            "one assessment column."
        )

    ids = df[student_id_column].astype("string").str.strip()

    if ids.isna().any() or ids.eq("").fillna(False).any():
        raise ValueError(
            "Every row must have a student ID. "
            "Resolve missing IDs before analysis."
        )

    if ids.duplicated().any():
        duplicates = ids[ids.duplicated(keep=False)].unique().tolist()
        raise ValueError(
            f"Duplicate student IDs found: {duplicates[:10]}. "
            "Combine or resolve duplicate records before analysis."
        )

    df[student_id_column] = ids
    assessment_columns = [
        column
        for column in df.columns
        if column != student_id_column
    ]

    for column in assessment_columns:
        original = df[column]
        numeric = pd.to_numeric(original, errors="coerce")

        # Empty cells are missing marks. Non-empty, non-numeric
        # values are rejected instead of silently being discarded.
        invalid = (
            original.notna()
            & original.astype("string").str.strip().ne("")
            & numeric.isna()
        )

        if invalid.any():
            examples = original[invalid].astype(str).unique().tolist()[:5]
            raise ValueError(
                f"Assessment '{column}' contains non-numeric values "
                f"{examples}. Clean these cells before analysis."
            )

        if (numeric.dropna() < 0).any():
            raise ValueError(
                f"Assessment '{column}' contains negative marks."
            )

        df[column] = numeric

    if not df[assessment_columns].notna().any().any():
        raise ValueError("No numeric assessment marks were found.")

    return df, assessment_columns


def analyze_marks(
    df: pd.DataFrame,
    student_id_column: str | None = None,
    assessment_max_marks: dict[str, float] | None = None,
    low_performance_percentile: float = 25.0,
) -> dict[str, Any]:
    """
    Produce descriptive class and student analysis.

    assessment_max_marks maps assessment column names to their
    maximum possible marks, for example:
        {"Quiz 1": 10, "Assignment": 20, "Midsem": 50}

    Assessments without a supplied maximum still receive raw-mark
    statistics, but are excluded from percentage-based comparisons.

    This function does not determine official grades or pass/fail.
    """
    if not 0 <= low_performance_percentile <= 100:
        raise ValueError(
            "low_performance_percentile must be between 0 and 100."
        )

    df = df.copy()
    df.columns = [str(column).strip() for column in df.columns]

    student_id_column = _find_student_id_column(
        df, student_id_column
    )

    df, assessment_columns = _prepare_marks(
        df, student_id_column
    )

    max_marks = assessment_max_marks or {}

    unknown_assessments = set(max_marks) - set(assessment_columns)
    if unknown_assessments:
        raise ValueError(
            "Maximum marks supplied for unknown assessments: "
            f"{sorted(unknown_assessments)}"
        )

    normalized_max_marks: dict[str, float] = {}

    for assessment, maximum in max_marks.items():
        try:
            value = float(maximum)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Maximum marks for '{assessment}' must be numeric."
            ) from exc

        if value <= 0:
            raise ValueError(
                f"Maximum marks for '{assessment}' must be positive."
            )

        if (df[assessment].dropna() > value).any():
            raise ValueError(
                f"Marks in '{assessment}' exceed its maximum of {value}."
            )

        normalized_max_marks[assessment] = value

    # Calculate percentages only when the maximum marks are known.
    percentage_df = pd.DataFrame(index=df.index)

    for assessment, maximum in normalized_max_marks.items():
        percentage_df[assessment] = (
            df[assessment] / maximum * 100
        )

    class_assessments: dict[str, Any] = {}

    for assessment in assessment_columns:
        scores = df[assessment].dropna()

        result: dict[str, Any] = {
            "students_with_marks": int(scores.count()),
            "missing_marks": int(df[assessment].isna().sum()),
            "mean_raw_marks": (
                round(float(scores.mean()), 2)
                if not scores.empty else None
            ),
            "median_raw_marks": (
                round(float(scores.median()), 2)
                if not scores.empty else None
            ),
            "minimum_raw_marks": (
                round(float(scores.min()), 2)
                if not scores.empty else None
            ),
            "maximum_observed_marks": (
                round(float(scores.max()), 2)
                if not scores.empty else None
            ),
        }

        if assessment in normalized_max_marks:
            percentages = percentage_df[assessment].dropna()
            result.update({
                "maximum_possible_marks": normalized_max_marks[assessment],
                "mean_percentage": (
                    round(float(percentages.mean()), 2)
                    if not percentages.empty else None
                ),
                "median_percentage": (
                    round(float(percentages.median()), 2)
                    if not percentages.empty else None
                ),
                "standard_deviation_percentage": (
                    round(float(percentages.std()), 2)
                    if len(percentages) > 1 else None
                ),
            })

        class_assessments[assessment] = result

    # A descriptive average across known-percentage assessments.
    # Missing marks are excluded; this is NOT an official weighted grade.
    if not percentage_df.empty:
        student_average = percentage_df.mean(axis=1)
    else:
        student_average = pd.Series(
            float("nan"), index=df.index
        )

    available_averages = student_average.dropna()

    if not available_averages.empty:
        low_cutoff = float(
            available_averages.quantile(
                low_performance_percentile / 100
            )
        )
    else:
        low_cutoff = None

    students: list[dict[str, Any]] = []

    for index, row in df.iterrows():
        assessment_results: dict[str, Any] = {}

        for assessment in assessment_columns:
            raw_mark = row[assessment]

            assessment_results[assessment] = {
                "marks": (
                    round(float(raw_mark), 2)
                    if pd.notna(raw_mark) else None
                ),
                "maximum_marks": normalized_max_marks.get(assessment),
                "percentage": (
                    round(
                        float(percentage_df.loc[index, assessment]), 2
                    )
                    if (
                        assessment in percentage_df.columns
                        and pd.notna(percentage_df.loc[index, assessment])
                    )
                    else None
                ),
            }

        average = student_average.loc[index]

        if pd.isna(average):
            relative_status = "insufficient_percentage_data"
            average_percentage = None
        else:
            average_percentage = round(float(average), 2)
            relative_status = (
                "lower_performance_group"
                if low_cutoff is not None and average <= low_cutoff
                else "not_in_lower_performance_group"
            )

        students.append({
            "student_id": str(row[student_id_column]),
            "assessments": assessment_results,
            "descriptive_average_percentage": average_percentage,
            "relative_performance": relative_status,
        })

    return {
        "student_id_column": student_id_column,
        "number_of_students": int(len(df)),
        "number_of_assessments": len(assessment_columns),
        "assessment_max_marks": normalized_max_marks,
        "class_assessments": class_assessments,
        "student_summaries": students,
        "relative_performance_threshold": {
            "percentile": low_performance_percentile,
            "cutoff_average_percentage": (
                round(low_cutoff, 2)
                if low_cutoff is not None else None
            ),
        },
        "interpretation_notes": [
            "This report provides descriptive statistics, not official grades.",
            "Missing marks are excluded from averages and are not treated as zero.",
            "The descriptive student average is an unweighted mean of "
            "available assessment percentages with known maximum marks.",
            "A lower relative performance group is not, by itself, "
            "evidence of persistent learning difficulty.",
            "Official evaluation requires the professor's grading scheme.",
        ],
    }


def analyze_marks_file(
    file_path: str | Path,
    student_id_column: str | None = None,
    assessment_max_marks: dict[str, float] | None = None,
    low_performance_percentile: float = 25.0,
) -> dict[str, Any]:
    """Load a marks file and analyze its contents."""
    df = load_marks_file(file_path)

    return analyze_marks(
        df=df,
        student_id_column=student_id_column,
        assessment_max_marks=assessment_max_marks,
        low_performance_percentile=low_performance_percentile,
    )
