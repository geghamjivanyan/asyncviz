from __future__ import annotations

from asyncviz.runtime.monitoring.blocking.stack_capture import FilterPolicy


def test_default_filter_marks_asyncio_internal() -> None:
    p = FilterPolicy.default()
    assert p.is_internal("asyncio", "/usr/lib/asyncio/__init__.py") is True
    assert p.is_internal("asyncio.base_events", "/usr/lib/asyncio/base_events.py") is True


def test_default_filter_marks_asyncviz_internal() -> None:
    p = FilterPolicy.default()
    assert p.is_internal("asyncviz.runtime.monitoring", "/path/asyncviz/x.py") is True


def test_user_module_is_not_internal() -> None:
    p = FilterPolicy.default()
    assert p.is_internal("myapp.db", "/tmp/db.py") is False


def test_partial_prefix_does_not_match() -> None:
    """`asyncio_foo` must not be treated as `asyncio`'s child."""
    p = FilterPolicy.default()
    assert p.is_internal("asyncio_foo", "/tmp/x.py") is False


def test_filename_fragment_matching() -> None:
    p = FilterPolicy(
        module_prefixes=(),
        filename_fragments=("/site-packages/somelib/",),
    )
    assert p.is_internal("anything", "/tmp/site-packages/somelib/mod.py") is True
    assert p.is_internal("anything", "/tmp/myapp.py") is False


def test_include_internal_frames_flag_independent_of_predicate() -> None:
    """The flag controls dropping at the sampler — not the predicate."""
    p = FilterPolicy(
        module_prefixes=("asyncio",),
        include_internal_frames=True,
    )
    assert p.is_internal("asyncio", "/x") is True
    assert p.include_internal_frames is True


def test_with_extra_prefixes_extends_base() -> None:
    base = FilterPolicy(module_prefixes=("asyncio",))
    extended = FilterPolicy.with_extra_prefixes(["mylib"], base=base)
    assert extended.is_internal("mylib.x", "/x") is True
    assert extended.is_internal("asyncio.base_events", "/x") is True
    assert extended.is_internal("myapp", "/x") is False


def test_to_dict_round_trips() -> None:
    p = FilterPolicy(
        module_prefixes=("asyncio", "asyncviz"),
        filename_fragments=("/x/",),
        include_internal_frames=True,
    )
    d = p.to_dict()
    assert d["module_prefixes"] == ["asyncio", "asyncviz"]
    assert d["filename_fragments"] == ["/x/"]
    assert d["include_internal_frames"] is True
