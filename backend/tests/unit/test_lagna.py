from vedic_engine.lagna import bhava_rashis, house_of


def test_bhava_rashis_karka() -> None:
    # 95 deg sidereal is 5 deg Karka (rashi index 3): whole-sign houses start there.
    assert bhava_rashis(95.0) == (3, 4, 5, 6, 7, 8, 9, 10, 11, 0, 1, 2)


def test_bhava_rashis_sign_boundaries() -> None:
    assert bhava_rashis(0.0)[0] == 0
    assert bhava_rashis(29.9999)[0] == 0
    assert bhava_rashis(30.0)[0] == 1
    assert bhava_rashis(359.9999) == (11, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)


def test_house_of() -> None:
    assert house_of(3, 3) == 1
    assert house_of(4, 3) == 2
    assert house_of(2, 3) == 12
    assert house_of(9, 3) == 7
    for lagna in range(12):
        houses = bhava_rashis(lagna * 30.0 + 1.0)
        assert [house_of(r, lagna) for r in houses] == list(range(1, 13))
