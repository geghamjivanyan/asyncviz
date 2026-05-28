from __future__ import annotations

import pytest

from asyncviz.configuration.environment.environment_namespaces import (
    NamespaceRegistry,
)


def test_register_then_dispatch_routes_subset() -> None:
    registry = NamespaceRegistry()
    seen: dict[str, dict[str, str]] = {}

    def core_loader(values: dict[str, str]) -> None:
        seen["core"] = values

    def plugin_loader(values: dict[str, str]) -> None:
        seen["plugin"] = values

    registry.register(prefix="ASYNCVIZ_", loader=core_loader)
    registry.register(prefix="ASYNCVIZ_ACME_", loader=plugin_loader)
    registry.dispatch(
        {
            "ASYNCVIZ_PORT": "9000",
            "ASYNCVIZ_ACME_FEATURE": "on",
            "UNRELATED": "x",
        },
    )
    assert "ASYNCVIZ_PORT" in seen["core"]
    assert "ASYNCVIZ_ACME_FEATURE" in seen["plugin"]


def test_register_rejects_duplicate_prefix() -> None:
    registry = NamespaceRegistry()
    registry.register(prefix="X_", loader=lambda _: None)
    with pytest.raises(ValueError):
        registry.register(prefix="X_", loader=lambda _: None)


def test_register_normalizes_trailing_underscore() -> None:
    registry = NamespaceRegistry()
    registry.register(prefix="MY_NS", loader=lambda _: None)
    entries = registry.entries()
    assert entries[0].prefix == "MY_NS_"


def test_reset_clears_entries() -> None:
    registry = NamespaceRegistry()
    registry.register(prefix="X_", loader=lambda _: None)
    registry.reset()
    assert registry.entries() == ()
