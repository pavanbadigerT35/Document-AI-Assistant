# Project status

Last updated: 20 October 2026 (completion pass on top of the earlier build).

## Where things stood

The earlier build already had the full pipeline (upload, PyMuPDF extraction, page-aware chunking, local embeddings, persistent ChromaDB, grounded chat with citations, topics, quizzes), all six frontend pages, tests, an evaluation script and a README. The completion pass audited every file against the original brief, fixed the defects below, and added the missing deliverables.

## Fixed in this pass

| # | Problem | Why it mattered | Fix |
|---|---|---|---|
| 1 | Default model `llama-3.3-70b-versatile` was **retired by Groq on 16 Aug 2026** | Chat and quizzes would have failed on first run | New default `openai/gpt-oss-120b`; `GROQ_REASONING_EFFORT` setting; a retired or unknown model now produces a message that says exactly what to change |
| 2 | Reasoning models spend hidden tokens from the same output limit | A 900-token cap could leave an empty or truncated answer | Token headroom for gpt-oss models; an empty reply is now an explicit error instead of a blank answer |
| 3 | SQLite drops timezone info | Upload times were shown shifted by the viewer's UTC offset (5h30 in India) | Timestamps are labelled UTC in the API; the browser converts to local time |
| 4 | Similarity score depended on Chroma's `hnsw:space` setting, which Chroma 1.x marks deprecated | If a future version ignored it, scores and the threshold would silently break | Cosine similarity is computed from the stored vectors, independent of Chroma's metric |
| 5 | One `add()` call per document | Chroma rejects batches above its internal maximum; a very large PDF would fail to index | Chunks are added in batches of 500 |
| 6 | `n_results` could exceed the matches inside a filtered document | Raises in some Chroma versions | Requests are capped to the number of matching chunks |
| 7 | Evaluation script crashed at exit on Windows | Chroma/SQLite files stay locked in the temp folder | `ignore_cleanup_errors=True` |
| 8 | Evaluation script could only label a single PDF | No way to measure multi-document retrieval | Items may name `expected_file`; hits are checked on (file, page) |
| 9 | Suggested questions came from the first document only, and kept numbers like "1." | Poor multi-document behaviour | Documents take turns; numbering, "Module N:" and "– 4 Hours" are stripped |
| 10 | `crypto.randomUUID` is undefined outside https/localhost | Chat would break when opened via a LAN IP | Safe fallback (`newId`) |

## Added

- `samples/`: two **synthetic** PDFs (3 pages each) for the multi-document demo, one with a deliberate prompt-injection sentence. `python -m evaluation.sample_docs` regenerates them.
- `backend/evaluation/sample_dataset.json`: 10 answerable and 5 unanswerable questions with file + page labels.
- `scripts/*.ps1`: `setup`, `start-backend`, `start-frontend`, `run-tests`, `run-evaluation` for Windows.
- Topic Explorer "Quiz me" links (the Quiz page now reads `?topic=` and `?doc=`).
- New tests: Groq provider (9), vector store (4), sample documents (7), plus extra API and frontend cases.
- `data/uploads/.gitkeep`, `data/chroma/.gitkeep`; dependency ceilings for major versions in `requirements.txt`.

## What was verified, and how

The completion pass ran in an environment **without internet access**, so packages could not be installed there. Only these checks were possible, and all passed:

- Every backend `.py` file compiles (`py_compile`).
- All 19 frontend `.ts`/`.tsx` files parse with TypeScript 6.0.3, and a filtered `tsc` pass shows no unused imports or undefined names. (A full type-check needs the React type packages from `npm install`.)
- The sample PDFs were opened with `pdfinfo`/`pdftotext`: text-based, 3 pages each, and **all 10 evidence phrases are on the labelled file and page**.
- The new `GroqProvider` logic was exercised with a stand-in HTTP layer against all 12 behaviours the new tests expect (payload shape, reasoning settings, retired-model message, empty reply, timeouts, no key in any error text).
- The cosine ranking helper and the heading-label cleanup were run directly.
- The `.gitignore` rules were checked with git: placeholders and `.env.example` files are tracked; `.env`, uploads, Chroma data and databases are not.
- Groq's retirement of the old default model and the recommended replacements were confirmed against Groq's deprecation page.

Offline simulation with the project's word-overlap test embedder (not the real model) put the right page in the top 5 for 10 of 10 sample questions and at rank 1 for 8 of 10. That is a smoke test of the dataset design, **not** a quality measurement of the real system.

## Not verified here (please run these)

- `pytest` and `npm test`, `npm run build`: **not executed in this pass.** The test inventory is 62 backend test functions (one needs a real key and is skipped by default) and 21 frontend cases.
- The real embedding model (downloaded on first use) and any real Groq call.
- The PowerShell scripts (no PowerShell was available); they are short and call the same commands as the README.
- The syllabus PDF was **not** in the archive received for this pass. `docs/syllabus_report.md` comes from the earlier session and was not re-checked, and no evaluation numbers for the syllabus have been measured. The README states no measured accuracy figures.
- The 0.25 similarity threshold is a starting point. Tune it with the evaluation sweep on your real documents.

## Close the remaining acceptance items

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run-tests.ps1                         # expect "All checks passed."
powershell -ExecutionPolicy Bypass -File .\scripts\run-evaluation.ps1                    # samples, real embeddings
powershell -ExecutionPolicy Bypass -File .\scripts\run-evaluation.ps1 -Syllabus "C:\path\to\syllabus.pdf"
```

Then set `GROQ_API_KEY` in `backend\.env`, start both servers, upload the syllabus and the two sample PDFs, ask *"What are the final deliverables of the capstone project?"* and confirm the answer cites a real file and page. If any test fails, the failing test's name and message are the quickest pointer to the cause; please paste them into your next message.

## Known limitations

Text-based PDFs only (no OCR); heuristic topic detection; synchronous indexing; chat history only in the browser tab; single user with no authentication. See the README for the full list.
