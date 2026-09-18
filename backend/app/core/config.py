from pathlib import Path
import os


# backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]

# backend/data/
DATA_DIR = BACKEND_ROOT / "data"

# An optional deployment-level default. Product flows should supply a source
# explicitly; the bundled sample database is not a platform assumption.
_sqlite_db_path = os.getenv("SQLITE_DB_PATH")
SQLITE_DB_PATH = Path(_sqlite_db_path).expanduser() if _sqlite_db_path else None

# Platform metadata (source profiles and ingestion-job history), distinct from
# any customer/source database being ingested.
PLATFORM_STATE_DB_PATH = Path(
    os.getenv("PLATFORM_STATE_DB_PATH", str(DATA_DIR / "platform_state.db"))
).expanduser()

# uip/semantic/mappings/
PROJECT_ROOT = BACKEND_ROOT.parent

MAPPING_DIR = (
    PROJECT_ROOT
    / "semantic"
    / "mappings"
)
PROJECT_MAPPING_ROOT = PROJECT_ROOT / "semantic" / "projects"
