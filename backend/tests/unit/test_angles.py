from vedic_engine.angles import arc, deg_in_sign, dms, nak_of, norm, sign_of


def test_wrap_and_edges() -> None:
    assert norm(360.0) == 0
    assert norm(-1e-12) == 0
    assert norm(-1e-12) < 360
    assert sign_of(359.9999999) == 11
    assert nak_of(359.9999999) == (26, 4)
    assert sign_of(29.999999999) == 0
    assert sign_of(30.0) == 1
    assert nak_of(40 / 3) == (1, 1)


def test_helpers() -> None:
    assert arc(350.0, 10.0) == 20.0
    assert deg_in_sign(45.5) == 15.5
    assert dms(10.5) == (10, 30, 0.0)
