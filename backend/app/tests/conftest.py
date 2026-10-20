import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.llm_provider import UnconfiguredLLM
from app.tests.mocks import MockLLM

ATP_PAGE_1 = "Photosynthesis converts light energy into chemical energy inside chloroplasts of plant cells."
ATP_PAGE_2 = "The mitochondria produce ATP through cellular respiration, supplying energy to the cell."
K8S_PAGE = "Kubernetes schedules containers across a cluster of worker nodes using a control plane scheduler."


def make_pdf(pages: list, headings: dict[int, list[str]] | None = None) -> bytes:
    """Build a tiny PDF. `pages` are body strings; `headings` maps page index -> bold heading lines."""
    doc = pymupdf.open()
    for i, body in enumerate(pages):
        page = doc.new_page()
        y = 72
        for h in (headings or {}).get(i, []):
            page.insert_text((72, y), h, fontsize=18, fontname="hebo")
            y += 34
        if body:
            page.insert_textbox(pymupdf.Rect(72, y, 540, 760), body, fontsize=11, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, data_dir=tmp_path, embedding_backend="hash", min_score=0.2, max_upload_mb=1, max_files_per_request=3)


@pytest.fixture
def llm():
    return MockLLM()


@pytest.fixture
def client(settings, llm):
    with TestClient(create_app(settings, llm=llm)) as c:
        yield c


@pytest.fixture
def client_no_llm(settings):
    with TestClient(create_app(settings, llm=UnconfiguredLLM("none"))) as c:
        yield c


def upload(client, name, data, content_type="application/pdf"):
    return client.post("/api/v1/documents", files=[("files", (name, data, content_type))])


@pytest.fixture
def doc_a(client):
    r = upload(client, "biology.pdf", make_pdf([ATP_PAGE_1, ATP_PAGE_2], {0: ["Cell Energy"]}))
    assert r.status_code == 201, r.text
    return r.json()["results"][0]["document"]


@pytest.fixture
def doc_b(client):
    r = upload(client, "devops.pdf", make_pdf([K8S_PAGE]))
    assert r.status_code == 201, r.text
    return r.json()["results"][0]["document"]
