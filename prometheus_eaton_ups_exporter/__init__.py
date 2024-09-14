"""Initials of the Prometheus Eaton UPS Exporter."""

import logging
import sys

# External (root level) logging level
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')


def create_logger(name: str,
                  disabled: bool = False) -> logging.Logger:
    """Create logger for debug and error levels."""
    logger = logging.Logger(name)
    logger.setLevel(logging.WARNING)

    # create console handler and set level to debug
    debug_sh = logging.StreamHandler(sys.stdout)
    debug_sh.setLevel(logging.DEBUG)

    # create debug formatter
    debug_formatter = logging.Formatter(
        '%(name)s: %(levelname)s %(message)s'
    )
    # add formatter to debug_sh
    debug_sh.setFormatter(debug_formatter)
    logger.addHandler(debug_sh)

    # Create console handler and set level to error
    error_sh = logging.StreamHandler()
    error_sh.setLevel(logging.ERROR)

    # create error formatter
    error_formatter = logging.Formatter(
        '%(name)s:%(lineno)s %(levelname)s %(message)s'
    )
    # add formatter to error_sh
    error_sh.setFormatter(error_formatter)
    logger.addHandler(error_sh)
    logger.disabled = disabled
    return logger
