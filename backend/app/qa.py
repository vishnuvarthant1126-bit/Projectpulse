"""Question answering orchestration (used by the API and the evaluation scripts)."""

from __future__ import annotations

import logging
import time

from .answering import ANSWER_SCHEMA, SYSTEM_PROMPT, assign_source_ids, build_user_prompt, validate_answer
from .demo import PRECOMPUTED_NOTICE, build_precomputed_answer, find_precomputed
from .llm import LLMError, parse_json
from .models import Answer, AskResponse, RetrievalMode, Validation
from .services import Services

log = logging.getLogger("projectpulse.qa")

NO_LLM_NOTICE = (
    "No answer model is configured, so ProjectPulse is showing the retrieved passages only. "
    "Set LLM_PROVIDER and LLM_API_KEY on the server to enable generated answers."
)


def ask(
    svc: Services, project: dict, question: str, mode: RetrievalMode, allow_precomputed: bool = True
) -> AskResponse:
    t0 = time.perf_counter()
    question = question.strip()
    result = svc.retriever.retrieve(project["id"], question, mode)
    passages = assign_source_ids(result.passages)
    if svc.settings.log_document_content:
        log.info("ask project=%s mode=%s question=%r", project["id"], mode, question)
    else:
        log.info(
            "ask project=%s mode=%s question_chars=%d passages=%d", project["id"], mode, len(question), len(passages)
        )

    def respond(answer_mode, answer, validation, notice=None, model=None, passages=passages):
        return AskResponse(
            question=question,
            mode=mode,
            answer_mode=answer_mode,
            notice=notice,
            model=model,
            answer=answer,
            passages=passages,
            validation=validation,
            intents=result.intents,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    # 1. Precomputed demo answers: sample project only, and only when no live model is configured.
    if allow_precomputed and project.get("is_sample") and svc.llm is None:
        entry = find_precomputed(svc, question)
        if entry:
            answer, validation, demo_passages = build_precomputed_answer(svc, project["id"], entry, passages)
            return respond("precomputed_demo", answer, validation, PRECOMPUTED_NOTICE, passages=demo_passages)

    # 2. Nothing retrieved: abstain without calling a model.
    if not passages:
        return respond(
            "no_evidence",
            Answer(
                answer_type="insufficient_evidence",
                summary="No passages in this project's ready documents matched the question, so there is no evidence to answer it.",
                missing_information=["Relevant documents may not be uploaded, or may still be processing."],
            ),
            Validation(),
        )

    # 3. No model configured: show evidence only.
    if svc.llm is None:
        return respond("retrieval_only", None, Validation(), NO_LLM_NOTICE)

    # 4. Live answer.
    docs = svc.db.query(
        "SELECT filename, doc_type, reporting_date FROM documents WHERE project_id = ? AND status = 'ready'",
        (project["id"],),
    )
    prompt = build_user_prompt(question, passages, docs)
    try:
        raw = parse_json(svc.llm.complete_json(SYSTEM_PROMPT, prompt, ANSWER_SCHEMA))
    except LLMError as exc:
        log.warning("answer model failed project=%s error=%s", project["id"], exc)
        return respond(
            "retrieval_only", None, Validation(), f"{exc} Showing the retrieved passages only.", svc.llm.name
        )
    answer, validation = validate_answer(raw, passages)
    if validation.invalid_citations or validation.removed_items:
        log.info(
            "answer validation project=%s invalid=%d removed=%d",
            project["id"],
            len(validation.invalid_citations),
            len(validation.removed_items),
        )
    return respond("live", answer, validation, None, svc.llm.name)
