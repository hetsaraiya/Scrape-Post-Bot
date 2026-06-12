"""Loguru-based logging configuration with correlation ID support."""

import logging
import os
import sys
from contextvars import ContextVar

from loguru import logger

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<yellow>{extra[correlation_id]}</yellow> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[correlation_id]} | "
    "{name}:{function}:{line} - {message}"
)


def _add_correlation_id(record) -> None:
    """Inject the current correlation ID into every log record."""
    record["extra"]["correlation_id"] = correlation_id_var.get("") or "-"


class InterceptHandler(logging.Handler):
    """Intercept standard logging messages and route them to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(log_level: str = "INFO") -> None:
    """Configure loguru logging with console and file handlers."""
    # Route standard logging (including uvicorn) through loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for uvicorn_logger in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging_logger = logging.getLogger(uvicorn_logger)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    log_dir = "app/logs"
    os.makedirs(log_dir, exist_ok=True)

    logger.remove()  # Remove default handler
    logger.configure(patcher=_add_correlation_id)

    logger.add(sys.stdout, level=log_level, format=_CONSOLE_FORMAT, colorize=True)
    logger.add(
        f"{log_dir}/{{time:YYYY-MM-DD}}.log",
        rotation="50 MB",
        retention="10 days",
        level="DEBUG",
        format=_FILE_FORMAT,
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )


def get_logger(name: str = ""):
    """Return the shared loguru logger (kept for call-site compatibility)."""
    return logger
