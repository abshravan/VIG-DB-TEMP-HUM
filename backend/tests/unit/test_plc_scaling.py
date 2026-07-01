import pytest

from app.plc.scaling import scale_raw_to_engineering


def test_scale_midpoint():
    assert scale_raw_to_engineering(13824, 0, 27648, 0, 50) == pytest.approx(25.0)


def test_scale_endpoints():
    assert scale_raw_to_engineering(0, 0, 27648, 0, 50) == pytest.approx(0.0)
    assert scale_raw_to_engineering(27648, 0, 27648, 0, 50) == pytest.approx(50.0)


def test_scale_rejects_zero_span():
    with pytest.raises(ValueError, match="must differ"):
        scale_raw_to_engineering(5, 10, 10, 0, 100)
