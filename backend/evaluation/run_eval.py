"""Measure retrieval quality on the labelled dataset. Everything printed is measured, nothing is hard-coded.

Usage (from backend/):
  python -m evaluation.run_eval --pdf "C:\\path\\syllabus.pdf"
  python -m evaluation.run_eval --pdf syllabus.pdf --with-llm        # also checks answers (needs GROQ_API_KEY)
Several PDFs can be given; an item may name the file it expects with "expected_file".
Use the real embedding model (default from .env). `--backend hash` is an offline smoke test only.
"""
import argparse
import json
import statistics
import tempfile
import time
import uuid
from pathlib import Path

from app.core.config import Settings
from app.core.container import build_container
from app.db.models import Document
from app.services.ingestion_service import ingest_document

THRESHOLDS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]


def is_expected(item: dict, filename: str, page: int) -> bool:
    """A retrieved (file, page) counts when the page matches and, if the item names a file, the file matches too."""
    return page in item["expected_pages"] and (not item.get("expected_file") or item["expected_file"] == filename)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, nargs="+")
    ap.add_argument("--dataset", default=str(Path(__file__).with_name("eval_dataset.json")))
    ap.add_argument("--backend", choices=["sentence-transformers", "hash"], default=None)
    ap.add_argument("--chunk-target-tokens", type=int, default=None)
    ap.add_argument("--chunk-max-tokens", type=int, default=None)
    ap.add_argument("--chunk-overlap-tokens", type=int, default=None)
    ap.add_argument("--with-llm", action="store_true")
    ap.add_argument("--out", default=str(Path(__file__).with_name("last_report.json")))
    args = ap.parse_args()

    overrides = {"embedding_backend": args.backend} if args.backend else {}
    for name in ("chunk_target_tokens", "chunk_max_tokens", "chunk_overlap_tokens"):
        value = getattr(args, name)
        if value is not None:
            overrides[name] = value
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:  # Windows keeps SQLite/Chroma files locked at exit
        settings = Settings(data_dir=Path(tmp), **overrides)
        c = build_container(settings)
        indexing_duration_ms = 0.0
        with c.session_factory() as db:
            from app.services.pdf_service import extract_pdf
            pages_text: dict[tuple[str, int], str] = {}  # (filename, page) -> extracted text, for label checking
            for pdf in args.pdf:
                path = Path(pdf)
                doc = Document(id=str(uuid.uuid4()), filename=path.name, stored_name="eval.pdf", file_hash=uuid.uuid4().hex)
                db.add(doc); db.commit()
                indexing_start = time.perf_counter()
                ingest_document(c, db, doc, path)
                indexing_duration_ms += (time.perf_counter() - indexing_start) * 1000
                print(f"Indexed {path.name}: status={doc.status}, pages={doc.page_count}, chunks={doc.chunk_count}")
                if doc.status != "Ready":
                    raise SystemExit(f"Indexing failed: {doc.error_message}")
                pages_text.update({(path.name, p.page_number): p.text for p in extract_pdf(path).pages})
        data = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
        rows, latencies, label_problems = [], [], []
        for item in data["answerable"]:
            files = [item["expected_file"]] if item.get("expected_file") else sorted({f for f, _ in pages_text})
            if not any(item["evidence_phrase"].lower() in pages_text.get((f, p), "").lower() for f in files for p in item["expected_pages"]):
                label_problems.append(item["question"])
            r = c.retrieval.search(item["question"], None, top_k=5, min_score=-1.0)
            latencies.append(r.latency_ms)
            pages = [(h.filename, h.page) for h in r.candidates]
            rows.append({"q": item["question"], "expected": item["expected_pages"], "expected_file": item.get("expected_file"),
                         "top5": [f"{f} p.{p}" for f, p in pages], "top_score": r.top_score,
                         "hit": any(is_expected(item, f, p) for f, p in pages), "top1": bool(pages) and is_expected(item, *pages[0])})
        un_scores = []
        for q in data["unanswerable"]:
            r = c.retrieval.search(q, None, top_k=5, min_score=-1.0)
            latencies.append(r.latency_ms)
            un_scores.append(r.top_score or 0.0)

        n = len(rows)
        report = {
            "embedding_model": c.embedder.name,
            "chunk_target_tokens": settings.chunk_target_tokens,
            "chunk_max_tokens": settings.chunk_max_tokens,
            "chunk_overlap_tokens": settings.chunk_overlap_tokens,
            "chunks_created": c.store.count(),
            "indexing_duration_ms": round(indexing_duration_ms, 1),
            "answerable_questions": n,
            "unanswerable_questions": len(un_scores),
            "recall_at_5_page": round(sum(r["hit"] for r in rows) / n, 3),
            "top1_page_accuracy": round(sum(r["top1"] for r in rows) / n, 3),
            "latency_ms_mean": round(statistics.mean(latencies), 1),
            "latency_ms_max": round(max(latencies), 1),
            "label_problems": label_problems,
            "threshold_sweep": [
                {"min_score": t,
                 "answerable_kept": round(sum((r["top_score"] or 0) >= t for r in rows) / n, 3),
                 "unanswerable_rejected": round(sum(s < t for s in un_scores) / len(un_scores), 3)}
                for t in THRESHOLDS
            ],
            "misses": [r for r in rows if not r["hit"]],
        }

        if args.with_llm:
            if not c.llm.configured:
                raise SystemExit("--with-llm needs GROQ_API_KEY in backend/.env")
            ok_cite = ok_refuse = 0
            for item in data["answerable"]:
                res = c.rag.answer(item["question"], c.retrieval.search(item["question"], None))
                ok_cite += int(not res.insufficient_evidence and any(is_expected(item, s.filename, s.page) for _, s in res.sources))
            for q in data["unanswerable"]:
                ok_refuse += int(c.rag.answer(q, c.retrieval.search(q, None)).insufficient_evidence)
            report["answers_with_correct_page_citation"] = round(ok_cite / n, 3)
            report["unanswerable_refused"] = round(ok_refuse / len(data["unanswerable"]), 3)

        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k not in ("misses", "threshold_sweep")}, indent=2))
        print("\nmin_score  answerable_kept  unanswerable_rejected")
        for row in report["threshold_sweep"]:
            print(f"{row['min_score']:<10} {row['answerable_kept']:<16} {row['unanswerable_rejected']}")
        print(f"\nReport written to {args.out}")
        if args.backend == "hash":
            print("NOTE: the hash embedder is a test double (word overlap only). These numbers are NOT representative of the real model.")


if __name__ == "__main__":
    main()
