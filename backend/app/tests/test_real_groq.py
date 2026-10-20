"""Optional integration test against the REAL Groq API. Excluded from the default run.

Run with:  pytest -m real_llm      (needs GROQ_API_KEY in backend/.env; may use your Groq quota)
"""
import pytest

from app.core.config import Settings
from app.services.llm_provider import GroqProvider

pytestmark = pytest.mark.real_llm


def test_groq_answers_a_trivial_prompt():
    s = Settings()
    if not s.llm_configured:
        pytest.skip("GROQ_API_KEY is not set")
    llm = GroqProvider(s.groq_api_key.get_secret_value(), s.groq_model, s.groq_base_url, s.llm_timeout_seconds)
    out = llm.generate("Reply with exactly one word.", "Say: ready", max_tokens=10)
    assert out.strip()
