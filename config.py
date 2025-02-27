import logging
from pathlib import Path

# ----------------------------------------------------------------------
# Constants & Directories
# ----------------------------------------------------------------------
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

# ----------------------------------------------------------------------
# Logging Configuration
# ----------------------------------------------------------------------
def setup_logging():
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )