"""Seed 40 synthetic students and course-scoped learning conversations.

Safety:
- Dry-run is the default. Pass --apply to write to MongoDB.
- The target course must already exist and must be named
  "Introduction to Agentic AI".
- Existing non-seed users, enrollments, sessions and interactions are never
  deleted or overwritten.
- Re-running an existing seed batch requires --reset-seed-batch, which removes
  only records carrying this script's exact seed_batch_id.
- Demo credentials are generated from each roll number for easy account switching.
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from backend.app.auth.security import hash_password
from backend.app.database.mongodb import get_mongodb_database

COURSE_ID_DEFAULT = "3ce7921b-cb0f-476f-b7d4-de62fc55dd12"
EXPECTED_COURSE_NAME = "Introduction to Agentic AI"
SEED_BATCH_ID = "agentic-ai-demo-cohort-v1"

PROFILES = {
    "strong_understanding": {
        "count": 10,
        "sessions": [
            [
                ("user", "An AI agent perceives its environment, reasons about the goal, and selects actions to make progress."),
                ("assistant", "Good explanation. You have identified the perception, reasoning and action cycle."),
                ("user", "An agent differs from a basic chatbot because it can take goal-directed actions and use tools, not only generate a response."),
                ("assistant", "That distinction is useful. Tool use and goal-directed action are important parts of the agent workflow."),
                ("user", "Planning means decomposing a goal into subgoals and ordering actions to achieve it."),
                ("assistant", "Correct. A plan represents a sequence or structure of actions toward the goal."),
            ],
            [
                ("user", "Memory stores information from previous interactions so the agent can use relevant context later."),
                ("assistant", "Exactly. Memory retains information; it is not the same operation as planning."),
                ("user", "The planner can use retrieved memory as input, but planning itself decides what steps should be taken."),
                ("assistant", "That clearly explains how the two components cooperate without confusing their roles."),
                ("user", "A tool lets an agent interact with an external system, while reasoning decides when and why the tool is useful."),
                ("assistant", "Well distinguished. Tool execution and reasoning are related but different responsibilities."),
            ],
            [
                ("user", "An orchestrator coordinates specialized agents or tasks and routes work according to the workflow."),
                ("assistant", "Correct. Orchestration coordinates execution rather than replacing each agent's specialized role."),
                ("user", "A retrieval system finds relevant course information, and the generated answer should stay grounded in that retrieved context."),
                ("assistant", "Good. Retrieval supplies evidence that can ground the response."),
                ("user", "If a tool fails, the agent should detect the failure and decide whether to retry, recover, or report it."),
                ("assistant", "That is a sensible description of robust agent execution."),
            ],
            [
                ("user", "For a goal such as preparing a report, the planner can create subtasks, use a search tool, store useful findings in memory, and then compose the result."),
                ("assistant", "Your example connects planning, tools, memory and execution in one coherent workflow."),
                ("user", "The memory is not the plan: it is the retained information that can inform a later plan."),
                ("assistant", "Exactly. You are consistently distinguishing those concepts."),
                ("user", "The orchestrator can route a request to the right agent and collect its result for the next workflow step."),
                ("assistant", "Good application of orchestration."),
            ],
        ],
    },
    "persistent_misconceptions": {
        "count": 10,
        "sessions": [
            [
                ("user", "Planning is basically remembering what happened before."),
                ("assistant", "Memory retains information from previous interactions, while planning determines actions toward a goal. Let's compare them."),
                ("user", "I think the planner just searches memory and that is the plan."),
                ("assistant", "Searching memory can provide context, but a plan is a proposed sequence of actions."),
                ("user", "So memory and planning are the same component with two names?"),
                ("assistant", "They are distinct responsibilities. Memory stores information; planning selects and organizes steps."),
            ],
            [
                ("user", "A tool is the same thing as reasoning because both make the agent intelligent."),
                ("assistant", "Reasoning selects or evaluates what to do. A tool is an external capability the agent can invoke."),
                ("user", "If the agent calls a search tool, the search tool is doing the planning."),
                ("assistant", "The tool performs the search operation; the agent's planning process decides whether and how to use it."),
                ("user", "I still think the tool itself is the agent's reasoning process."),
                ("assistant", "That statement still combines two different roles. Let's work through a concrete example."),
            ],
            [
                ("user", "An orchestrator is just the memory database because it keeps all the agents together."),
                ("assistant", "An orchestrator coordinates and routes workflow execution. A memory store retains information."),
                ("user", "The orchestrator remembers everything, so it is the memory component."),
                ("assistant", "Coordination and storage are different responsibilities, even if a system uses both."),
                ("user", "Planning means recalling the last action and repeating it."),
                ("assistant", "That describes recalling past information, not constructing a goal-directed plan."),
            ],
            [
                ("user", "An AI agent is only a chatbot that replies to messages. It does not need actions."),
                ("assistant", "A conversational interface can be part of an agent, but an agent can also select actions and use tools to pursue a goal."),
                ("user", "Using a tool is just another word for generating text."),
                ("assistant", "Tool invocation is an action against an external capability, not simply text generation."),
                ("user", "I still define planning as remembering the previous conversation."),
                ("assistant", "That is the same unresolved distinction we should revisit with a worked example."),
            ],
        ],
    },
    "partial_understanding": {
        "count": 10,
        "sessions": [
            [
                ("user", "An agent can take actions to reach a goal, but I am not sure how it decides which action comes first."),
                ("assistant", "A planner can break the goal into smaller subgoals and arrange actions in a useful order."),
                ("user", "Planning is breaking a goal into steps. I understand that part."),
                ("assistant", "Good. Next, distinguish the plan from information remembered from earlier interactions."),
                ("user", "Memory stores earlier information, although I sometimes mix it up with the plan."),
                ("assistant", "You have the storage role right. The plan is the action structure."),
            ],
            [
                ("user", "A tool connects the agent to an external service, I think."),
                ("assistant", "Yes. The agent can invoke a tool to perform an operation such as searching or calculating."),
                ("user", "Does the tool decide the goal or does the planner decide it?"),
                ("assistant", "The goal and action sequence are handled by the planning/reasoning process; the tool performs its defined operation."),
                ("user", "An orchestrator sends work to the right agent, but I am unsure how it handles the result."),
                ("assistant", "It can collect the output and pass it to the next workflow step."),
            ],
            [
                ("user", "Retrieval finds information from documents. Is every retrieved paragraph automatically correct for the question?"),
                ("assistant", "No. Retrieval returns candidate context; relevance and grounding still need to be considered."),
                ("user", "The answer should use relevant retrieved material, but I sometimes assume the first result is always enough."),
                ("assistant", "It is better to assess relevance and use sufficient supporting context."),
                ("user", "I can explain tools and memory, but planning and orchestration still feel similar."),
                ("assistant", "Planning creates action steps; orchestration coordinates components and workflow execution."),
            ],
            [
                ("user", "For a travel task, an agent might plan destinations, use a map tool, and remember preferences."),
                ("assistant", "Good example. Now state which part creates the ordered steps and which part stores preferences."),
                ("user", "The planner creates the steps and memory stores preferences. I think I understand the difference now."),
                ("assistant", "That is a clearer distinction. Try applying it to a new task to check consistency."),
                ("user", "I still need practice deciding when orchestration is needed instead of one agent doing the task."),
                ("assistant", "That is a useful area to strengthen with workflow examples."),
            ],
        ],
    },
    "insufficient_evidence": {
        "count": 5,
        "sessions": [
            [
                ("user", "What is an AI agent?"),
                ("assistant", "An AI agent can perceive context, reason about a goal and take actions. What do you think distinguishes it from a basic chatbot?"),
                ("user", "I am not sure."),
                ("assistant", "That's okay. We can build the idea step by step."),
            ],
            [
                ("user", "Can you explain planning?"),
                ("assistant", "Planning is deciding a sequence of actions or subgoals to achieve a goal."),
                ("user", "I don't understand this yet."),
                ("assistant", "Let's use a simple everyday example next."),
            ],
            [
                ("user", "What does memory mean here?"),
                ("assistant", "Memory retains useful information from previous interactions."),
                ("user", "Can you repeat that in simpler words?"),
                ("assistant", "Memory helps an agent retain information it may need later."),
            ],
            [
                ("user", "I have not practiced tool use."),
                ("assistant", "We can work through a small example when you're ready."),
                ("user", "I am still confused."),
                ("assistant", "Let's identify which part is unclear before drawing a conclusion."),
            ],
        ],
    },
    "improving_understanding": {
        "count": 5,
        "sessions": [
            [
                ("user", "Planning is remembering previous information and repeating the last action."),
                ("assistant", "Memory retains previous information. Planning constructs actions toward a goal. Let's revisit this distinction."),
                ("user", "I am confused about the difference between planning and memory."),
                ("assistant", "Memory stores information; planning decides what steps to take."),
            ],
            [
                ("user", "Memory stores information from earlier interactions, while planning chooses actions to reach a goal."),
                ("assistant", "That is a much clearer distinction than before."),
                ("user", "A planner can use memory as input, but the stored information is not itself the plan."),
                ("assistant", "Correct. You have separated the two responsibilities."),
                ("user", "I can now explain why a tool is different from reasoning: the tool performs an operation selected by the agent."),
                ("assistant", "Good progress. That explanation is aligned with the course concepts."),
            ],
            [
                ("user", "An orchestrator coordinates agents and routes outputs through a workflow; it is not the same as a memory store."),
                ("assistant", "Correct. You have also clarified the orchestration distinction."),
                ("user", "For a research task, planning creates subtasks, a search tool gathers sources, and memory retains useful findings."),
                ("assistant", "That example applies the concepts together accurately."),
                ("user", "The agent should check whether retrieved evidence is relevant before grounding its answer in it."),
                ("assistant", "Good. This shows progress in applying retrieval and grounding."),
            ],
            [
                ("user", "Planning creates a sequence of actions, memory retains information, tools perform external operations, and orchestration coordinates workflow steps."),
                ("assistant", "That is a concise and accurate summary of the four distinct responsibilities."),
                ("user", "If a tool returns an error, the workflow should handle the failure rather than assume the task succeeded."),
                ("assistant", "Exactly. That is a useful reliability consideration."),
                ("user", "I can now apply these roles to a multi-step agent task."),
                ("assistant", "Your later explanations show a stronger and more consistent understanding."),
            ],
        ],
    },
}

def build_conversations():
    """Return student records with deterministic multi-session message sets."""
    result = []
    idx = 1
    for category, spec in PROFILES.items():
        for _ in range(spec["count"]):
            roll = f"23bcs{idx-1:03d}"
            email = f"{roll}@gmail.com"
            result.append({
                "index": idx,
                "roll_number": roll,
                "email": email,
                "category": category,
                "sessions": spec["sessions"],
            })
            idx += 1
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-id", default=COURSE_ID_DEFAULT)
    parser.add_argument("--apply", action="store_true", help="Actually write seed data. Without this flag, only preview.")
    parser.add_argument("--reset-seed-batch", action="store_true", help="Delete only this script's prior seed-batch records before recreating.")
    args = parser.parse_args()

    db = get_mongodb_database()
    course = db["courses"].find_one({"course_id": args.course_id}, {"_id": 0})
    if not course:
        raise SystemExit(f"Course {args.course_id!r} was not found. No data changed.")
    if course.get("name", "").strip().casefold() != EXPECTED_COURSE_NAME.casefold():
        raise SystemExit(f"Course name mismatch: expected {EXPECTED_COURSE_NAME!r}, found {course.get('name')!r}. No data changed.")
    if course.get("status") != "active":
        raise SystemExit("The target course is not active. No data changed.")

    students = build_conversations()
    users = db["users"]
    enrollments = db["course_enrollments"]
    sessions = db["learning_sessions"]
    interactions = db["learning_interactions"]

    # Check collisions before any write.
    rolls = [s["roll_number"] for s in students]
    emails = [s["email"] for s in students]
    roll_collisions = list(users.find({"roll_number": {"$in": rolls}}, {"_id": 0, "email": 1, "roll_number": 1, "seed_batch_id": 1}))
    email_collisions = list(users.find({"email": {"$in": emails}}, {"_id": 0, "email": 1, "roll_number": 1, "seed_batch_id": 1}))
    foreign_rolls = [u for u in roll_collisions if u.get("seed_batch_id") != SEED_BATCH_ID]
    foreign_emails = [u for u in email_collisions if u.get("seed_batch_id") != SEED_BATCH_ID]
    if foreign_rolls or foreign_emails:
        raise SystemExit("Seed identity collision with existing non-seed users. No data changed. Inspect the roll_number/email collisions and choose a different cohort range.")

    prior_count = users.count_documents({"seed_batch_id": SEED_BATCH_ID})
    if prior_count and not args.reset_seed_batch:
        raise SystemExit(f"Found {prior_count} users from this seed batch. Use --reset-seed-batch to replace only this batch.")

    # Demo-only predictable credentials so the instructor can switch accounts quickly.
    # These are application login credentials; no Gmail inboxes are created.

    total_sessions = sum(len(s["sessions"]) for s in students)
    total_interactions = sum(sum(len(session) for session in s["sessions"]) for s in students)
    print(f"Target course: {course['name']} ({course['course_id']})")
    print(f"Professor owner: {course['professor_id']}")
    print(f"Students: {len(students)} | Sessions: {total_sessions} | Interactions: {total_interactions}")
    print(f"Existing records in this seed batch: {prior_count}")
    if not args.apply:
        print("DRY RUN ONLY. No records were written. Re-run with --apply to create the cohort.")
        return

    if args.reset_seed_batch:
        # Delete only records carrying this exact batch marker; never touch user-created data.
        seed_ids = [u["user_id"] for u in users.find({"seed_batch_id": SEED_BATCH_ID}, {"_id": 0, "user_id": 1})]
        sessions.delete_many({"seed_batch_id": SEED_BATCH_ID})
        interactions.delete_many({"seed_batch_id": SEED_BATCH_ID})
        enrollments.delete_many({"seed_batch_id": SEED_BATCH_ID})
        users.delete_many({"seed_batch_id": SEED_BATCH_ID})
        print(f"Removed prior seed batch only ({len(seed_ids)} users).")

    # Create/verify indexes before inserting any seed records.
    users.create_index("email", unique=True)
    users.create_index("roll_number", unique=True, sparse=True, name="unique_student_roll_number")
    enrollments.create_index([("student_id", ASCENDING), ("course_id", ASCENDING)], unique=True, name="unique_student_course_enrollment")
    sessions.create_index([("student_id", ASCENDING), ("course_id", ASCENDING), ("session_id", ASCENDING)], unique=True, name="unique_student_course_session")
    interactions.create_index([("student_id", ASCENDING), ("course_id", ASCENDING), ("session_id", ASCENDING), ("sequence", ASCENDING)], unique=True, name="unique_session_interaction_sequence")

    now = datetime.now(timezone.utc)
    created_users = []
    for student in students:
        user_id = str(uuid4())
        demo_password = f"{student['roll_number']}smtg"
        user_doc = {
            "user_id": user_id,
            "email": student["email"],
            "password_hash": hash_password(demo_password),
            "role": "student",
            "roll_number": student["roll_number"],
            "is_active": True,
            "created_at": now,
            "seed_batch_id": SEED_BATCH_ID,
            "synthetic_demo_data": True,
            "learning_profile": student["category"],
        }
        users.insert_one(user_doc)
        created_users.append((student, user_id))
        enrollment_doc = {
            "enrollment_id": str(uuid4()),
            "course_id": course["course_id"],
            "student_id": user_id,
            "professor_id": course["professor_id"],
            "enrolled_at": now,
            "status": "active",
            "seed_batch_id": SEED_BATCH_ID,
        }
        enrollments.insert_one(enrollment_doc)

        for session_number, messages in enumerate(student["sessions"], start=1):
            session_id = f"seed-{student['index']:03d}-session-{session_number:02d}"
            # Spread sessions across the preceding month in a stable chronological order.
            session_time = now - timedelta(days=(5 - session_number) * 3, hours=student["index"] % 8)
            session_doc = {
                "student_id": user_id,
                "course_id": course["course_id"],
                "session_id": session_id,
                "professor_id": course["professor_id"],
                "status": "completed",
                "created_at": session_time,
                "updated_at": session_time + timedelta(minutes=25),
                "interaction_count": len(messages),
                "seed_batch_id": SEED_BATCH_ID,
                "synthetic_demo_data": True,
            }
            sessions.insert_one(session_doc)
            for sequence, (role, content) in enumerate(messages, start=1):
                interactions.insert_one({
                    "student_id": user_id,
                    "course_id": course["course_id"],
                    "session_id": session_id,
                    "professor_id": course["professor_id"],
                    "sequence": sequence,
                    "role": role,
                    "content": content,
                    "created_at": session_time + timedelta(minutes=sequence * 2),
                    "seed_batch_id": SEED_BATCH_ID,
                    "synthetic_demo_data": True,
                    "learning_profile": student["category"],
                })

    print("Seed completed successfully.")
    print("Demo login credentials: email = roll_number@gmail.com; password = roll_numbersmtg.")
    print("Marks CSV/XLSX files are keyed by roll_number, not internal student_id.")
    print("Synthetic data marker:", SEED_BATCH_ID)

if __name__ == "__main__":
    main()
