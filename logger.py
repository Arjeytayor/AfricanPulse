"""Shared error logger for all AfricanPulse modules."""

import logging
import os

LOG_PATH = r"C:\Users\DELL\Documents\AfricanPulse\logs\errors.log"
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(module)s.%(funcName)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)

logger = logging.getLogger("WorldPulseLogger")
