"""Serial Agent Harness for TraceResearch MVP runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from traceresearch.agents.critic import Critic
from traceresearch.agents.lead_researcher import LeadResearchAgent
from traceresearch.agents.llm_verifier import LLMVerifier
from traceresearch.agents.llm_writer import LLMWriter
from traceresearch.agents.planner import Planner
from traceresearch.agents.researcher import Researcher
from traceresearch.agents.verifier_protocol import VerifierProtocol
from traceresearch.agents.writer_protocol import WriterProtocol
from traceresearch.evidence.models import (
    Evidence,
    EvidenceStatus,
    ResearchRun,
    ResearchRunStatus,
)
from traceresearch.evidence.store import EvidenceStore
from traceresearch.harness.artifacts import RunArtifacts
from traceresearch.harness.mode_factory import build_verifier, build_writer
from traceresearch.llm.provider import LLMProvider
from traceresearch.source_discovery.base import SourceDiscoveryError, SourceDiscoveryProvider
from traceresearch.source_discovery.fixture_provider import FixtureSourceProvider
from traceresearch.trace.models import (
    AgentRole,
    ErrorInfo,
    EventType,
    TokenUsage,
    TraceEvent,
    TraceStatus,
)
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
        lead_researcher: LeadResearchAgent | None = None,
        verifier: VerifierProtocol | None = None,
        critic: Critic | None = None,
        writer: WriterProtocol | None = None,
        writer_mode: str = "deterministic",
        verifier_mode: str = "deterministic",
        llm_provider: LLMProvider | None = None,
        max_concurrent_research_tasks: int | None = None,
    ) -> None:
        self.planner = planner or Planner()
        self.researcher = researcher or Researcher()
        self.lead_researcher = lead_researcher or LeadResearchAgent(
            max_concurrent=max_concurrent_research_tasks,
        )
        self.critic = critic or Critic()

        # Direct injection takes priority over mode-based construction
        if writer is not None:
            self.writer = writer
        else:
            self.writer = build_writer(mode=writer_mode, llm_provider=llm_provider)

        if verifier is not None:
            self.verifier = verifier
        else:
            self.verifier = build_verifier(mode=verifier_mode, llm_provider=llm_provider)

    def run(
        self,
        *,
        query: str,
        source_provider: SourceDiscoveryProvider,
        output_dir: str | Path,
    ) -> RunResult:
        return self._run_with_provider(
            query=query,
            provider=source_provider,
            output_dir=output_dir,
            run_id=_new_run_id(None),
            eval_case=None,
            case_id=None,
        )

    def run_fixture(
        self,
        *,
        query: str,
        case_id: str | None,
        output_dir: str | Path,
    ) -> RunResult:
        provider = FixtureSourceProvider(case_id=case_id)
        eval_case = provider.load_eval_case(case_id) if case_id else None
        return self._run_with_provider(
            query=query,
            provider=provider,
            output_dir=output_dir,
            run_id=_new_run_id(case_id),
            eval_case=eval_case,
            case_id=case_id,
        )

    def _run_with_provider(
        self,
        *,
        query: str,
        provider: SourceDiscoveryProvider,
        output_dir: str | Path,
        run_id: str,
        eval_case,
        case_id: str | None,
    ) -> RunResult:
        artifacts = RunArtifacts.create(output_dir, run_id)
        trace = _TraceRecorder(run_id=run_id, writer=TraceWriter(artifacts.trace))
        evidence_store = EvidenceStore(artifacts.evidence)
        provider_tool_name = _provider_tool_name(provider)

        trace.record(
            AgentRole.HARNESS,
            EventType.START,
            "Harness run started",
            f"case_id={case_id or 'none'}; source_provider={provider.provider_name}",
        )

        trace.record(AgentRole.PLANNER, EventType.START, query, "planning")
        brief = self.planner.plan(run_id=run_id, query=query, eval_case=eval_case)
        _write_json(artifacts.research_brief, brief.model_dump(mode="json"))
        trace.record(
            AgentRole.PLANNER,
            EventType.FINISH,
            "research question",
            f"created {len(brief.research_tasks)} research tasks",
            status=TraceStatus.NEEDS_CLARIFICATION
            if brief.open_clarifications
            else TraceStatus.SUCCESS,
        )

        if brief.open_clarifications:
            trace.record(
                AgentRole.HARNESS,
                EventType.FINISH,
                "needs clarification",
                "research stopped before source discovery",
                status=TraceStatus.NEEDS_CLARIFICATION,
            )
            return RunResult(
                run_id=run_id,
                status=ResearchRunStatus.NEEDS_CLARIFICATION,
                artifact_dir=artifacts.run_dir,
                final_report_path=None,
            )

        _write_json(
            artifacts.research_tasks,
            [task.model_dump(mode="json") for task in brief.research_tasks],
        )

        trace.record(
            AgentRole.RESEARCHER,
            EventType.START,
            "research tasks",
            "source discovery via subagent executor",
        )
        research_result = self.lead_researcher.conduct_research(
            brief=brief,
            provider=provider,
            run_id=run_id,
            run_dir=artifacts.run_dir,
            trace_writer=trace.writer,
            provider_tool_name=provider_tool_name,
        )
        stored_evidence: list[Evidence] = research_result.evidence
        failed_task_ids: list[str] = research_result.failed_task_ids
        trace.record(
            AgentRole.RESEARCHER,
            EventType.FINISH,
            f"{provider.provider_name} provider results",
            f"stored {len(stored_evidence)} evidence candidates",
        )

        # All-failure detection: if tasks existed but no evidence was collected,
        # treat as a failed run (partial failure policy still allows 0-evidence
        # but the run should surface the failure).
        if brief.research_tasks and not stored_evidence:
            trace.record(
                AgentRole.HARNESS,
                EventType.FINISH,
                "failed run — no evidence collected",
                "status=failed; all research tasks failed or timed out",
                status=TraceStatus.FAILED,
                error=ErrorInfo(
                    type="AllResearchTasksFailed",
                    message="All research tasks failed or timed out — no evidence collected",
                ),
            )
            return RunResult(
                run_id=run_id,
                status=ResearchRunStatus.FAILED,
                artifact_dir=artifacts.run_dir,
                final_report_path=None,
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

        _verifier_is_llm = isinstance(self.verifier, LLMVerifier)
        _verifier_llm_mode = "llm" if _verifier_is_llm else "deterministic"
        _verifier_llm_model = (
            self.verifier._provider.model if _verifier_is_llm else None  # type: ignore[union-attr]
        )
        trace.record(
            AgentRole.VERIFIER,
            EventType.START,
            "draft claims",
            "verifying claim support",
            llm_mode=_verifier_llm_mode,
            llm_model=_verifier_llm_model,
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
            llm_mode=_verifier_llm_mode,
            llm_model=_verifier_llm_model,
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
            failed_task_ids=failed_task_ids,
        )
        _write_json(artifacts.critique, critique.model_dump(mode="json"))
        trace.record(
            AgentRole.CRITIC,
            EventType.FINISH,
            "coverage review",
            f"decision={critique.decision.value}",
        )

        _writer_is_llm = isinstance(self.writer, LLMWriter)
        _writer_llm_mode = "llm" if _writer_is_llm else "deterministic"
        _writer_llm_model = (
            self.writer._provider.model if _writer_is_llm else None  # type: ignore[union-attr]
        )
        trace.record(
            AgentRole.WRITER,
            EventType.START,
            "verified evidence",
            "writing final report",
            llm_mode=_writer_llm_mode,
            llm_model=_writer_llm_model,
        )
        final_report = self.writer.final(
            brief=brief,
            verified_evidence=verified_evidence,
            verification=verification,
            critique=critique,
        )
        # Record LLM token usage if available
        _writer_llm_usage = None
        if _writer_is_llm:
            try:
                _writer_llm_usage = self.writer._provider.last_token_usage  # type: ignore[union-attr]
            except AttributeError:
                pass
        artifacts.final_report.write_text(final_report.markdown, encoding="utf-8")
        _write_json(artifacts.report_json, final_report.report_json)
        trace.record(
            AgentRole.WRITER,
            EventType.FINISH,
            "final report",
            "wrote final_report.md and report.json",
            llm_mode=_writer_llm_mode,
            llm_model=_writer_llm_model,
            llm_token_usage=_writer_llm_usage,
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
        trace.writer.validate_completed_run_coverage()
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
        error: ErrorInfo | None = None,
        latency_ms: int = 0,
        token_usage: TokenUsage | None = None,
        llm_mode: str | None = None,
        llm_model: str | None = None,
        llm_token_usage: TokenUsage | None = None,
        failover_reason: str | None = None,
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
            latency_ms=latency_ms,
            token_usage=token_usage,
            error=error,
            llm_mode=llm_mode,
            llm_model=llm_model,
            llm_token_usage=llm_token_usage,
            failover_reason=failover_reason,
            created_at=datetime.now(timezone.utc),
        )
        self.writer.append(event)
        self.sequence += 1


def _new_run_id(case_id: str | None) -> str:
    prefix = case_id or "run"
    return f"{prefix}-{uuid4().hex[:8]}"


def _provider_tool_name(provider: SourceDiscoveryProvider) -> str:
    explicit_tool_name = getattr(provider, "tool_name", None)
    if explicit_tool_name:
        return str(explicit_tool_name)
    if provider.provider_name == "fixture":
        return "fixture.search"
    provider_display_name = getattr(provider, "provider_display_name", None)
    if provider_display_name == "exa":
        return "exa.search"
    if provider.provider_name == "web":
        return "web_search"
    return f"{provider.provider_name}.search"


def _trace_error(error: SourceDiscoveryError) -> ErrorInfo:
    to_trace_error = getattr(error, "to_trace_error", None)
    if callable(to_trace_error):
        return to_trace_error()
    return ErrorInfo(type=error.code, message=str(error))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
