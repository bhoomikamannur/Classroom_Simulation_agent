
import json
from typing import Any

from backend.app.llm.ollama_client import generate


INTERVENTION_INSTRUCTIONS = """
You are the Intervention and Teacher Insight Agent in a classroom
simulation system.

YOUR RESPONSIBILITIES:
1. Recommend targeted learning interventions using the supplied diagnosis.
2. Suggest an activity that addresses the identified learning difficulty.
3. Generate a follow-up question that checks the student's understanding.
4. Provide evidence-based insights and actionable recommendations for
   the teacher.

RULES:
- Treat the supplied diagnosis as the source of diagnostic findings.
- Do not independently diagnose the student or invent misconceptions.
- Base recommendations on the provided evidence and course context.
- If evidence is insufficient, recommend gathering more evidence rather
  than assuming the student has a misconception.
- If the student understands the concept, recommend an appropriate
  extension or application activity rather than unnecessary remediation.
- If the student is confused, address the specific reported difficulty.
- If the student is improving, acknowledge progress and recommend a
  follow-up check.
- Distinguish observed evidence from possible explanations.
- Do not claim that an intervention has already worked.
- Use clear, practical language.

Return ONLY valid JSON with this structure:
{
  "student_id": "string",
  "subject_id": "string",
  "intervention": {
    "priority": "high | medium | low",
    "objective": "string",
    "explanation": "string",
    "activity": "string",
    "follow_up_question": "string",
    "success_criteria": "string"
  },
  "teacher_insight": {
    "observed_learning_state": "string",
    "evidence_summary": "string",
    "recommended_teaching_action": "string",
    "next_step": "string"
  }
}
"""


class InterventionAgent:
    """Generate student interventions and teacher insights from a diagnosis."""

    def __init__(self):
        pass

    @staticmethod
    def _serialize(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2)

    @staticmethod
    def _validate_diagnosis(diagnosis: dict[str, Any]) -> None:
        if not isinstance(diagnosis, dict):
            raise ValueError("diagnosis must be a dictionary.")

        if not diagnosis:
            raise ValueError("diagnosis cannot be empty.")

    @staticmethod
    def _parse_response(response: str) -> dict[str, Any]:
        if not isinstance(response, str) or not response.strip():
            raise ValueError("The LLM returned an empty response.")

        text = response.strip()

        # Handle JSON enclosed in Markdown code fences.
        if text.startswith("```"):
            lines = text.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            text = "\n".join(lines).strip()

            if text.lower().startswith("json"):
                text = text[4:].strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "The LLM response was not valid JSON."
            ) from exc

        if not isinstance(result, dict):
            raise ValueError("The LLM response must be a JSON object.")

        required = {"intervention", "teacher_insight"}

        if not required.issubset(result):
            raise ValueError(
                "The LLM response is missing intervention or teacher_insight."
            )

        if not isinstance(result["intervention"], dict):
            raise ValueError("intervention must be a JSON object.")

        if not isinstance(result["teacher_insight"], dict):
            raise ValueError("teacher_insight must be a JSON object.")

        return result

    def generate_recommendations(
        self,
        student_id: str,
        subject_id: str,
        diagnosis: dict[str, Any],
        evidence_interpretation: dict[str, Any] | None = None,
        course_context: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate an intervention and teacher insight from diagnostic output.

        The diagnosis should be the Performance Agent's diagnosis dictionary,
        not the entire Performance Agent result.
        """
        self._validate_diagnosis(diagnosis)

        if evidence_interpretation is None:
            evidence_interpretation = {}

        prompt = f"""
{INTERVENTION_INSTRUCTIONS}

STUDENT ID:
{student_id}

SUBJECT ID:
{subject_id}

COURSE CONTEXT:
{course_context or "No additional course context supplied."}

PERFORMANCE AGENT DIAGNOSIS:
{self._serialize(diagnosis)}

EVIDENCE INTERPRETATION:
{self._serialize(evidence_interpretation)}

Generate an appropriate intervention and teacher insight.
Return only the required JSON object.
"""

        response = generate(prompt)
        result = self._parse_response(response)

        # Keep identity fields consistent with the input.
        result["student_id"] = student_id
        result["subject_id"] = subject_id

        return result

    def analyze(
        self,
        performance_result: dict[str, Any],
        course_context: str | None = None,
    ) -> dict[str, Any]:
        """
        Accept the complete result returned by PerformanceAgent.analyze().
        """
        if not isinstance(performance_result, dict):
            raise ValueError("performance_result must be a dictionary.")

        student_id = performance_result.get("student_id")
        subject_id = performance_result.get("subject_id")
        diagnosis = performance_result.get("diagnosis")
        evidence_interpretation = performance_result.get(
            "evidence_interpretation", {}
        )

        if not student_id or not subject_id:
            raise ValueError(
                "performance_result must contain student_id and subject_id."
            )

        if not isinstance(diagnosis, dict) or not diagnosis:
            raise ValueError(
                "performance_result must contain a non-empty diagnosis."
            )

        return self.generate_recommendations(
            student_id=student_id,
            subject_id=subject_id,
            diagnosis=diagnosis,
            evidence_interpretation=evidence_interpretation,
            course_context=course_context,
        )
