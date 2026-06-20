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
        perspectives = (
            list(eval_case.expected_perspectives)
            if eval_case is not None
            else ["technical grounding", "source authority", "risk and limitation"]
        )
        objective = eval_case.input_query if eval_case is not None else query

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
