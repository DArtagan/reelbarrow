import argparse
import logging
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="reelbarrow")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="run the web UI")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)

    export = commands.add_parser(
        "export-manifests",
        help="copy ARM's database out as job manifests, on an interval",
    )
    export.add_argument("--db", type=Path, required=True, help="ARM's arm.db")
    # Required, as no default is right everywhere and a wrong one makes
    # plausible paths and times rather than failing.
    export.add_argument(
        "--arm-root",
        required=True,
        metavar="CONTAINER=SHARE",
        help="where ARM's container sees its slice of the share, and that slice's "
        "path from the share's root, e.g. /root/video=import/automatic-ripping-machine",
    )
    export.add_argument(
        "--arm-timezone",
        required=True,
        help="the IANA time zone ARM's container runs in, e.g. Etc/UTC",
    )
    export.add_argument(
        "--out",
        type=Path,
        help="the manifest directory (default: REELBARROW_MANIFEST_DIR)",
    )
    export.add_argument(
        "--interval", type=float, default=30.0, help="seconds between passes"
    )
    export.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="seconds a pass waits on ARM's write lock before trying next time",
    )
    export.add_argument("--once", action="store_true", help="one pass, then exit")

    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        from reelbarrow.web import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port)
    elif args.command == "export-manifests":
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        from reelbarrow.config import Settings
        from reelbarrow.exporter import ArmRoot, Exporter

        try:
            root = ArmRoot.parse(args.arm_root)
            zone = ZoneInfo(args.arm_timezone)
        except (ValueError, ZoneInfoNotFoundError) as error:
            parser.error(str(error))
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
        )
        out = args.out or Settings().manifest_dir
        exporter = Exporter(
            db=args.db, out=out, root=root, zone=zone, timeout=args.timeout
        )
        if args.once:
            raise SystemExit(0 if exporter.run_pass() else 1)
        exporter.run(args.interval)
