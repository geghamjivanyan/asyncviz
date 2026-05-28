"""Top-level replay package.

Subpackages:

* :mod:`asyncviz.replay.recording` — append-oriented, crash-resilient
  runtime event persistence. The lower-level streaming layer that
  writes every observed event to disk so a future replay engine can
  reconstruct the runtime deterministically.

This package is distinct from :mod:`asyncviz.runtime.replay` (the
in-memory live-replay buffer + session-bundle exporter). The two
coexist: the in-memory buffer powers websocket reconnect catch-up; the
recording layer here powers offline replay + time-travel debugging.
"""
