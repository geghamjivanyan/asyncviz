"""Frame-filter chain.

A filter is a stable, deterministic predicate over a :class:`CapturedFrame`
that decides whether the frame is *user-relevant*. The chain is applied
once at sample time and the filter result is cached on the frame
(``is_internal``).

Today the chain is just a module-prefix matcher: any frame whose module
starts with one of the configured prefixes is flagged internal. The
serializer's default policy drops internals; users can opt back in via
``include_internal_frames=True`` on the configuration.

The filter chain is replay-safe by construction — it never reads the
clock and never mutates state.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

#: Modules whose frames are *infrastructure noise* relative to user
#: code. Walking through these adds zero diagnostic value when looking
#: for blocking root cause: ``asyncio.base_events.run_forever`` shows
#: up in every freeze.
DEFAULT_INTERNAL_MODULE_PREFIXES: tuple[str, ...] = (
    "asyncio",
    "asyncviz",
    "concurrent.futures",
    "selectors",
    "_thread",
    "threading",
    "queue",
)

#: Filename substrings to mark as internal regardless of module name.
#: Useful for site-packages frameworks the user doesn't want to dig into.
DEFAULT_INTERNAL_FILENAME_FRAGMENTS: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FilterPolicy:
    """Frame-filter configuration.

    ``module_prefixes`` and ``filename_fragments`` are matched
    case-sensitively (Python module names already enforce that). Empty
    tuples disable that dimension.

    ``include_internal_frames``:

    * ``False`` (default) → filtered frames are dropped from the
      ``frames`` tuple but counted in ``filtered_count``.
    * ``True`` → filtered frames stay in ``frames`` with
      ``is_internal=True``; the UI can render them dimmed.
    """

    module_prefixes: tuple[str, ...] = field(
        default_factory=lambda: DEFAULT_INTERNAL_MODULE_PREFIXES
    )
    filename_fragments: tuple[str, ...] = field(
        default_factory=lambda: DEFAULT_INTERNAL_FILENAME_FRAGMENTS
    )
    include_internal_frames: bool = False

    @classmethod
    def default(cls) -> FilterPolicy:
        return cls()

    def is_internal(self, module: str, filename: str) -> bool:
        for prefix in self.module_prefixes:
            if module == prefix or module.startswith(prefix + "."):
                return True
        return any(fragment and fragment in filename for fragment in self.filename_fragments)

    def to_dict(self) -> dict[str, object]:
        return {
            "module_prefixes": list(self.module_prefixes),
            "filename_fragments": list(self.filename_fragments),
            "include_internal_frames": self.include_internal_frames,
        }

    @classmethod
    def with_extra_prefixes(
        cls,
        extra: Iterable[str],
        *,
        base: FilterPolicy | None = None,
    ) -> FilterPolicy:
        """Convenience: extend the base policy's prefix list."""
        base = base or cls.default()
        merged = (*base.module_prefixes, *tuple(extra))
        return FilterPolicy(
            module_prefixes=merged,
            filename_fragments=base.filename_fragments,
            include_internal_frames=base.include_internal_frames,
        )
