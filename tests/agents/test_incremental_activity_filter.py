from backend.app.memory.learning_store import is_meaningful_student_response


def test_short_greetings_and_acknowledgements_are_not_counted():
    assert not is_meaningful_student_response("Hi there")
    assert not is_meaningful_student_response("Thanks, got it")
    assert not is_meaningful_student_response("Okay")


def test_pure_questions_and_simple_uncertainty_are_not_counted():
    assert not is_meaningful_student_response("What is an agentic workflow?")
    assert not is_meaningful_student_response("Can you explain planning?")
    assert not is_meaningful_student_response("I don't understand planning")


def test_explanations_and_proposed_mental_models_are_counted():
    assert is_meaningful_student_response(
        "Planning helps an agent decide which actions it should take next."
    )
    assert is_meaningful_student_response(
        "So does that mean memory stores previous results for later retrieval?"
    )


def test_longer_uncertainty_with_reasoning_is_kept_for_later_semantic_review():
    assert is_meaningful_student_response(
        "I am confused because planning and memory seem to perform similar roles in this example."
    )
