# Review: Live Provider Demo Readiness

## Decision

complete

## Next Phase

complete

## Findings

- Full regression passed: `python3 -m pytest` reported `117 passed`.
- Fixture eval regression passed: `eval/results/eval-20260620180616-26276f94-summary.json` contains 5 seed cases, 5/5 pass, `case_pass_rate=1.0`, and all 9 required metrics per case.
- Unconfigured web smoke passed: missing `EXA_API_KEY` returned `status=failed` and `error_type=provider_not_configured`.
- Configured live smoke passed: `runs/run-d09f5082` completed with live Exa source discovery, 14 web evidence rows, `exa.search` trace events, and `[EV-...]` final report references.
- Web provider failure handling is explicit and does not silently fallback to Fixture.
- README and `.env.example` document fixture demo, Live web demo, manual live smoke, secret handling, artifact inspection, and limitations.
- Secret scan passed for tracked files: no tracked `.env`; no real API key pattern found outside known fake test redaction tokens.

## Bad Cases

- No fixture eval bad cases.
- Configured live smoke succeeded after loading the local `.env` and setting `SSL_CERT_FILE` to the local `certifi` CA bundle.

## Known Limitations

- Live web smoke remains manual/non-CI.
- Live web results depend on Exa availability, account quota, network behavior, ranking, and source freshness.
- This local Python environment required `SSL_CERT_FILE` to point at `certifi` for Exa HTTPS verification.
- The deterministic Agents are not LLM-backed in this feature.
- Exa is the only live provider implemented in this feature.
- No Web UI exists.

## Non-Goals Check

- LLM-backed Agents: not implemented.
- Web UI: not implemented.
- PDF export: not implemented.
- HTML export: not implemented.
- Large benchmark: not implemented.
- Live web CI gate: not implemented.
- Fixture deterministic tests/eval: preserved.

## Next Actions

- Preserve `runs/run-d09f5082` as the current configured live demo artifact path.
- Use future planning to decide whether to add richer live-source relevance checks, additional providers, or LLM-backed Agent roles.
- Keep fixture eval as the stable regression gate before expanding live web behavior.
