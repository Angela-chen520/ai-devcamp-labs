"""The App wrapper and the opt-in analytics plugin (Lab 4).

A plugin that is silently not loaded raises nothing and logs nothing, so the two
failure modes worth pinning are: it is on when it should be off, and the AG-UI adapter
is built in a way that drops it.
"""

import inspect

from backend.social_poster import agent as agent_module


def test_app_wraps_the_root_agent_with_no_plugins_by_default(monkeypatch):
    monkeypatch.setattr(agent_module, "_BQ_DATASET", "")

    assert agent_module.app.name == "social_poster"
    assert agent_module.app.root_agent is agent_module.root_agent
    assert agent_module._analytics_plugins() == []


def test_analytics_plugin_is_built_when_a_dataset_is_set(monkeypatch):
    import google.adk.plugins.bigquery_agent_analytics_plugin as bq

    seen = {}

    class FakePlugin:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr(bq, "BigQueryAgentAnalyticsPlugin", FakePlugin)
    monkeypatch.setattr(agent_module, "_BQ_DATASET", "agent_analytics")
    monkeypatch.setenv("PROJECT_ID", "my-project-id")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "123456789")  # Agent Runtime sets the NUMBER

    plugins = agent_module._analytics_plugins()

    assert len(plugins) == 1
    assert seen["project_id"] == "my-project-id"  # the id, not the number
    assert seen["dataset_id"] == "agent_analytics"
    assert seen["table_id"] == "agent_events"


def test_main_builds_the_adapter_from_the_app():
    """ADKAgent(adk_agent=...) cannot carry plugins; only from_app can."""
    from pathlib import Path

    source = (Path(inspect.getsourcefile(agent_module)).parents[1] / "main.py").read_text()

    assert "ADKAgent.from_app(" in source
    assert "ADKAgent(\n    adk_agent=" not in source
