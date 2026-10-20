from pydantic import BaseModel, Field, field_validator


class _Scoped(BaseModel):
    document_ids: list[str] | None = Field(None, description="Restrict to these documents. Omit to search all.")

    @field_validator("document_ids")
    @classmethod
    def _not_empty(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("document_ids must contain at least one id, or be omitted to search all documents")
        return v


class SearchRequest(_Scoped):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(None, ge=1, le=20)
    min_score: float | None = Field(None, ge=-1, le=1)


class Passage(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page: int
    text: str
    score: float


class RetrievalMeta(BaseModel):
    top_k: int
    min_score: float
    candidates: int
    above_threshold: int
    top_score: float | None
    latency_ms: float


class SearchResponse(BaseModel):
    results: list[Passage]
    retrieval: RetrievalMeta
    request_id: str | None = None


class ChatRequest(_Scoped):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(None, ge=1, le=20)


class Source(BaseModel):
    source_id: str
    chunk_id: str
    document_id: str
    filename: str
    page: int
    excerpt: str
    score: float


class LLMInfo(BaseModel):
    provider: str
    model: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    insufficient_evidence: bool
    warning: str | None = None
    retrieval: RetrievalMeta
    llm: LLMInfo | None = None
    request_id: str | None = None


class TopicOut(BaseModel):
    title: str
    page: int
    level: int


class DocumentTopics(BaseModel):
    document_id: str
    filename: str
    topics: list[TopicOut]


class TopicsResponse(BaseModel):
    grouping: str = "heuristic"
    note: str = "Topics are detected heuristically from headings, numbering and font styling. They may be incomplete."
    documents: list[DocumentTopics]


class Suggestion(BaseModel):
    question: str
    document_id: str
    filename: str
    page: int


class QuizRequest(_Scoped):
    topic: str | None = Field(None, max_length=300)
    num_questions: int = Field(5, ge=1, le=10)
    kind: str = Field("mcq", pattern="^(mcq|short_answer)$")


class QuizSource(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page: int
    excerpt: str


class QuizQuestion(BaseModel):
    question: str
    options: list[str] = []
    correct_index: int | None = None
    answer: str | None = None
    explanation: str = ""
    source: QuizSource


class QuizResponse(BaseModel):
    label: str = "AI-generated learning content based on your documents. Not official exam questions; verify against the source."
    questions: list[QuizQuestion]
    request_id: str | None = None


class QuizHealth(BaseModel):
    available: bool
    reason: str | None = None
