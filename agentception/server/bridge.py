"""
Path bridge: gives this project runtime access to the
ai-learning-path-generator data (role_projects.json, job_market.json, etc.)
without copying any files.
"""
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Learning path data directory
LEARNING_PATH_DATA = os.getenv(
    "LEARNING_PATH_DATA",
    os.path.join(os.path.dirname(__file__), "..", "..", "learning-path-generator"),
)

if LEARNING_PATH_DATA and LEARNING_PATH_DATA not in sys.path:
    sys.path.insert(0, LEARNING_PATH_DATA)

# Expose available modules for other devs
BRIDGE_MODULES = [
    "src.learning_path",
    "src.ml.job_market",
    "src.ml.resource_search",
    "src.utils.perplexity",
]

# Convenience: resolve data file paths
DATA_DIR = os.path.join(LEARNING_PATH_DATA, "src", "data") if LEARNING_PATH_DATA else None


def data_file(name: str) -> str | None:
    """Return absolute path to a learning-path data JSON file, or None."""
    if DATA_DIR and os.path.isfile(os.path.join(DATA_DIR, name)):
        return os.path.join(DATA_DIR, name)
    return None
