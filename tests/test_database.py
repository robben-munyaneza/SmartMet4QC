"""Database tests. They use the separate smartmet4qc_test database and are
skipped if the database libraries or PostgreSQL are not available."""

import unittest

try:
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError, OperationalError

    from smartmet_db import db
    from smartmet_db.models import Base
    from smartmet_db.store import InvalidReading, batch_readings, batch_summaries, store_readings
except ImportError as exc:
    raise unittest.SkipTest(f"database libraries not installed: {exc}")

from smartmet_sim import Simulator


def setUpModule():
    global engine, Session
    try:
        engine = db.get_engine(test=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except (RuntimeError, OperationalError) as exc:
        raise unittest.SkipTest(f"test database not available: {exc}")
    Session = db.get_sessionmaker(engine)


def tearDownModule():
    engine.dispose()


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def store(self, readings):
        with Session.begin() as session:
            return store_readings(session, readings)

    def test_stores_full_simulated_batch(self):
        readings = list(Simulator(batch_id="BATCH-T1", seed=1).readings())
        self.assertEqual(self.store(readings), (121, 0))
        with Session() as session:
            [summary] = batch_summaries(session)
            stored = batch_readings(session, "BATCH-T1")
        self.assertEqual(summary["code"], "BATCH-T1")
        self.assertEqual(summary["readings"], 121)
        self.assertEqual(stored[0].brix, readings[0]["measurements"]["brix"])
        self.assertEqual(stored[-1].simulation["scenario"], "normal")

    def test_importing_twice_creates_no_duplicates(self):
        readings = list(Simulator(seed=2).readings(10))
        self.store(readings)
        self.assertEqual(self.store(readings), (0, 10))

    def test_dropout_is_stored_as_null(self):
        reading = next(Simulator(seed=3).readings())
        reading["measurements"]["ph"] = None
        self.store([reading])
        with Session() as session:
            [stored] = batch_readings(session, "BATCH-001")
        self.assertIsNone(stored.ph)

    def test_manual_reading_with_only_some_measurements(self):
        self.store([{
            "timestamp": "2026-10-09T08:00:00+02:00",
            "batch_id": "BATCH-M1",
            "source": "manual",
            "measurements": {"brix": 18.5},
        }])
        with Session() as session:
            [stored] = batch_readings(session, "BATCH-M1")
        self.assertEqual(stored.brix, 18.5)
        self.assertIsNone(stored.temperature_c)

    def test_invalid_readings_are_rejected(self):
        good = next(Simulator(seed=4).readings())
        cases = [
            {k: v for k, v in good.items() if k != "timestamp"},
            {**good, "source": "phone"},
            {**good, "timestamp": "2026-10-09T08:00:00"},
            {**good, "measurements": {"sugar": 3}},
            {**good, "measurements": {"ph": "low"}},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(InvalidReading):
                self.store([case])

    def test_database_rejects_impossible_values(self):
        reading = next(Simulator(seed=5).readings())
        reading["measurements"]["ph"] = 20
        with self.assertRaises(IntegrityError):
            self.store([reading])


if __name__ == "__main__":
    unittest.main()
