'''
    One-off, idempotent schema migration for an existing events.db.

    Adds the tables/columns newer code expects (models, user_results,
    races.cat_needs_backfill) and the query indexes. Safe to run repeatedly;
    on a full DB the first run takes ~30 s (index builds + ANALYZE) and holds
    a write lock, so don't run it while a loader is writing.

    Usage:
        PYTHONPATH=src python -m database.migrate [-p data/events.db]
        docker compose run --rm mltrail python -m database.migrate
'''
import argparse
import logging
import os
import time

from config import get_config
from database.create_db import Database

logger = logging.getLogger(__name__)


def migrate(path: str) -> list:
    '''Apply all idempotent migrations to the DB at ``path``.'''
    if not os.path.exists(path):
        raise FileNotFoundError(f"No database at {path}")
    Database.ensure_cat_backfill_column(path)
    Database.ensure_user_results_table(path)
    Database.ensure_models_table(path)
    return Database.ensure_indexes(path)


def main():
    parser = argparse.ArgumentParser(description='Apply schema migrations to the app DB.')
    parser.add_argument('-p', '--path', default=None, help='DB path (default: from config).')
    args = parser.parse_args()
    cfg = get_config()  # also configures logging
    path = args.path or cfg.db_path

    start = time.time()
    created = migrate(path)
    logger.info("Migration of %s done in %.1fs; indexes created: %s",
                path, time.time() - start, ", ".join(created) or "none (already present)")


if __name__ == "__main__":
    main()
