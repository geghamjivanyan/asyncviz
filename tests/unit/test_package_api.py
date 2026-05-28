import asyncviz


def test_package_exports_start_and_stop() -> None:
    assert callable(asyncviz.start)
    assert callable(asyncviz.stop)


def test_package_has_version() -> None:
    assert isinstance(asyncviz.__version__, str)
    assert asyncviz.__version__.count(".") >= 1
