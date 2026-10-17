import logging

LOGGER = logging.getLogger("BlastFX")


def info(message):
    LOGGER.info("[Blast FX] %s", message)


def warning(message):
    LOGGER.warning("[Blast FX] %s", message)


def error(message):
    LOGGER.error("[Blast FX] %s", message)
