"""Presence roster — each agent's DECLARED speaking voice and desk character. Pure stdlib.

    python -m awavatar.presence --self-test

A presence roster is the document a desk reads to give every agent its own voice and body
before anyone has configured them by hand:

    {
      "schema_version": 1,
      "agents": ["atlas", "hydra", ...],
      "presence": {
        "atlas": {"voice": "en-US-MichelleNeural", "character": "charlie"},
        "hydra": {"voice": "en-US-AvaNeural"}
      }
    }

``agents`` is the flat id list; ``presence`` is optional per agent and carries only
``voice`` (the same rule as ``character_spec.voice``: a stock engine voice id or
``custom:<name>``) and ``character`` (the name of the body the desk loads). It is a
DEFAULT, never an override: whatever a person authored for that agent on their own desk
wins, and a ``character_spec`` that already names a ``voice`` keeps it
(:func:`apply_presence`).
"""

from __future__ import annotations

import copy
import sys

from .schemas import PERSONA_ID_MAX, PERSONA_ID_RE, _version, _voice_problems

PRESENCE_FIELDS = ("voice", "character")
CHARACTER_MAX = 120


def validate_presence_roster(doc) -> list[str]:
    """Structural problems with a presence roster (empty = valid)."""
    w = "presence_roster"
    out: list[str] = []
    if not _version(doc, 1, w, out):
        return out
    agents = doc.get("agents")
    if not isinstance(agents, list) or not all(isinstance(a, str) and a for a in agents):
        out.append(f"{w}: agents must be a list of non-empty strings")
        agents = []
    presence = doc.get("presence", {})
    if not isinstance(presence, dict):
        out.append(f"{w}: presence must be an object")
        return out
    for agent_id, entry in presence.items():
        where = f"{w}: presence[{agent_id!r}]"
        if (
            not isinstance(agent_id, str)
            or not PERSONA_ID_RE.match(agent_id)
            or len(agent_id) > PERSONA_ID_MAX
        ):
            out.append(f"{where}: agent id must match ^[A-Za-z0-9][A-Za-z0-9._-]*$")
        if agents and agent_id not in agents:
            out.append(f"{where}: not in agents (a presence for nobody)")
        if not isinstance(entry, dict):
            out.append(f"{where}: must be an object of voice/character")
            continue
        for key in entry:
            if key not in PRESENCE_FIELDS:
                out.append(f"{where}: unknown key {key!r} (voice, character)")
        if "voice" in entry:
            out.extend(_voice_problems(entry["voice"], where))
        if "character" in entry:
            ch = entry["character"]
            if not isinstance(ch, str) or not ch.strip() or len(ch) > CHARACTER_MAX:
                out.append(f"{where}: character must be a 1..{CHARACTER_MAX} char string")
    return out


def presence_for(doc, persona_id) -> dict:
    """The declared {voice?, character?} for one agent id (case-insensitive), or {}.

    Never raises: a malformed roster or an unknown id is simply "nothing declared"."""
    if not isinstance(doc, dict) or not isinstance(persona_id, str):
        return {}
    presence = doc.get("presence")
    if not isinstance(presence, dict):
        return {}
    want = persona_id.strip().lower()
    for agent_id, entry in presence.items():
        if isinstance(agent_id, str) and agent_id.lower() == want and isinstance(entry, dict):
            return {k: entry[k] for k in PRESENCE_FIELDS if isinstance(entry.get(k), str)}
    return {}


def apply_presence(spec, roster) -> dict:
    """A copy of ``spec`` (a character_spec) with ``voice`` defaulted from the roster.

    The spec's own ``voice`` always wins; the roster only fills a gap, and only for a
    spec whose ``persona_id`` names a roster agent. The input is never mutated."""
    out = copy.deepcopy(spec) if isinstance(spec, dict) else {}
    if "voice" in out:
        return out
    declared = presence_for(roster, out.get("persona_id"))
    voice = declared.get("voice")
    if voice and not _voice_problems(voice, "presence"):
        out["voice"] = voice
    return out


def example_presence_roster() -> dict:
    return {
        "schema_version": 1,
        "agents": ["atlas", "hydra", "saga"],
        "presence": {
            "atlas": {"voice": "en-US-MichelleNeural", "character": "charlie"},
            "hydra": {"voice": "en-US-AvaNeural"},
        },
    }


def self_test() -> int:
    problems: list[str] = []

    def expect_bad(label: str, doc) -> None:
        if not validate_presence_roster(doc):
            problems.append(f"{label}: should be refused")

    good = example_presence_roster()
    got = validate_presence_roster(good)
    if got:
        problems.append(f"example should validate: {got}")
    bad = copy.deepcopy(good)
    bad["schema_version"] = 2
    expect_bad("unknown schema_version", bad)
    bad = copy.deepcopy(good)
    bad["presence"]["atlas"]["voise"] = "x"
    expect_bad("typo key", bad)
    bad = copy.deepcopy(good)
    bad["presence"]["atlas"]["voice"] = "has space"
    expect_bad("bad voice", bad)
    bad = copy.deepcopy(good)
    bad["presence"]["ghost"] = {"voice": "nova"}
    expect_bad("presence for an agent not in agents", bad)
    bad = copy.deepcopy(good)
    bad["presence"]["atlas"]["character"] = ""
    expect_bad("empty character", bad)

    spec = {"persona_id": "Atlas"}
    if apply_presence(spec, good).get("voice") != "en-US-MichelleNeural":
        problems.append("apply_presence should default the voice from the roster")
    if "voice" in spec:
        problems.append("apply_presence must not mutate its input")
    if apply_presence({"persona_id": "atlas", "voice": "af_heart"}, good)["voice"] != "af_heart":
        problems.append("a spec's own voice must beat the roster")
    if "voice" in apply_presence({"persona_id": "saga"}, good):
        problems.append("an agent with no declared voice must not gain one")

    if problems:
        print("SELF-TEST FAILED")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("SELF-TEST PASSED — presence roster rules each refuse a bad document")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        sys.exit(self_test())
    print(__doc__)
    sys.exit(0)
