import argparse
import json
import logging
import sys
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
        action="append",
        metavar="ARM=SHARE",
        help="a folder as ARM's container mounts it and as its path on the "
        "share, e.g. /root/video=import/automatic-ripping-machine; again for "
        "each folder ARM's older jobs recorded paths in",
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

    analyse_command = commands.add_parser(
        "analyse",
        help="measure the files a manifest's job holds, and print them as JSON",
    )
    analyse_command.add_argument("manifest", type=Path)

    plan_command = commands.add_parser(
        "plan",
        help="plan and gate manifests, printing each plan; records and changes nothing",
    )
    plan_command.add_argument(
        "path",
        type=Path,
        nargs="?",
        help="a manifest, or a folder of them (default: REELBARROW_MANIFEST_DIR)",
    )
    plan_command.add_argument("--json", action="store_true", help="each plan as JSON")

    file_command = commands.add_parser(
        "file",
        help="plan manifests as `plan` does, and carry out each automatic plan; "
        "in dry run every change is refused and reported",
    )
    file_command.add_argument(
        "path",
        type=Path,
        nargs="?",
        help="a manifest, or a folder of them (default: REELBARROW_MANIFEST_DIR)",
    )
    file_command.add_argument(
        "--json", action="store_true", help="each plan and its report as JSON"
    )

    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        from reelbarrow.web import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port)
    elif args.command == "arm-export-manifests":
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        from reelbarrow.config import Settings
        from reelbarrow.exporter import ArmPaths, Exporter

        settings = Settings()
        try:
            root = ArmPaths.parse(args.arm_path)
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
    elif args.command == "analyse":
        raise SystemExit(_analyse(args.manifest))
    elif args.command == "plan":
        raise SystemExit(_plan(args.path, args.json))
    elif args.command == "file":
        raise SystemExit(_file(args.path, args.json))


def _analyse(path: Path) -> int:
    from reelbarrow import intake
    from reelbarrow.analyse import analyse
    from reelbarrow.config import Settings

    settings = Settings()
    job = intake.read(path)
    index = intake.RawIndex(settings.video_root, settings.arm_raw)
    document = analyse(job, settings.video_root, index)
    print(json.dumps(document.to_json(), indent=2, ensure_ascii=False))
    return 0


def _missing(*names: str) -> int:
    for name in names:
        print(f"reelbarrow: {name} is not set", file=sys.stderr)
    return 2


def _planned(settings, tmdb, path: Path | None, as_json: bool):
    """Each manifest's plan, as (manifest, plan); None for one that couldn't
    be planned, which is reported here."""
    from pydantic import ValidationError

    from reelbarrow import intake, plan
    from reelbarrow.analyse import analyse
    from reelbarrow.manifest import State
    from reelbarrow.tmdb import TmdbError

    index = intake.RawIndex(settings.video_root, settings.arm_raw)
    library = plan.ShareLibrary(settings.video_root, settings.movies)
    for manifest_path in intake.manifest_paths(path or settings.manifest_dir):
        try:
            job = intake.read(manifest_path)
        except (OSError, ValidationError) as error:
            print(f"{manifest_path.name}: unreadable: {error}", file=sys.stderr)
            yield None
            continue
        if job.state is State.RUNNING:
            if not as_json:
                print(f"{job.source} {job.id}: running, not planned yet\n")
            continue
        try:
            analysis = analyse(job, settings.video_root, index)
            made = plan.plan(job, analysis, tmdb, library, movies=settings.movies)
        except TmdbError as error:
            print(f"{job.source} {job.id}: {error}", file=sys.stderr)
            yield None
            continue
        yield job, made


def _plan(path: Path | None, as_json: bool) -> int:
    from reelbarrow import plan
    from reelbarrow.config import Settings
    from reelbarrow.tmdb import Client

    settings = Settings()
    if settings.tmdb_token is None:
        return _missing("REELBARROW_TMDB_TOKEN")
    tmdb = Client(settings.tmdb_token.get_secret_value())
    failed = False
    plans = []
    for planned in _planned(settings, tmdb, path, as_json):
        if planned is None:
            failed = True
            continue
        _, made = planned
        if as_json:
            plans.append(made.to_json())
        else:
            print(plan.render(made) + "\n")
    if as_json:
        print(json.dumps(plans, indent=2, ensure_ascii=False))
    return 1 if failed else 0


def _file(path: Path | None, as_json: bool) -> int:
    from reelbarrow import executor, fanart, plan, sidecars
    from reelbarrow.config import Settings
    from reelbarrow.ledger import Ledger
    from reelbarrow.plex import Plex
    from reelbarrow.tmdb import Client

    settings = Settings()
    missing = [
        name
        for name, value in [
            ("REELBARROW_TMDB_TOKEN", settings.tmdb_token),
            ("REELBARROW_FANART_KEY", settings.fanart_key),
        ]
        if value is None
    ]
    # Only a live run scans, and a filing Plex never sees would go unnoticed.
    if not settings.dry_run:
        missing += [
            name
            for name, value in [
                ("REELBARROW_PLEX_URL", settings.plex_url),
                ("REELBARROW_PLEX_TOKEN", settings.plex_token),
                ("REELBARROW_PLEX_PATHS", settings.plex_paths),
            ]
            if not value
        ]
    if missing:
        return _missing(*missing)
    assert settings.tmdb_token is not None and settings.fanart_key is not None
    tmdb = Client(settings.tmdb_token.get_secret_value())
    plex = None
    if settings.plex_url is not None and settings.plex_token is not None:
        plex = Plex(
            str(settings.plex_url),
            settings.plex_token.get_secret_value(),
            settings.plex_paths,
        )
    carrying_out = executor.Executor(
        writer=executor.Writer(settings.video_root, dry_run=settings.dry_run),
        ledger=Ledger(settings.data_dir),
        sources=sidecars.Sources(
            tmdb=tmdb,
            fanart=fanart.Client(settings.fanart_key.get_secret_value()),
            images=sidecars.HttpImages(),
        ),
        libraries=[settings.movies],
        plex=plex,
    )
    if not as_json:
        print(
            "Dry run: every change is refused.\n"
            if settings.dry_run
            else "Filing is live.\n"
        )
    failed = False
    documents = []
    for planned in _planned(settings, tmdb, path, as_json):
        if planned is None:
            failed = True
            continue
        job, made = planned
        report = None
        if made.gate is plan.Gate.AUTOMATIC:
            report = carrying_out.carry_out(made, job)
            failed = failed or not report.succeeded
        if as_json:
            documents.append(
                {
                    "plan": made.to_json(),
                    "report": report.to_json() if report is not None else None,
                }
            )
        elif report is None:
            print(plan.render(made))
            print(f"  left for {made.gate}\n")
        else:
            print(executor.render_report(report) + "\n")
    if as_json:
        print(json.dumps(documents, indent=2, ensure_ascii=False))
    return 1 if failed else 0
