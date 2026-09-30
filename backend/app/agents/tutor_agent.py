from typing import Any

from backend.app.llm.ollama_client import generate
from backend.app.rag.retriever import retrieve


TUTOR_INSTRUCTIONS = """
You are the Tutor Agent in a classroom simulation system.

Your goal is to help the student understand concepts, not simply provide
information.

TEACHING RULES:
- Your goal is to help the student understand the concept, not to provide an
  exhaustive explanation.
- Start with the simplest explanation that answers the student's question.
- For simple questions, keep the response to 2–4 short paragraphs or bullets.
- Do not list every characteristic, component, application, or related concept
  unless it is necessary for understanding the student's question.
- Prefer one clear example or analogy over several examples.
- If the student says they are confused, change the explanation strategy rather
  than repeating the same explanation.
- If the student demonstrates understanding, acknowledge it and continue
  naturally.
- Ask a comprehension question only when it would genuinely help learning.
- Do not mechanically ask a question after every response.
- Do not repeat information that has already been established in the
  conversation.
- Expand the explanation when the student explicitly asks for more detail,
  examples, or deeper understanding.
- Do not assess or score the student's overall performance. That belongs to the
  Performance and Diagnostic Agent.

COURSE MATERIAL RULES:
- When relevant course material is provided, use it as the primary academic
  reference.
- You may add general knowledge when it genuinely helps the student understand.
- Never present general knowledge as if it came from the course material.
- If no relevant course material is available, clearly indicate that the topic
  is not covered in the provided course material before giving a general
  explanation.
- Do not introduce general claims, examples, or terminology as if they came
  from the course material.
- When additional general knowledge is useful, keep it clearly distinguishable
  from the course-supported explanation.

CONVERSATION RULES:
- Use the conversation history to understand what the student already knows
  and what they are currently confused about.
- Treat the current student message in the context of the conversation.
- Avoid unnecessary repetition.
"""


class TutorAgent:
    """Tutor Agent for conversational, course-aware teaching."""

    def __init__(self):
        self.sessions: dict[str, list[dict[str, str]]] = {}

    def answer(
        self,
        student_id: str,
        subject_id: str,
        session_id: str,
        message: str,
        top_k: int = 5,
    ) -> dict[str, Any]:

        # Keep student, subject, and session separate.
        session_key = f"{student_id}:{subject_id}:{session_id}"

        history = self.sessions.setdefault(session_key, [])

        # Retrieve relevant course material.
        results = retrieve(message, top_k=top_k)

        if results:
            context_parts = []

            for index, result in enumerate(results, start=1):
                context_parts.append(
                    f"[Course Material {index}]\n"
                    f"{result['text']}"
                )

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

        # Format recent conversation history.
        history_text = "\n".join(
            f"{item['role'].upper()}: {item['content']}"
            for item in history[-10:]
        )

        if not history_text:
            history_text = "No previous conversation."

        prompt = f"""
{TUTOR_INSTRUCTIONS}

STUDENT ID:
{student_id}

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

        answer = generate(prompt)

        if not results:
            answer = (
                "💡 Not covered in the provided course material:\n\n"
                + answer
            )

        history.append({
            "role": "user",
            "content": message,
        })

        history.append({
            "role": "assistant",
            "content": answer,
        })

        return {
            "student_id": student_id,
            "subject_id": subject_id,
            "session_id": session_id,
            "answer": answer,
            "sources": [
                result.get("metadata", {})
                for result in results
            ],
        }