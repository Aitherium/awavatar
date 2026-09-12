"""awavatar CLI — validate a spec, validate a pack, submit a spec to a media-forge-shaped server.

    awavatar validate-spec <character_spec.json>
    awavatar validate-world <world_spec.yaml|json>
    awavatar validate-pack <pack_dir>
    awavatar submit <character_spec.json> --server http://127.0.0.1:8200 [--wait]

Exit 0 valid | 1 invalid | 2 could not judge (unreadable file, unreachable server).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

from .schemas import validate_character_spec, validate_world_spec


def _load(path: str):
    p = pathlib.Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        raise SystemExit(f"DEAD: {path}: {e}") from e
    if p.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # optional; only needed for YAML documents
        except ImportError as e:  # pragma: no cover - environment dependent
            raise SystemExit(
                "DEAD: PyYAML is required to read YAML specs (pip install pyyaml)"
            ) from e
        return yaml.safe_load(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise SystemExit(f"DEAD: {path}: not JSON ({e})") from e


def _report(problems: list[str], what: str) -> int:
    if problems:
        print(f"{what}: {len(problems)} problem(s)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"{what}: ok")
    return 0


def cmd_validate_spec(a) -> int:
    return _report(validate_character_spec(_load(a.path)), "character_spec")


def cmd_validate_world(a) -> int:
    return _report(validate_world_spec(_load(a.path)), "world_spec")


def cmd_validate_pack(a) -> int:
    """Delegates to the gate that owns the pack rules (CPK001-CPK008)."""
    here = pathlib.Path(__file__).resolve()
    candidates = [
        here.parents[3]
        / "dev"
        / "tools"
        / "check_character_pack.py",  # AitherOS/dev/tools from AitherOS/packages/awavatar/awavatar
        here.parent / "pack.py",  # vendored copy (planned)
    ]
    for c in candidates:
        if c.is_file():
            return subprocess.call([sys.executable, str(c), a.path])
    print("DEAD: no pack validator found (check_character_pack.py or vendored awavatar/pack.py)")
    return 2


def cmd_submit(a) -> int:
    doc = _load(a.path)
    problems = validate_character_spec(doc)
    if problems:
        return _report(problems, "character_spec")
    body = json.dumps({"spec": doc}).encode("utf-8")
    url = a.server.rstrip("/") + "/api/studio/character_pack_async"
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"DEAD: {url}: {e}")
        return 2
    print(json.dumps(res))
    return 0 if res.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="awavatar", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("validate-spec")
    s.add_argument("path")
    s.set_defaults(fn=cmd_validate_spec)
    s = sub.add_parser("validate-world")
    s.add_argument("path")
    s.set_defaults(fn=cmd_validate_world)
    s = sub.add_parser("validate-pack")
    s.add_argument("path")
    s.set_defaults(fn=cmd_validate_pack)
    s = sub.add_parser("submit")
    s.add_argument("path")
    s.add_argument("--server", default="http://127.0.0.1:8200")
    s.set_defaults(fn=cmd_submit)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
