# Evaluation

Everything here runs against the fictional **Project Beacon** sample (`sample_data/beacon/`).
The dataset is small (30 questions over 6 documents / 38 chunks), so treat the numbers as a
sanity check for this corpus, not a benchmark.

## Dataset: `questions.json`

30 hand-written questions, each with a reference answer and supporting passages (exact quotes
from a named document) for human review.

| Category | Count | What it tests |
|---|---:|---|
| `exact` | 8 | Exact names and identifiers (`BCN-201`, `SP-7781`, `M3`, `R4`, `A2`, people) |
| `paraphrase` | 7 | Wording that differs from the documents ("overnight data load" for "nightly batch sync") |
| `comparison` | 7 | Plan versus progress, including one milestone (M5) with no update, where the right answer is "not stated", not "delayed" |
| `conflict` | 3 | The deliberate disagreement over when M2 was completed (4 Mar meeting notes vs 6 Mar report) |
| `unanswerable` | 5 | Budget, scanner counts, a meeting that doesn't exist, a false premise, contract value |

`backend/tests/test_eval_dataset.py` checks that every supporting quote exists in the named
document, so a typo can't silently lower recall.

## Relevance labels

Binary and derived automatically from the supporting quotes. A chunk is relevant to a question
if its text contains, ignoring case and whitespace, at least one of that question's supporting
quotes. Because labels are tied to quotes rather than chunk IDs, they stay valid when chunk
size or overlap change. Questions without supporting quotes (U02 to U05) are left out of
retrieval metrics. U01 (budget) keeps its one related passage.

## Retrieval metrics: `run_retrieval_eval.py`

```bash
python eval/run_retrieval_eval.py            # writes results/retrieval_results.{md,json}
python eval/run_retrieval_eval.py --tag bge  # e.g. after changing EMBEDDING_* settings
```

- **Recall@k**: fraction of a question's supporting quotes found in the top-k ranked chunks.
  This is quote-level, so a question that needs two passages scores 0.5 when only one is found.
- **MRR**: mean of 1 / rank of the first relevant chunk (0 if none is ranked).
- **Evidence recall**: the same recall measured on the final evidence set sent to the answer
  model, after the plan/update coverage rules and truncation to `ANSWER_MAX_PASSAGES` (8).
- **Paired bootstrap**: 95% CI of the per-question difference (hybrid minus each single mode),
  from 10,000 resamples.

The metrics measure the raw ranking. They do not include the coverage rules, apart from
evidence recall. Ties in RRF are broken deterministically, and repeated runs give identical
numbers.

### Measured results (run 2026-09-25, local all-MiniLM-L6-v2, chunk 900/150)

| Mode | Recall@1 | Recall@3 | Recall@5 | Recall@8 | MRR | Evidence recall |
|---|---:|---:|---:|---:|---:|---:|
| keyword (BM25) | 0.340 | 0.532 | 0.647 | 0.801 | 0.631 | 0.821 |
| semantic | 0.218 | 0.567 | 0.676 | 0.894 | 0.569 | 0.904 |
| hybrid (RRF) | 0.282 | 0.567 | **0.734** | 0.891 | **0.645** | 0.891 |

What these numbers support:

- Hybrid had the highest Recall@5 and MRR, but the margins are small, and every paired bootstrap
  CI includes zero (MRR vs keyword: +0.013 [-0.060, +0.080]; vs semantic: +0.076 [-0.046, +0.199]).
  **On this dataset, hybrid is not shown to be significantly better than either single mode.**
- Keyword search is best at rank 1 (Recall@1 0.340) and on identifier questions. Semantic search
  has the best Recall@8 and evidence recall. Hybrid sits between them on those measures.
- Per category: keyword wins on the 3 conflict questions (which reuse exact wording); hybrid and
  semantic do better on paraphrase and comparison questions.
- The retrieval settings were not tuned on this set. The numbers above are from the first
  configuration. The only change after the first run was the deterministic RRF tie-break, made for
  reproducibility.

The full per-question table is in `results/retrieval_results.md`.

## Answer quality: `run_answer_eval.py`

This needs a configured answer model (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`). **It has not
been run for this release, because no API key was available in the build environment. No
answer-quality numbers are claimed.**

```bash
python eval/run_answer_eval.py --mode hybrid            # deterministic checks only
python eval/run_answer_eval.py --mode hybrid --judge    # + automated LLM judge
python eval/run_answer_eval.py --template-only          # blank manual review sheet
```

Three things are scored separately:

| Dimension | How it is scored |
|---|---|
| Citation validity (deterministic) | Share of model-returned citations that refer to a retrieved passage, before the validator removes invalid ones. Also counts dropped statements and dates that are not in the cited passages. |
| Abstention (deterministic) | Unanswerable questions should come back as `insufficient_evidence`; the false-abstention rate on answerable questions is reported too. Conflict questions should include a `conflicts` entry. |
| Correctness and citation support (automated LLM judge) | Optional `--judge`. Grades correctness against the reference answer and whether cited passages support each statement. Reported under the label **"Automated LLM judge - not human-verified"**. |

The precomputed demo answers are never evaluated: they were written by hand and are not model
output. The script also disables them explicitly.

### Manual review format

`results/manual_review_<mode>.csv` (or `manual_review_template.csv`) has one row per question:
the question, expected behaviour, reference answer, model answer, cited passage text, the
automated verdicts, and blank reviewer columns:

- `human_correctness`: correct / partial / incorrect
- `human_citation_support`: supported / partial / unsupported
- `human_abstention_ok`: y / n
- `human_notes`

Report human-reviewed numbers separately from automated-judge numbers.
