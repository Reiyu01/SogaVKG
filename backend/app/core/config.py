from pathlib import Path


# backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]

# backend/data/
DATA_DIR = BACKEND_ROOT / "data"

# backend/data/lab.db
SQLITE_DB_PATH = DATA_DIR / "lab.db"

# uip/semantic/mappings/
PROJECT_ROOT = BACKEND_ROOT.parent

MAPPING_DIR = (
    PROJECT_ROOT
    / "semantic"
    / "mappings"
)