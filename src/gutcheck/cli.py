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

    import uvicorn

    from gutcheck.app import create_app

    uvicorn.run(
        create_app(settings), host=settings.host, port=settings.port, log_level=settings.log_level
    )
    return 0
