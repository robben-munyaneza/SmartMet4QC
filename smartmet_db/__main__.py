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
        db.migrate(engine)
        engine.dispose()
    print("tables up to date in smartmet4qc and smartmet4qc_test")
    print("connection settings saved to .env")


def cmd_migrate(args):
    db.migrate(db.get_engine())
    print("database schema is up to date")


def _sessionmaker():
    engine = db.get_engine()
    db.migrate(engine)  # applies changes introduced by newer phases
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


def cmd_device(args):
    from . import devices

    Session = _sessionmaker()
    try:
        with Session.begin() as session:
            if args.action == "add":
                key = devices.add_device(session, args.name)
                _print_key(args.name, key)
            elif args.action == "rotate-key":
                key = devices.rotate_key(session, args.name)
                _print_key(args.name, key, "The old key no longer works.")
            elif args.action == "revoke":
                devices.revoke_key(session, args.name)
                print(f"{args.name}: key revoked; the device can no longer send readings")
            elif args.action == "assign":
                devices.assign_batch(session, args.name, None if args.batch == "none" else args.batch)
                print(f"{args.name} now measures batch {args.batch}")
            else:
                rows = devices.list_devices(session)
                if not rows:
                    print("no devices yet: python -m smartmet_db device add NAME")
                for d in rows:
                    state = "revoked" if d.api_key_hash is None else "active"
                    seen = f"{d.last_seen_at:%Y-%m-%d %H:%M}" if d.last_seen_at else "never"
                    print(f"{d.name:<15} {state:<8} batch {d.batch.code if d.batch else '-':<12} last seen {seen}")
    except ValueError as exc:
        sys.exit(f"error: {exc}")


def _print_key(name, key, extra=""):
    print(f"Device {name!r}. Its API key (shown only this once; put it in the device's config.h):\n")
    print(f"    {key}\n")
    if extra:
        print(extra)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m smartmet_db", description="SmartMet4QC database tools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="create the smartmet role and databases, bring tables up to date, write .env")
    sub.add_parser("migrate", help="bring the database schema up to date")
    sub.add_parser("init", help="same as migrate (kept for older instructions)")
    imp = sub.add_parser("import", help="import simulator .jsonl files")
    imp.add_argument("files", nargs="+")
    sub.add_parser("summary", help="list batches and reading counts")
    al = sub.add_parser("alerts", help="list open alerts (or all with --all)")
    al.add_argument("batch", nargs="?", help="only this batch code")
    al.add_argument("--all", action="store_true", help="include resolved alerts")
    al.add_argument("--rebuild", action="store_true", help="recompute alerts from the stored readings first")

    dev = sub.add_parser("device", help="manage measuring devices (ESP32) and their API keys")
    dev_sub = dev.add_subparsers(dest="action", required=True)
    dev_sub.add_parser("list", help="list devices")
    for action, text in (("add", "add a device and print its API key"),
                         ("rotate-key", "give a device a new API key"),
                         ("revoke", "stop a device from sending readings")):
        dev_sub.add_parser(action, help=text).add_argument("name")
    assign = dev_sub.add_parser("assign", help="choose the batch a device measures ('none' to unassign)")
    assign.add_argument("name")
    assign.add_argument("batch")
    args = parser.parse_args(argv)

    commands = {"setup": cmd_setup, "migrate": cmd_migrate, "init": cmd_migrate, "import": cmd_import,
                "summary": cmd_summary, "alerts": cmd_alerts, "device": cmd_device}
    try:
        commands[args.command](args)
    except OperationalError as exc:
        sys.exit(f"cannot connect to PostgreSQL. Is the service running?\n{exc.orig}")
    except RuntimeError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
