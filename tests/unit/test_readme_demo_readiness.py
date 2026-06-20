from pathlib import Path


def test_readme_contains_demo_readiness_sections() -> None:
    readme = Path("README.md")

    assert readme.is_file()
    text = readme.read_text(encoding="utf-8")

    required_terms = [
        "Deep Research",
        "Planner",
        "Researcher",
        "Verifier",
        "Critic",
        "Writer",
        "Evidence Store",
        "Trace Log",
        "Fixture",
        "Live web",
        "EXA_API_KEY",
        "traceresearch eval",
        "final_report.md",
        "evidence.jsonl",
        "trace.jsonl",
        "Limitations",
        "interview",
    ]
    for term in required_terms:
        assert term in text


def test_readme_documents_fixture_and_live_demo_commands() -> None:
    text = Path("README.md").read_text(encoding="utf-8")

    for command in [
        "python3 -m pytest",
        "traceresearch run",
        "--source-provider fixture",
        "--source-provider web",
        "traceresearch eval --cases-dir eval/cases --source-provider fixture",
        "unset EXA_API_KEY",
        "export TRACERESEARCH_WEB_PROVIDER=exa",
        "export EXA_API_KEY=",
    ]:
        assert command in text


def test_env_example_documents_live_provider_without_secret() -> None:
    env_example = Path(".env.example")

    assert env_example.is_file()
    text = env_example.read_text(encoding="utf-8")

    assert "TRACERESEARCH_WEB_PROVIDER=exa" in text
    assert "EXA_API_KEY=" in text
    assert "TRACERESEARCH_WEB_TIMEOUT_SECONDS=10" in text
    assert "TRACERESEARCH_WEB_MAX_RESULTS=5" in text
    assert "sk-" not in text
    assert "exa_live_" not in text
    assert "<your-local-key>" not in text
