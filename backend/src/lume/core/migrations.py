from functools import lru_cache

from alembic.config import Config
from alembic.script import ScriptDirectory


@lru_cache
def expected_revision() -> str:
    revision = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    if revision is None:
        raise RuntimeError("Alembic migration graph has no head revision")
    return revision
