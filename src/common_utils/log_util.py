import logging
import os


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance with basic configuration that works reliably in AWS Lambda
    (where a default handler is already attached).
    """
    # Desired log level (defaults to INFO)
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level_str, logging.INFO)

    root_logger = logging.getLogger()
    # Always set the root logger level – Lambda attaches a default handler but leaves level at WARNING
    root_logger.setLevel(numeric_level)

    # Configure basic logging **only** if no handlers are present (first invocation / local env)
    if not root_logger.handlers:
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    return logging.getLogger(name or __name__) 