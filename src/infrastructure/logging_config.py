import logging

import structlog


def configure_structlog(debug: bool = False) -> None:
    """Configure structlog processor pipeline for the entire application.

    In production (debug=False): JSON output for machine parsing.
    In development (debug=True): Colored, human-readable console output.

    All logs include service="merkly" via an inline processor.
    stdlib logging (APScheduler, aiogram) is routed through structlog.
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        lambda _, __, event_dict: {**event_dict, "service": "merkly"},
    ]

    renderer = structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors
        + [
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through structlog so APScheduler/aiogram logs are captured
    logging.basicConfig(format="%(message)s", level=logging.DEBUG if debug else logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
