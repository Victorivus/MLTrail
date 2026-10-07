"""Per-user trained models, stored in the app database.

Each successful training inserts a row in ``models`` holding the serialized
estimator plus its metadata, and makes it the user's single active model in
the same transaction. Pages ask this module whether a user has a model and
load it from here; nothing is kept in Streamlit session state or in a shared
file, so models survive refreshes and restarts and never leak across users.

Artifacts are serialized with skops rather than pickle/joblib: loading a
pickle executes arbitrary code, while skops only rebuilds an allow-listed set
of types. :data:`TRUSTED_TYPES` lists the extra types our pipeline needs on
top of skops' defaults; anything else in an artifact makes loading fail.
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import sqlite3
import zipfile

import sklearn
import skops
import skops.io as sio

from database.create_db import Database

logger = logging.getLogger(__name__)

ARTIFACT_FORMAT = "skops"
# Feature columns/conventions the model was trained with; bump on any change
# to ai.features / ai.gpx.FEATURE_COLUMNS so stale models can be detected.
FEATURE_SCHEMA_VERSION = 1
# Types beyond skops' defaults that a GradientBoostingRegressor pipeline uses.
TRUSTED_TYPES = ("sklearn.tree._tree.Tree",)
# Successful models kept per user (the active one is always kept).
KEEP_PER_USER = 5

# Columns safe to read for listing/gating: everything but the artifact.
_INFO_COLUMNS = ("model_id, user_id, status, is_active, algorithm, "
                 "feature_schema_version, hyperparams, metrics, training_set, "
                 "library_versions, artifact_sha256, artifact_format, created_at")


class ModelLoadError(Exception):
    """A stored model can't be loaded safely (corrupt, untrusted or stale)."""


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def serialize(model) -> bytes:
    """Serialize an estimator to skops bytes (deflate-compressed)."""
    return sio.dumps(model, compression=zipfile.ZIP_DEFLATED)


def deserialize(blob: bytes, expected_sha256: str | None = None):
    """Rebuild an estimator, refusing tampered or non-allow-listed content."""
    if expected_sha256 is not None:
        actual = hashlib.sha256(blob).hexdigest()
        if actual != expected_sha256:
            raise ModelLoadError("Model artifact checksum mismatch")
    try:
        untrusted = sio.get_untrusted_types(data=blob)
    except Exception as exc:
        raise ModelLoadError(f"Unreadable model artifact: {exc}") from exc
    unexpected = sorted(set(untrusted) - set(TRUSTED_TYPES))
    if unexpected:
        raise ModelLoadError(f"Model artifact contains untrusted types: {unexpected}")
    return sio.loads(blob, trusted=list(untrusted))


def _row_to_info(row) -> dict:
    info = dict(row)
    for key in ("hyperparams", "metrics", "training_set", "library_versions"):
        if info.get(key):
            info[key] = json.loads(info[key])
    info["is_active"] = bool(info["is_active"])
    return info


def save_model(db_path: str, user_id: int, model, *, training_set: list,
               hyperparams: dict | None = None, metrics: dict | None = None) -> int:
    """Store ``model`` as ``user_id``'s new active model; return its id.

    Deactivating the previous model, inserting the new one and pruning old
    versions happen in one transaction, so a crash can't leave a user with
    zero or two active models.
    """
    blob = serialize(model)
    versions = {"sklearn": sklearn.__version__, "skops": skops.__version__}
    conn = _connect(db_path)
    try:
        with conn:  # one transaction
            Database.create_models_table(conn)
            conn.execute("UPDATE models SET is_active = 0 "
                         "WHERE user_id = ? AND is_active = 1", (user_id,))
            cur = conn.execute(
                "INSERT INTO models (user_id, status, is_active, algorithm, "
                "feature_schema_version, hyperparams, metrics, training_set, "
                "library_versions, artifact, artifact_sha256, artifact_format) "
                "VALUES (?, 'succeeded', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, _algorithm_name(model), FEATURE_SCHEMA_VERSION,
                 json.dumps(hyperparams, default=str) if hyperparams else None,
                 json.dumps(metrics) if metrics else None,
                 json.dumps([list(t) for t in training_set]),
                 json.dumps(versions), blob,
                 hashlib.sha256(blob).hexdigest(), ARTIFACT_FORMAT))
            model_id = cur.lastrowid
            conn.execute(
                "DELETE FROM models WHERE user_id = ? AND is_active = 0 AND model_id NOT IN "
                "(SELECT model_id FROM models WHERE user_id = ? "
                " ORDER BY model_id DESC LIMIT ?)",
                (user_id, user_id, KEEP_PER_USER))
    finally:
        conn.close()
    logger.info("Saved model %s for user %s (%d bytes)", model_id, user_id, len(blob))
    return model_id


def _algorithm_name(model) -> str:
    est = model.steps[-1][1] if hasattr(model, "steps") else model
    return f"{type(est).__module__}.{type(est).__name__}"


def get_active_model_info(db_path: str, user_id) -> dict | None:
    """Metadata of the user's active model (no artifact), or ``None``."""
    if user_id is None:
        return None
    conn = _connect(db_path)
    try:
        row = conn.execute(f"SELECT {_INFO_COLUMNS} FROM models "
                           "WHERE user_id = ? AND is_active = 1", (user_id,)).fetchone()
    except sqlite3.OperationalError as exc:
        # Reads never run DDL: a DB without the table simply has no models.
        if "no such table" in str(exc):
            return None
        raise
    finally:
        conn.close()
    return _row_to_info(row) if row else None


def deactivate_models(db_path: str, user_id) -> None:
    """Make the user have no active model (stored versions are kept)."""
    conn = _connect(db_path)
    try:
        with conn:
            Database.create_models_table(conn)
            conn.execute("UPDATE models SET is_active = 0 WHERE user_id = ?", (user_id,))
    finally:
        conn.close()


def load_active_model(db_path: str, user_id):
    """Return ``(estimator, info)`` for the user's active model.

    Raises:
        LookupError: the user has no active model.
        ModelLoadError: the stored model can't be loaded safely; the user
            should retrain.
    """
    info = get_active_model_info(db_path, user_id)
    if info is None:
        raise LookupError("No trained model for this user")
    if info["feature_schema_version"] != FEATURE_SCHEMA_VERSION:
        raise ModelLoadError("This model was trained with an older feature "
                             "format; please retrain it.")
    model = _load_artifact(db_path, info["model_id"], info["artifact_sha256"])
    return model, info


@functools.lru_cache(maxsize=32)
def _load_artifact(db_path: str, model_id: int, sha256: str):
    # Cached by (model_id, sha256): a row's artifact never changes, so the
    # cache can't serve one user's model for another's id.
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT artifact FROM models WHERE model_id = ?",
                           (model_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise LookupError(f"Model {model_id} no longer exists")
    return deserialize(row["artifact"], expected_sha256=sha256)
