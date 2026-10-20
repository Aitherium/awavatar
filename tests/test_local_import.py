"""publish-local: an imported body reaches only the owner's own desk, stamped local-only + private."""

import hashlib
import json
import struct

import pytest

from awavatar.cli import main
from awavatar.local_import import Refused, attestation_problems, glb_json, publish_local, vrm_problems

BONES = ("hips", "spine", "head", "leftUpperArm", "leftLowerArm", "leftHand", "rightUpperArm", "rightLowerArm",
         "rightHand", "leftUpperLeg", "leftLowerLeg", "leftFoot", "rightUpperLeg", "rightLowerLeg", "rightFoot")
OWNER = {"schema": "dm-import-attestation/1", "asset_id": "mara", "owner_name": "Owner Name", "source_kind": "cc5",
         "source_description": "CC5 base + packs", "licence_note": "Reallusion per-seat EULA", "owner_holds_licence": True,
         "depicts_real_person": False, "local_only_acknowledged": True, "date": "2026-10-19"}
STRICT = {"avatarPermission": "onlyAuthor", "allowRedistribution": False, "modification": "prohibited"}
OPEN = {"avatarPermission": "everyone", "allowRedistribution": True, "modification": "allowModificationRedistribution"}


def vrm_bytes(stamp=True, meta=None):
    doc = {"asset": {"version": "2.0"}, "nodes": [{"name": b} for b in BONES], "skins": [{"joints": list(range(len(BONES)))}],
           "extensions": {"VRMC_vrm": {"specVersion": "1.0", "meta": meta or STRICT,
                                       "humanoid": {"humanBones": {b: {"node": i} for i, b in enumerate(BONES)}}}}}
    if stamp:
        doc["asset"]["extras"] = {"dm_import": {"local_only": True, "not_for_distribution": True, "importer": "dm-import-rung/1"}}
    js = json.dumps(doc).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    return b"glTF" + struct.pack("<II", 2, 20 + len(js)) + struct.pack("<II", len(js), 0x4E4F534A) + js


def import_folder(tmp_path, att=None, dressed=True, data=None):
    d = tmp_path / "imported" / "mara"
    d.mkdir(parents=True)
    data = data or vrm_bytes()
    (d / "body.vrm").write_bytes(data)
    (d / "attestation.json").write_text(json.dumps(att if att is not None else OWNER))
    man = {"id": "mara", "label": "Mara (CC5)", "local_only": True, "not_for_distribution": True, "dressed": dressed,
           "source_kind": "cc5", "attestation_sha256": hashlib.sha256((d / "attestation.json").read_bytes()).hexdigest(),
           "files": {"body.vrm": {"sha256": hashlib.sha256(data).hexdigest()}}}
    (d / "import.json").write_text(json.dumps(man))
    roster = tmp_path / "characters"
    roster.mkdir()
    return d / "body.vrm", roster


def test_publishes_privately(tmp_path):
    vrm, roster = import_folder(tmp_path)
    r = publish_local(vrm, "mara-cc5", roster)
    assert r["ok"] and (roster / "mara-cc5" / "model.vrm").read_bytes() == vrm.read_bytes()
    cj = json.loads((roster / "mara-cc5" / "character.json").read_text())
    assert cj["local_only"] is True and cj["private"] is True and cj["distribution"] == "local-only" and cj["source"] == "import"
    assert publish_local(vrm, "mara-cc5", roster)["ok"], "re-publishing the same import is allowed"


def test_blank_attestation_is_refused(tmp_path):
    blank = {"schema": "dm-import-attestation/1", "asset_id": "mara", "owner_name": "", "owner_holds_licence": False,
             "depicts_real_person": None, "local_only_acknowledged": False}
    vrm, roster = import_folder(tmp_path, att=blank)
    with pytest.raises(Refused, match="attestation"):
        publish_local(vrm, "mara", roster)
    assert attestation_problems({**OWNER, "depicts_real_person": True}, "mara")
    assert not attestation_problems(OWNER, "mara")


@pytest.mark.parametrize("data,why", [(vrm_bytes(stamp=False), "stamp"), (vrm_bytes(meta=OPEN), "redistribution")])
def test_only_import_rung_output_publishes(tmp_path, data, why):
    vrm, roster = import_folder(tmp_path, data=data)
    with pytest.raises(Refused, match=why):
        publish_local(vrm, "mara", roster)


def test_tampered_body_and_stranger_slot_refused(tmp_path):
    vrm, roster = import_folder(tmp_path)
    (roster / "kafka").mkdir()
    (roster / "kafka" / "character.json").write_text(json.dumps({"source": "vroid"}))
    with pytest.raises(Refused, match="another character"):
        publish_local(vrm, "kafka", roster)
    vrm.write_bytes(vrm_bytes() + b"    ")
    with pytest.raises(Refused, match="sha256"):
        publish_local(vrm, "mara", roster)


def test_undressed_import_is_r18_only(tmp_path):
    vrm, roster = import_folder(tmp_path, dressed=False)
    with pytest.raises(Refused, match="r18"):
        publish_local(vrm, "mara", roster)
    assert publish_local(vrm, "mara", roster, rating="r18")["ok"]


def test_cli(tmp_path, capsys):
    vrm, roster = import_folder(tmp_path)
    assert main(["check-local", str(vrm)]) == 0
    assert main(["publish-local", str(vrm), "--id", "mara", "--roster", str(roster)]) == 0
    assert "set_character" in capsys.readouterr().out
    assert vrm_problems(glb_json(vrm_bytes(stamp=False)))
