"""Basic tests for awavatar schemas module."""

from awavatar import schemas


def test_schemas_module_imports():
    """Verify the schemas module can be imported."""
    assert schemas is not None


def _spec(**extra):
    d = schemas.example_character_spec()
    d.update(extra)
    return d


def test_voice_is_optional():
    d = schemas.example_character_spec()
    d.pop("voice", None)
    assert schemas.validate_character_spec(d) == []


def test_voice_accepts_stock_ids_and_custom_names():
    for v in ("af_heart", "en-US-AvaNeural", "custom:grandma-reads", "custom:ab"):
        assert schemas.validate_character_spec(_spec(voice=v)) == [], v


def test_voice_rejects_bad_values():
    for v in ("custom:", "custom:x", "custom:Grandma", "custom:9lives", "custom:a b",
              "custom:" + "a" * 33, "has space", "", 7, None,
              # `$` alone would accept a trailing newline; the id becomes a URL path segment
              "custom:ab\n", "af_heart\n"):
        problems = schemas.validate_character_spec(_spec(voice=v))
        assert problems and all("voice" in p for p in problems), (v, problems)


def test_self_test_passes():
    assert schemas.self_test() == 0


def test_injuries_is_optional():
    d = schemas.example_character_spec()
    assert "injuries" not in d
    assert schemas.validate_character_spec(d) == []


def test_injuries_accepts_a_well_formed_projection():
    assert schemas.validate_character_spec(_spec(injuries=schemas.example_injuries())) == []
    gore = {**schemas.example_injuries(), "tier": "gore", "blood": 80,
            "wounds": [{"region": "leftLeg", "kind": "stump", "severity": 3, "bleeding": True,
                        "bandaged": False, "healed": 0}]}
    brutal = _spec(rating="brutal", targets=["coc"], skeletons=["cc5"], injuries=gore)
    assert schemas.validate_character_spec(brutal) == []


def test_injuries_rejects_bad_types_and_tier_leaks():
    base = schemas.example_injuries()
    bad = [
        ("not-an-object", "injuries must be an object"),
        ({**base, "tier": "splatter"}, "injuries.tier"),
        ({**base, "tier": "blood"}, "exceeds the spec rating"),           # spec is pg
        ({**base, "blood": 5}, "may not carry blood"),
        ({**base, "blood": 500}, "blood must be a number"),
        ({**base, "wounds": "cut"}, "wounds must be an array"),
        ({**base, "wounds": [{"region": "tail", "kind": "cut", "severity": 1}]}, "region"),
        ({**base, "wounds": [{"region": "head", "kind": "cut", "severity": 4}]}, "severity"),
        ({**base, "wounds": [{"region": "head", "kind": "cut", "severity": True}]}, "severity"),
        ({**base, "wounds": [{"region": "head", "kind": "cut", "severity": 1, "bleeding": True}]},
         "may not carry bleeding"),
        ({**base, "severed": [3]}, "severed must be an array"),
        ({**base, "scars": [{"region": "head"}]}, "scars must be an array"),
        ({**base, "limp": "sideways"}, "limp"),
        ({**base, "as_of": "yesterday"}, "as_of must be an ISO 8601"),
        ({**base, "as_of": 1760875200}, "as_of must be an ISO 8601"),
        ({**base, "wounds": [{"region": "head", "kind": "cut", "severity": 1, "heal_days": -1}]},
         "heal_days"),
        ({**base, "wounds": [{"region": "head", "kind": "cut", "severity": 1, "heal_days": 9999}]},
         "heal_days"),
        ({**base, "descriptors_by_tier": []}, "descriptors_by_tier must be an object"),
        ({**base, "descriptors_by_tier": {"splatter": ["x"]}}, "is not a tier"),
        ({**base, "descriptors_by_tier": {"blood": ["x"]}}, "exceeds the projection tier"),
        ({**base, "descriptors_by_tier": {"pg": [""]}}, "non-empty strings"),
    ]
    for inj, needle in bad:
        problems = schemas.validate_character_spec(_spec(injuries=inj))
        assert any(needle in p for p in problems), (inj, needle, problems)


def test_injuries_timestamps_and_tiered_text_are_optional_and_validate():
    drop = ("as_of", "descriptors_by_tier")
    base = {k: v for k, v in schemas.example_injuries().items() if k not in drop}
    base["wounds"] = [{k: v for k, v in w.items() if k != "heal_days"} for w in base["wounds"]]
    # the #13612 shape still validates
    assert schemas.validate_character_spec(_spec(injuries=base)) == []
    gore = {**schemas.example_injuries(), "tier": "gore", "blood": 60,
            "descriptors_by_tier": {"pg": ["a grievous stab wound on the torso, untended"],
                                    "blood": ["grievous stab wound on the torso, still bleeding"],
                                    "gore": ["grievous stab wound on the torso, "
                                             "gaping open and bleeding freely"]},
            "as_of": "2026-10-19T12:00:00+02:00"}
    brutal = _spec(rating="brutal", targets=["coc"], skeletons=["cc5"], injuries=gore)
    assert schemas.validate_character_spec(brutal) == []


def test_example_injuries_are_honest_at_pg():
    """A pg export keeps the TRUE kind: the bandaged cut stays a cut (was exported a bruise)."""
    ex = schemas.example_injuries()
    assert ex["tier"] == "pg"
    assert any(w["kind"] == "cut" and w["bandaged"] for w in ex["wounds"])
    assert not any("neatly bandaged" in d for d in ex["descriptors"])
