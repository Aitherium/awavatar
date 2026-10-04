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
