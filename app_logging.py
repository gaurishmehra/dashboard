import logging
import os
from typing import Callable


_CONFIGURED = False


def _resolve_level() -> int:
    level_from_env = os.environ.get("DASHBOARD_LOG_LEVEL")
    if level_from_env:
        return getattr(logging, level_from_env.upper(), logging.WARNING)

    debug_flag = os.environ.get("DASHBOARD_DEBUG", "").strip().lower()
    if debug_flag in {"1", "true", "yes", "on"}:
        return logging.DEBUG

    return logging.WARNING


def _configure_once() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    logging.basicConfig(
        level=_resolve_level(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_once()
    return logging.getLogger(name)


def module_print(name: str, level: int = logging.DEBUG) -> Callable[..., None]:
    """Replacement for noisy print() calls routed into structured logging."""
    logger = get_logger(name)

    def _printer(*args, sep=" ", end="\n", **_kwargs):
        message = sep.join(str(arg) for arg in args)
        if end and end != "\n":
            message += end.replace("\n", "")
        logger.log(level, message)

    return _printer
