"""Deterministic Planner for the MVP run path."""

from __future__ import annotations

from traceresearch.evidence.models import EvalCase, ResearchBrief, ResearchTask


class Planner:
    def plan(
        self,
        *,
        run_id: str,
        query: str,
        eval_case: EvalCase | None = None,
    ) -> ResearchBrief:
        if eval_case is None:
            ambiguity = _detect_ambiguity(query)
            if ambiguity.open_clarifications:
                return ResearchBrief(
                    run_id=run_id,
                    objective=query,
                    scope_boundaries=[
                        "Research will not start until the request is scoped safely.",
                    ],
                    assumptions=ambiguity.assumptions,
                    open_clarifications=ambiguity.open_clarifications,
                    perspectives=[],
                    success_criteria=[
                        "User provides enough scope to create deterministic research tasks.",
                    ],
                    research_tasks=[],
                )

        perspectives = (
            list(eval_case.expected_perspectives)
            if eval_case is not None
            else ["technical grounding", "source authority", "risk and limitation"]
        )
        objective = eval_case.input_query if eval_case is not None else query
        ambiguity = _detect_ambiguity(query)

        tasks = [
            ResearchTask(
                research_task_id=f"{run_id}-task-{index:02d}",
                run_id=run_id,
                perspective=perspective,
                objective=f"Gather evidence for {perspective}",
                query=f"{query} {perspective}",
                source_limit=5,
            )
            for index, perspective in enumerate(perspectives, start=1)
        ]

        return ResearchBrief(
            run_id=run_id,
            objective=objective,
            scope_boundaries=[
                "Use deterministic fixture sources for this MVP run.",
                "Do not use live web search.",
            ],
            assumptions=[
                "Fixture sources are treated as the source discovery corpus.",
                "The report should surface evidence IDs for key claims.",
                *ambiguity.assumptions,
            ],
            open_clarifications=[],
            perspectives=perspectives,
            success_criteria=[
                "Each key claim references verified evidence.",
                "Unsupported claims are excluded from the final report.",
                "Trace events record every Agent step.",
            ],
            research_tasks=tasks,
        )


class _AmbiguityResult:
    def __init__(
        self,
        *,
        open_clarifications: list[str] | None = None,
        assumptions: list[str] | None = None,
    ) -> None:
        self.open_clarifications = open_clarifications or []
        self.assumptions = assumptions or []


def _detect_ambiguity(query: str) -> _AmbiguityResult:
    normalized = " ".join(query.lower().split())
    clarifications: list[str] = []
    assumptions: list[str] = []

    if "everything about" in normalized or normalized in {
        "research everything",
        "research everything about technology",
    }:
        clarifications.append(
            "Please narrow the research object, scope boundaries, and expected output."
        )

    if any(
        phrase in normalized
        for phrase in [
            "best options",
            "best choice",
            "for adoption",
        ]
    ) and not any(
        token in normalized
        for token in [
            "langgraph",
            "autogen",
            "crewai",
            "openhands",
            "rag",
            "ai coding agent",
            "financial",
        ]
    ):
        clarifications.append("Please specify the research object or decision target.")

    asks_current_trends = any(
        token in normalized
        for token in ["current", "latest", "trend", "trends", "market"]
    )
    has_time_range = any(
        token in normalized
        for token in ["2024", "2025", "2026", "last ", "past ", "current stable"]
    )
    if asks_current_trends and not has_time_range:
        clarifications.append(
            "Please specify the time range for current or trend-oriented research."
        )

    if normalized.startswith("research ") and not any(
        token in normalized
        for token in [
            "compare",
            "assess",
            "evaluate",
            "summarize",
            "explain",
            "design",
            "decision",
            "report",
            "memo",
        ]
    ):
        clarifications.append(
            "Please specify the output goal, such as comparison, assessment, report, or recommendation."
        )

    if not clarifications and not has_time_range:
        assumptions.append("Assume current stable public documentation is acceptable.")

    return _AmbiguityResult(
        open_clarifications=_unique(clarifications),
        assumptions=_unique(assumptions),
    )


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
