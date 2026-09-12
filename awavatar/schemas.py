"""Versioned validators for the character factory's contracts. Pure stdlib.

    python -m awavatar.schemas --self-test

Each validator takes a decoded JSON object and returns a list of problems (empty = valid).
`schema_version` is REQUIRED and routed: an unknown version is a problem, never a silent
pass, so a v2 document handed to a v1 validator is refused rather than half-read. The
rules are deliberately structural (shape, enums, cross-field consistency) — they say
nothing about whether a character is a good one.
"""

from __future__ import annotations

import sys

RATING_ORDER = {"pg": 0, "suggestive": 1, "explicit": 2, "brutal": 3}
STYLES = {"3d", "anime", "pixel", "lowpoly"}
SKELETONS = {"anny", "kaykit", "cc5"}
TARGETS = {"coc", "dm-world", "awdesk", "space"}
TARGET_CEILING = {"coc": "brutal", "dm-world": "pg", "awdesk": "suggestive", "space": "pg"}
CLIP_MIN = ("idle",)
QUEST_OBJECTIVE_TYPES = {"collect", "kill", "explore", "talk", "craft", "escort"}


class SchemaError(ValueError):
    """Raised by the strict wrappers when a document is invalid."""


def _req(doc: dict, field: str, typ, out: list[str], where: str) -> bool:
    if field not in doc:
        out.append(f"{where}: missing {field!r}")
        return False
    if typ is not None and not isinstance(doc[field], typ):
        out.append(f"{where}: {field!r} must be {getattr(typ, '__name__', typ)}")
        return False
    return True


def _version(doc, expected: int, where: str, out: list[str]) -> bool:
    if not isinstance(doc, dict):
        out.append(f"{where}: document is not an object")
        return False
    v = doc.get("schema_version")
    if v != expected:
        out.append(
            f"{where}: schema_version {v!r} is not {expected} "
            "(unknown versions are refused, never half-read)"
        )
        return False
    return True


# ------------------------------------------------------ character_spec ----


def validate_character_spec(doc) -> list[str]:
    out: list[str] = []
    w = "character_spec"
    if not _version(doc, 1, w, out):
        return out
    for f, t in (
        ("id", str),
        ("name", str),
        ("provenance", dict),
        ("rating", str),
        ("creature", dict),
        ("saga_visual", dict),
        ("styles", list),
        ("skeletons", list),
        ("clips", list),
        ("targets", list),
        ("seed", int),
    ):
        _req(doc, f, t, out, w)
    if out:
        return out
    if not doc["id"].strip() or " " in doc["id"]:
        out.append(f"{w}: id {doc['id']!r} must be a non-empty token")
    prov = doc["provenance"]
    for f in ("author", "license"):
        if not str(prov.get(f) or "").strip():
            out.append(f"{w}: provenance.{f} is required")
    if doc["rating"] not in RATING_ORDER:
        out.append(f"{w}: rating {doc['rating']!r} not in {sorted(RATING_ORDER)}")
    bad = sorted(set(doc["styles"]) - STYLES)
    if bad:
        out.append(f"{w}: unknown styles {bad}")
    if not doc["styles"]:
        out.append(f"{w}: styles is empty")
    bad = sorted(set(doc["skeletons"]) - SKELETONS)
    if bad:
        out.append(f"{w}: unknown skeletons {bad}")
    if not doc["skeletons"]:
        out.append(f"{w}: skeletons is empty")
    bad = sorted(set(doc["targets"]) - TARGETS)
    if bad:
        out.append(f"{w}: unknown targets {bad}")
    if not doc["targets"]:
        out.append(f"{w}: targets is empty")
    if not all(isinstance(c, str) and c for c in doc["clips"]):
        out.append(f"{w}: clips must be non-empty strings")
    for c in CLIP_MIN:
        if c not in doc["clips"]:
            out.append(f"{w}: clips must include {c!r}")
    # cross-field: the rating may not exceed any target's ceiling
    r = RATING_ORDER.get(doc["rating"], 99)
    for t in doc["targets"]:
        ceiling = TARGET_CEILING.get(t)
        if ceiling and r > RATING_ORDER[ceiling]:
            out.append(f"{w}: rating {doc['rating']} exceeds target {t}'s ceiling {ceiling}")
    if "awdesk" in doc["targets"] and "anny" not in doc["skeletons"]:
        out.append(f"{w}: target awdesk needs the anny skeleton (VRM export source)")
    if "dm-world" in doc["targets"] and "kaykit" not in doc["skeletons"]:
        out.append(f"{w}: target dm-world needs the kaykit skeleton")
    if doc["seed"] < 0:
        out.append(f"{w}: seed must be >= 0")
    return out


# ---------------------------------------------------------- world_spec ----


def validate_world_spec(doc) -> list[str]:
    out: list[str] = []
    w = "world_spec"
    if not _version(doc, 1, w, out):
        return out
    for f, t in (
        ("id", str),
        ("seed", int),
        ("realm_rating", str),
        ("zones", list),
        ("npcs", list),
        ("spawn_camps", list),
        ("quests", list),
        ("dungeons", list),
        ("recipes", list),
        ("lore", dict),
    ):
        _req(doc, f, t, out, w)
    if out:
        return out
    if doc["realm_rating"] not in RATING_ORDER:
        out.append(f"{w}: realm_rating {doc['realm_rating']!r} not in {sorted(RATING_ORDER)}")
        return out
    realm = RATING_ORDER[doc["realm_rating"]]
    zone_ids = set()
    for i, z in enumerate(doc["zones"]):
        zw = f"{w}.zones[{i}]"
        if not isinstance(z, dict):
            out.append(f"{zw}: not an object")
            continue
        for f in ("id", "biome", "level_min", "level_max"):
            if f not in z:
                out.append(f"{zw}: missing {f!r}")
        if isinstance(z.get("id"), str):
            if z["id"] in zone_ids:
                out.append(f"{zw}: duplicate zone id {z['id']!r}")
            zone_ids.add(z["id"])
        if (
            isinstance(z.get("level_min"), int)
            and isinstance(z.get("level_max"), int)
            and z["level_min"] > z["level_max"]
        ):
            out.append(f"{zw}: level_min > level_max")
    npc_ids = set()
    for i, n in enumerate(doc["npcs"]):
        nw = f"{w}.npcs[{i}]"
        if not isinstance(n, dict):
            out.append(f"{nw}: not an object")
            continue
        for f in ("id", "spec_id", "zone", "role"):
            if f not in n:
                out.append(f"{nw}: missing {f!r}")
        if isinstance(n.get("id"), str):
            if n["id"] in npc_ids:
                out.append(f"{nw}: duplicate npc id {n['id']!r}")
            npc_ids.add(n["id"])
        if n.get("zone") not in zone_ids:
            out.append(f"{nw}: zone {n.get('zone')!r} is not a declared zone")
        rating = n.get("rating", "pg")
        if rating not in RATING_ORDER:
            out.append(f"{nw}: rating {rating!r} not in {sorted(RATING_ORDER)}")
        elif RATING_ORDER[rating] > realm:
            out.append(f"{nw}: rating {rating} exceeds realm_rating {doc['realm_rating']}")
    for i, c in enumerate(doc["spawn_camps"]):
        cw = f"{w}.spawn_camps[{i}]"
        if not isinstance(c, dict):
            out.append(f"{cw}: not an object")
            continue
        for f in ("zone", "family", "level", "count", "respawn_mult"):
            if f not in c:
                out.append(f"{cw}: missing {f!r}")
        if c.get("zone") not in zone_ids:
            out.append(f"{cw}: zone {c.get('zone')!r} is not a declared zone")
        if isinstance(c.get("count"), int) and c["count"] <= 0:
            out.append(f"{cw}: count must be > 0")
    quest_ids = set()
    quests = [q for q in doc["quests"] if isinstance(q, dict)]
    for i, q in enumerate(doc["quests"]):
        qw = f"{w}.quests[{i}]"
        if not isinstance(q, dict):
            out.append(f"{qw}: not an object")
            continue
        for f in ("id", "giver", "title", "objectives", "rewards"):
            if f not in q:
                out.append(f"{qw}: missing {f!r}")
        if isinstance(q.get("id"), str):
            if q["id"] in quest_ids:
                out.append(f"{qw}: duplicate quest id {q['id']!r}")
            quest_ids.add(q["id"])
        if q.get("giver") not in npc_ids:
            out.append(f"{qw}: giver {q.get('giver')!r} is not a declared npc")
        for j, o in enumerate(q.get("objectives") or []):
            if not isinstance(o, dict) or o.get("type") not in QUEST_OBJECTIVE_TYPES:
                out.append(
                    f"{qw}.objectives[{j}]: type must be one of {sorted(QUEST_OBJECTIVE_TYPES)}"
                )
        rating = q.get("rating", "pg")
        if rating in RATING_ORDER and RATING_ORDER[rating] > realm:
            out.append(f"{qw}: rating {rating} exceeds realm_rating {doc['realm_rating']}")
    # quest chains must be acyclic
    nxt = {q.get("id"): q.get("next") for q in quests if isinstance(q.get("id"), str)}
    for start in nxt:
        seen, cur = set(), start
        while cur in nxt and nxt[cur]:
            if cur in seen:
                out.append(f"{w}: quest chain cycle through {cur!r}")
                break
            seen.add(cur)
            cur = nxt[cur]
        else:
            if (
                cur
                and cur not in nxt
                and cur != start
                and nxt.get(start) is not None
                and cur not in quest_ids
            ):
                out.append(f"{w}: quest {start!r} chains to unknown quest {cur!r}")
    for i, r in enumerate(doc["recipes"]):
        rw = f"{w}.recipes[{i}]"
        if not isinstance(r, dict):
            out.append(f"{rw}: not an object")
            continue
        for f in ("id", "profession", "reagents", "result", "skill_req"):
            if f not in r:
                out.append(f"{rw}: missing {f!r}")
        if r.get("skill_req") not in (0, 25, 50, 75, 150):
            out.append(
                f"{rw}: skill_req {r.get('skill_req')!r} not in the tier ladder 0/25/50/75/150"
            )
    for i, d in enumerate(doc["dungeons"]):
        dw = f"{w}.dungeons[{i}]"
        if not isinstance(d, dict):
            out.append(f"{dw}: not an object")
            continue
        for f in ("id", "zone", "encounters"):
            if f not in d:
                out.append(f"{dw}: missing {f!r}")
        if d.get("zone") not in zone_ids:
            out.append(f"{dw}: zone {d.get('zone')!r} is not a declared zone")
        for j, e in enumerate(d.get("encounters") or []):
            groups = (e or {}).get("loot_rollgroups") if isinstance(e, dict) else None
            if groups:
                total = sum(float(g.get("weight", 0)) for g in groups if isinstance(g, dict))
                if abs(total - 1.0) > 1e-6:
                    out.append(
                        f"{dw}.encounters[{j}]: loot_rollgroups weights sum to {total:.4f}, not 1.0"
                    )
    return out


# ----------------------------------------------------- companion_state ----


def validate_companion_state(doc) -> list[str]:
    out: list[str] = []
    w = "companion_state"
    if not _version(doc, 1, w, out):
        return out
    for f, t in (
        ("spec_id", str),
        ("tick", int),
        ("wallclock_iso", str),
        ("needs", dict),
        ("mood", str),
        ("stage", str),
        ("form", str),
        ("knowledge_count", int),
    ):
        _req(doc, f, t, out, w)
    if out:
        return out
    for k in ("hunger", "energy", "hygiene", "bond"):
        v = doc["needs"].get(k)
        if not isinstance(v, (int, float)) or not 0.0 <= float(v) <= 1.0:
            out.append(f"{w}: needs.{k} must be a number in [0, 1]")
    if doc["tick"] < 0:
        out.append(f"{w}: tick must be >= 0")
    if doc["knowledge_count"] < 0:
        out.append(f"{w}: knowledge_count must be >= 0")
    return out


# ------------------------------------------------------------ scene_spec ----

BEAT_KINDS = {"clip", "tf", "vfx", "line", "camera", "wait"}
BACKDROP_KINDS = {"band", "sky", "image", "video"}
CAMERA_MODES = {"orbit", "fixed", "follow", "orthographic"}


def validate_scene_spec(doc) -> list[str]:
    """W14 - a composed scene: style + backdrop layers + cast + props + camera + timeline."""
    out: list[str] = []
    w = "scene_spec"
    if not _version(doc, 1, w, out):
        return out
    for f, t in (
        ("id", str),
        ("style", str),
        ("rating", str),
        ("backdrop", list),
        ("cast", list),
        ("props", list),
        ("camera", dict),
        ("timeline", list),
    ):
        _req(doc, f, t, out, w)
    if out:
        return out
    if doc["style"] not in STYLES:
        out.append(f"{w}: style {doc['style']!r} not in {sorted(STYLES)}")
    if doc["rating"] not in RATING_ORDER:
        out.append(f"{w}: rating {doc['rating']!r} not in {sorted(RATING_ORDER)}")
    last_depth = None
    for i, layer in enumerate(doc["backdrop"]):
        lw = f"{w}.backdrop[{i}]"
        if not isinstance(layer, dict):
            out.append(f"{lw}: not an object")
            continue
        if layer.get("kind") not in BACKDROP_KINDS:
            out.append(f"{lw}: kind {layer.get('kind')!r} not in {sorted(BACKDROP_KINDS)}")
        d = layer.get("depth")
        if not isinstance(d, (int, float)) or not 0.0 <= float(d) <= 1.0:
            out.append(f"{lw}: depth must be a number in [0, 1] (0 = far, 1 = near)")
        elif last_depth is not None and float(d) < last_depth:
            out.append(f"{lw}: depth {d} is out of order (layers list far -> near)")
        else:
            last_depth = float(d)
    cast_ids: set[str] = set()
    cast_clips: dict[str, set[str]] = {}
    for i, c in enumerate(doc["cast"]):
        cw = f"{w}.cast[{i}]"
        if not isinstance(c, dict):
            out.append(f"{cw}: not an object")
            continue
        for f in ("id", "pack", "clips"):
            if f not in c:
                out.append(f"{cw}: missing {f!r}")
        cid = str(c.get("id") or "")
        if cid in cast_ids:
            out.append(f"{cw}: duplicate cast id {cid!r}")
        cast_ids.add(cid)
        cast_clips[cid] = {str(x) for x in (c.get("clips") or [])}
        if not str(c.get("pack") or "").strip():
            out.append(f"{cw}: pack must reference a character_pack id")
    for i, pr in enumerate(doc["props"]):
        if not isinstance(pr, dict) or not str(pr.get("pack") or "").strip():
            out.append(f"{w}.props[{i}]: must reference a pack")
    cam = doc["camera"]
    if cam.get("mode") not in CAMERA_MODES:
        out.append(f"{w}: camera.mode {cam.get('mode')!r} not in {sorted(CAMERA_MODES)}")
    if doc["style"] == "pixel" and cam.get("mode") not in {"orthographic", "fixed"}:
        out.append(f"{w}: a pixel scene needs an orthographic or fixed camera")
    t_prev = -1.0
    for i, b in enumerate(doc["timeline"]):
        bw = f"{w}.timeline[{i}]"
        if not isinstance(b, dict):
            out.append(f"{bw}: not an object")
            continue
        kind = b.get("kind")
        if kind not in BEAT_KINDS:
            out.append(f"{bw}: kind {kind!r} not in {sorted(BEAT_KINDS)}")
            continue
        at = b.get("at")
        if not isinstance(at, (int, float)) or float(at) < 0:
            out.append(f"{bw}: at must be a number >= 0 (seconds)")
        elif float(at) < t_prev:
            out.append(f"{bw}: beats must be in time order")
        else:
            t_prev = float(at)
        who = str(b.get("cast") or "")
        if kind in {"clip", "tf", "line"} and who not in cast_ids:
            out.append(f"{bw}: cast {who!r} is not in the scene")
        if kind == "clip" and who in cast_clips and str(b.get("clip")) not in cast_clips[who]:
            out.append(f"{bw}: clip {b.get('clip')!r} is not one of {who}'s clips")
        if kind == "tf" and not isinstance(b.get("tf_event"), dict):
            out.append(f"{bw}: a tf beat carries a tf_event object")
    return out


def example_scene_spec() -> dict:
    return {
        "schema_version": 1,
        "id": "dm-scene-vale-dawn",
        "style": "3d",
        "rating": "pg",
        "backdrop": [
            {"kind": "sky", "depth": 0.0, "ref": "sky/dawn"},
            {"kind": "band", "depth": 0.3, "ref": "vale/hills"},
            {"kind": "band", "depth": 0.8, "ref": "vale/road"},
        ],
        "cast": [
            {"id": "elara", "pack": "dm-elara-001", "clips": ["idle", "walk", "talk"], "morph": {}}
        ],
        "props": [{"pack": "dm-prop-bridge-001", "at": [0, 0, -2]}],
        "camera": {"mode": "orbit", "fov": 20},
        "timeline": [
            {"kind": "clip", "at": 0.0, "cast": "elara", "clip": "idle"},
            {"kind": "line", "at": 1.0, "cast": "elara", "text": "Quiet morning."},
            {"kind": "camera", "at": 2.0, "to": {"mode": "follow", "cast": "elara"}},
            {"kind": "clip", "at": 2.5, "cast": "elara", "clip": "walk"},
            {
                "kind": "tf",
                "at": 4.0,
                "cast": "elara",
                "tf_event": {"morphs": {"muscle": 0.8}, "duration": 1.5},
            },
        ],
    }


# ------------------------------------------------------------ strict ----


def require_valid(doc, validator, name: str) -> None:
    problems = validator(doc)
    if problems:
        raise SchemaError(f"{name}: " + "; ".join(problems))


# ---------------------------------------------------------- fixtures ----


def example_character_spec() -> dict:
    return {
        "schema_version": 1,
        "id": "dm-elara-001",
        "name": "Elara",
        "provenance": {"author": "aither:slice1", "license": "original"},
        "rating": "pg",
        "creature": {"race": "human", "sex": "female", "tallness": 66},
        "saga_visual": {
            "gender": "female",
            "age_appearance": "adult",
            "hair": "black",
            "eyes": "green",
            "body_type": "athletic",
            "default_outfit": "leather",
            "distinguishing_features": "",
            "art_style": "3d",
            "reference_images": [],
        },
        "styles": ["3d", "anime"],
        "skeletons": ["anny", "kaykit"],
        "clips": ["idle", "walk", "run", "attack", "cast", "sit", "death"],
        "targets": ["coc", "dm-world", "awdesk"],
        "seed": 20061,
    }


def example_world_spec() -> dict:
    return {
        "schema_version": 1,
        "id": "dm-vale",
        "seed": 20061,
        "realm_rating": "pg",
        "zones": [{"id": "ashen-vale", "biome": "temperate", "level_min": 1, "level_max": 7}],
        "npcs": [
            {
                "id": "npc-elara",
                "spec_id": "dm-elara-001",
                "zone": "ashen-vale",
                "role": "quest_giver",
                "rating": "pg",
            }
        ],
        "spawn_camps": [
            {"zone": "ashen-vale", "family": "beast", "level": 2, "count": 6, "respawn_mult": 4}
        ],
        "quests": [
            {
                "id": "q1",
                "giver": "npc-elara",
                "title": "Wolves at the gate",
                "objectives": [{"type": "kill", "target": "wolf", "count": 5}],
                "rewards": {"xp": 100},
                "next": "q2",
            },
            {
                "id": "q2",
                "giver": "npc-elara",
                "title": "The den",
                "objectives": [{"type": "explore", "target": "den"}],
                "rewards": {"xp": 200},
            },
        ],
        "dungeons": [
            {
                "id": "hollow",
                "zone": "ashen-vale",
                "encounters": [
                    {
                        "boss": "Morthen",
                        "loot_rollgroups": [
                            {"item": "a", "weight": 0.7},
                            {"item": "b", "weight": 0.3},
                        ],
                    }
                ],
            }
        ],
        "recipes": [
            {
                "id": "r1",
                "profession": "cooking",
                "reagents": [{"item": "meat", "count": 1}],
                "result": {"item": "stew", "count": 1},
                "skill_req": 0,
            }
        ],
        "lore": {"ashen-vale": "A quiet valley."},
    }


def example_companion_state() -> dict:
    return {
        "schema_version": 1,
        "spec_id": "dm-elara-001",
        "tick": 1200,
        "wallclock_iso": "2026-09-05T21:00:00Z",
        "needs": {"hunger": 0.8, "energy": 0.6, "hygiene": 0.9, "bond": 0.2},
        "mood": "content",
        "stage": "child",
        "form": "base",
        "knowledge_count": 3,
    }


# ------------------------------------------------------------ tf_event ----

# duration bounds, milliseconds. MIRRORED in the CoC engine (engine/src/render/tfEvent.ts
# TF_DURATION_MIN_MS/MAX_MS) and the stage consumer (tfTween.mjs) -- RTT003 in
# check_rtt_contract.py asserts the three copies agree, because a client that trusts an
# unclamped duration tweens forever and a server that emits one past the client's clamp
# snaps.
TF_DURATION_MS = (50, 5000)
_TF_ID = "abcdefghijklmnopqrstuvwxyz0123456789_"


def _tf_id_ok(s: str) -> bool:
    return bool(s) and s[0].isalpha() and all(ch in _TF_ID for ch in s)


def validate_tf_event(doc, known_bodies=None) -> list[str]:
    """A real-time transformation event: ONE body moving from one shape to another.

    The stage tweens `from_morphs` -> `to_morphs` over `duration_ms`, toggles the
    attachment groups in `attach_on`/`attach_off` when the body has arrived, swaps
    the base GLB when `body_from` != `body_to`, and refits the ragdoll colliders after
    (`collider_refit` is literally True -- an event that skipped the refit would leave
    a heavy body with a thin body's capsules, which reads as a physics bug, not a TF
    bug). An event that changes NOTHING is refused: it would tween for a second and
    show nothing, indistinguishable from a broken emitter.

    `known_bodies`: an optional set of BODY_REGISTRY ids; when given, a non-null
    body_from/body_to must be in it. The registry lives in the engine (model3d.ts),
    so the pure contract only pins the id SHAPE by default.
    """
    out: list[str] = []
    w = "tf_event"
    if not _version(doc, 1, w, out):
        return out
    for fld in ("from_morphs", "to_morphs"):
        if _req(doc, fld, dict, out, w):
            for k, v in doc[fld].items():
                if not isinstance(k, str) or not k:
                    out.append(f"{w}: {fld} has a non-string key {k!r}")
                elif isinstance(v, bool) or not isinstance(v, (int, float)):
                    out.append(f"{w}: {fld}.{k} must be a number")
                elif v != v or v in (float("inf"), float("-inf")):
                    out.append(f"{w}: {fld}.{k} is not finite")
    for fld in ("attach_on", "attach_off"):
        if _req(doc, fld, list, out, w):
            for a in doc[fld]:
                if not isinstance(a, str) or not a:
                    out.append(f"{w}: {fld} entries must be non-empty strings")
    on = set(a for a in doc.get("attach_on", []) if isinstance(a, str))
    off = set(a for a in doc.get("attach_off", []) if isinstance(a, str))
    both = sorted(on & off)
    if both:
        out.append(f"{w}: attach_on and attach_off both name {both}")
    for fld in ("body_from", "body_to"):
        if fld not in doc:
            out.append(f"{w}: missing {fld!r}")
            continue
        b = doc[fld]
        if b is None:
            continue
        if not isinstance(b, str) or not _tf_id_ok(b):
            out.append(f"{w}: {fld} must be null or a BODY_REGISTRY id ([a-z][a-z0-9_]*)")
        elif known_bodies is not None and b not in known_bodies:
            out.append(f"{w}: {fld} {b!r} is not a known body")
    if _req(doc, "duration_ms", int, out, w):
        d = doc["duration_ms"]
        lo, hi = TF_DURATION_MS
        if isinstance(d, bool) or not (lo <= d <= hi):
            out.append(f"{w}: duration_ms {d!r} outside {lo}..{hi}")
    if _req(doc, "cue", dict, out, w):
        for k, v in doc["cue"].items():
            if k not in ("audio", "vfx"):
                out.append(f"{w}: cue.{k} is not audio|vfx")
            elif not isinstance(v, str):
                out.append(f"{w}: cue.{k} must be a string")
    if _req(doc, "collider_refit", bool, out, w) and doc["collider_refit"] is not True:
        out.append(f"{w}: collider_refit must be true (a TF that skips the refit is refused)")
    # an event must MOVE something -- a no-op event is a broken emitter presenting as a TF
    if not out:
        fm, tm = doc["from_morphs"], doc["to_morphs"]
        moved = any(tm.get(k) != fm.get(k) for k in set(fm) | set(tm))
        if not moved and not on and not off and doc["body_from"] == doc["body_to"]:
            out.append(f"{w}: changes nothing (no morph delta, no attach change, no body swap)")
    return out


def example_tf_event() -> dict:
    return {
        "schema_version": 1,
        "from_morphs": {"breasts": 4, "hips": 6, "thickness": 30},
        "to_morphs": {"breasts": 10, "hips": 9, "thickness": 30},
        "attach_on": ["tail"],
        "attach_off": [],
        "body_from": None,
        "body_to": None,
        "duration_ms": 1200,
        "cue": {"vfx": "morph"},
        "collider_refit": True,
    }


# ---------------------------------------------------------- self-test ----


def self_test() -> int:
    import copy

    problems: list[str] = []
    for name, fn, ex in (
        ("character_spec", validate_character_spec, example_character_spec),
        ("world_spec", validate_world_spec, example_world_spec),
        ("companion_state", validate_companion_state, example_companion_state),
        ("scene_spec", validate_scene_spec, example_scene_spec),
        ("tf_event", validate_tf_event, example_tf_event),
    ):
        clean = fn(ex())
        if clean:
            problems.append(f"{name}: clean example reported {clean}")
        v2 = ex()
        v2["schema_version"] = 2
        if not fn(v2):
            problems.append(f"{name}: v2 document was not refused")
        if not fn("not an object"):
            problems.append(f"{name}: non-object was not refused")

    def expect(name, doc, needle):
        found = {
            "character_spec": validate_character_spec,
            "world_spec": validate_world_spec,
            "companion_state": validate_companion_state,
            "scene_spec": validate_scene_spec,
            "tf_event": validate_tf_event,
        }[name](doc)
        if not any(needle in f for f in found):
            problems.append(f"{name}: expected a problem containing {needle!r}, got {found}")

    d = example_character_spec()
    d["rating"] = "explicit"
    expect("character_spec", d, "exceeds target dm-world")
    d = example_character_spec()
    d["styles"] = ["oil"]
    expect("character_spec", d, "unknown styles")
    d = example_character_spec()
    d["skeletons"] = ["kaykit"]
    expect("character_spec", d, "awdesk needs the anny")
    d = example_character_spec()
    d["clips"] = ["walk"]
    expect("character_spec", d, "must include 'idle'")
    d = example_character_spec()
    d["provenance"] = {"author": "x"}
    expect("character_spec", d, "provenance.license")
    d = example_world_spec()
    d["npcs"][0]["rating"] = "brutal"
    expect("world_spec", d, "exceeds realm_rating")
    d = example_world_spec()
    d["quests"][1]["next"] = "q1"
    expect("world_spec", d, "cycle")
    d = example_world_spec()
    d["quests"][0]["giver"] = "ghost"
    expect("world_spec", d, "not a declared npc")
    d = example_world_spec()
    d["dungeons"][0]["encounters"][0]["loot_rollgroups"][0]["weight"] = 0.9
    expect("world_spec", d, "sum to")
    d = example_world_spec()
    d["recipes"][0]["skill_req"] = 30
    expect("world_spec", d, "tier ladder")
    d = example_world_spec()
    d["spawn_camps"][0]["zone"] = "nowhere"
    expect("world_spec", d, "not a declared zone")
    d = copy.deepcopy(example_companion_state())
    d["needs"]["bond"] = 1.5
    expect("companion_state", d, "needs.bond")
    d = example_companion_state()
    d["tick"] = -1
    expect("companion_state", d, "tick must be")
    d = example_scene_spec()
    d["timeline"][0]["clip"] = "dance"
    expect("scene_spec", d, "not one of elara's clips")
    d = example_scene_spec()
    d["backdrop"][1]["depth"] = 0.9
    expect("scene_spec", d, "out of order")
    d = example_scene_spec()
    d["timeline"][1]["cast"] = "ghost"
    expect("scene_spec", d, "not in the scene")
    d = example_scene_spec()
    d["style"] = "pixel"
    expect("scene_spec", d, "orthographic")
    d = example_scene_spec()
    d["timeline"][3]["at"] = 0.5
    expect("scene_spec", d, "time order")
    d = example_tf_event()
    d["duration_ms"] = 5001
    expect("tf_event", d, "outside 50..5000")
    d = example_tf_event()
    d["duration_ms"] = 49
    expect("tf_event", d, "outside 50..5000")
    d = example_tf_event()
    d["collider_refit"] = False
    expect("tf_event", d, "collider_refit must be true")
    d = example_tf_event()
    d["attach_off"] = ["tail"]
    expect("tf_event", d, "both name")
    d = example_tf_event()
    d["body_to"] = "Anny Body"
    expect("tf_event", d, "BODY_REGISTRY id")
    d = example_tf_event()
    d["to_morphs"] = dict(d["from_morphs"])
    d["attach_on"] = []
    expect("tf_event", d, "changes nothing")
    d = example_tf_event()
    d["cue"] = {"haptic": "x"}
    expect("tf_event", d, "not audio|vfx")
    d = example_tf_event()
    d["body_to"] = "susan"
    if validate_tf_event(d, known_bodies={"female", "male"}) == []:
        problems.append("tf_event: unknown body passed against known_bodies")
    if validate_tf_event(d, known_bodies={"female", "susan"}):
        problems.append("tf_event: known body refused against known_bodies")
    try:
        require_valid({"schema_version": 1}, validate_companion_state, "companion_state")
        problems.append("require_valid did not raise")
    except SchemaError as e:
        if "companion_state" not in str(e):
            problems.append(f"require_valid raised without the schema name: {e}")
    if problems:
        print("SELF-TEST FAILED")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(
        "SELF-TEST OK: 5 schemas, clean examples pass, "
        "unknown versions refused, 27 mutation arms fire"
    )
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
