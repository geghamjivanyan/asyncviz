"""Plugin-friendly namespace registry for env-var loaders.

Future enterprise / plugin packages can claim their own prefix
(``ASYNCVIZ_ACME_*``) without colliding with the core loader.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

#: Built-in namespace: every core option lives under this prefix.
CORE_NAMESPACE = "ASYNCVIZ_"


@dataclass(slots=True)
class NamespaceRegistration:
    """One namespace + the loader that consumes its env vars."""

    prefix: str
    loader: Callable[[dict[str, str]], None]
    """Called with the env-vars matching the prefix."""
    description: str = ""


@dataclass(slots=True)
class NamespaceRegistry:
    """In-process registry of namespace handlers."""

    _entries: list[NamespaceRegistration] = field(default_factory=list)

    def register(
        self,
        *,
        prefix: str,
        loader: Callable[[dict[str, str]], None],
        description: str = "",
    ) -> None:
        if not prefix.endswith("_"):
            prefix = prefix + "_"
        # Reject overlapping prefixes — explicit is better than implicit.
        for existing in self._entries:
            if existing.prefix == prefix:
                raise ValueError(f"namespace {prefix!r} already registered")
        self._entries.append(
            NamespaceRegistration(
                prefix=prefix.upper(),
                loader=loader,
                description=description,
            ),
        )

    def entries(self) -> tuple[NamespaceRegistration, ...]:
        return tuple(self._entries)

    def dispatch(self, environ: dict[str, str]) -> None:
        for entry in self._entries:
            subset = {k: v for k, v in environ.items() if k.startswith(entry.prefix)}
            if subset:
                entry.loader(subset)

    def reset(self) -> None:
        self._entries.clear()


_registry = NamespaceRegistry()


def get_default_namespace_registry() -> NamespaceRegistry:
    return _registry


def reset_default_namespace_registry() -> None:
    _registry.reset()
