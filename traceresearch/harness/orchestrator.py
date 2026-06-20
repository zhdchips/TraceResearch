"""Serial Agent Harness for TraceResearch MVP runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from traceresearch.agents.critic import Critic
from traceresearch.agents.planner import Planner
from traceresearch.agents.researcher import Researcher
from traceresearch.agents.verifier import Verifier
from traceresearch.agents.writer import Writer
from traceresearch.evidence.models import (
    Evidence,
    EvidenceStatus,
    ResearchRun,
    ResearchRunStatus,
)
from traceresearch.evidence.store import EvidenceStore
from traceresearch.harness.artifacts import RunArtifacts
from traceresearch.source_discovery.fixture_provider import FixtureSourceProvider
from traceresearch.trace.models import AgentRole, EventType, TraceEvent, TraceStatus
from traceresearch.trace.writer import TraceWriter


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: ResearchRunStatus
    artifact_dir: Path
    final_report_path: Path | None


class ResearchHarness:
    def __init__(
        self,
        *,
        planner: Planner | None = None,
        researcher: Researcher | None = None,
        verifier: Verifier | None = None,
        critic: Critic | None = None,
        writer: Writer | None = None,
    ) -> None:
        self.planner = planner or Planner()
        self.researcher = researcher or Researcher()
        self.verifier = verifier or Verifier()
        self.critic = critic or Critic()
        self.writer = writer or Writer()

    def run_fixture(
        self,
        *,
        query: str,
        case_id: str | None,
        output_dir: str | Path,
    ) -> RunResult:
        run_id = _new_run_id(case_id)
        artifacts = RunArtifacts.create(output_dir, run_id)
        trace = _TraceRecorder(run_id=run_id, writer=TraceWriter(artifacts.trace))
        evidence_store = EvidenceStore(artifacts.evidence)
        provider = FixtureSourceProvider(case_id=case_id)
        eval_case = provider.load_eval_case(case_id) if case_id else None

        trace.record(
            AgentRole.HARNESS,
            EventType.START,
            "Harness run started",
            f"case_id={case_id or 'none'}",
        )

        trace.record(AgentRole.PLANNER, EventType.START, query, "planning")
        brief = self.planner.plan(run_id=run_id, query=query, eval_case=eval_case)
        _write_json(artifacts.research_brief, brief.model_dump(mode="json"))
        _write_json(
            artifacts.research_tasks,
            [task.model_dump(mode="json") for task in brief.research_tasks],
        )
        trace.record(
            AgentRole.PLANNER,
            EventType.FINISH,
            "research question",
            f"created {len(brief.research_tasks)} research tasks",
        )

        trace.record(
            AgentRole.RESEARCHER,
            EventType.START,
            "research tasks",
            "source discovery",
        )
        stored_evidence: list[Evidence] = []
        sequence = 1
        for task in brief.research_tasks:
            task_evidence = self.researcher.research(
                run_id=run_id,
                task=task,
                provider=provider,
                start_index=sequence,
            )
            sequence += len(task_evidence)
            for item in task_evidence:
                stored = evidence_store.add(item)
                if stored.evidence_id not in {existing.evidence_id for existing in stored_evidence}:
                    stored_evidence.append(stored)
        trace.record(
            AgentRole.RESEARCHER,
            EventType.FINISH,
            "fixture provider results",
            f"stored {len(stored_evidence)} evidence candidates",
        )

        trace.record(
            AgentRole.HARNESS,
            EventType.TOOL_RESULT,
            "Evidence Store",
            f"evidence.jsonl contains {len(evidence_store.list_all())} rows",
        )

        trace.record(
            AgentRole.WRITER,
            EventType.START,
            "evidence candidates",
            "drafting outline and claims",
        )
        draft = self.writer.draft(brief=brief, evidence=stored_evidence)
        artifacts.outline.write_text(draft.outline_markdown, encoding="utf-8")
        artifacts.draft_report.write_text(draft.draft_markdown, encoding="utf-8")
        trace.record(
            AgentRole.WRITER,
            EventType.FINISH,
            "outline and draft claims",
            f"drafted {len(draft.claims)} claims",
        )

        trace.record(
            AgentRole.VERIFIER,
            EventType.START,
            "draft claims",
            "verifying claim support",
        )
        verification = self.verifier.verify(
            run_id=run_id,
            draft=draft,
            evidence=stored_evidence,
        )
        _write_json(artifacts.verification, verification.model_dump(mode="json"))
        verified_ids = {
            evidence_id
            for claim in verification.claim_results
            for evidence_id in claim.evidence_ids
        }
        for evidence_id in verified_ids:
            evidence_store.update_status(
                evidence_id,
                EvidenceStatus.VERIFIED,
                ["Verified by deterministic fixture verifier."],
            )
        verified_evidence = [
            item for item in evidence_store.list_all() if item.status == EvidenceStatus.VERIFIED
        ]
        trace.record(
            AgentRole.VERIFIER,
            EventType.FINISH,
            "draft claims",
            f"verified {len(verification.claim_results)} claims",
        )

        trace.record(
            AgentRole.CRITIC,
            EventType.START,
            "verified claims",
            "reviewing coverage",
        )
        critique = self.critic.review(
            brief=brief,
            evidence=verified_evidence,
            verification=verification,
        )
        _write_json(artifacts.critique, critique.model_dump(mode="json"))
        trace.record(
            AgentRole.CRITIC,
            EventType.FINISH,
            "coverage review",
            f"decision={critique.decision.value}",
        )

        trace.record(
            AgentRole.WRITER,
            EventType.START,
            "verified evidence",
            "writing final report",
        )
        final_report = self.writer.final(
            brief=brief,
            verified_evidence=verified_evidence,
            verification=verification,
            critique=critique,
        )
        artifacts.final_report.write_text(final_report.markdown, encoding="utf-8")
        _write_json(artifacts.report_json, final_report.report_json)
        trace.record(
            AgentRole.WRITER,
            EventType.FINISH,
            "final report",
            "wrote final_report.md and report.json",
        )

        run = ResearchRun(
            run_id=run_id,
            input_query=query,
            status=ResearchRunStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            artifact_dir=str(artifacts.run_dir),
            final_report_path=str(artifacts.final_report),
        )
        trace.record(
            AgentRole.HARNESS,
            EventType.FINISH,
            "completed run",
            f"status={run.status.value}",
        )
        return RunResult(
            run_id=run.run_id,
            status=run.status,
            artifact_dir=artifacts.run_dir,
            final_report_path=artifacts.final_report,
        )


class _TraceRecorder:
    def __init__(self, *, run_id: str, writer: TraceWriter) -> None:
        self.run_id = run_id
        self.writer = writer
        self.sequence = 1

    def record(
        self,
        agent_role: AgentRole,
        event_type: EventType,
        input_summary: str,
        output_summary: str,
        *,
        task_id: str | None = None,
        tool_name: str | None = None,
        status: TraceStatus = TraceStatus.SUCCESS,
    ) -> None:
        event = TraceEvent(
            trace_id=f"TR-{self.run_id}-{self.sequence:03d}",
            run_id=self.run_id,
            task_id=task_id,
            agent_role=agent_role,
            event_type=event_type,
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=output_summary,
            status=status,
            latency_ms=0,
            created_at=datetime.now(timezone.utc),
        )
        self.writer.append(event)
        self.sequence += 1


def _new_run_id(case_id: str | None) -> str:
    prefix = case_id or "run"
    return f"{prefix}-{uuid4().hex[:8]}"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
