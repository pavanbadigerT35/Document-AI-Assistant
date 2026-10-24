"""Test-only doubles. Nothing in app/ (outside tests) imports this module."""
import json
import re


class MockLLM:
    """Deterministic stand-in for the LLM so tests need no API key or network."""

    provider = "mock"
    model = "mock-1"
    configured = True

    def __init__(self, reply: str | None = None, quiz_json: dict | None = None):
        self.reply, self.quiz_json = reply, quiz_json
        self.calls: list[dict] = []

    def generate(self, system, user, *, json_mode=False, temperature=0.1, max_tokens=1200):
        self.calls.append({"system": system, "user": user, "json_mode": json_mode})
        if json_mode:
            if self.quiz_json is not None:
                return json.dumps(self.quiz_json)
            sid = (re.findall(r'<excerpt id="(S\d+)"', user) or ["S1"])[0]
            if "descriptive-answer" in system:
                return json.dumps({"questions": [{"question": "What is described?", "answer": "The excerpt describes the main idea in detail. It explains how the relevant process works and why it matters. These details are supported by the source passage.", "source_id": sid}]})
            return json.dumps({"questions": [{"question": "Pick the right statement", "options": ["A", "B", "C", "D"], "correct_index": 1, "explanation": "Because the excerpt says so.", "source_id": sid}]})
        if self.reply is not None:
            return self.reply
        sid = (re.findall(r'<excerpt id="(S\d+)"', user) or ["S1"])[0]
        return f"According to the document, the answer is in the excerpt. [{sid}]"
