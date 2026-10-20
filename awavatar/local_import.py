"""publish-local — put the owner's IMPORTED body on his own desk as a private awdesk avatar.

    awavatar publish-local <import_dir>/<id>/body.vrm --id mara --roster D:/desk/characters
    awavatar check-local <file.vrm>

An imported body is the owner's own licensed content (Reallusion Character Creator 5 characters,
Virt-A-Mate / DAZ looks) converted to VRM 1.0 by the Darkmatter import rung (tools/3d-import in the
game repo). None of it is licence-clean for redistribution, so this command only ever writes to the
owner's LOCAL desk roster and stamps the character so nothing downstream uploads it:

* the VRM must carry the converter's stamp: ``asset.extras.dm_import`` with ``local_only`` and
  ``not_for_distribution``, and a VRM meta that forbids redistribution (``avatarPermission:
  onlyAuthor``, ``allowRedistribution: false``, ``modification: prohibited``);
* the import folder's ``attestation.json`` must be the owner's filled attestation (or a
  licence-clean pipeline stand-in) and ``import.json`` must still match the body's bytes —
  this command never attests on the owner's behalf;
* the written ``character.json`` says ``local_only: true``, ``private: true``,
  ``distribution: "local-only"`` — awdesk's library sync and every upload path refuse it
  (``.DEPLOYMENT/awdesk/electron/local-only.cjs``), and the VRM bytes carry the same mark.

Nothing here talks to a network. stdlib only, Python 3.10.
Exit 0 published / is local-only | 1 refused | 2 could not judge (unreadable input).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
from pathlib import Path
from typing import Any

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
REQUIRED_BONES = ("hips", "spine", "head", "leftUpperArm", "leftLowerArm", "leftHand", "rightUpperArm",
                  "rightLowerArm", "rightHand", "leftUpperLeg", "leftLowerLeg", "leftFoot", "rightUpperLeg",
                  "rightLowerLeg", "rightFoot")
OWNER_FIELDS = ("owner_name", "source_kind", "source_description", "licence_note", "date")
SOURCE_KINDS = ("cc5", "vam", "daz", "other")
RATINGS = ("general", "r15", "r18")


class Refused(Exception):
    """The input is readable but may not be published (the message says why)."""


def glb_json(data: bytes) -> dict | None:
    """The glTF JSON chunk of a GLB, or None."""
    if len(data) < 20 or data[:4] != b"glTF":
        return None
    n, kind = struct.unpack_from("<II", data, 12)
    if kind != 0x4E4F534A or 20 + n > len(data):
        return None
    try:
        return json.loads(data[20:20 + n].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def local_only_stamp(doc: dict | None) -> dict | None:
    """The converter's dm_import stamp when it marks the body local-only, else None."""
    x = (((doc or {}).get("asset") or {}).get("extras") or {}).get("dm_import")
    if isinstance(x, dict) and (x.get("local_only") is True or x.get("not_for_distribution") is True):
        return x
    return None


def vrm_problems(doc: dict) -> list[str]:
    """What stops this VRM from being a private imported desk body ([] = fine)."""
    p: list[str] = []
    vrm = (doc.get("extensions") or {}).get("VRMC_vrm")
    if not isinstance(vrm, dict) or vrm.get("specVersion") != "1.0":
        return ["not a VRM 1.0 (no VRMC_vrm specVersion 1.0)"]
    bones = (vrm.get("humanoid") or {}).get("humanBones") or {}
    n_nodes = len(doc.get("nodes") or [])
    for b in REQUIRED_BONES:
        node = (bones.get(b) or {}).get("node")
        if not isinstance(node, int) or not 0 <= node < n_nodes:
            p.append(f"humanoid bone {b} missing")
    if not doc.get("skins"):
        p.append("no skin")
    m = vrm.get("meta") or {}
    if m.get("allowRedistribution") is not False or m.get("avatarPermission") != "onlyAuthor" or m.get("modification") != "prohibited":
        p.append("VRM meta must forbid redistribution (onlyAuthor / allowRedistribution false / modification prohibited)")
    if not local_only_stamp(doc):
        p.append("no local-only import stamp (asset.extras.dm_import) — only import-rung output is published here")
    return p


def attestation_problems(att: Any, asset_id: str) -> list[str]:
    """The owner-attestation rule (mirror of the game's web/importAttestation.mjs)."""
    if not isinstance(att, dict):
        return ["attestation.json is not an object"]
    if att.get("schema") == "dm-import-standin/1":
        ok = att.get("asset_id") == asset_id and len(str(att.get("licence_evidence") or "").strip()) >= 10
        return [] if ok else ["stand-in record incomplete"]
    p: list[str] = []
    if att.get("schema") != "dm-import-attestation/1":
        p.append("schema must be dm-import-attestation/1")
    if att.get("asset_id") != asset_id:
        p.append(f"asset_id must be {asset_id!r}")
    for k in OWNER_FIELDS:
        if len(str(att.get(k) or "").strip()) < (2 if k == "owner_name" else 8 if k == "date" else 3):
            p.append(f"{k} is not filled in (the owner fills the attestation)")
    if att.get("source_kind") not in SOURCE_KINDS:
        p.append("source_kind must be cc5 | vam | daz | other")
    if att.get("owner_holds_licence") is not True:
        p.append("owner_holds_licence must be true")
    if att.get("depicts_real_person") is not False:
        p.append("depicts_real_person must be false (no models of real people)")
    if att.get("local_only_acknowledged") is not True:
        p.append("local_only_acknowledged must be true")
    return p


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def check_import_folder(vrm_path: Path, data: bytes) -> tuple[str, dict, dict]:
    """(asset_id, attestation, import manifest) for a body.vrm inside its import folder; raises Refused."""
    folder = vrm_path.parent
    try:
        att = json.loads((folder / "attestation.json").read_text(encoding="utf-8"))
        man = json.loads((folder / "import.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise Refused(f"the body must sit in its import folder next to attestation.json + import.json ({e})") from e
    asset_id = str(man.get("id") or "")
    probs = attestation_problems(att, asset_id)
    if probs:
        raise Refused("attestation: " + "; ".join(probs))
    if man.get("local_only") is not True or man.get("not_for_distribution") is not True:
        raise Refused("import.json does not say local_only + not_for_distribution")
    want = ((man.get("files") or {}).get(vrm_path.name) or {}).get("sha256")
    if want != _sha(data):
        raise Refused(f"{vrm_path.name} does not match the sha256 import.json recorded (re-convert)")
    if man.get("attestation_sha256") != _sha((folder / "attestation.json").read_bytes()):
        raise Refused("attestation.json changed since conversion (re-convert)")
    return asset_id, att, man


def publish_local(vrm: str | os.PathLike, char_id: str, roster: str | os.PathLike, *, name: str | None = None,
                  rating: str = "general") -> dict:
    """Install the imported body into ``roster/<char_id>/`` as a private, local-only desk character."""
    if not ID_RE.match(char_id or ""):
        raise Refused("--id must match [a-z0-9][a-z0-9_-]{0,63}")
    if rating not in RATINGS:
        raise Refused("--rating must be general | r15 | r18")
    vp = Path(vrm)
    data = vp.read_bytes()
    doc = glb_json(data)
    if doc is None:
        raise Refused(f"{vp} is not a GLB/VRM")
    probs = vrm_problems(doc)
    if probs:
        raise Refused("; ".join(probs))
    asset_id, att, man = check_import_folder(vp, data)
    if man.get("dressed") is not True and rating != "r18":
        raise Refused("an undressed import is r18 only")
    root = Path(roster)
    if not root.is_dir():
        raise Refused(f"desk roster {root} does not exist")
    dest = root / char_id
    if dest.exists():
        try:
            prev = json.loads((dest / "character.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prev = {}
        if not (prev.get("source") == "import" and (prev.get("import") or {}).get("id") == asset_id):
            raise Refused(f"{dest} already holds another character; pick another --id")
    dest.mkdir(parents=True, exist_ok=True)
    tmp = dest / "model.vrm.part"
    shutil.copyfile(vp, tmp)
    os.replace(tmp, dest / "model.vrm")
    stamp = local_only_stamp(doc) or {}
    character = {
        "rating": rating, "source": "import", "persona_id": char_id,
        "display_name": (name or man.get("label") or char_id)[:80],
        "local_only": True, "private": True, "distribution": "local-only",
        "import": {"id": asset_id, "source_kind": man.get("source_kind"), "source_sha256": man.get("source_sha256"),
                   "attestation_sha256": man.get("attestation_sha256"), "owner_name": att.get("owner_name"),
                   "standin": bool(man.get("standin")), "importer": stamp.get("importer"), "model_sha256": _sha(data)},
    }
    (dest / "character.json").write_text(json.dumps(character, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "dir": str(dest), "id": char_id, "rating": rating, "local_only": True}
