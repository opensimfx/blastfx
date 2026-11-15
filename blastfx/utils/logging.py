import logging

LOGGER = logging.getLogger("BlastFX")


def info(message):
    LOGGER.info("[BlastFX] %s", message)


def warning(message):
    LOGGER.warning("[BlastFX] %s", message)


def error(message):
    LOGGER.error("[BlastFX] %s", message)
