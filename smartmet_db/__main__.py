"""Database commands: python -m smartmet_db --help"""

import argparse
import json
import sys

from sqlalchemy.exc import OperationalError

from . import db
from .store import InvalidReading, batch_summaries, store_readings


def cmd_setup(args):
    result = db.setup_databases()
    for item in result["created"] or ["nothing new; role and databases already exist"]:
        print(f"created: {item}" if result["created"] else item)
    for test in (False, True):
        engine = db.get_engine(test)
        db.init_tables(engine)
        engine.dispose()
    print("tables ready in smartmet4qc and smartmet4qc_test")
    print("connection settings saved to .env")


def cmd_init(args):
    db.init_tables(db.get_engine())
    print("tables ready")


def _sessionmaker():
    engine = db.get_engine()
    db.init_tables(engine)  # adds tables introduced by newer phases, e.g. alerts
    return db.get_sessionmaker(engine)


def cmd_import(args):
    from smartmet_qc.service import rebuild_batch_alerts

    Session = _sessionmaker()
    for path in args.files:
        with open(path, encoding="utf-8") as f:
            readings = [json.loads(line) for line in f if line.strip()]
        try:
            with Session.begin() as session:
                inserted, duplicates = store_readings(session, readings)
                codes = sorted({str(r["batch_id"]) for r in readings})
                alerts = sum(rebuild_batch_alerts(session, code) for code in codes)
        except InvalidReading as exc:
            sys.exit(f"{path}: invalid reading, nothing imported: {exc}")
        print(f"{path}: {inserted} readings imported, {duplicates} already in the database, "
              f"{alerts} alerts for {', '.join(codes)}")


def cmd_alerts(args):
    from smartmet_qc.service import list_alerts, rebuild_batch_alerts

    Session = _sessionmaker()
    if args.rebuild:
        with Session.begin() as session:
            codes = [args.batch] if args.batch else [r["code"] for r in batch_summaries(session)]
            for code in codes:
                print(f"{code}: {rebuild_batch_alerts(session, code)} alerts rebuilt")
    with Session() as session:
        rows = list_alerts(session, None if args.all else "open", args.batch)
    if not rows:
        print("no alerts" if args.all else "no open alerts")
    for alert, code in rows:
        print(f"{code:<12} {alert.severity:<8} {alert.status:<8} {alert.opened_at:%Y-%m-%d %H:%M}  "
              f"{alert.rule:<20} {alert.message}")


def cmd_summary(args):
    Session = _sessionmaker()
    with Session() as session:
        rows = batch_summaries(session)
    if not rows:
        print("no batches yet")
        return
    print(f"{'batch':<15} {'status':<9} {'readings':>8}  first reading               last reading")
    for r in rows:
        print(f"{r['code']:<15} {r['status']:<9} {r['readings']:>8}  {r['first']!s:<26}  {r['last']}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m smartmet_db", description="SmartMet4QC database tools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="create the smartmet role, databases and tables; write .env")
    sub.add_parser("init", help="create any missing tables")
    imp = sub.add_parser("import", help="import simulator .jsonl files")
    imp.add_argument("files", nargs="+")

    try:
        commands[args.command](args)
    except OperationalError as exc:
        sys.exit(f"cannot connect to PostgreSQL. Is the service running?\n{exc.orig}")
    except RuntimeError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
