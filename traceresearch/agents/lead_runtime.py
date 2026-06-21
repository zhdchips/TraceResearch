"""Lead Agent Runtime — unified pipeline orchestration with explicit state management.

The LeadAgentRuntime wraps the existing pipeline stages (Plan → Research →
Write → Verify → Critique → Finalize) as discrete, traceable steps. Each step
records its own lifecycle events (START / TOOL_CALL / TOOL_RESULT / FINISH)
using the LEAD_RUNTIME agent role.

Design constraints (005):
- Single runtime, single thread (concurrency only inside run_research_subagents).
- Reuses 004's LeadResearchAgent for the research phase — no subagent reimplementation.
- Does NOT change Writer/Verifier/Critic business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from traceresearch.agents.critic import Critic
from traceresearch.agents.lead_researcher import LeadResearchAgent
from traceresearch.agents.planner import Planner
from traceresearch.agents.verifier_protocol import VerifierProtocol
from traceresearch.agents.verifier import Verifier
from traceresearch.agents.writer_protocol import WriterProtocol
from traceresearch.agents.writer import Writer
from traceresearch.evidence.models import (
    Evidence,
    EvidenceStatus,
    ResearchBrief,
    ResearchTask,
)
from traceresearch.evidence.store import EvidenceStore
from traceresearch.source_discovery.base import SourceDiscoveryProvider
from traceresearch.trace.models import (
    AgentRole,
    ErrorInfo,
    EventType,
    TraceEvent,
    TraceStatus,
)
from traceresearch.trace.writer import TraceWriter


@dataclass
class RuntimeState:
    """Mutable state container passed between runtime steps.

    Only the LeadAgentRuntime main thread writes to this state.
    Concurrency is confined to the run_research_subagents step (004 SubagentExecutor).
    """

    run_id: str
    run_dir: str
    trace_writer: TraceWriter | None = None
    research_brief: ResearchBrief | None = None
    planned_tasks: list[ResearchTask] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    failed_task_ids: list[str] = field(default_factory=list)
    draft_report: Any = None
    verification_result: Any = None
    critique_result: Any = None
    final_report: Any = None
    status: str = "initialized"


# RunContext is an alias for code that prefers the "context" naming.
RunContext = RuntimeState


class LeadAgentRuntime:
    """Unified runtime that orchestrates the research pipeline as discrete steps.

    Each step method:
    1. Records LEAD_RUNTIME START/TOOL_CALL trace events
    2. Delegates to the appropriate internal agent (Planner, LeadResearchAgent, etc.)
    3. Records LEAD_RUNTIME TOOL_RESULT/FINISH trace events
    4. Updates RuntimeState with results

    Usage::

        state = RuntimeState(run_id="...", run_dir="...", trace_writer=tw)
        runtime = LeadAgentRuntime(state=state)
        state = runtime.run_pipeline(query="...", provider=provider)
    """

    def __init__(
        self,
        state: RuntimeState,
        *,
        planner: Planner | None = None,
        lead_researcher: LeadResearchAgent | None = None,
        writer: WriterProtocol | None = None,
        verifier: VerifierProtocol | None = None,
        critic: Critic | None = None,
    ) -> None:
        self.state = state
        self._planner = planner or Planner()
        self._lead_researcher = lead_researcher or LeadResearchAgent()
        self._writer = writer or Writer()
        self._verifier = verifier or Verifier()
        self._critic = critic or Critic()

    # ------------------------------------------------------------------
    # Step methods
    # ------------------------------------------------------------------

    def plan_research(
        self,
        query: str,
        eval_case: Any = None,
    ) -> RuntimeState:
        """Step 1: Plan research tasks from the user query.

        Delegates to Planner.plan(). Records PLANNER trace events (preserving
        existing contract) plus LEAD_RUNTIME wrapper events.
        """
        step = "plan_research"
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.START,
                         input_summary=query, output_summary="starting plan_research")

        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_CALL,
                         input_summary="calling Planner.plan",
                         output_summary=f"query={query[:80]}")

        # Record PLANNER events (preserving existing trace contract)
        self._trace_agent(AgentRole.PLANNER, EventType.START, query, "planning")
        brief = self._planner.plan(run_id=self.state.run_id, query=query, eval_case=eval_case)
        self._trace_agent(
            AgentRole.PLANNER, EventType.FINISH,
            "research question",
            f"created {len(brief.research_tasks)} research tasks",
            status=TraceStatus.NEEDS_CLARIFICATION if brief.open_clarifications else TraceStatus.SUCCESS,
        )

        self.state.research_brief = brief
        self.state.planned_tasks = list(brief.research_tasks)

        if brief.open_clarifications:
            self.state.status = "needs_clarification"
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                             input_summary="Planner returned",
                             output_summary="needs clarification")
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                             input_summary="plan_research complete",
                             output_summary="needs_clarification",
                             status=TraceStatus.NEEDS_CLARIFICATION)
        else:
            self.state.status = "planned"
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                             input_summary="Planner returned",
                             output_summary=f"created {len(brief.research_tasks)} research tasks")
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                             input_summary="plan_research complete",
                             output_summary=f"{len(brief.research_tasks)} tasks planned")

        return self.state

    def run_research_subagents(
        self,
        provider: SourceDiscoveryProvider,
        provider_tool_name: str | None = None,
    ) -> RuntimeState:
        """Step 2: Execute research via LeadResearchAgent (reuses 004 subagent logic).

        MUST call LeadResearchAgent.conduct_research() — does NOT reimplement
        subagent dispatch, concurrency, dedup, or evidence store writing.
        """
        step = "run_research_subagents"
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.START,
                         input_summary="starting research",
                         output_summary="dispatching subagents")

        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_CALL,
                         input_summary="calling LeadResearchAgent.conduct_research",
                         output_summary=f"provider={provider.provider_name}")

        # Record RESEARCHER events (preserving existing trace contract)
        self._trace_agent(AgentRole.RESEARCHER, EventType.START,
                          "research tasks", "source discovery via subagent executor")

        research_result = self._lead_researcher.conduct_research(
            brief=self.state.research_brief,
            provider=provider,
            run_id=self.state.run_id,
            run_dir=self.state.run_dir,
            trace_writer=self.state.trace_writer,
            provider_tool_name=provider_tool_name,
        )

        self.state.evidence = list(research_result.evidence)
        self.state.failed_task_ids = list(research_result.failed_task_ids)

        self._trace_agent(
            AgentRole.RESEARCHER, EventType.FINISH,
            f"{provider.provider_name} provider results",
            f"stored {len(self.state.evidence)} evidence candidates",
        )

        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                         input_summary="LeadResearchAgent returned",
                         output_summary=f"evidence={len(self.state.evidence)} failed={len(self.state.failed_task_ids)}")

        self.state.status = "researched"
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                         input_summary="run_research_subagents complete",
                         output_summary=f"evidence={len(self.state.evidence)} tasks_failed={len(self.state.failed_task_ids)}")

        return self.state

    def write_report(self) -> RuntimeState:
        """Step 3: Draft report from evidence.

        Delegates to Writer.draft().
        """
        step = "write_report"
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.START,
                         input_summary="starting draft",
                         output_summary="writing report from evidence")

        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_CALL,
                         input_summary="calling Writer.draft",
                         output_summary=f"evidence_count={len(self.state.evidence)}")

        # Record WRITER events
        self._trace_agent(AgentRole.WRITER, EventType.START,
                          "evidence candidates", "drafting outline and claims")
        draft = self._writer.draft(brief=self.state.research_brief, evidence=self.state.evidence)
        self._trace_agent(AgentRole.WRITER, EventType.FINISH,
                          "outline and draft claims",
                          f"drafted {len(draft.claims)} claims")

        self.state.draft_report = draft
        self.state.status = "drafted"

        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                         input_summary="Writer returned draft",
                         output_summary=f"claims={len(draft.claims)}")
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                         input_summary="write_report complete",
                         output_summary=f"drafted {len(draft.claims)} claims")

        return self.state

    def verify_report(self, *, writer_mode: str = "deterministic",
                      verifier_mode: str = "deterministic") -> RuntimeState:
        """Step 4: Verify claims against evidence.

        Delegates to Verifier.verify(). Updates EvidenceStore statuses for
        verified evidence items.
        """
        step = "verify_report"
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.START,
                         input_summary="starting verification",
                         output_summary="verifying claims against evidence")

        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_CALL,
                         input_summary="calling Verifier.verify",
                         output_summary=f"claims={len(self.state.draft_report.claims)}")

        # LLM mode detection for trace
        _verifier_is_llm = hasattr(self._verifier, '_provider') and verifier_mode == "llm"
        _verifier_llm_mode = "llm" if _verifier_is_llm else "deterministic"
        _verifier_llm_model = getattr(self._verifier, '_provider', None)
        if _verifier_llm_model is not None and hasattr(_verifier_llm_model, 'model'):
            _verifier_llm_model = _verifier_llm_model.model
        else:
            _verifier_llm_model = None

        self._trace_agent(
            AgentRole.VERIFIER, EventType.START,
            "draft claims", "verifying claim support",
            llm_mode=_verifier_llm_mode, llm_model=_verifier_llm_model,
        )
        verification = self._verifier.verify(
            run_id=self.state.run_id,
            draft=self.state.draft_report,
            evidence=self.state.evidence,
        )
        self._trace_agent(
            AgentRole.VERIFIER, EventType.FINISH,
            "draft claims",
            f"verified {len(verification.claim_results)} claims",
            llm_mode=_verifier_llm_mode, llm_model=_verifier_llm_model,
        )

        # Update EvidenceStore statuses for verified evidence
        evidence_path = f"{self.state.run_dir}/evidence.jsonl"
        evidence_store = EvidenceStore(evidence_path)
        verified_ids = {
            evidence_id
            for claim in verification.claim_results
            for evidence_id in claim.evidence_ids
        }
        for evidence_id in verified_ids:
            evidence_store.update_status(
                evidence_id,
                EvidenceStatus.VERIFIED,
                ["Verified by verifier."],
            )

        self.state.verification_result = verification
        self.state.status = "verified"

        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                         input_summary="Verifier returned",
                         output_summary=f"verified {len(verification.claim_results)} claims")
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                         input_summary="verify_report complete",
                         output_summary=f"claims_verified={len(verification.claim_results)}")

        return self.state

    def critique_report(self) -> RuntimeState:
        """Step 5: Critique the report for missing perspectives and weaknesses.

        Delegates to Critic.review().
        """
        step = "critique_report"
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.START,
                         input_summary="starting critique",
                         output_summary="reviewing coverage and quality")

        # Build verified evidence list
        evidence_path = f"{self.state.run_dir}/evidence.jsonl"
        evidence_store = EvidenceStore(evidence_path)
        verified_evidence = [
            item for item in evidence_store.list_all()
            if item.status == EvidenceStatus.VERIFIED
        ]

        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_CALL,
                         input_summary="calling Critic.review",
                         output_summary=f"verified_evidence={len(verified_evidence)}")

        self._trace_agent(AgentRole.CRITIC, EventType.START,
                          "verified claims", "reviewing coverage")
        critique = self._critic.review(
            brief=self.state.research_brief,
            evidence=verified_evidence,
            verification=self.state.verification_result,
            failed_task_ids=self.state.failed_task_ids,
        )
        self._trace_agent(AgentRole.CRITIC, EventType.FINISH,
                          "coverage review",
                          f"decision={critique.decision.value}")

        self.state.critique_result = critique
        self.state.status = "critiqued"

        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                         input_summary="Critic returned",
                         output_summary=f"decision={critique.decision.value}")
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                         input_summary="critique_report complete",
                         output_summary=f"decision={critique.decision.value}")

        return self.state

    def finalize_run(self, *, writer_mode: str = "deterministic") -> RuntimeState:
        """Step 6: Finalize report — produce final markdown and JSON output.

        Delegates to Writer.final().
        """
        step = "finalize_run"
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.START,
                         input_summary="starting finalize",
                         output_summary="producing final report")

        # Build verified evidence list
        evidence_path = f"{self.state.run_dir}/evidence.jsonl"
        evidence_store = EvidenceStore(evidence_path)
        verified_evidence = [
            item for item in evidence_store.list_all()
            if item.status == EvidenceStatus.VERIFIED
        ]

        # LLM mode detection for trace
        _writer_is_llm = hasattr(self._writer, '_provider') and writer_mode == "llm"
        _writer_llm_mode = "llm" if _writer_is_llm else "deterministic"
        _writer_llm_model = getattr(self._writer, '_provider', None)
        if _writer_llm_model is not None and hasattr(_writer_llm_model, 'model'):
            _writer_llm_model = _writer_llm_model.model
        else:
            _writer_llm_model = None

        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_CALL,
                         input_summary="calling Writer.final",
                         output_summary=f"verified_evidence={len(verified_evidence)}")

        self._trace_agent(
            AgentRole.WRITER, EventType.START,
            "verified evidence", "writing final report",
            llm_mode=_writer_llm_mode, llm_model=_writer_llm_model,
        )
        final_report = self._writer.final(
            brief=self.state.research_brief,
            verified_evidence=verified_evidence,
            verification=self.state.verification_result,
            critique=self.state.critique_result,
        )
        # Record LLM token usage if available
        _writer_llm_usage = None
        if _writer_is_llm:
            try:
                _writer_llm_usage = self._writer._provider.last_token_usage
            except AttributeError:
                pass
        self._trace_agent(
            AgentRole.WRITER, EventType.FINISH,
            "final report", "wrote final_report.md and report.json",
            llm_mode=_writer_llm_mode, llm_model=_writer_llm_model,
            llm_token_usage=_writer_llm_usage,
        )

        self.state.final_report = final_report
        self.state.status = "completed"

        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                         input_summary="Writer returned final report",
                         output_summary="final report ready")
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                         input_summary="finalize_run complete",
                         output_summary="final report written")

        return self.state

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def run_pipeline(
        self,
        query: str,
        provider: SourceDiscoveryProvider,
        eval_case: Any = None,
        provider_tool_name: str | None = None,
        *,
        writer_mode: str = "deterministic",
        verifier_mode: str = "deterministic",
    ) -> RuntimeState:
        """Run the full research pipeline: plan → research → write → verify → critique → finalize.

        Returns early if plan_research produces open_clarifications (NEEDS_CLARIFICATION).
        Returns early if all research tasks fail (state.status = "failed").

        Returns the final RuntimeState for the harness to construct RunResult.
        """
        # Step 1: Plan
        self.plan_research(query, eval_case)
        if self.state.research_brief and self.state.research_brief.open_clarifications:
            return self.state

        # Step 2: Research
        self.run_research_subagents(provider, provider_tool_name)
        if self.state.research_brief and self.state.research_brief.research_tasks and not self.state.evidence:
            self.state.status = "failed"
            return self.state

        # Step 3: Write
        self.write_report()

        # Step 4: Verify
        self.verify_report(writer_mode=writer_mode, verifier_mode=verifier_mode)

        # Step 5: Critique
        self.critique_report()

        # Step 6: Finalize
        self.finalize_run(writer_mode=writer_mode)

        return self.state

    # ------------------------------------------------------------------
    # Trace helpers
    # ------------------------------------------------------------------

    def _trace_step(
        self,
        tool_name: str,
        agent_role: AgentRole,
        event_type: EventType,
        input_summary: str,
        output_summary: str,
        *,
        status: TraceStatus = TraceStatus.SUCCESS,
        error: ErrorInfo | None = None,
        latency_ms: int = 0,
    ) -> None:
        """Record a LEAD_RUNTIME lifecycle event for the current step."""
        if self.state.trace_writer is None:
            return
        event = TraceEvent(
            trace_id=self.state.trace_writer.next_trace_id(self.state.run_id),
            run_id=self.state.run_id,
            agent_role=agent_role,
            event_type=event_type,
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=output_summary,
            status=status,
            latency_ms=latency_ms,
            error=error,
            created_at=datetime.now(timezone.utc),
        )
        self.state.trace_writer.append(event)

    def _trace_agent(
        self,
        agent_role: AgentRole,
        event_type: EventType,
        input_summary: str,
        output_summary: str,
        *,
        status: TraceStatus = TraceStatus.SUCCESS,
        error: ErrorInfo | None = None,
        latency_ms: int = 0,
        llm_mode: str | None = None,
        llm_model: str | None = None,
        llm_token_usage: Any = None,
        failover_reason: str | None = None,
    ) -> None:
        """Record a trace event for an internal agent (preserving existing contract)."""
        if self.state.trace_writer is None:
            return
        event = TraceEvent(
            trace_id=self.state.trace_writer.next_trace_id(self.state.run_id),
            run_id=self.state.run_id,
            agent_role=agent_role,
            event_type=event_type,
            input_summary=input_summary,
            output_summary=output_summary,
            status=status,
            latency_ms=latency_ms,
            error=error,
            llm_mode=llm_mode,
            llm_model=llm_model,
            llm_token_usage=llm_token_usage,
            failover_reason=failover_reason,
            created_at=datetime.now(timezone.utc),
        )
        self.state.trace_writer.append(event)
