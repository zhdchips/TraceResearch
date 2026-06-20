from traceresearch.agents.planner import Planner


def test_planner_returns_clarifications_without_tasks_for_ambiguous_query() -> None:
    brief = Planner().plan(
        run_id="run-ambiguous",
        query="Research everything about artificial intelligence.",
    )

    assert brief.open_clarifications
    assert brief.research_tasks == []
    assert brief.perspectives == []


def test_planner_records_explicit_assumption_for_missing_time_range() -> None:
    brief = Planner().plan(
        run_id="run-assumption",
        query="Compare LangGraph and AutoGen for building research agents",
    )

    assert "Assume current stable public documentation is acceptable." in brief.assumptions
    assert brief.open_clarifications == []
    assert brief.research_tasks
