import argparse
import sys

from pydantic import ValidationError

from gutcheck import __version__
from gutcheck.config import Settings, load_settings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gutcheck", description="Open-source decision gateway")
    parser.add_argument("--version", action="version", version=f"gutcheck {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the HTTP gateway")
    serve.add_argument("--config", help="path to a YAML config file")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument("--log-level", dest="log_level")

    show = sub.add_parser("config", help="print the resolved configuration as JSON")
    show.add_argument("--config", help="path to a YAML config file")

    packs = sub.add_parser("packs", help="list installed question packs")
    packs.add_argument("--config", help="path to a YAML config file")

    ev = sub.add_parser("eval", help="evaluate question packs against their datasets")
    ev.add_argument("packs", nargs="*", metavar="PACK", help="pack ids (default: all)")
    ev.add_argument("--config", help="path to a YAML config file")
    ev.add_argument(
        "--calibrate", action="store_true", help="refit temperatures on the calibration split"
    )
    ev.add_argument(
        "--write",
        action="store_true",
        help="write eval.json, EVAL.md (and calibration.json) into each pack directory",
    )
    ev.add_argument(
        "--check", action="store_true", help="exit 1 if results fall below the committed baseline"
    )
    ev.add_argument("--summary", help="write a Markdown summary of the run to this file")
    ev.add_argument("--cache-dir", help="where downloaded datasets are kept")

    cal = sub.add_parser("calibrate", help="refit temperatures from feedback in the decision log")
    cal.add_argument("--config", help="path to a YAML config file")
    cal.add_argument("--min-samples", type=int, help="labels a question needs before refitting")
    return parser


def _load(args: argparse.Namespace) -> Settings:
    keys = ("host", "port", "log_level")
    overrides = {k: getattr(args, k) for k in keys if getattr(args, k, None) is not None}
    return load_settings(args.config, **overrides)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        settings = _load(args)
    except (FileNotFoundError, ValidationError) as e:
        print(f"gutcheck: invalid configuration: {e}", file=sys.stderr)
        return 2

    if args.command == "config":
        print(settings.model_dump_json(indent=2))
        return 0
    if args.command == "packs":
        return _list_packs(settings)
    if args.command == "eval":
        return _eval(settings, args)
    if args.command == "calibrate":
        return _calibrate(settings, args)

    import uvicorn

    from gutcheck.app import create_app

    uvicorn.run(
        create_app(settings), host=settings.host, port=settings.port, log_level=settings.log_level
    )
    return 0


def _list_packs(settings: Settings) -> int:
    from gutcheck.packs import PackError, load_packs

    try:
        packs = load_packs(settings.packs.dirs)
    except PackError as e:
        print(f"gutcheck: {e}", file=sys.stderr)
        return 2
    for pack in packs.values():
        status = "calibrated" if pack.temperatures else "uncalibrated"
        print(f"{pack.id}@{pack.version} ({status}): {pack.description}")
        for qid, q in pack.questions.items():
            print(f"  {pack.id}.{qid} [{q.type}] {q.instructions}")
    return 0


def _eval(settings: Settings, args: argparse.Namespace) -> int:
    from pathlib import Path

    from gutcheck import evals
    from gutcheck.engine import LayaEngine
    from gutcheck.packs import PackError, load_packs, resolve

    try:
        installed = load_packs(settings.packs.dirs)
        selected = [resolve(installed, ref) for ref in args.packs] or list(installed.values())
    except PackError as e:
        print(f"gutcheck: {e}", file=sys.stderr)
        return 2
    cache_dir = Path(args.cache_dir) if args.cache_dir else evals.DEFAULT_CACHE

    engine = LayaEngine(settings.engine)
    engine.start()
    failed = False
    summary = []
    try:
        for pack in selected:
            # a pack that was never calibrated gets its temperatures fitted on first evaluation
            calibrate = args.calibrate or not pack.temperatures
            report = evals.evaluate_pack(
                engine,
                pack,
                settings.policy,
                calibrate=calibrate,
                cache_dir=cache_dir,
                log=lambda m: print(m, file=sys.stderr),
            )
            problems = evals.check(report, pack.baseline) if args.check else []
            failed = failed or bool(problems)
            for p in problems:
                print(f"gutcheck: {pack.id}: {p}", file=sys.stderr)
            if args.write:
                evals.write_outputs(report, pack, calibrate)
            print(evals.render_markdown(report, pack))
            summary.append(evals.render_summary(report, pack, problems, calibrate))
    finally:
        engine.close()
    if args.summary:
        Path(args.summary).write_text("\n".join(summary))
    return 1 if failed else 0


def _calibrate(settings: Settings, args: argparse.Namespace) -> int:
    from gutcheck.feedback import recalibrate
    from gutcheck.store import DecisionStore

    if not settings.store.path:
        print("gutcheck: the decision log is disabled (store.path is null)", file=sys.stderr)
        return 2
    min_samples = args.min_samples or settings.calibration.min_samples
    store = DecisionStore(settings.store.path, settings.store.save_state)
    try:
        refits = recalibrate(store, min_samples)
        described = store.questions()
    finally:
        store.close()
    if not refits:
        print("No labelled answers yet. Send some with POST /v1/feedback.")
        return 0
    for key, r in refits.items():
        name = described.get(key, {}).get("question_id") or key
        if r.temperature is None:
            print(f"{name}: {r.n} labels, needs {min_samples}; unchanged")
        else:
            print(
                f"{name}: {r.n} labels, accuracy {r.accuracy:.3f}, temperature {r.temperature}, "
                f"ECE {r.ece_before:.3f} -> {r.ece_after:.3f}"
            )
    print("A running server applies new temperatures after a restart or POST /v1/calibrate.")
    return 0
