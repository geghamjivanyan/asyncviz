import logging

from asyncviz.utils.logging import get_logger, setup_logging


def test_setup_logging_is_idempotent() -> None:
    first = setup_logging(debug=False)
    handler_count = len(first.handlers)
    second = setup_logging(debug=True)
    assert first is second
    assert len(second.handlers) == handler_count


def test_get_logger_uses_asyncviz_namespace() -> None:
    logger = get_logger("module")
    assert logger.name == "asyncviz.module"
    assert isinstance(logger, logging.Logger)
