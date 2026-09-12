from remoteid_sensor.astm.cta2063a import parse_serial


def test_valid_serial_splits_into_manufacturer_and_serial():
    s = parse_serial("1596F123456789ABCDEF")
    assert s.valid, s.problems
    assert s.manufacturer_code == "1596"
    assert s.declared_length == 15
    assert s.manufacturer_serial == "123456789ABCDEF"


def test_numeric_length_code():
    s = parse_serial("ABCD5XYZ12")
    assert s.valid, s.problems
    assert s.manufacturer_code == "ABCD"
    assert s.declared_length == 5
    assert s.manufacturer_serial == "XYZ12"


def test_length_mismatch_is_reported_not_raised():
    s = parse_serial("ABCD9XYZ")
    assert not s.valid
    assert any("declared length 9" in p for p in s.problems)
    assert s.raw == "ABCD9XYZ"


def test_excluded_characters_flagged():
    s = parse_serial("ABCD3IOQ")
    assert not s.valid
    assert any("excluded characters" in p for p in s.problems)


def test_invalid_serial_still_preserves_raw():
    """A validator must never destroy evidence it merely disagrees with."""
    s = parse_serial("!!not-a-serial!!")
    assert not s.valid
    assert s.raw == "!!not-a-serial!!"
    assert s.as_record()["raw"] == "!!not-a-serial!!"


def test_empty_serial():
    s = parse_serial("")
    assert not s.valid
    assert "empty" in s.problems


def test_too_short_serial():
    s = parse_serial("AB1")
    assert not s.valid
    assert any("too short" in p for p in s.problems)
