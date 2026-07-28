from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
DATE_FORMAT = "%H:%M:%S"


def configure_logging(*, verbose: bool = False, quiet: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        force=True,
    )


@contextmanager
def timed_operation(logger: logging.Logger, label: str) -> Iterator[None]:
    logger.info("%s started", label)
    started = perf_counter()
    try:
        yield
    except Exception:
        logger.info("%s failed after %.1fs", label, perf_counter() - started)
        raise
    logger.info("%s completed in %.1fs", label, perf_counter() - started)
