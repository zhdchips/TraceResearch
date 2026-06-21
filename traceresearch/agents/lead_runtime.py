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

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

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
    # Iteration fields (006)
    iteration_index: int = 0
    max_iterations: int = 1
    iteration_history: list[dict] = field(default_factory=list)
    revision_reason: str | None = None
    next_phase: str | None = None
    # Context engineering (007)
    latest_context_pack: Any = None  # ContextPack | None


# RunContext is an alias for code that prefers the "context" naming.
RunContext = RuntimeState


def _read_max_iterations() -> int:
    """Read TRACERESEARCH_MAX_RUNTIME_ITERATIONS from env, default 1."""
    raw = os.environ.get("TRACERESEARCH_MAX_RUNTIME_ITERATIONS", "1")
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "TRACERESEARCH_MAX_RUNTIME_ITERATIONS=%r is not an integer, using 1", raw
        )
        return 1
    if value < 1:
        logger.warning(
            "TRACERESEARCH_MAX_RUNTIME_ITERATIONS=%d < 1, using 1", value
        )
        return 1
    return value


def _resolve_llm_mode(agent: Any) -> tuple[str | None, str | None]:
    """Detect whether an agent instance is LLM-backed via its _provider attribute.

    Returns (llm_mode, llm_model) suitable for trace event fields.
    - If the instance has ``_provider`` with a ``model`` attribute → ("llm", model).
    - Otherwise → ("deterministic", None).

    This works for direct-injected LLMWriter / LLMVerifier regardless of any
    mode string passed separately.
    """
    provider = getattr(agent, "_provider", None)
    if provider is not None and hasattr(provider, "model"):
        return ("llm", str(provider.model))
    return ("deterministic", None)


def _resolve_llm_token_usage(agent: Any) -> Any | None:
    """Return ``last_token_usage`` from an LLM-backed agent, or None."""
    try:
        return agent._provider.last_token_usage
    except AttributeError:
        return None


def _error_info(exc: Exception) -> ErrorInfo:
    """Build an ErrorInfo with a guaranteed non-empty message.

    TraceEvent validation requires ``error.message`` to be non-empty for
    FAILED events.  If ``str(exc)`` returns an empty string we fall back
    to the exception class name so a Pydantic ValidationError never masks
    the original exception.
    """
    msg = str(exc) or type(exc).__name__
    return ErrorInfo(type=type(exc).__name__, message=msg)


def _safe_str(value: object, fallback: str = "unknown") -> str:
    """Return ``str(value)`` or *fallback* when *value* is None."""
    return str(value) if value is not None else fallback


class LeadAgentRuntime:
    """Unified runtime that orchestrates the research pipeline as discrete steps.

    Each step method:
    1. Records LEAD_RUNTIME START/TOOL_CALL trace events
    2. Delegates to the appropriate internal agent (Planner, LeadResearchAgent, etc.)
    3. Records LEAD_RUNTIME TOOL_RESULT/FINISH trace events
    4. Updates RuntimeState with results

    On internal agent exception, records LEAD_RUNTIME FINISH with status=FAILED
    and ErrorInfo, then re-raises the original exception.

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

        try:
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

        except Exception as exc:
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                             input_summary="Planner failed",
                             output_summary=str(exc),
                             status=TraceStatus.FAILED,
                             error=_error_info(exc))
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                             input_summary="plan_research failed",
                             output_summary=str(exc),
                             status=TraceStatus.FAILED,
                             error=_error_info(exc))
            raise

        return self.state

    def run_research_subagents(
        self,
        provider: SourceDiscoveryProvider,
        provider_tool_name: str | None = None,
    ) -> RuntimeState:
        """Step 2: Execute research via LeadResearchAgent (reuses 004 subagent logic).

        MUST call LeadResearchAgent.conduct_research() — does NOT reimplement
        subagent dispatch, concurrency, dedup, or evidence store writing.

        When all research tasks fail (zero evidence despite having tasks),
        records FINISH with status=FAILED so the trace reflects the failure
        rather than showing SUCCESS followed by a post-hoc status change.
        """
        step = "run_research_subagents"
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.START,
                         input_summary="starting research",
                         output_summary="dispatching subagents")

        _safe_provider = _safe_str(getattr(provider, "provider_name", None), "provider")
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_CALL,
                         input_summary="calling LeadResearchAgent.conduct_research",
                         output_summary=f"provider={_safe_provider}")

        try:
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
                f"{_safe_provider} provider results",
                f"stored {len(self.state.evidence)} evidence candidates",
            )

            # Detect all-tasks-failed: tasks existed but zero evidence collected.
            _all_failed = (
                self.state.research_brief is not None
                and bool(self.state.research_brief.research_tasks)
                and not self.state.evidence
            )

            if _all_failed:
                self.state.status = "failed"
                self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                                 input_summary="LeadResearchAgent returned — all tasks failed",
                                 output_summary=f"evidence=0 failed={len(self.state.failed_task_ids)}",
                                 status=TraceStatus.FAILED,
                                 error=ErrorInfo(
                                     type="AllResearchTasksFailed",
                                     message="All research tasks failed or timed out — no evidence collected",
                                 ))
                self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                                 input_summary="run_research_subagents failed",
                                 output_summary="all research tasks failed",
                                 status=TraceStatus.FAILED,
                                 error=ErrorInfo(
                                     type="AllResearchTasksFailed",
                                     message="All research tasks failed or timed out — no evidence collected",
                                 ))
            else:
                self.state.status = "researched"
                self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                                 input_summary="LeadResearchAgent returned",
                                 output_summary=f"evidence={len(self.state.evidence)} failed={len(self.state.failed_task_ids)}")
                self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                                 input_summary="run_research_subagents complete",
                                 output_summary=f"evidence={len(self.state.evidence)} tasks_failed={len(self.state.failed_task_ids)}")

        except Exception as exc:
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                             input_summary="LeadResearchAgent failed",
                             output_summary=str(exc),
                             status=TraceStatus.FAILED,
                             error=_error_info(exc))
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                             input_summary="run_research_subagents failed",
                             output_summary=str(exc),
                             status=TraceStatus.FAILED,
                             error=_error_info(exc))
            raise

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

        try:
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

        except Exception as exc:
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                             input_summary="Writer.draft failed",
                             output_summary=str(exc),
                             status=TraceStatus.FAILED,
                             error=_error_info(exc))
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                             input_summary="write_report failed",
                             output_summary=str(exc),
                             status=TraceStatus.FAILED,
                             error=_error_info(exc))
            raise

        return self.state

    def verify_report(self, *, writer_mode: str = "deterministic",
                      verifier_mode: str = "deterministic") -> RuntimeState:
        """Step 4: Verify claims against evidence.

        Delegates to Verifier.verify(). Updates EvidenceStore statuses for
        verified evidence items.

        The *writer_mode* and *verifier_mode* parameters are retained for
        backward compatibility.  LLM observability is inferred directly from
        the verifier instance (``hasattr(verifier, '_provider')``), so a
        direct-injected LLMVerifier is always traced as llm regardless of
        the mode string.
        """
        step = "verify_report"
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.START,
                         input_summary="starting verification",
                         output_summary="verifying claims against evidence")

        # LLM mode detection — instance-based, works for direct injection.
        _verifier_llm_mode, _verifier_llm_model = _resolve_llm_mode(self._verifier)

        try:
            _claim_count = len(self.state.draft_report.claims) if self.state.draft_report is not None else 0
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_CALL,
                             input_summary="calling Verifier.verify",
                             output_summary=f"claims={_claim_count}")
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

        except Exception as exc:
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                             input_summary="Verifier.verify failed",
                             output_summary=str(exc),
                             status=TraceStatus.FAILED,
                             error=_error_info(exc))
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                             input_summary="verify_report failed",
                             output_summary=str(exc),
                             status=TraceStatus.FAILED,
                             error=_error_info(exc))
            raise

        return self.state

    def critique_report(self) -> RuntimeState:
        """Step 5: Critique the report for missing perspectives and weaknesses.

        Delegates to Critic.review().
        """
        step = "critique_report"
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.START,
                         input_summary="starting critique",
                         output_summary="reviewing coverage and quality")

        try:
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

        except Exception as exc:
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                             input_summary="Critic.review failed",
                             output_summary=str(exc),
                             status=TraceStatus.FAILED,
                             error=_error_info(exc))
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                             input_summary="critique_report failed",
                             output_summary=str(exc),
                             status=TraceStatus.FAILED,
                             error=_error_info(exc))
            raise

        return self.state

    def finalize_run(self, *, writer_mode: str = "deterministic") -> RuntimeState:
        """Step 6: Finalize report — produce final markdown and JSON output.

        Delegates to Writer.final().

        The *writer_mode* parameter is retained for backward compatibility.
        LLM observability is inferred directly from the writer instance
        (``hasattr(writer, '_provider')``), so a direct-injected LLMWriter is
        always traced as llm regardless of the mode string.
        """
        step = "finalize_run"
        self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.START,
                         input_summary="starting finalize",
                         output_summary="producing final report")

        # LLM mode detection — instance-based, works for direct injection.
        _writer_llm_mode, _writer_llm_model = _resolve_llm_mode(self._writer)

        try:
            # Build verified evidence list
            evidence_path = f"{self.state.run_dir}/evidence.jsonl"
            evidence_store = EvidenceStore(evidence_path)
            verified_evidence = [
                item for item in evidence_store.list_all()
                if item.status == EvidenceStatus.VERIFIED
            ]

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
            _writer_llm_usage = _resolve_llm_token_usage(self._writer)
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

        except Exception as exc:
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.TOOL_RESULT,
                             input_summary="Writer.final failed",
                             output_summary=str(exc),
                             status=TraceStatus.FAILED,
                             error=_error_info(exc))
            self._trace_step(step, AgentRole.LEAD_RUNTIME, EventType.FINISH,
                             input_summary="finalize_run failed",
                             output_summary=str(exc),
                             status=TraceStatus.FAILED,
                             error=_error_info(exc))
            raise

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
        """Run the full research pipeline with bounded iteration (006).

        Plan → Research → [Write → Verify → Critique]×N → Finalize

        The Critique→Revise loop iterates up to max_iterations.
        On PASS → finalize and exit.
        On REVISE → loop back based on next_phase (research/write/verify).
        On FAIL → finalize and exit.
        Unsupported next_phase → warn + finalize.

        Returns early for NEEDS_CLARIFICATION or all-tasks-failed.
        """
        # Resolve max_iterations: state value takes priority, env var as fallback
        if self.state.max_iterations == 1:
            self.state.max_iterations = _read_max_iterations()

        # Step 1: Plan
        self.plan_research(query, eval_case)
        if self.state.research_brief and self.state.research_brief.open_clarifications:
            return self.state

        # Step 2: Research (all-tasks-failed sets state.status="failed" and
        # records FAILED trace inside run_research_subagents).
        self.run_research_subagents(provider, provider_tool_name)
        if self.state.status == "failed":
            return self.state

        # Step 3-5: Iterative write → verify → critique loop
        from traceresearch.evidence.models import CritiqueDecision, NextPhase

        while self.state.iteration_index < self.state.max_iterations:
            self.state.iteration_index += 1
            it = self.state.iteration_index

            self._trace_iteration(
                EventType.START,
                f"iteration {it} starting",
                next_phase=self.state.next_phase or "write",
            )

            # Write (skip if looping back to verify only)
            if self.state.next_phase != "verify":
                self.write_report()

            # Verify
            self.verify_report(writer_mode=writer_mode, verifier_mode=verifier_mode)

            # Critique
            self.critique_report()

            critique = self.state.critique_result
            decision = critique.decision

            self._trace_iteration(
                EventType.TOOL_RESULT,
                f"critic decision: {decision.value}",
                decision=decision.value,
                next_phase=str(critique.next_phase.value) if critique.next_phase else None,
                revision_reason=(
                    "; ".join(critique.missing_perspectives)
                    if critique.missing_perspectives else None
                ),
            )

            # Record iteration history
            self.state.iteration_history.append({
                "iteration_index": it,
                "decision": decision.value,
                "next_phase": str(critique.next_phase.value) if critique.next_phase else None,
                "revision_reason": (
                    "; ".join(critique.missing_perspectives)
                    if critique.missing_perspectives else None
                ),
            })

            if decision == CritiqueDecision.PASS:
                self._trace_iteration(
                    EventType.FINISH,
                    f"iteration {it} complete — PASS",
                    decision="PASS",
                )
                break

            if decision == CritiqueDecision.FAIL:
                self._trace_iteration(
                    EventType.FINISH,
                    f"iteration {it} complete — FAIL, finalizing",
                    decision="FAIL",
                )
                break

            # REVISE: check if we have more iterations
            if it >= self.state.max_iterations:
                self._trace_iteration(
                    EventType.FINISH,
                    f"iteration {it} — max_iterations reached, finalizing",
                    decision="REVISE",
                    status=TraceStatus.SKIPPED,
                )
                break

            # Set up next iteration
            self.state.revision_reason = (
                "; ".join(critique.missing_perspectives)
                if critique.missing_perspectives else "revision requested"
            )
            next_phase_val = critique.next_phase
            self.state.next_phase = str(next_phase_val.value) if next_phase_val else None

            # Route based on next_phase
            if next_phase_val == NextPhase.RESEARCH:
                self._trace_iteration(
                    EventType.FINISH,
                    f"iteration {it} complete — REVISE, looping to research",
                    decision="REVISE",
                    next_phase="research",
                )
                self.run_research_subagents(provider, provider_tool_name)
                self.state.next_phase = "write"  # reset for full pipeline re-run
            elif next_phase_val == NextPhase.WRITE:
                self._trace_iteration(
                    EventType.FINISH,
                    f"iteration {it} complete — REVISE, looping to write",
                    decision="REVISE",
                    next_phase="write",
                )
                # next_phase stays "write" — will re-enter from write_report
            elif next_phase_val == NextPhase.VERIFY:
                self._trace_iteration(
                    EventType.FINISH,
                    f"iteration {it} complete — REVISE, looping to verify",
                    decision="REVISE",
                    next_phase="verify",
                )
                # next_phase stays "verify" — will skip write_report
            else:
                # Unsupported next_phase — warn and finalize
                logger.warning(
                    "Unsupported next_phase=%r for REVISE — finalizing",
                    self.state.next_phase,
                )
                self._trace_iteration(
                    EventType.FINISH,
                    f"iteration {it} — unsupported next_phase={self.state.next_phase}, finalizing",
                    decision="REVISE",
                    next_phase=self.state.next_phase,
                    status=TraceStatus.SKIPPED,
                )
                break

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

    def _trace_iteration(
        self,
        event_type: EventType,
        output_summary: str,
        *,
        decision: str | None = None,
        next_phase: str | None = None,
        revision_reason: str | None = None,
        status: TraceStatus = TraceStatus.SUCCESS,
    ) -> None:
        """Record an iteration lifecycle event (006)."""
        if self.state.trace_writer is None:
            return
        detail_parts = [f"iter={self.state.iteration_index}"]
        if decision:
            detail_parts.append(f"decision={decision}")
        if next_phase:
            detail_parts.append(f"next_phase={next_phase}")
        if revision_reason:
            detail_parts.append(
                f"revision_reason={revision_reason[:120]}"
            )
        event = TraceEvent(
            trace_id=self.state.trace_writer.next_trace_id(self.state.run_id),
            run_id=self.state.run_id,
            agent_role=AgentRole.LEAD_RUNTIME,
            event_type=event_type,
            tool_name="iteration_loop",
            input_summary=", ".join(detail_parts),
            output_summary=output_summary,
            status=status,
            latency_ms=0,
            created_at=datetime.now(timezone.utc),
        )
        self.state.trace_writer.append(event)
