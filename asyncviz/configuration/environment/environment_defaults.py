"""Constants that describe the AsyncViz environment-variable contract.

Every env-var-related module in this package reads from here so a
single change (renaming the prefix, adding a new namespace) ripples
through one place.
"""

from __future__ import annotations

from typing import Final

#: Canonical prefix for every AsyncViz-owned env var.
DEFAULT_NAMESPACE: Final[str] = "ASYNCVIZ_"

#: Suffix appended to keys whose value carries a sensitive payload
#: (auth tokens, signing keys). Future task: the loader will redact
#: these from diagnostics automatically.
SECRET_KEY_SUFFIXES: Final[tuple[str, ...]] = (
    "_TOKEN",
    "_SECRET",
    "_PASSWORD",
    "_KEY",
)

#: Maximum bytes we'll accept for any one env-var value. Larger
#: values are treated as a parse failure so a misconfigured shell
#: doesn't OOM the resolver.
MAX_VALUE_BYTES: Final[int] = 16 * 1024
