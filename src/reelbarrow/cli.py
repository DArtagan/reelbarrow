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
        "arm-export-manifests",
        help="copy ARM's jobs out of its database as manifests, on an interval",
    )
    export.add_argument("--db", type=Path, required=True, help="ARM's arm.db")
    # Required, as no default is right everywhere and a wrong one makes
    # plausible paths rather than failing.
    export.add_argument(
        "--arm-path",
        required=True,
        metavar="ARM=REELBARROW",
        help="one folder as ARM's container and reelbarrow each mount it, e.g. "
        "/root/video=/video/import/automatic-ripping-machine",
    )
    export.add_argument(
        "--arm-timezone",
        default="Etc/UTC",
        help="the IANA time zone ARM's container runs in (default: Etc/UTC, "
        "ARM's image's)",
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
    elif args.command == "arm-export-manifests":
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        from reelbarrow.config import Settings
        from reelbarrow.exporter import ArmPath, Exporter

        settings = Settings()
        try:
            root = ArmPath.parse(args.arm_path, settings.video_root)
            zone = ZoneInfo(args.arm_timezone)
        except (ValueError, ZoneInfoNotFoundError) as error:
            parser.error(str(error))
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
        )
        out = args.out or settings.manifest_dir
        exporter = Exporter(
            db=args.db, out=out, root=root, zone=zone, timeout=args.timeout
        )
        if args.once:
            raise SystemExit(0 if exporter.run_pass() else 1)
        exporter.run(args.interval)
