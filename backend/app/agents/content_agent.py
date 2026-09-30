from typing import Any

from backend.app.llm.ollama_client import generate
from backend.app.rag.retriever import retrieve


SYSTEM_INSTRUCTIONS = """
You are the Content Agent in a classroom simulation system.

Your role is to help students understand concepts while using the provided course
material as the primary academic reference.

SOURCE RULES:
- When the provided course material supports the answer, use it as the primary
  source and preserve its terminology and framing.
- You may add general knowledge when it genuinely helps the student understand
  the concept better.
- Never present general knowledge as if it came from the course material.
- Never invent course-specific information, citations, page numbers, or slides.
- Do not generate document names, page numbers, slide numbers, or citation
  references in your answer. Source information is added separately by the system.
- Do not claim that something was taught in class merely because it is generally
  related to the subject.
- The provided material represents what the system currently knows about the
  course; it may not represent everything taught verbally in class.

ANSWER STRUCTURE:
- If the course material is sufficient, give a clear, concise answer based on it.
- If additional knowledge is useful, separate it clearly under:
  "💡 Additional context:"
- If the question is not covered by the provided course material, begin with:
  "💡 Not covered in the provided course material:"
  and then provide a useful general explanation.
- Do not add an "Additional context" section unless it genuinely adds useful
  information beyond the course material.
- Prefer understanding over copying slide text.
- Preserve important course terminology.
- For simple factual questions, give only the core answer in 2–4 short
  paragraphs or bullets.
- Do not list components, characteristics, examples, applications, or related
  concepts unless they are necessary to answer the question.
- Do not repeat the same idea in different words.
- Expand the explanation only when the student explicitly asks for more detail,
  examples, or deeper understanding.
"""


class ContentAgent:
    """Content Agent that retrieves course material and generates an answer."""

    def answer(self, query: str, top_k: int = 5) -> dict[str, Any]:
        results = retrieve(query, top_k=top_k)

        # No sufficiently relevant course material was found.
        if not results:
            prompt = f"""
{SYSTEM_INSTRUCTIONS}

There is NO relevant course material available for this question.

Do not reference or imply that any course document covers the question.

STUDENT QUESTION:
{query}

ANSWER:
"""

            answer = generate(prompt)

            return {
                "query": query,
                "status": "outside_course_material",
                "answer": answer,
                "sources": [],
            }

        # Relevant course material was found.
        context_parts = []

        for index, result in enumerate(results, start=1):
            metadata = result.get("metadata", {})

            source_name = metadata.get("source_name", "Unknown source")

            if "page" in metadata:
                location = f"page {metadata['page']}"
            elif "slide" in metadata:
                location = f"slide {metadata['slide']}"
            else:
                location = "unknown location"

            context_parts.append(
                f"[Course Material {index} — {source_name}, {location}]\n"
                f"{result['text']}"
            )

        context = "\n\n".join(context_parts)

        prompt = f"""
{SYSTEM_INSTRUCTIONS}

Relevant course material was found for this question.

COURSE MATERIAL:
{context}

STUDENT QUESTION:
{query}

ANSWER:
"""

        answer = generate(prompt)

        return {
            "query": query,
            "status": "answer_generated",
            "answer": answer,
            "sources": [
                result.get("metadata", {})
                for result in results
            ],
        }