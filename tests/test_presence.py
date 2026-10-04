"""Presence roster: an agent's declared voice/character, a default that never overrides."""

import copy
import json

import pytest

from awavatar import apply_presence, presence, presence_for, validate_presence_roster
from awavatar.cli import main


def _roster():
    return presence.example_presence_roster()


def test_example_roster_validates():
    assert validate_presence_roster(_roster()) == []


def test_self_test_passes():
    assert presence.self_test() == 0


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(schema_version=2),
    lambda d: d.pop("schema_version"),
    lambda d: d.update(agents="atlas"),
    lambda d: d.update(presence=["atlas"]),
    lambda d: d["presence"]["atlas"].update(voise="nova"),
    lambda d: d["presence"]["atlas"].update(voice="has space"),
    lambda d: d["presence"]["atlas"].update(voice="custom:X"),
    lambda d: d["presence"]["atlas"].update(character=""),
    lambda d: d["presence"]["atlas"].update(character="c" * 121),
    lambda d: d["presence"].update(ghost={"voice": "nova"}),
    lambda d: d["presence"].update(atlas="en-US-AvaNeural"),
])
def test_bad_rosters_are_refused(mutate):
    d = copy.deepcopy(_roster())
    mutate(d)
    assert validate_presence_roster(d)


def test_presence_for_is_case_insensitive_and_never_raises():
    assert presence_for(_roster(), "ATLAS") == {
        "voice": "en-US-MichelleNeural", "character": "charlie"}
    assert presence_for(_roster(), "saga") == {}
    assert presence_for(None, "atlas") == {}
    assert presence_for(_roster(), None) == {}


def test_apply_presence_fills_only_a_missing_voice():
    spec = {"persona_id": "hydra"}
    out = apply_presence(spec, _roster())
    assert out["voice"] == "en-US-AvaNeural"
    assert spec == {"persona_id": "hydra"}  # input untouched
    own = apply_presence({"persona_id": "hydra", "voice": "af_heart"}, _roster())
    assert own["voice"] == "af_heart"
    assert "voice" not in apply_presence({"persona_id": "saga"}, _roster())
    assert "voice" not in apply_presence({"name": "no persona"}, _roster())


def test_cli_apply_presence_defaults_a_character_spec_voice(tmp_path, capsys):
    from awavatar import schemas

    spec = schemas.example_character_spec()
    spec.pop("voice", None)
    spec["persona_id"] = "atlas"
    sp = tmp_path / "spec.json"
    rp = tmp_path / "roster.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    rp.write_text(json.dumps(_roster()), encoding="utf-8")
    assert main(["apply-presence", str(sp), "--roster", str(rp)]) == 0
    merged = json.loads(capsys.readouterr().out)
    assert merged["voice"] == "en-US-MichelleNeural"
    assert main(["validate-presence", str(rp)]) == 0


def test_cli_refuses_a_bad_roster(tmp_path):
    bad = _roster()
    bad["presence"]["atlas"]["voice"] = "has space"
    rp = tmp_path / "roster.json"
    rp.write_text(json.dumps(bad), encoding="utf-8")
    assert main(["validate-presence", str(rp)]) == 1
    sp = tmp_path / "spec.json"
    sp.write_text(json.dumps({"persona_id": "atlas"}), encoding="utf-8")
    assert main(["apply-presence", str(sp), "--roster", str(rp)]) == 1
