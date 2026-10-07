'''
Tests for ai.model_store: per-user model persistence in the app database.
'''
import os
import sqlite3
import tempfile
import unittest
import zipfile

import numpy as np
import pandas as pd
import skops.io as sio
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from ai import model_store
from ai.model_store import (save_model, get_active_model_info, load_active_model,
                            deactivate_models, deserialize, serialize,
                            ModelLoadError, KEEP_PER_USER)
from database.create_db import Database


def _fit(seed):
    '''A small pipeline shaped like the trained one (passthrough + GBR).'''
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(rng.random((60, 3)), columns=["a", "b", "c"])
    y = X["a"] * 1000 * (seed + 1) + rng.random(60)
    return Pipeline([("std_scaler", "passthrough"),
                     ("regression", GradientBoostingRegressor(n_estimators=10, random_state=0))]
                    ).fit(X, y), X


class ModelStoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self._tmp.name, "events.db")
        Database.create_database(self.db)
        model_store._load_artifact.cache_clear()

    def tearDown(self):
        self._tmp.cleanup()

    def _count(self, user_id):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT count(*) FROM models WHERE user_id = ?",
                                (user_id,)).fetchone()[0]
        finally:
            conn.close()


class TestSaveAndLoad(ModelStoreTestCase):
    def test_round_trip_and_metadata(self):
        model, X = _fit(0)
        model_id = save_model(self.db, 1, model, training_set=[(10, "r1", "42")],
                              hyperparams={"regression__max_depth": 3},
                              metrics={"holdout_mae_seconds": 61.0})

        info = get_active_model_info(self.db, 1)
        self.assertEqual(info["model_id"], model_id)
        self.assertTrue(info["is_active"])
        self.assertEqual(info["training_set"], [[10, "r1", "42"]])
        self.assertEqual(info["metrics"]["holdout_mae_seconds"], 61.0)
        self.assertEqual(info["algorithm"],
                         "sklearn.ensemble._gb.GradientBoostingRegressor")
        self.assertNotIn("artifact", info)

        loaded, info2 = load_active_model(self.db, 1)
        self.assertEqual(info2["model_id"], model_id)
        np.testing.assert_allclose(loaded.predict(X), model.predict(X))

    def test_models_are_isolated_per_user(self):
        model_a, X = _fit(0)
        model_b, _ = _fit(5)
        save_model(self.db, 1, model_a, training_set=[])
        save_model(self.db, 2, model_b, training_set=[])

        loaded_a, _ = load_active_model(self.db, 1)
        loaded_b, _ = load_active_model(self.db, 2)
        np.testing.assert_allclose(loaded_a.predict(X), model_a.predict(X))
        np.testing.assert_allclose(loaded_b.predict(X), model_b.predict(X))
        self.assertFalse(np.allclose(loaded_a.predict(X), loaded_b.predict(X)))
        self.assertIsNone(get_active_model_info(self.db, 3))

    def test_retrain_replaces_active_model(self):
        first, X = _fit(0)
        second, _ = _fit(3)
        first_id = save_model(self.db, 1, first, training_set=[])
        load_active_model(self.db, 1)  # warm the cache with the first model
        second_id = save_model(self.db, 1, second, training_set=[])

        self.assertNotEqual(first_id, second_id)
        loaded, info = load_active_model(self.db, 1)
        self.assertEqual(info["model_id"], second_id)
        np.testing.assert_allclose(loaded.predict(X), second.predict(X))
        conn = sqlite3.connect(self.db)
        active = conn.execute("SELECT count(*) FROM models WHERE user_id = 1 "
                              "AND is_active = 1").fetchone()[0]
        conn.close()
        self.assertEqual(active, 1)

    def test_old_versions_are_pruned(self):
        model, _ = _fit(0)
        for _ in range(KEEP_PER_USER + 3):
            last_id = save_model(self.db, 1, model, training_set=[])
        save_model(self.db, 2, model, training_set=[])
        self.assertEqual(self._count(1), KEEP_PER_USER)
        self.assertEqual(self._count(2), 1)
        self.assertEqual(get_active_model_info(self.db, 1)["model_id"], last_id)

    def test_deactivate_means_no_model(self):
        model, _ = _fit(0)
        save_model(self.db, 1, model, training_set=[])
        deactivate_models(self.db, 1)
        self.assertIsNone(get_active_model_info(self.db, 1))
        with self.assertRaises(LookupError):
            load_active_model(self.db, 1)
        self.assertEqual(self._count(1), 1)  # kept, just inactive

    def test_missing_table_reads_as_no_model(self):
        conn = sqlite3.connect(self.db)
        conn.execute("DROP TABLE models")
        conn.commit()
        conn.close()
        self.assertIsNone(get_active_model_info(self.db, 1))
        self.assertIsNone(get_active_model_info(self.db, None))


class TestSafety(ModelStoreTestCase):
    def test_tampered_artifact_is_refused(self):
        model, _ = _fit(0)
        model_id = save_model(self.db, 1, model, training_set=[])
        conn = sqlite3.connect(self.db)
        blob = conn.execute("SELECT artifact FROM models WHERE model_id = ?",
                            (model_id,)).fetchone()[0]
        conn.execute("UPDATE models SET artifact = ? WHERE model_id = ?",
                     (blob[:-1] + bytes([blob[-1] ^ 1]), model_id))
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(ModelLoadError, "checksum"):
            load_active_model(self.db, 1)

    def test_untrusted_types_are_refused(self):
        # A pipeline smuggling a callable (os.system) must never be loaded.
        evil = Pipeline([("f", FunctionTransformer(func=os.system))])
        blob = sio.dumps(evil, compression=zipfile.ZIP_DEFLATED)
        with self.assertRaisesRegex(ModelLoadError, "untrusted types"):
            deserialize(blob)

    def test_trained_pipeline_needs_only_allow_listed_types(self):
        model, X = _fit(0)
        np.testing.assert_allclose(deserialize(serialize(model)).predict(X),
                                   model.predict(X))

    def test_stale_feature_schema_requires_retrain(self):
        model, _ = _fit(0)
        model_id = save_model(self.db, 1, model, training_set=[])
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE models SET feature_schema_version = 0 WHERE model_id = ?",
                     (model_id,))
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(ModelLoadError, "retrain"):
            load_active_model(self.db, 1)


if __name__ == "__main__":
    unittest.main()
