# awavatar — Aither World Avatar

One character spec in, a rigged, animated, multi-style asset pack out.

`awavatar` ships the **contracts** of a character factory and a thin client that speaks to any
media-forge-shaped server. It generates nothing itself: the mesh, rig, clips and renders come
from whatever factory you point it at. What it owns is the question *"is this spec well-formed,
and is this pack something a host may load?"* — answered the same way on every machine.

```
pip install awavatar
awavatar validate-spec character_spec.json          # schema_version-routed validation
awavatar validate-pack ./character_pack/            # hashes, licences, rig audit, VRM bones
awavatar submit character_spec.json --server http://127.0.0.1:8200   # any media-forge-shaped server
```

## Not the desktop app — and the boundary is worth stating

[`awdesk`](https://github.com/Aitherium/awdesk) is the **consumer**: it renders a
pack (tray, VRM avatars, the Living Desktop). `awavatar` is the **contract
side**: it decides what a pack must contain and whether one may load, and it
generates nothing itself. The two never do each other's job — install awdesk to
*see* a character, install awavatar to *produce and audit* the pack a character
arrives in. If you are looking for a face on your desktop, you want `awdesk`.

## Contracts (all versioned by `schema_version`)

| schema | what it is | consumers |
|---|---|---|
| `character_spec` v1 | the one input: identity, rating, creature/visual descriptors, styles, skeletons, clips, targets, seed | the factory, the World Spec compiler |
| `character_pack` v1 | the one output: `manifest.json` + bodies/clips/VRM/renders, every file hashed and licensed | game clients, awdesk, Spaces |
| `world_spec` v1 | zones, NPCs, spawn camps, quests, dungeons, recipes, lore, realm rating | the World Spec compiler |
| `companion_state` v1 | one companion state, three hosts (sim tick, wallclock, published snapshot) | game clients, awdesk, Spaces |

Validators are pure stdlib and carry a `--self-test` that proves each rule can fail.
`validate-pack` delegates to the same rule set the AitherOS gate `check_character_pack.py`
runs (CPK001–CPK008); when that file is present next to a monorepo checkout it is used, and
otherwise the vendored copy in `awavatar/pack.py` is — the two are kept identical by
`check_awavatar_mirror` (planned).

Status: **planned** (registered in the Aither World registry before code, per the family
rule). Nothing here is published yet.
