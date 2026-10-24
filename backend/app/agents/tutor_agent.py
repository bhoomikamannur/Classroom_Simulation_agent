
from typing import Any

from backend.app.llm.ollama_client import generate
from backend.app.rag.retriever import retrieve
from backend.app.memory.learning_store import (
    get_or_create_session,
    get_recent_interactions,
    save_interaction,
)


TUTOR_INSTRUCTIONS = """
You are the Tutor Agent in a classroom simulation system.

Your goal is to help the student understand concepts, not simply provide
information.

TEACHING RULES:
- Start with the simplest explanation that answers the student's question.
- For simple questions, keep the response to 2-4 short paragraphs or bullets.
- Prefer one clear example or analogy over several examples.
- If the student says they are confused, change the explanation strategy.
- If the student demonstrates understanding, acknowledge it.
- Ask a comprehension question only when it genuinely helps learning.
- Do not repeat information already established in the conversation.
- Expand the explanation when the student asks for more detail.
- Do not assess or score overall performance. That belongs to the
  Performance and Diagnostic Agent.

COURSE MATERIAL RULES:
- Use relevant course material as the primary academic reference.
- General knowledge may help explain a concept, but distinguish it from
  course-supported information.
- If no relevant course material is found, say so before providing a
  general explanation.

CONVERSATION RULES:
- Use conversation history to understand what the student already knows.
- Treat the current message in the context of the conversation.
- Avoid unnecessary repetition.
"""


class TutorAgent:
    """Course-aware Tutor Agent with MongoDB-backed conversation history."""

    def answer(
        self,
        student_id: str,
        subject_id: str,
        session_id: str,
        message: str,
        top_k: int = 5,
        course_id: str | None = None,
        professor_id: str | None = None,
    ) -> dict[str, Any]:

        student_id = student_id.strip()
        subject_id = subject_id.strip()
        session_id = session_id.strip()
        message = message.strip()

        if not student_id or not subject_id or not session_id:
            raise ValueError(
                "student_id, subject_id and session_id must be non-empty."
            )

        if not message:
            raise ValueError("message must not be empty.")

        # Temporary backward compatibility for callers that have not yet
        # started sending course_id. Replace this fallback with a required
        # course_id after the frontend and course registry are integrated.
        course_id = (course_id or subject_id).strip()

        if not course_id:
            raise ValueError("course_id must be non-empty.")

        # Ensure the session is scoped to this student and course.
        get_or_create_session(
            student_id=student_id,
            course_id=course_id,
            session_id=session_id,
            professor_id=professor_id,
        )

        # Load persistent history before generating the next response.
        history = get_recent_interactions(
            student_id=student_id,
            course_id=course_id,
            session_id=session_id,
            limit=10,
        )

        history_text = "\n".join(
            f"{item['role'].upper()}: {item['content']}"
            for item in history
        )

        if not history_text:
            history_text = "No previous conversation."

        # Retrieve relevant course material.
        # Course-specific filtering of ChromaDB is a separate upcoming step.
        results = retrieve(message, top_k=top_k)

        if results:
            context_parts = [
                f"[Course Material {index}]\n{result['text']}"
                for index, result in enumerate(results, start=1)
            ]
            course_context = "\n\n".join(context_parts)
            material_status = (
                "Relevant course material was found and is provided below."
            )
        else:
            course_context = (
                "No sufficiently relevant course material was found "
                "for this question."
            )
            material_status = (
                "No sufficiently relevant course material was found."
            )

        prompt = f"""
{TUTOR_INSTRUCTIONS}

STUDENT ID:
{student_id}

COURSE ID:
{course_id}

SUBJECT:
{subject_id}

{material_status}

COURSE MATERIAL:
{course_context}

CONVERSATION HISTORY:
{history_text}

CURRENT STUDENT MESSAGE:
{message}

Now respond as a tutor. Focus on the student's current learning need.

TUTOR RESPONSE:
"""

        # Save the student message before generating the answer so it remains
        # available as evidence even if generation fails.
        save_interaction(
            student_id=student_id,
            course_id=course_id,
            session_id=session_id,
            role="user",
            content=message,
        )

        answer = generate(prompt)

        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("The Tutor Agent generated an empty response.")

        answer = answer.strip()

        if not results:
            answer = (
                "Not covered in the provided course material:\n\n" + answer
            )

        # Persist the tutor reply only after generation succeeds.
        save_interaction(
            student_id=student_id,
            course_id=course_id,
            session_id=session_id,
            role="assistant",
            content=answer,
        )

        return {
            "student_id": student_id,
            "course_id": course_id,
            "subject_id": subject_id,
            "session_id": session_id,
            "answer": answer,
            "sources": [
                result.get("metadata", {})
                for result in results
            ],
        }
