"""Pytest configuration for LLM smoke tests."""

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "llm_smoke: tests requiring real LLM provider")


def pytest_collection_modifyitems(config, items):
    """Skip llm_smoke tests by default — only run when -m llm_smoke is passed."""
    if not config.getoption("-m") or "llm_smoke" not in str(config.getoption("-m")):
        skip_llm = pytest.mark.skip(reason="LLM smoke test — use -m llm_smoke to run")
        for item in items:
            if "llm_smoke" in item.keywords:
                item.add_marker(skip_llm)
