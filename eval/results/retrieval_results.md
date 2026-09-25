# Retrieval evaluation: keyword vs semantic vs hybrid

Run: 2026-09-25T04:14:24+00:00 · embeddings `local:sentence-transformers/all-MiniLM-L6-v2` · chunk 900/150 chars · 38 chunks · RRF k=60 · 20 candidates per retriever

Scored questions: 26 (questions with at least one supporting passage; the 4 questions with none are excluded).
Relevance: a chunk is relevant if it contains one of the question's hand-written supporting quotes.

## Overall

| Mode | Recall@1 | Recall@3 | Recall@5 | Recall@8 | MRR | Evidence recall |
|---|---:|---:|---:|---:|---:|---:|
| keyword | 0.340 | 0.532 | 0.647 | 0.801 | 0.631 | 0.821 |
| semantic | 0.218 | 0.567 | 0.676 | 0.894 | 0.569 | 0.904 |
| hybrid | 0.282 | 0.567 | 0.734 | 0.891 | 0.645 | 0.891 |

## By category (MRR / Recall@5)

| Category | n | keyword | semantic | hybrid |
|---|---:|---|---|---|
| comparison | 7 | 0.498 / 0.405 | 0.571 / 0.655 | 0.616 / 0.655 |
| conflict | 3 | 1.000 / 1.000 | 0.583 / 0.833 | 0.833 / 0.833 |
| exact | 8 | 0.640 / 0.812 | 0.609 / 0.625 | 0.634 / 0.750 |
| paraphrase | 7 | 0.544 / 0.500 | 0.452 / 0.643 | 0.554 / 0.714 |
| unanswerable | 1 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |

## Hybrid vs single modes (per-question reciprocal rank)

- vs keyword: hybrid better on 7, tie on 16, worse on 3
- vs semantic: hybrid better on 9, tie on 12, worse on 5

## Paired bootstrap (10,000 resamples of questions, 95% CI of hybrid minus single mode)

- hybrid_minus_keyword_rr: mean +0.013, 95% CI [-0.060, +0.080]
- hybrid_minus_keyword_recall@5: mean +0.087, 95% CI [-0.026, +0.208]
- hybrid_minus_semantic_rr: mean +0.076, 95% CI [-0.046, +0.199]
- hybrid_minus_semantic_recall@5: mean +0.058, 95% CI [-0.077, +0.212]

## Per question (first relevant rank: keyword / semantic / hybrid)

| ID | Category | keyword | semantic | hybrid |
|---|---|---:|---:|---:|
| E01 | exact | 1 | 1 | 1 |
| E02 | exact | 1 | 1 | 1 |
| E03 | exact | 6 | 8 | 8 |
| E04 | exact | 5 | 6 | 5 |
| E05 | exact | 2 | 4 | 2 |
| E06 | exact | 1 | 1 | 1 |
| E07 | exact | 1 | 1 | 1 |
| E08 | exact | 4 | 3 | 4 |
| P01 | paraphrase | 1 | 2 | 2 |
| P02 | paraphrase | 7 | 1 | 2 |
| P03 | paraphrase | 1 | 3 | 1 |
| P04 | paraphrase | not found | 3 | 8 |
| P05 | paraphrase | 2 | 2 | 2 |
| P06 | paraphrase | 6 | 6 | 4 |
| P07 | paraphrase | 1 | 3 | 1 |
| C01 | comparison | 6 | 3 | 3 |
| C02 | comparison | not found | 1 | 3 |
| C03 | comparison | 1 | 3 | 1 |
| C04 | comparison | 1 | 1 | 1 |
| C05 | comparison | 4 | 2 | 2 |
| C06 | comparison | 1 | 2 | 1 |
| C07 | comparison | 15 | 3 | 7 |
| X01 | conflict | 1 | 2 | 1 |
| X02 | conflict | 1 | 1 | 1 |
| X03 | conflict | 1 | 4 | 2 |
| U01 | unanswerable | 1 | 1 | 1 |
