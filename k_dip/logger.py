import logging
import warnings

from k_dip.settings import settings


def configure_logging():
    # Setup k_dip logger
    logger = get_logger()

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(settings.LOGLEVEL)

    # Ignore future warnings
    warnings.simplefilter(action="ignore", category=FutureWarning)

    # Set component loglevels
    logging.getLogger("PIL").setLevel(logging.ERROR)
    logging.getLogger("fontTools.subset").setLevel(logging.ERROR)
    logging.getLogger("fontTools.ttLib.ttFont").setLevel(logging.ERROR)
    logging.getLogger("weasyprint").setLevel(logging.CRITICAL)


def get_logger():
    return logging.getLogger("k_dip")
