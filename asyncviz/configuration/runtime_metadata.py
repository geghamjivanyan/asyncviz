"""Per-option provenance + value metadata.

Stored alongside each :class:`RuntimeOptions` snapshot so the
diagnostics endpoint can answer "where did this option come from,
and what was its raw value?".

Kept tiny on purpose — the metadata is a separate structure so the
``RuntimeOptions`` dataclasses stay clean and easy to construct
without provenance fields polluting every field signature.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from asyncviz.configuration.runtime_sources import OptionSource


@dataclass(frozen=True, slots=True)
class OptionProvenance:
    """One option's resolved value + the source that supplied it."""

    value: Any
    source: OptionSource
    raw_text: str | None = None
    """Original string as observed (env var, CLI flag). ``None`` for
    typed defaults / API kwargs."""


@dataclass(slots=True)
class ProvenanceMap:
    """Mutable map of ``"namespace.option" → OptionProvenance``.

    Used during resolution; frozen once the resolver hands it off.
    """

    entries: dict[str, OptionProvenance] = field(default_factory=dict)

    def record(
        self,
        key: str,
        *,
        value: Any,
        source: OptionSource,
        raw_text: str | None = None,
    ) -> None:
        existing = self.entries.get(key)
        if existing is not None and not source.precedes(existing.source):
            return
        self.entries[key] = OptionProvenance(value=value, source=source, raw_text=raw_text)

    def get(self, key: str) -> OptionProvenance | None:
        return self.entries.get(key)

    def source_for(self, key: str) -> OptionSource:
        entry = self.entries.get(key)
        return entry.source if entry is not None else OptionSource.UNSET

    def items(self):  # type: ignore[no-untyped-def]
        return self.entries.items()

    def to_dict(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for key, prov in self.entries.items():
            out[key] = {
                "value": prov.value,
                "source": prov.source.name,
                "raw_text": prov.raw_text,
            }
        return out
