"""Loguru-based logging configuration with correlation ID support."""

import os
import sys
from contextvars import ContextVar
from loguru import logger

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def _get_correlation_id() -> str:
    """Get the current correlation ID from context."""
    return correlation_id_var.get("") or "-"


def _format_with_cid(record):
    """Add correlation ID to the log record."""
    record["extra"]["correlation_id"] = _get_correlation_id()
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<yellow>{extra[correlation_id]}</yellow> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>\n"
    )


import logging

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
    # Intercept standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Silence uvicorn's default handlers to avoid double logging
    for uvicorn_logger in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging_logger = logging.getLogger(uvicorn_logger)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    log_dir = "app/logs"
    os.makedirs(log_dir, exist_ok=True)
    logger.remove()  # Remove default handler

    # Configure console logging
    logger.add(sys.stdout, level=log_level, format=_format_with_cid, colorize=True)

    # Configure file logging (no colors)
    def _file_format(record):
        record["extra"]["correlation_id"] = _get_correlation_id()
        return (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[correlation_id]} | "
            "{name}:{function}:{line} - {message}\n"
        )

    logger.add(
        "app/logs/{time:YYYY-MM-DD}.log",
        rotation="50 MB",
        retention="10 days",
        level="DEBUG",
        format=_file_format,
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )


def get_logger(name: str):
    """Return a named logger (for compatibility)."""
    return logger.bind(name=name)
