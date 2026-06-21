# Research Notes: Research Subagents

**Created**: 2026-06-21
**Feature**: 004-research-subagents

## Research Questions & Decisions

### Q1: ThreadPoolExecutor vs asyncio for subagent concurrency

**Decision**: `concurrent.futures.ThreadPoolExecutor`

**Rationale**:
- SourceDiscoveryProvider interface is fully synchronous (`search()`, `fetch()`)
- All existing test infrastructure is synchronous
- FixtureSourceProvider reads local YAML files — thread-safe
- ExaSearchProvider uses httpx (synchronous) — I/O-bound, threads are natural fit
- asyncio would require rewriting the entire harness call chain (or mixer patterns)
- MVP constraint: "不要新增重型依赖"

**Alternatives considered**:
- `asyncio`: Would provide true non-blocking I/O but requires async/await throughout call chain. Overkill for 3-thread concurrency.
- `multiprocessing.Pool`: Heavier, serialization overhead, unnecessary for I/O-bound tasks.
- Third-party task queues (Celery, RQ): Heavy dependency, violates FR-016.

### Q2: Evidence ID generation strategy under concurrency

**Decision**: Lead Agent assigns IDs post-collection, in task definition order (not completion order)

**Rationale**:
- Fixture eval requires deterministic evidence IDs for regression testing
- If IDs are assigned by subagents at creation time, concurrent completion order makes them non-deterministic
- Lead Agent collects all batches → sorts by task index in `brief.research_tasks` → assigns sequential IDs
- This preserves the same ID stability as current serial implementation

**Alternatives considered**:
- Let subagents assign IDs: Non-deterministic ordering, breaks fixture eval
- Hash-based IDs: Unpredictable in tests, harder to inspect
- Timestamp-based IDs: Non-deterministic

### Q3: Subagent context compression design

**Decision**: `CompressedResearchContext` dataclass with minimal fields

**Rationale**:
- Subagent only needs: brief summary (from ResearchBrief.objective), the specific ResearchTask, provider reference, run_id
- Explicitly excludes: EvidenceStore, TraceWriter, Writer, Verifier, Critic, harness configuration
- This enforces context isolation (Constitution IV) and prevents accidental coupling
- Also prepares for future LLM-backed subagent by bounding context budget

**Fields**:
```python
@dataclass(frozen=True)
class CompressedResearchContext:
    run_id: str
    brief_summary: str          # from ResearchBrief.objective
    task: ResearchTask          # full task object
    provider_name: str          # e.g. "fixture", "web"
    created_at: datetime
```

### Q4: Partial failure policy details

**Decision**: Keep partial evidence, mark failures in CritiqueResult.missing_perspectives

**Rationale**:
- Current behavior: first SourceDiscoveryError → run FAILS immediately
- New behavior: SubagentExecutor catches per-task errors, returns status in CandidateEvidenceBatch
- LeadResearchAgent counts successful vs failed batches
- If ≥1 success: continue with stored evidence, pass failed_tasks info to Critic
- If 0 success: run = FAILED (no evidence to work with)
- Critic.missing_perspectives tracks which research task(s) failed

**Implementation**: LeadResearchAgent adds failed task info as a note/warning to the run, passed to Critic via a new optional parameter in `Critic.review()` or via a `failed_task_ids` field in CritiqueResult.

### Q5: Trace model extension impact

**Decision**: Add `subagent_id` as optional field to TraceEvent; add RESEARCH_LEAD and RESEARCH_SUBAGENT to AgentRole

**Rationale**:
- `subagent_id: str | None = None` — backward compatible, existing Trace reader unaffected
- New AgentRole entries are just new StrEnum values — existing validation unchanged
- More invasive changes (e.g., parent_event_id to link subagent events to lead events) deferred to future

### Q6: ExaSearchProvider thread safety assessment

**Decision**: ExaSearchProvider is thread-safe for concurrent use

**Rationale**:
- ExaSearchProvider.search() calls httpx (synchronous HTTP client) — each call is independent
- ExaSearchProvider.fetch() similarly makes independent HTTP calls
- No shared mutable state between calls (no instance cache beyond the document cache dict, which is accessed per-instance)
- If multiple subagents share the same ExaSearchProvider instance, the internal cache could have race conditions → mitigation: each subagent gets its own provider instance, or the cache is protected. For the current MVP, each run uses one provider instance, but since all threads are I/O-bound and the cache is only write-once per source_id, the race condition risk is low. Future improvement: add `threading.Lock` around cache writes.

## Best Practices Applied

- **ThreadPoolExecutor sizing**: default `max_workers=3` — appropriate for I/O-bound tasks where most latency is in HTTP/file reads. Python's GIL doesn't block I/O operations.
- **Failure isolation via Future objects**: each submitted task returns a Future; executor collects results with `as_completed()`, catching exceptions per-future rather than failing the whole batch.
- **Deterministic ordering in tests**: refer to fixture eval baseline (003) to verify evidence order matches.
- **Trace consistency**: trace events are appended synchronously via TraceWriter (file append), avoiding concurrent write issues. Each subagent records events through the same TraceWriter — since writing to a file in append mode from multiple threads is atomic for single-line writes, this is safe.
