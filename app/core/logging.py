"""Configuration structlog — logs structurés avec niveau, timestamp et rendu console coloré."""

import logging
import structlog


def configure_logging() -> None:
    """Configure structlog au démarrage de l'application."""
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Retourne un logger structlog lié au composant spécifié."""
    return structlog.get_logger(name)
