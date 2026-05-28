"""Hard-coded defaults for every canonical runtime option.

Single source of truth — every per-domain options dataclass reads
its defaults from here so a tweak (e.g. flipping the default
``heartbeat_interval``) ripples through one place.
"""

from __future__ import annotations

from typing import Final, Literal

# ── Dashboard / network ────────────────────────────────────────────────

DEFAULT_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 8877
DEFAULT_HEARTBEAT_INTERVAL_SECONDS: Final[float] = 5.0
DEFAULT_STARTUP_TIMEOUT_SECONDS: Final[float] = 5.0
DEFAULT_LOG_LEVEL: Final[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None] = None
DEFAULT_DEBUG: Final[bool] = False
DEFAULT_FRONTEND_MODE: Final[Literal["auto", "embedded", "api-only"]] = "auto"

# ── Browser ─────────────────────────────────────────────────────────────

DEFAULT_BROWSER_POLICY: Final[Literal["auto", "always", "never"]] = "auto"
DEFAULT_BROWSER_OPEN: Final[bool] = True
DEFAULT_READINESS_TIMEOUT_SECONDS: Final[float] = 5.0
DEFAULT_READINESS_INTERVAL_SECONDS: Final[float] = 0.1

# ── Monitoring ──────────────────────────────────────────────────────────

DEFAULT_ENABLE_INSTRUMENTATION: Final[bool] = True
DEFAULT_LAG_WARNING_MS: Final[float] = 50.0
DEFAULT_LAG_CRITICAL_MS: Final[float] = 250.0
DEFAULT_LAG_FREEZE_MS: Final[float] = 1000.0
DEFAULT_LAG_SAMPLE_INTERVAL_MS: Final[float] = 10.0
DEFAULT_CAPTURE_STACK_TRACES: Final[bool] = True

# ── Warning ────────────────────────────────────────────────────────────

DEFAULT_WARNING_BUFFER: Final[int] = 256
DEFAULT_BLOCKING_COOLDOWN_MS: Final[float] = 500.0

# ── Recording ──────────────────────────────────────────────────────────

DEFAULT_RECORDING_ENABLED: Final[bool] = False
DEFAULT_RECORDING_COMPRESSION: Final[Literal["none", "gzip"]] = "gzip"
DEFAULT_RECORDING_CHUNK_EVENTS: Final[int] = 4096
DEFAULT_RECORDING_CHUNK_BYTES: Final[int] = 4 * 1024 * 1024
DEFAULT_RECORDING_QUEUE_CAPACITY: Final[int] = 16_384
DEFAULT_RECORDING_FLUSH_INTERVAL_SECONDS: Final[float] = 1.0

# ── Replay ─────────────────────────────────────────────────────────────

DEFAULT_REPLAY_BUFFER_CAPACITY: Final[int] = 8192
DEFAULT_REPLAY_RETENTION_SECONDS: Final[float] = 600.0
DEFAULT_REPLAY_CHECKPOINT_INTERVAL_SECONDS: Final[float] = 30.0

# ── Security ───────────────────────────────────────────────────────────

DEFAULT_BIND_LOOPBACK_ONLY: Final[bool] = True
DEFAULT_ALLOW_REMOTE_CONNECTIONS: Final[bool] = False
