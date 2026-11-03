"""Seed realistic, timestamped learning conversations for five existing students.

Run from the repository root:
  .venv\\Scripts\\python.exe scripts\\seed_performance_scenarios.py --dry-run
  .venv\\Scripts\\python.exe scripts\\seed_performance_scenarios.py --apply
  .venv\\Scripts\\python.exe scripts\\seed_performance_scenarios.py --cleanup

The script only writes learning_sessions, learning_interactions, and the
corresponding learning_analysis_state counters. It does not call Ollama or
modify course enrolments, marks, policies, profiles, or alerts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.database.mongodb import get_mongodb_database, close_mongodb_connection
from backend.app.memory.learning_store import (
    ensure_learning_indexes,
    is_meaningful_student_response,
)

COURSE_ID = "3ce7921b-cb0f-476f-b7d4-de62fc55dd12"
SEED_TAG = "agentic-ai-five-student-learning-scenarios-v1"

STUDENTS = {
    "23bcs001": "72736a0c-66f1-42d9-96cf-8d031b031a2f",  # strong understanding
    "23bcs002": "9fa2c073-6d26-4967-bf07-f72f72eb307c",  # persistent misconceptions
    "23bcs003": "4fc9a1cb-c2d6-492d-a70a-02072a0f26f9",  # partial understanding
    "23bcs004": "b433f220-d18a-48eb-aa80-bbd6d7eceb3a",  # insufficient evidence
    "23bcs005": "fe6e7745-233a-495a-977f-7b98045ea4c1",  # improving understanding
}

# Each of the first, second, third and fifth students has 18 substantive
# student responses spread over three separate chats. Student four deliberately
# has only noise/acknowledgements and should remain below the trigger threshold.
SCENARIOS: dict[str, list[list[tuple[str, str]]]] = {
    "23bcs001": [
        [
            ("user", "An agent is a system that observes its environment, reasons about the current state, and takes actions to achieve a goal. It is more than a single text response because it can decide what step to take next."),
            ("assistant", "Good explanation. You have identified observation, reasoning, action, and goal-directed behaviour."),
            ("user", "Planning is the process of breaking a goal into ordered steps. The agent can check whether each step is possible and revise the plan when an action produces an unexpected result."),
            ("assistant", "Exactly. Planning helps the agent decide how to reach its goal and adapt when conditions change."),
            ("user", "Memory stores useful information from earlier interactions or actions. Planning uses that information to choose the next steps, so memory and planning work together but perform different jobs."),
            ("assistant", "Correct distinction. Memory provides context; planning uses context to select actions."),
            ("user", "A tool is an external capability such as a calculator or search function. The agent decides when to call the tool, sends it an input, and uses the returned result in its reasoning."),
            ("assistant", "Well stated. The tool performs a defined operation while the agent controls when and why to use it."),
        ],
        [
            ("user", "Orchestration coordinates multiple components or agents so that their work happens in the right order. It can route a task to a specialist and combine the results into one response."),
            ("assistant", "Good. Orchestration manages the workflow and hand-offs between components."),
            ("user", "If a research agent gathers sources and a writing agent drafts a report, the orchestrator can pass the research output to the writing agent and check that the final task is complete."),
            ("assistant", "That is a relevant example of coordinated multi-agent work."),
            ("user", "A tool is not itself an agent because it normally performs a narrow operation when called. An agent can choose among tools, interpret their results, and decide what to do next."),
            ("assistant", "Correct. That distinction is important when designing agent systems."),
            ("user", "If the search tool returns irrelevant pages, the agent can evaluate the result, change its query, and search again instead of blindly accepting the first output."),
            ("assistant", "Exactly. The agent's reasoning loop makes the tool use adaptive."),
        ],
        [
            ("user", "For a travel assistant, memory could retain the user's preferred budget, planning could create an itinerary, and tools could check live transport options. The agent combines these capabilities to complete the task."),
            ("assistant", "Strong application. You have connected the concepts in one practical workflow."),
            ("user", "The orchestrator would be useful if separate agents handle flights, hotels, and local activities. It coordinates their outputs and resolves the order in which tasks should run."),
            ("assistant", "Yes. That is a good example of why orchestration is useful."),
            ("user", "If a flight search fails, the system should report the failure or try another search strategy. It should not claim that a booking was completed when the tool did not confirm it."),
            ("assistant", "Correct. Reliable agents must ground their next action in tool results."),
            ("user", "I can now distinguish the roles: memory retains context, planning selects steps, tools perform external operations, and orchestration coordinates the workflow."),
            ("assistant", "Excellent summary of the four concepts."),
        ],
    ],
    "23bcs002": [
        [
            ("user", "I think planning and memory are basically the same thing because both keep information for the agent and tell it what to do next. The agent remembers its plan, so I do not see a real difference between them."),
            ("assistant", "They are related but different. Memory stores information; planning uses information to decide a sequence of actions."),
            ("user", "I still think memory is the plan itself. When the agent saves the next steps, that saved plan is memory, so planning is just another name for remembering."),
            ("assistant", "A plan can be stored in memory, but storing a plan is not the same operation as creating or revising it. Consider a calendar that stores an itinerary versus the process of deciding the itinerary."),
            ("user", "In that example I would still call the calendar the planner because it contains the itinerary. The stored steps and the decision process seem identical to me."),
            ("assistant", "The calendar stores the result. The planning process evaluates options and chooses those steps. Let's keep those roles separate."),
            ("user", "A tool is also an agent in my view because a search tool can search the web and return an answer. It acts on a request, so it has the same role as an intelligent agent."),
            ("assistant", "A tool usually performs a bounded operation. An agent decides when to use it and interprets the result."),
        ],
        [
            ("user", "I continue to think a tool and an agent are the same because both receive input and produce output. The search function receives keywords and returns pages, which is already a complete agent behaviour."),
            ("assistant", "Input and output alone do not make a component an agent. An agent can reason across steps, choose tools, and adapt its actions."),
            ("user", "The orchestrator is just the memory of all agents because it keeps their outputs together. If it stores the outputs, then it is memory rather than a separate coordination component."),
            ("assistant", "An orchestrator coordinates task flow and hand-offs. It may use stored context, but coordination is its main responsibility."),
            ("user", "I would still describe orchestration as shared memory because agents pass information through it. Passing information and storing information are the same function in a multi-agent system."),
            ("assistant", "Passing information is part of coordination, but orchestration also decides routing, order, and completion conditions."),
            ("user", "Planning is still memory because the plan has to be retained before it can be executed. I do not think the system needs two separate concepts for that."),
            ("assistant", "Let's revisit this with a worked example and identify which component makes each decision."),
        ],
        [
            ("user", "Even after the example, I think the agent's memory decides the next action because it contains the previous plan. The planning component and memory component are still interchangeable to me."),
            ("assistant", "The previous plan is context. A planner can inspect that context and revise it when a step fails; memory alone does not make that decision."),
            ("user", "If a search tool returns a poor result, the tool is the agent because it should know that the result is poor and decide to search again. The tool and agent are still one component."),
            ("assistant", "In this design, the tool returns results. The agent evaluates them and decides whether to call the tool again."),
            ("user", "I also think the orchestrator is memory because it receives messages from the agents. Coordinating agents and keeping their messages are effectively the same thing."),
            ("assistant", "The distinction remains: orchestration routes and coordinates work; memory retains information for later use."),
            ("user", "My current understanding is that memory, planning, tools, and orchestration all store or move information, so they can be treated as one general function."),
            ("assistant", "We should focus the next practice activity on distinguishing each component's responsibility."),
        ],
    ],
    "23bcs003": [
        [
            ("user", "An agent is a program that does tasks for a user. I understand that it can take actions, but I am not yet sure how it decides which action is suitable for the goal."),
            ("assistant", "An agent uses its goal, current context, available tools, and reasoning to select an action."),
            ("user", "Planning means writing down steps before doing the task. I understand the basic idea, but I am unsure how the agent changes the plan if one step does not work."),
            ("assistant", "It can inspect the result of the action, update its context, and create a revised plan."),
            ("user", "Memory can keep earlier information such as user preferences. I am not certain whether every tool result should be saved or only information that may help later."),
            ("assistant", "Good question to consider. Memory design selects useful information rather than saving every result indiscriminately."),
            ("user", "A tool lets the agent do something outside its own reasoning, such as searching or calculating. I understand that part, but I am not sure how the agent checks whether the tool result is reliable."),
            ("assistant", "The agent can validate the result against the task, expected format, and other available evidence."),
        ],
        [
            ("user", "Orchestration seems to manage multiple agents, but I am still confused about how it decides which agent should receive a task first."),
            ("assistant", "The workflow can define routing rules based on task type, required capability, and dependencies."),
            ("user", "I think memory and planning are different because memory stores previous information while planning chooses steps. I can explain the difference, but I struggle to show how they interact during a long task."),
            ("assistant", "Try tracing one task: retrieve a preference from memory, then use it while selecting the next actions."),
            ("user", "If a research agent gives information to a writing agent, orchestration passes the result along. I understand the hand-off, but I am not sure how errors are handled between the two agents."),
            ("assistant", "The orchestrator can validate outputs and route failures for retry or clarification."),
            ("user", "The tool does not usually decide the overall goal, while the agent chooses when to use it. I understand this distinction in a simple example but need more practice with complex workflows."),
            ("assistant", "That is a useful distinction. Let's apply it to a multi-step assistant."),
        ],
        [
            ("user", "In a shopping assistant, memory could retain a budget and planning could compare possible steps. I can identify those roles, but I am not fully confident about when orchestration is needed."),
            ("assistant", "Orchestration becomes useful when the task is divided across components or agents with dependencies."),
            ("user", "If one agent searches products and another checks delivery, an orchestrator can coordinate both tasks and combine their results. That makes more sense than using orchestration for every single tool call."),
            ("assistant", "Correct. A simple single-agent tool call may not need a separate orchestrator."),
            ("user", "I understand that a tool performs an operation and the agent interprets the result. I still need practice evaluating whether a result is trustworthy before using it."),
            ("assistant", "Good self-assessment. Evidence validation is a useful next practice topic."),
            ("user", "I can now explain the basic roles, but connecting memory, planning, tool use, and orchestration in one design still takes me time."),
            ("assistant", "You have the foundations. More worked examples should help connect them."),
        ],
    ],
    "23bcs004": [
        [
            ("user", "Hi"), ("assistant", "Hello! What would you like to learn about agents today?"),
            ("user", "Okay thanks"), ("assistant", "You're welcome."),
            ("user", "I am not sure"), ("assistant", "That's okay. We can start with a simple example."),
            ("user", "Good morning"), ("assistant", "Good morning!"),
        ],
        [
            ("user", "Yes, got it"), ("assistant", "Would you like to try a short example?"),
            ("user", "I don't know"), ("assistant", "No problem. Take your time."),
            ("user", "Thanks for helping"), ("assistant", "You're welcome."),
            ("user", "Okay"), ("assistant", "We can continue whenever you're ready."),
        ],
        [
            ("user", "Hello again"), ("assistant", "Welcome back."),
            ("user", "Not now thanks"), ("assistant", "Sure. We can pick this up later."),
            ("user", "I have no idea"), ("assistant", "That's fine. We can work through it step by step."),
            ("user", "Thank you"), ("assistant", "You're welcome."),
        ],
    ],
    "23bcs005": [
        [
            ("user", "An agent is just a chatbot that answers questions. I do not yet understand how it can take actions or work toward a goal beyond producing text."),
            ("assistant", "A chatbot may only respond, while an agent can select actions and use tools to pursue a goal."),
            ("user", "I think memory is the same as planning because the system remembers the steps it needs to perform. I am not clear about the difference yet."),
            ("assistant", "Memory stores context; planning decides which steps should be taken."),
            ("user", "A tool might be the same as an agent because it performs a task when the system asks it. I cannot yet explain who decides which tool should be called."),
            ("assistant", "The agent selects a tool based on the task and interprets the returned result."),
            ("user", "Orchestration sounds like another word for memory because it keeps information from different agents together. I am still mixing up those responsibilities."),
            ("assistant", "Orchestration coordinates the workflow and hand-offs; memory retains useful information."),
        ],
        [
            ("user", "I now think memory stores previous context, while planning uses that context to choose actions. I can state the difference, although I still confuse them when describing a full workflow."),
            ("assistant", "That is progress. Try explaining what happens when a planned action fails."),
            ("user", "If an action fails, the agent can use the result as new context and revise its plan. Memory may retain the failure, but planning decides the revised steps."),
            ("assistant", "Exactly. You have separated the stored information from the decision process."),
            ("user", "A tool performs a specific operation, and the agent chooses when to call it. The agent should inspect the returned result instead of assuming the tool always succeeds."),
            ("assistant", "Correct. That is a more accurate description of tool use."),
            ("user", "An orchestrator can route work between agents and combine their outputs. It is not simply a memory store, even if it passes information between agents."),
            ("assistant", "Well done. You have corrected an important distinction."),
        ],
        [
            ("user", "For a study assistant, memory can retain my course and learning preferences, while planning creates a sequence of revision activities based on my goal."),
            ("assistant", "Good application of memory and planning."),
            ("user", "The assistant could call a calendar tool to schedule a revision session. The tool handles the calendar operation, while the agent decides when that operation is useful."),
            ("assistant", "Correct. The agent remains responsible for selecting and interpreting the tool call."),
            ("user", "If separate agents prepare notes and quizzes, an orchestrator can assign each task and combine their outputs. It can also detect when one task must finish before another begins."),
            ("assistant", "Excellent. You have described coordination and task dependencies."),
            ("user", "I used to treat memory, planning, tools, and orchestration as the same thing, but now I can explain their different responsibilities and how they work together."),
            ("assistant", "That is a clear improvement across the concepts."),
        ],
    ],
}


# Extend session 1 to exactly ten substantive student responses. This is
# intentional: the first threshold batch contains evidence from one session,
# while later forced/manual batches contain evidence from subsequent sessions.
# That lets the persistent-misconception rule observe separate sessions.
_EXTRA_SESSION_ONE = {
    "23bcs001": [
        ("user", "An agent can use a feedback loop: observe the result of an action, compare it with the goal, and decide whether another action is needed."),
        ("assistant", "Yes. Feedback lets the agent adapt rather than execute a fixed sequence blindly."),
        ("user", "A plan is not necessarily permanent. If a required website is unavailable, the agent can update the plan and choose another valid route to the same goal."),
        ("assistant", "Correct. Planning can be revised when the environment changes."),
        ("user", "Memory can be short term for the current task or longer term for preferences that are useful in future sessions. The system should retain relevant information rather than every detail."),
        ("assistant", "Good distinction. Memory should be selected according to usefulness and the system's design."),
        ("user", "A calculator tool returns a calculation, but the agent still needs to check whether the inputs represent the right quantities before trusting the answer."),
        ("assistant", "Exactly. A valid tool response can still be based on incorrect inputs."),
        ("user", "An orchestrator can enforce dependencies, such as waiting for research to finish before asking a writing agent to draft the report."),
        ("assistant", "Correct. Dependency management is a key part of orchestration."),
        ("user", "A multi-agent system should also define what happens when one specialist fails, such as retrying, asking for clarification, or reporting that the task could not be completed."),
        ("assistant", "Well reasoned. Failure handling should be explicit in the workflow."),
    ],
    "23bcs002": [
        ("user", "When an agent saves a plan, that proves planning and memory are identical because the saved steps are what guide the next action. I still do not accept that they are separate functions."),
        ("assistant", "Saving a plan is a memory operation; deciding and revising the steps is planning. One artifact can be stored without making the operations identical."),
        ("user", "A search tool is still an agent because it receives a query, performs work, and returns information. I think reasoning is just what happens inside the search tool."),
        ("assistant", "In this architecture the search tool executes a bounded search. The agent decides the query, evaluates results, and chooses the next step."),
        ("user", "If the agent keeps the search result, that is memory, and if it passes the result to another agent, that is also memory. I do not see orchestration as a different responsibility."),
        ("assistant", "Orchestration controls routing and order. Memory stores information that may be needed later."),
        ("user", "A planner only recalls the steps that memory has already stored. It does not really decide anything new, so planning is still just retrieving memory."),
        ("assistant", "A planner evaluates alternatives and can generate a new sequence, not merely retrieve an old one."),
        ("user", "Even if a tool fails, I would say the tool decides to retry because it is the component that performed the search. The agent does not need a separate decision."),
        ("assistant", "The tool reports success or failure; the agent or workflow decides whether to retry."),
        ("user", "I continue to combine the roles of memory, planning, tools, and orchestration because each one seems to move information through the system."),
        ("assistant", "Let's use a component-mapping exercise to distinguish storage, decision-making, execution, and coordination."),
    ],
    "23bcs003": [
        ("user", "I understand that an agent has a goal and can select actions, but I am not yet confident about how it decides when it has enough information to stop searching."),
        ("assistant", "A workflow can define completion criteria and the agent can check whether the available evidence satisfies them."),
        ("user", "Planning can include conditions as well as steps. For example, if a result is missing, the agent may need another search before continuing."),
        ("assistant", "Correct. Conditional branches make plans more flexible."),
        ("user", "Memory should keep useful preferences and task facts, but I am unsure how the system decides when old information is no longer relevant."),
        ("assistant", "Memory systems can use relevance, age, and explicit update rules to manage retained information."),
        ("user", "A tool result needs checking because a successful response does not guarantee that the returned information answers the user's actual request."),
        ("assistant", "Exactly. The agent should validate relevance, not just whether the tool call succeeded."),
        ("user", "An orchestrator can decide the order of specialist tasks when one agent depends on another agent's output. I understand this better when the dependencies are clearly stated."),
        ("assistant", "Good. Dependency diagrams can help make that order explicit."),
        ("user", "I can identify each component separately, but I still need examples that show how the system handles two failures in a multi-step workflow."),
        ("assistant", "That is a useful next practice goal. We can trace retries and fallback routes."),
    ],
    "23bcs005": [
        ("user", "I used to think an agent only generates text, but now I see that it can choose an action and use a tool to change something outside the conversation."),
        ("assistant", "Good correction. Tool use allows an agent to act beyond producing text."),
        ("user", "Memory stores earlier information, while planning decides what to do next. I can explain the difference in a simple example now."),
        ("assistant", "That is a clear improvement from your earlier explanation."),
        ("user", "If a planned search fails, the agent can inspect the failure and revise its plan. The failure can be retained in memory, but memory does not decide the new plan."),
        ("assistant", "Exactly. You have connected feedback, memory, and planning correctly."),
        ("user", "A tool performs a bounded operation such as searching or calculating. The agent chooses the tool and checks whether the returned result is useful."),
        ("assistant", "Correct. That is an accurate description of tool use."),
        ("user", "Orchestration is useful when several agents have dependent tasks. It routes outputs between them and checks that the workflow reaches its completion condition."),
        ("assistant", "Well explained. You have identified coordination and dependency management."),
        ("user", "I still sometimes mix up orchestration and memory, but I now understand that passing a message between agents is coordination while retaining useful context is memory."),
        ("assistant", "That distinction is becoming clearer. Keep applying it to examples."),
    ],
}

for _roll, _extra_messages in _EXTRA_SESSION_ONE.items():
    SCENARIOS[_roll][0].extend(_extra_messages)


def _utc(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    # Simulated local classroom time is IST; convert to UTC for MongoDB.
    return datetime(year, month, day, hour, minute, tzinfo=timezone(timedelta(hours=5, minutes=30))).astimezone(timezone.utc)


def _build_messages(roll: str) -> list[tuple[str, str, datetime, str]]:
    sessions = SCENARIOS[roll]
    # All dates are after the supplied enrolment date (2026-11-02 15:12 IST).
    starts = [_utc(2026, 11, 2, 16, 0), _utc(2026, 11, 2, 18, 15), _utc(2026, 11, 3, 10, 0)]
    result: list[tuple[str, str, datetime, str]] = []
    for session_index, messages in enumerate(sessions):
        for message_index, (role, content) in enumerate(messages):
            created_at = starts[session_index] + timedelta(minutes=message_index * 3)
            result.append((role, content, created_at, f"{roll}-session-{session_index + 1}"))
    return result


def validate(db) -> dict[str, Any]:
    course = db["courses"].find_one({"course_id": COURSE_ID})
    if not course:
        raise SystemExit(f"Course not found: {COURSE_ID}")
    if course.get("status") != "active":
        raise SystemExit(f"Course is not active: {COURSE_ID}")
    enrollment_ids = {
        row.get("student_id")
        for row in db["course_enrollments"].find({"course_id": COURSE_ID}, {"student_id": 1})
    }
    missing = [roll for roll, sid in STUDENTS.items() if sid not in enrollment_ids]
    if missing:
        raise SystemExit("These supplied students are not enrolled in the selected course: " + ", ".join(missing))
    return course


def cleanup(db) -> int:
    sessions = list(db["learning_sessions"].find({"seed_tag": SEED_TAG}, {"session_id": 1, "student_id": 1, "course_id": 1}))
    identities = [{"student_id": s["student_id"], "course_id": s["course_id"], "session_id": s["session_id"]} for s in sessions]
    deleted_interactions = db["learning_interactions"].delete_many({"seed_tag": SEED_TAG}).deleted_count
    deleted_sessions = db["learning_sessions"].delete_many({"seed_tag": SEED_TAG}).deleted_count
    # Recompute pending counters from actual pending records; never clear unrelated records.
    for student_id in STUDENTS.values():
        pending = db["learning_interactions"].count_documents({
            "student_id": student_id, "course_id": COURSE_ID, "role": "user",
            "meaningful_candidate": True, "analysis_status": "pending",
        })
        db["learning_analysis_state"].update_one(
            {"student_id": student_id, "course_id": COURSE_ID},
            {"$set": {"pending_count": pending, "updated_at": datetime.now(timezone.utc)}},
        )
    return deleted_interactions + deleted_sessions


def seed(db, course: dict, dry_run: bool) -> None:
    professor_id = course["professor_id"]
    existing = db["learning_interactions"].count_documents({"seed_tag": SEED_TAG})
    if existing:
        raise SystemExit(f"Seed data already exists ({existing} interactions). Run --cleanup before reseeding.")

    summary = []
    for roll, student_id in STUDENTS.items():
        rows = _build_messages(roll)
        candidates = sum(1 for role, content, _, _ in rows if role == "user" and is_meaningful_student_response(content))
        summary.append((roll, len(rows), candidates, len({r[3] for r in rows})))
    print("Seed preview (roll, total messages, meaningful student responses, sessions):")
    for row in summary:
        print(f"  {row[0]}: {row[1]} messages, {row[2]} meaningful candidates, {row[3]} sessions")
    if dry_run:
        print("Dry run only. No MongoDB records were written.")
        return

    ensure_learning_indexes()
    now = datetime.now(timezone.utc)
    for roll, student_id in STUDENTS.items():
        session_groups: dict[str, list[tuple[str, str, datetime, str]]] = {}
        for message in _build_messages(roll):
            session_groups.setdefault(message[3], []).append(message)
        for session_id, messages in session_groups.items():
            start = min(m[2] for m in messages)
            end = max(m[2] for m in messages)
            db["learning_sessions"].insert_one({
                "student_id": student_id,
                "course_id": COURSE_ID,
                "session_id": session_id,
                "professor_id": professor_id,
                "status": "active",
                "created_at": start,
                "updated_at": end,
                "interaction_count": len(messages),
                "seed_tag": SEED_TAG,
                "seed_roll_number": roll,
            })
            docs = []
            for sequence, (role, content, created_at, _) in enumerate(messages, start=1):
                meaningful = role == "user" and is_meaningful_student_response(content)
                doc = {
                    "student_id": student_id,
                    "course_id": COURSE_ID,
                    "session_id": session_id,
                    "professor_id": professor_id,
                    "sequence": sequence,
                    "role": role,
                    "content": content,
                    "created_at": created_at,
                    "meaningful_candidate": meaningful,
                    "seed_tag": SEED_TAG,
                    "seed_roll_number": roll,
                }
                if meaningful:
                    doc["analysis_status"] = "pending"
                docs.append(doc)
            if docs:
                db["learning_interactions"].insert_many(docs, ordered=True)

        pending = db["learning_interactions"].count_documents({
            "student_id": student_id, "course_id": COURSE_ID, "role": "user",
            "meaningful_candidate": True, "analysis_status": "pending",
        })
        db["learning_analysis_state"].update_one(
            {"student_id": student_id, "course_id": COURSE_ID},
            {
                "$setOnInsert": {
                    "student_id": student_id,
                    "course_id": COURSE_ID,
                    "professor_id": professor_id,
                    "created_at": now,
                    "last_analyzed_at": None,
                    "last_analysis_status": "not_yet_analyzed",
                },
                "$set": {"pending_count": pending, "updated_at": now},
            },
            upsert=True,
        )
    print("Seed inserted successfully. No analysis was started automatically.")
    print("Use the professor dashboard's Check learning activity / Manually analyze pending evidence controls to test the pipeline.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    group.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    db = get_mongodb_database()
    try:
        if args.cleanup:
            print(f"Removed {cleanup(db)} seed-tagged session/interaction records.")
            return
        course = validate(db)
        seed(db, course, dry_run=args.dry_run)
    finally:
        close_mongodb_connection()


if __name__ == "__main__":
    main()
