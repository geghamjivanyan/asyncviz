from __future__ import annotations

from asyncviz.runtime.monitoring.blocking.stack_capture import (
    FilterPolicy,
    LiveFrameProvider,
    StackCaptureLimits,
    StackSampler,
)

from ._helpers import asyncio_frame, static_provider, user_frame


def _build_sampler(**overrides) -> StackSampler:
    limits = overrides.pop("limits", StackCaptureLimits(capture_code_context=False))
    filters = overrides.pop("filters", FilterPolicy.default())
    return StackSampler(limits=limits, filters=filters)


# ── filter behavior ────────────────────────────────────────────────────


def test_sampler_drops_internal_frames_by_default() -> None:
    sampler = _build_sampler()
    provider = static_provider(
        user_frame(function="handler"),
        asyncio_frame(),
        user_frame(function="db_call"),
    )
    out = sampler.sample(provider)
    assert out.frames_total == 3
    assert out.filtered_count == 1
    assert [f.function for f in out.frames] == ["handler", "db_call"]


def test_sampler_keeps_internal_frames_when_opted_in() -> None:
    sampler = _build_sampler(
        filters=FilterPolicy(
            module_prefixes=("asyncio",),
            include_internal_frames=True,
        )
    )
    provider = static_provider(user_frame(), asyncio_frame())
    out = sampler.sample(provider)
    assert out.filtered_count == 0
    assert any(f.is_internal for f in out.frames)


# ── depth bounds ───────────────────────────────────────────────────────


def test_sampler_truncates_deeper_than_max_depth() -> None:
    sampler = _build_sampler(limits=StackCaptureLimits(max_depth=3, capture_code_context=False))
    provider = static_provider(*[user_frame(lineno=i) for i in range(10)])
    out = sampler.sample(provider)
    # frames_total reflects the *pre-truncation* count
    assert out.frames_total == 10
    assert len(out.frames) == 3


def test_sampler_preserves_top_of_stack_when_truncating() -> None:
    sampler = _build_sampler(limits=StackCaptureLimits(max_depth=2, capture_code_context=False))
    provider = static_provider(
        user_frame(function="top"),
        user_frame(function="middle"),
        user_frame(function="bottom"),
    )
    out = sampler.sample(provider)
    # First two frames preserved — "top" stays index 0
    assert [f.function for f in out.frames] == ["top", "middle"]


# ── async-flag detection ───────────────────────────────────────────────


def test_async_flag_from_co_flags() -> None:
    sampler = _build_sampler()
    coro_frame = user_frame(co_flags=0x100)  # CO_COROUTINE
    out = sampler.sample(static_provider(coro_frame))
    assert out.frames[0].is_async is True


def test_non_async_flag_remains_false() -> None:
    sampler = _build_sampler()
    out = sampler.sample(static_provider(user_frame(co_flags=0)))
    assert out.frames[0].is_async is False


# ── code-context resolution ────────────────────────────────────────────


def test_code_context_disabled_returns_none() -> None:
    sampler = _build_sampler(limits=StackCaptureLimits(capture_code_context=False))
    out = sampler.sample(static_provider(user_frame()))
    assert out.frames[0].code_context is None


def test_code_context_for_nonexistent_file_is_none() -> None:
    sampler = _build_sampler(
        limits=StackCaptureLimits(capture_code_context=True),
    )
    out = sampler.sample(
        static_provider(user_frame(filename="/this/path/does/not/exist.py", lineno=99))
    )
    assert out.frames[0].code_context is None


def test_code_context_truncates_to_max_length() -> None:
    sampler = _build_sampler(
        limits=StackCaptureLimits(capture_code_context=True, max_code_length=20),
    )
    # Use the test file itself — it exists; this line is long enough.
    own_frame = user_frame(filename=__file__, lineno=1)
    out = sampler.sample(static_provider(own_frame))
    # First line of this test file ("from __future__ import annotations") is
    # 34 chars; should be truncated to 20.
    assert out.frames[0].code_context is not None
    assert len(out.frames[0].code_context) <= 20


# ── determinism ────────────────────────────────────────────────────────


def test_sample_is_deterministic_for_identical_input() -> None:
    sampler = _build_sampler()
    provider = static_provider(user_frame(), asyncio_frame(), user_frame(function="g"))
    out_a = sampler.sample(provider)
    out_b = sampler.sample(static_provider(*provider.collect()))
    assert out_a == out_b


# ── live provider ──────────────────────────────────────────────────────


def test_live_provider_returns_at_least_one_frame() -> None:
    p = LiveFrameProvider()
    frames = p.collect()
    assert len(frames) >= 1
    # The call site is in this test, so the top frame should reference it.
    assert any("test_sampler" in f.filename for f in frames)


def test_live_provider_skip_engine_frames() -> None:
    a = LiveFrameProvider(skip_engine_frames=0).collect()
    b = LiveFrameProvider(skip_engine_frames=2).collect()
    # b should have at most as many frames as a, since we asked to skip
    # additional ones.
    assert len(b) <= len(a)
