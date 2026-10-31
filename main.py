# Thin root entrypoint so the repo can be run with `python main.py`.
import argparse
import os

from app.main import run

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080


def parse_runtime_config(
    argv: list[str] | None = None, environ: dict[str, str] | None = None
) -> tuple[str, int]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args([] if argv is None else argv)

    runtime_environ = os.environ if environ is None else environ
    host = args.host or runtime_environ.get("HOST") or DEFAULT_HOST
    port_text = runtime_environ.get("PORT", str(DEFAULT_PORT))
    port = args.port if args.port is not None else int(port_text)
    return host, port


if __name__ == "__main__":
    host, port = parse_runtime_config()
    run(host=host, port=port)
