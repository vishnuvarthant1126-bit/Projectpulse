# ruff: noqa: I001  (common must be imported first: it puts backend/ on sys.path)
"""Compare keyword-only, semantic-only and hybrid (RRF) retrieval on the sample project.

Relevance labels
----------------
Binary, derived from the hand-written supporting quotes in eval/questions.json: a chunk
is *relevant* to a question if its text contains (case/whitespace-insensitive) at least
one of that question's supporting quotes. Questions with no supporting quotes (pure
"not in the documents" questions) are excluded from retrieval metrics.

Metrics (per mode, averaged over questions)
-------------------------------------------
Recall@k  fraction of a question's supporting quotes found in at least one of the top-k
          ranked chunks (quote-level recall, so a question needing two passages scores
          0.5 when only one is retrieved).
MRR       1 / rank of the first relevant chunk in the ranked list (0 if none is ranked).
Evidence recall  the same quote-level recall, but over the final evidence set actually
          sent to the answer model (after coverage rules and truncation to
          ANSWER_MAX_PASSAGES).

Usage:  python eval/run_retrieval_eval.py [--ks 1 3 5 8] [--tag name]
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from datetime import datetime, UTC

from common import RESULTS_DIR, build_eval_services, load_questions, relevant_chunks

MODES = ("keyword", "semantic", "hybrid")


def recall_at(ranked: list[str], quotes: list[set[str]], k: int) -> float:
    top = set(ranked[:k])
    return sum(1 for ids in quotes if ids & top) / len(quotes)


def reciprocal_rank(ranked: list[str], quotes: list[set[str]]) -> float:
    relevant = set().union(*quotes)
    for i, cid in enumerate(ranked, start=1):
        if cid in relevant:
            return 1.0 / i
    return 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ks", type=int, nargs="+", default=[1, 3, 5, 8])
    ap.add_argument("--tag", default=None, help="suffix for the output files")
    args = ap.parse_args()

    svc, project = build_eval_services()
    pid = project["id"]
    questions = [q for q in load_questions() if q["supporting"]]
    n_chunks = svc.db.one("SELECT COUNT(*) AS n FROM chunks WHERE project_id = ?", (pid,))["n"]

    per_q: list[dict] = []
    for q in questions:
        quotes = relevant_chunks(svc, pid, q)
        row = {"id": q["id"], "category": q["category"], "n_quotes": len(quotes)}
        for mode in MODES:
            ranked = [c.chunk_id for c in svc.retriever.rank(pid, q["question"], mode)]
            evidence = [p.chunk_id for p in svc.retriever.retrieve(pid, q["question"], mode).passages]
            row[mode] = {
                **{f"recall@{k}": recall_at(ranked, quotes, k) for k in args.ks},
                "rr": reciprocal_rank(ranked, quotes),
                "evidence_recall": recall_at(evidence, quotes, len(evidence)),
                "first_relevant_rank": next((i for i, c in enumerate(ranked, 1) if c in set().union(*quotes)), None),
            }
        per_q.append(row)

    def agg(rows: list[dict], mode: str, key: str) -> float:
        return statistics.fmean(r[mode][key] for r in rows)

    metric_keys = [f"recall@{k}" for k in args.ks] + ["rr", "evidence_recall"]
    categories = sorted({r["category"] for r in per_q})
    summary = {
        "overall": {m: {k: agg(per_q, m, k) for k in metric_keys} for m in MODES},
        "by_category": {
            c: {m: {k: agg([r for r in per_q if r["category"] == c], m, k) for k in metric_keys} for m in MODES}
            for c in categories
        },
    }

    # Head-to-head: questions where hybrid's reciprocal rank beats / ties / loses to each single mode.
    h2h = {}
    for other in ("keyword", "semantic"):
        wins = sum(1 for r in per_q if r["hybrid"]["rr"] > r[other]["rr"])
        losses = sum(1 for r in per_q if r["hybrid"]["rr"] < r[other]["rr"])
        h2h[other] = {"hybrid_better": wins, "tie": len(per_q) - wins - losses, "hybrid_worse": losses}

    # Paired bootstrap 95% CI for the per-question difference in reciprocal rank / Recall@5.
    rng = random.Random(1234)
    ci = {}
    for other in ("keyword", "semantic"):
        for key in ("rr", "recall@5" if 5 in args.ks else metric_keys[0]):
            diffs = [r["hybrid"][key] - r[other][key] for r in per_q]
            boots = sorted(statistics.fmean(rng.choice(diffs) for _ in diffs) for _ in range(10_000))
            ci[f"hybrid_minus_{other}_{key}"] = {
                "mean": statistics.fmean(diffs),
                "ci95": [boots[249], boots[9749]],
            }

    meta = {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "embedding_model": svc.embedder.name,
        "chunk_size": svc.settings.chunk_size,
        "chunk_overlap": svc.settings.chunk_overlap,
        "candidates_per_retriever": svc.settings.retrieval_candidates,
        "answer_max_passages": svc.settings.answer_max_passages,
        "rrf_k": svc.settings.rrf_k,
        "n_questions_scored": len(per_q),
        "n_chunks_in_corpus": n_chunks,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.tag}" if args.tag else ""
    out_json = RESULTS_DIR / f"retrieval_results{suffix}.json"
    out_json.write_text(
        json.dumps(
            {"meta": meta, "summary": summary, "head_to_head": h2h, "bootstrap": ci, "per_question": per_q}, indent=2
        )
    )

    # Markdown report
    lines = [
        "# Retrieval evaluation: keyword vs semantic vs hybrid",
        "",
        f"Run: {meta['run_at']} · embeddings `{meta['embedding_model']}` · chunk {meta['chunk_size']}/{meta['chunk_overlap']} chars · "
        f"{meta['n_chunks_in_corpus']} chunks · RRF k={meta['rrf_k']} · {meta['candidates_per_retriever']} candidates per retriever",
        "",
        f"Scored questions: {len(per_q)} (questions with at least one supporting passage; the 4 questions with none are excluded).",
        "Relevance: a chunk is relevant if it contains one of the question's hand-written supporting quotes.",
        "",
        "## Overall",
        "",
        "| Mode | " + " | ".join(f"Recall@{k}" for k in args.ks) + " | MRR | Evidence recall |",
        "|---|" + "---:|" * (len(args.ks) + 2),
    ]
    for m in MODES:
        s = summary["overall"][m]
        lines.append(
            f"| {m} | "
            + " | ".join(f"{s[f'recall@{k}']:.3f}" for k in args.ks)
            + f" | {s['rr']:.3f} | {s['evidence_recall']:.3f} |"
        )
    lines += [
        "",
        "## By category (MRR / Recall@5)",
        "",
        "| Category | n | keyword | semantic | hybrid |",
        "|---|---:|---|---|---|",
    ]
    for c in categories:
        n = sum(1 for r in per_q if r["category"] == c)
        cells = [
            f"{summary['by_category'][c][m]['rr']:.3f} / {summary['by_category'][c][m].get('recall@5', float('nan')):.3f}"
            for m in MODES
        ]
        lines.append(f"| {c} | {n} | " + " | ".join(cells) + " |")
    lines += ["", "## Hybrid vs single modes (per-question reciprocal rank)", ""]
    for other, v in h2h.items():
        lines.append(
            f"- vs {other}: hybrid better on {v['hybrid_better']}, tie on {v['tie']}, worse on {v['hybrid_worse']}"
        )
    lines += ["", "## Paired bootstrap (10,000 resamples of questions, 95% CI of hybrid minus single mode)", ""]
    for name, v in ci.items():
        lines.append(f"- {name}: mean {v['mean']:+.3f}, 95% CI [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]")
    lines += [
        "",
        "## Per question (first relevant rank: keyword / semantic / hybrid)",
        "",
        "| ID | Category | keyword | semantic | hybrid |",
        "|---|---|---:|---:|---:|",
    ]
    for r in per_q:
        lines.append(
            f"| {r['id']} | {r['category']} | "
            + " | ".join(str(r[m]["first_relevant_rank"] or "not found") for m in MODES)
            + " |"
        )
    out_md = RESULTS_DIR / f"retrieval_results{suffix}.md"
    out_md.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:16]))
    print(f"\nWrote {out_json} and {out_md}")


if __name__ == "__main__":
    main()
