from typing import Any
import json
import re

from backend.app.llm.ollama_client import generate
from backend.app.rag.course_context import build_course_context


PERFORMANCE_INSTRUCTIONS = """
You are the Performance & Diagnostic Agent in a classroom simulation system.

YOUR ROLE:
Analyze evidence from a student's learning interactions and determine what
those interactions indicate about the student's current understanding.

You are a diagnostic agent, NOT a tutor.

IMPORTANT:
You must compare the student's substantive responses against the provided
COURSE REFERENCE.

You must NOT rely on outside knowledge when deciding whether a student
statement is correct or incorrect.

Your job is to interpret evidence. The Python diagnostic layer will determine
the final learning state.

RESPONSIBILITIES:
- Identify the concept being discussed.
- Identify substantive claims made by the student.
- Compare those claims with the course reference.
- Determine whether each substantive claim is aligned with, conflicts with,
  or cannot be evaluated against the course reference.
- Track changes across the student's interaction.
- Give greater importance to later substantive responses when they provide
  stronger evidence of understanding.
- Identify demonstrated misconceptions.
- Do not treat tutor statements as evidence of student understanding.

EVIDENCE RULES:
- A pure question such as "What is planning?" is not evidence of understanding.
- A statement such as "I don't understand planning" is not evidence of a
  misconception.
- A question containing a proposed mental model can be evidence.
  Example:
  "So planning is basically reasoning?"
- A student explanation or claim is substantive evidence.
- Tutor responses are context only.
- Never invent student statements.

CLASSIFICATION RULES:

- "aligned" means the student's claim is consistent with the definition
  of the concept in the course reference.

- "conflict" means the student's claim defines the concept as something
  different from the course definition, especially when the student
  substitutes one course concept for another.

- If the course reference explicitly distinguishes two concepts, and the
  student treats those concepts as the same thing, classify the student's
  statement as "conflict".

- Do not classify a statement as "aligned" merely because it contains
  words or ideas that are related to the correct concept.

- Evaluate the central claim of the student's statement.

- For example, if the course says:
    Planning = deciding actions to achieve a goal
    Memory = retaining previous information

  and the student says:
    "Planning means remembering previous information."

  the classification MUST be "conflict".

- If a student says that memory provides information that planning can use,
  that can be "aligned", because this does not equate memory with planning.

- A student's statement can mention a correct consequence or related idea
  while still being conceptually incorrect. Evaluate the student's actual
  definition, not isolated words.

COURSE REFERENCE:
- Use the provided course reference as the authoritative reference.
- If the student's claim agrees with the course reference, mark it "aligned".
- If the student's claim contradicts the course reference, mark it "conflict".
- If the course reference does not provide enough information to evaluate the
  claim, mark it "uncertain".
- Do not use outside knowledge to make the comparison.

OUTPUT:

Return ONLY valid JSON.

{
  "concept": "main concept being discussed",
  "evidence_analysis": [
    {
      "student_statement": "exact or near-exact student statement",
      "central_claim": "what the student is actually claiming",
      "classification": "aligned | conflict | uncertain",
      "reason": "brief comparison with the course reference"
    }
  ]
}

IMPORTANT — CENTRAL CLAIM FIDELITY:

The central_claim must faithfully represent what the student ACTUALLY
said or believes.

Do NOT rewrite, repair, improve, correct, or reinterpret the student's
claim into a course-aligned statement before classification.

The process MUST be:

1. First extract the student's actual central claim.
2. Then compare that claim against the COURSE REFERENCE.
3. Then assign aligned, conflict, or uncertain.

The central_claim describes the student's mental model, not the correct
answer.

Example:

COURSE REFERENCE:
Planning = deciding a sequence of actions or subgoals to achieve a goal.
Memory = retaining information from previous interactions.

STUDENT:
"Planning means remembering previous information."

CORRECT:
{
  "central_claim": "The student believes that planning means remembering previous information.",
  "classification": "conflict"
}

INCORRECT:
{
  "central_claim": "Planning uses memory to determine the actions needed.",
  "classification": "aligned"
}

The incorrect version changes the student's meaning and MUST NOT be used.

Another example:

STUDENT:
"Yes, planning means using previous information to decide what happened."

The central claim must preserve the student's actual assertion.

Do NOT transform it into:
"Planning uses memory to help decide actions."

That would change the student's meaning.

If the student's statement contains a correct-related word such as
"decide", "use", "information", "action", or "goal", do not assume the
overall claim is correct. Evaluate what the student is asserting about
the concept.

If the student is incorrectly defining one concept using another
concept, preserve that incorrect definition in central_claim and then
classify it as conflict.

CONCEPT DISTINCTION:

If the course reference distinguishes two concepts, determine whether
the student is:

- saying that one concept IS the other concept → conflict
- saying that one concept USES or interacts with the other → this may be
  aligned, depending on the course reference
- describing a relationship that the course reference does not establish
  → uncertain

Do not infer a correct relationship merely because one concept can
reasonably be related to another.

UNCERTAINTY:

If the student says:

"I don't understand planning."
"I am confused about planning."
"What is planning?"

do not invent a central claim from the course definition.

For such statements, use:

"central_claim": "The student states that they do not understand planning."

and classify it as "uncertain".

NEVER replace an uncertain student's statement with the course definition.

TRAJECTORY AND CONTEXT:

Interpret each substantive student response in the context of the
student's preceding responses.

Do not assume that a later statement represents a new or corrected
understanding simply because it contains words associated with the
correct concept.

A later response should be classified as aligned only when the student's
conceptual model has actually changed or the student explicitly
distinguishes previously confused concepts.

If the student previously equated two concepts and a later response
continues that same conceptual model using slightly different wording,
the later response remains conflict.

Example:

1. Student:
"Planning means remembering previous information."

→ conflict

2. Student:
"So planning is basically the agent remembering what happened before?"

→ conflict

3. Student:
"Yes, planning means using previous information to decide what happened."

The third statement must remain conflict if the student is continuing
the same planning = memory mental model.

Do NOT classify the third statement as aligned merely because it contains
the word "decide" or describes memory as being used in a decision.

To classify a later response as aligned, look for evidence that the
student has actually corrected the misconception.

For example:

"Planning decides what actions to take, while memory stores previous
information that planning can use."

→ aligned

The important distinction is whether the student's mental model changed,
not whether the latest sentence contains words related to the correct
definition.

CLASSIFICATION CONSISTENCY:

The classification MUST be consistent with the reason.

If the reason states or implies that the student's claim:
- conflicts with the course reference,
- equates two concepts that the course distinguishes,
- continues a previously identified misconception,
- remains based on an incorrect conceptual model,
- or does not fully align with the course definition,

then the classification MUST be "conflict".

Do NOT classify such a response as "aligned" merely because part of
the student's statement describes a relationship that is valid in the
course.

For example:

Previous student model:
"Planning means remembering previous information."

Later:
"Yes, planning means using previous information to decide what happened."

If the student's conceptual model still treats planning as remembering
or using memory as the definition of planning, this remains "conflict".

The fact that planning may use information from memory does not make
the student's definition of planning correct.

"Aligned" should mean that the student's ACTUAL conceptual model is
consistent with the course reference, not merely that some relationship
mentioned in the statement is valid.

NEVER produce a response where:
classification = "aligned"
while the reason says that the student's claim is conflicting,
incorrect, unresolved, continues a misconception, or does not fully
align with the course reference.

FINAL CHECK BEFORE OUTPUT:

For every evidence item, ask:

"Does my central_claim describe what the student believes, or did I
accidentally write what the student SHOULD believe?"

If it describes what the student SHOULD believe, rewrite it before
classifying.

Then ask:

"Does the classification follow from comparing that faithful student
claim with the course reference?"

Return ONLY valid JSON.

Do not include markdown fences.
Do not include additional fields.


"""


class PerformanceAgent:
    """Analyzes student interactions and produces a learning diagnosis."""

    # ================================================================
    # 1. EVIDENCE CLASSIFICATION
    # ================================================================

    def classify_evidence(
        self,
        interactions: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Deterministically identify whether the student has provided
        substantive evidence.

        This method does NOT determine whether the student is correct.
        """

        student_messages = [
            item.get("content", "").strip()
            for item in interactions
            if item.get("role", "").lower() == "user"
            and item.get("content", "").strip()
        ]

        if not student_messages:
            return {
                "state": "insufficient_evidence",
                "student_messages": [],
                "substantive_messages": [],
                "reason": "No student-generated messages were provided.",
            }

        uncertainty_phrases = (
            "i don't understand",
            "i do not understand",
            "i'm confused",
            "i am confused",
            "i don't get it",
            "i do not get it",
            "can you explain",
            "what does this mean",
            "what is",
            "what are",
            "how does this work",
            "can you clarify",
        )

        proposed_understanding_markers = (
            "so ",
            "then ",
            "does that mean",
            "is that why",
            "is it correct that",
            "am i right that",
            "basically",
        )

        substantive_messages = []

        for message in student_messages:
            normalized = message.lower().strip()

            is_uncertainty_statement = normalized.startswith(
                uncertainty_phrases
            )

            is_question = normalized.endswith("?")

            contains_proposed_understanding = any(
                marker in normalized
                for marker in proposed_understanding_markers
            )

            # A pure question is not evidence.
            #
            # However, a question containing a proposed mental model
            # is evidence because it reveals what the student currently
            # believes.
            if is_question:
                if contains_proposed_understanding:
                    substantive_messages.append(message)

                continue

            # Pure uncertainty is not evidence of understanding.
            if is_uncertainty_statement:
                continue

            # Other student-generated statements are potentially
            # substantive evidence.
            substantive_messages.append(message)

        if not substantive_messages:
            return {
                "state": "insufficient_evidence",
                "student_messages": student_messages,
                "substantive_messages": [],
                "reason": (
                    "The student has expressed questions or uncertainty, "
                    "but has not provided substantive evidence of "
                    "understanding."
                ),
            }

        return {
            "state": "evidence_available",
            "student_messages": student_messages,
            "substantive_messages": substantive_messages,
            "reason": (
                "The student has provided substantive responses or "
                "proposed understandings."
            ),
        }

    # ================================================================
    # 2. PARSE LLM RESPONSE
    # ================================================================

    def parse_llm_response(
        self,
        response: str,
    ) -> dict[str, Any]:
        """
        Parse and validate the structured JSON returned by Qwen.
        """

        if not isinstance(response, str):
            return {
                "concept": "",
                "evidence_analysis": [],
            }

        cleaned = response.strip()

        # Remove markdown fences if Qwen adds them.
        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        try:
            data = json.loads(cleaned)

        except json.JSONDecodeError:

            # Try extracting a JSON object from surrounding text.
            match = re.search(
                r"\{.*\}",
                cleaned,
                flags=re.DOTALL,
            )

            if not match:
                return {
                    "concept": "",
                    "evidence_analysis": [],
                }

            try:
                data = json.loads(match.group(0))

            except json.JSONDecodeError:
                return {
                    "concept": "",
                    "evidence_analysis": [],
                }

        if not isinstance(data, dict):
            return {
                "concept": "",
                "evidence_analysis": [],
            }

        # ------------------------------------------------------------
        # Concept
        # ------------------------------------------------------------

        concept = data.get("concept", "")

        if not isinstance(concept, str):
            concept = str(concept)

        concept = concept.strip()

        # ------------------------------------------------------------
        # Evidence analysis
        # ------------------------------------------------------------

        evidence_analysis = data.get(
            "evidence_analysis",
            [],
        )

        if not isinstance(evidence_analysis, list):
            evidence_analysis = []

        valid_classifications = {
            "aligned",
            "conflict",
            "uncertain",
        }

        validated_analysis = []

        for item in evidence_analysis:

            if not isinstance(item, dict):
                continue

            student_statement = item.get(
                "student_statement",
                "",
            )

            central_claim = item.get(
                "central_claim",
                "",
            )

            classification = item.get(
                "classification",
                "uncertain",
            )

            reason = item.get(
                "reason",
                "",
            )

            if not isinstance(student_statement, str):
                student_statement = str(student_statement)

            if not isinstance(central_claim, str):
                central_claim = str(central_claim)

            if not isinstance(reason, str):
                reason = str(reason)

            if classification not in valid_classifications:
                classification = "uncertain"

            student_statement = student_statement.strip()
            central_claim = central_claim.strip()
            reason = reason.strip()

            if not student_statement:
                continue

            validated_analysis.append(
                {
                    "student_statement": student_statement,
                    "central_claim": central_claim,
                    "classification": classification,
                    "reason": reason,
                }
            )

        return {
            "concept": concept,
            "evidence_analysis": validated_analysis,
        }

    # ================================================================
    # 3. DETERMINE FINAL LEARNING STATE
    # ================================================================

    def determine_learning_state(
        self,
        evidence_analysis: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Determine the final learning state from ordered substantive
        evidence.

        Later evidence has greater weight.

        Rules:

        conflict → conflict → conflict
            => confused

        conflict → aligned
            => understood

        uncertainty → aligned
            => understood

        conflict → uncertain
            => partial
        """

        if not evidence_analysis:
            return {
                "understanding": "insufficient_evidence",
                "confidence": "low",
            }

        classifications = [
            item.get(
                "classification",
                "uncertain",
            )
            for item in evidence_analysis
        ]

        latest = classifications[-1]

        conflict_count = classifications.count(
            "conflict"
        )

        aligned_count = classifications.count(
            "aligned"
        )

        # ------------------------------------------------------------
        # Repeated conflict.
        #
        # If the student repeatedly demonstrates the same conflict
        # and the latest response is still conflicting, the student
        # currently holds a persistent misconception.
        # ------------------------------------------------------------

        if conflict_count >= 2 and latest == "conflict":
            return {
                "understanding": "confused",
                "confidence": "high",
            }

        # ------------------------------------------------------------
        # Latest aligned response.
        #
        # A later demonstrated understanding can override earlier
        # confusion or incorrect hypotheses.
        # ------------------------------------------------------------

        if latest == "aligned":
            return {
                "understanding": "understood",
                "confidence": "high",
            }

        # ------------------------------------------------------------
        # Latest conflict.
        # ------------------------------------------------------------

        if latest == "conflict":
            return {
                "understanding": "confused",
                "confidence": "medium",
            }

        # ------------------------------------------------------------
        # Latest response uncertain.
        # ------------------------------------------------------------

        if latest == "uncertain":

            if aligned_count > 0:
                return {
                    "understanding": "partial",
                    "confidence": "medium",
                }

            if conflict_count > 0:
                return {
                    "understanding": "partial",
                    "confidence": "medium",
                }

            return {
                "understanding": "partial",
                "confidence": "low",
            }

        return {
            "understanding": "insufficient_evidence",
            "confidence": "low",
        }

    # ================================================================
    # 4. BUILD FINAL DIAGNOSIS
    # ================================================================

    def build_diagnosis(
        self,
        interpretation: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convert Qwen's evidence interpretation into the final
        Performance Agent diagnosis.
        """

        concept = interpretation.get(
            "concept",
            "",
        ).strip()

        evidence_analysis = interpretation.get(
            "evidence_analysis",
            [],
        )

        state = self.determine_learning_state(
            evidence_analysis
        )

        understanding = state["understanding"]
        confidence = state["confidence"]

        # ------------------------------------------------------------
        # Only include substantive student evidence.
        #
        # Pure uncertainty such as:
        # "I don't understand planning"
        #
        # should not appear as evidence of understanding.
        # ------------------------------------------------------------

        evidence = []

        for item in evidence_analysis:

            statement = item.get(
                "student_statement",
                "",
            ).strip()

            if not statement:
                continue

            # Don't treat pure uncertainty statements as evidence.
            normalized = statement.lower()

            uncertainty_only = (
                normalized.startswith("i don't understand")
                or normalized.startswith("i do not understand")
                or normalized.startswith("i'm confused")
                or normalized.startswith("i am confused")
                or normalized.startswith("i don't get it")
                or normalized.startswith("i do not get it")
            )

            if uncertainty_only:
                continue

            evidence.append(statement)

        # ------------------------------------------------------------
        # Misconceptions
        # ------------------------------------------------------------

        misconceptions = []

        for item in evidence_analysis:

            if item.get("classification") != "conflict":
                continue

            reason = item.get(
                "reason",
                "",
            ).strip()

            if reason and reason not in misconceptions:
                misconceptions.append(reason)

        # ------------------------------------------------------------
        # Strengths
        # ------------------------------------------------------------

        strengths = []

        if understanding == "understood":
            strengths.append(
                f"Demonstrated understanding of {concept} "
                "through a course-aligned explanation."
            )

        # ------------------------------------------------------------
        # Weaknesses
        # ------------------------------------------------------------

        weaknesses = []

        if understanding == "confused":

            if misconceptions:
                weaknesses.append(
                    misconceptions[-1]
                )
            else:
                weaknesses.append(
                    f"Current understanding of {concept} "
                    "conflicts with the course reference."
                )

        elif understanding == "partial":

            weaknesses.append(
                f"Understanding of {concept} remains incomplete "
                "or contains unresolved uncertainty."
            )

        # ------------------------------------------------------------
        # Overall observation
        # ------------------------------------------------------------

        if understanding == "understood":

            observation = (
                f"The student's latest substantive response is "
                f"consistent with the course reference for {concept}."
            )

        elif understanding == "confused":

            observation = (
                f"The student's latest substantive response conflicts "
                f"with the course reference for {concept}."
            )

            if len(misconceptions) >= 2:
                observation += (
                    " The conflicting interpretation appears repeatedly "
                    "across the interaction."
                )

        elif understanding == "partial":

            observation = (
                f"The student shows partial understanding of {concept}, "
                "but the available evidence does not demonstrate a "
                "consistently course-aligned understanding."
            )

        else:

            observation = (
                "There is insufficient evidence to determine "
                "the student's understanding."
            )

        concept_result = {
            "concept": concept or "Unknown",
            "understanding": understanding,
            "evidence": evidence,
            "misconceptions": misconceptions,
        }

        return {
            "concepts": [concept_result],
            "strengths": strengths,
            "weaknesses": weaknesses,
            "overall_observation": observation,
            "confidence": confidence,
        }

    # ================================================================
    # 5. MAIN ANALYSIS
    # ================================================================

    def analyze(
        self,
        student_id: str,
        subject_id: str,
        interactions: list[dict[str, str]],
        course_context: str | None = None,
    ) -> dict[str, Any]:

        # ------------------------------------------------------------
        # STEP 1 — Deterministic evidence check
        # ------------------------------------------------------------

        evidence = self.classify_evidence(
            interactions
        )

        if evidence["state"] == "insufficient_evidence":

            return {
                "student_id": student_id,
                "subject_id": subject_id,
                "diagnosis": {
                    "concepts": [],
                    "strengths": [],
                    "weaknesses": [],
                    "overall_observation": evidence["reason"],
                    "confidence": "low",
                },
            }

        # ------------------------------------------------------------
        # STEP 2 — Course context
        # ------------------------------------------------------------

        if not course_context:
            student_query = "\n".join(
                item.get("content", "").strip()
                for item in interactions
                if item.get("role", "").lower() == "user"
                and item.get("content", "").strip()
            )

            try:
                course_context = build_course_context(student_query)
            except Exception:
                # Retrieval failure must not crash diagnosis.
                # Without course material, the LLM must not use
                # outside knowledge to decide correctness.
                course_context = None

        if not course_context:
            course_context = (
                "No relevant course reference was retrieved or provided. "
                "Do not assume whether the student's statements are "
                "correct or incorrect based on outside knowledge. "
                "Classify claims as uncertain when the reference is "
                "insufficient to evaluate them."
            )


        # ------------------------------------------------------------
        # STEP 3 — Separate student evidence and tutor context
        # ------------------------------------------------------------

        student_evidence = []
        tutor_context = []

        for item in interactions:

            role = item.get(
                "role",
                ""
            ).lower()

            content = item.get(
                "content",
                ""
            ).strip()

            if not content:
                continue

            if role == "user":

                student_evidence.append(
                    f"[Student response "
                    f"{len(student_evidence) + 1}]\n"
                    f"{content}"
                )

            elif role == "assistant":

                tutor_context.append(
                    f"[Tutor response "
                    f"{len(tutor_context) + 1}]\n"
                    f"{content}"
                )

        student_evidence_text = "\n\n".join(
            student_evidence
        )

        tutor_context_text = "\n\n".join(
            tutor_context
        )

        if not tutor_context_text:
            tutor_context_text = (
                "No tutor context available."
            )

        # ------------------------------------------------------------
        # STEP 4 — Qwen interprets evidence
        # ------------------------------------------------------------

        prompt = f"""
{PERFORMANCE_INSTRUCTIONS}

SUBJECT:
{subject_id}

COURSE REFERENCE:
{course_context}

STUDENT EVIDENCE:
{student_evidence_text}

TUTOR CONTEXT:
{tutor_context_text}

Analyze the student's substantive evidence against the course reference.

Remember:
- Do not diagnose from pure questions or uncertainty.
- Track the student's progression.
- A later course-aligned explanation is stronger evidence than earlier
  uncertainty.
- A later conflicting explanation indicates current confusion.
- Identify repeated conflicts when they occur.
- Determine the student's CENTRAL CLAIM before assigning classification.
- Do not classify based on individual words.

Return ONLY the required JSON.
"""

        response = generate(
            prompt
        )

        # ------------------------------------------------------------
        # STEP 5 — Parse Qwen interpretation
        # ------------------------------------------------------------

        interpretation = self.parse_llm_response(
            response
        )

        # ------------------------------------------------------------
        # STEP 6 — Deterministic final diagnosis
        # ------------------------------------------------------------

        diagnosis = self.build_diagnosis(
            interpretation
        )

        return {
            "student_id": student_id,
            "subject_id": subject_id,
            "diagnosis": diagnosis,
            "evidence_interpretation": interpretation,
        }