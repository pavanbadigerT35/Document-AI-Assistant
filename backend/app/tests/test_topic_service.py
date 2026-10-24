from app.services.topic_service import (
    _question_for,
    _section_content,
    _similar_topics,
    _valid_heading,
    topic_label,
)
from app.services.vector_store import StoredChunk
from app.db.models import Topic


def test_heading_cleanup_removes_numbering_duration_and_replacement_dash():
    assert topic_label("Module 2: Cluster Basics \ufffd 3 Hours") == "Cluster Basics"
    assert topic_label("1.2 Information Retrieval") == "Information Retrieval"
    assert topic_label("GENERATIVE AI \u2014 Complete Study Notes") == "GENERATIVE AI"


def test_incomplete_malformed_and_generic_headings_are_rejected():
    for heading in ("Information Retrieval and", "Overview of", "\ufffd\ufffd", "References", "1."):
        assert _valid_heading(heading) is None


def test_introduction_heading_normalizes_for_semantic_deduplication():
    first = _valid_heading("Prompt Engineering")
    second = _valid_heading("Introduction to Prompt Engineering")
    assert first == second == "Prompt Engineering"
    assert _similar_topics(first, second)


def test_short_section_does_not_generate_a_question():
    topic = Topic(title="RAG", page=1)
    chunks = [StoredChunk("d:0", "d", "notes.pdf", 1, 0, "RAG retrieves context.")]
    assert _section_content(topic, chunks) is None


def test_section_without_supported_intent_does_not_generate_a_question():
    assert _question_for("Unrelated Topic", "A collection of details about the subject, its context, and related terminology.") is None


def test_process_question_is_grounded_in_section_text():
    question, intent = _question_for(
        "Cluster Scheduling",
        "The scheduler processes each task in steps and schedules a container on a suitable worker node.",
    )
    assert question == "How does Cluster Scheduling work, and what are its main steps?"
    assert intent == "process"


def test_question_intents_follow_section_evidence():
    cases = [
        ("Few-shot Prompting", "For example, researchers use exemplars such as demonstrations in applications.", "examples"),
        ("Attention Mechanism", "The components include queries, keys, and values.", "components"),
        ("Encoder and Decoder", "Compared with the encoder, the decoder has a different role.", "comparison"),
        ("Retrieval", "Retrieval enables the system to find supporting passages.", "application"),
    ]
    for heading, content, expected_intent in cases:
        question = _question_for(heading, content)
        assert question is not None
        assert question[1] == expected_intent
        assert heading in question[0]
