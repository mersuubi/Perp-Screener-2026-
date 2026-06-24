"""Юнит-тесты контрактов API (без БД). Запускаются в CI."""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# делаем api/ импортируемым
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import ScreenerFilter, ScreenerRequest  # noqa: E402


def test_valid_filter():
    f = ScreenerFilter(field="volume_zscore", op=">", value=3)
    assert f.field == "volume_zscore"
    assert f.op == ">"
    assert f.value == 3


def test_rejects_unknown_field():
    # Защита: поле не из белого списка не должно пройти валидацию.
    with pytest.raises(ValidationError):
        ScreenerFilter(field="DROP TABLE ohlcv", op=">", value=1)


def test_rejects_unknown_operator():
    with pytest.raises(ValidationError):
        ScreenerFilter(field="ret_1h", op="LIKE", value=1)


def test_screener_request_defaults_empty():
    req = ScreenerRequest()
    assert req.filters == []
    assert req.preset is None


def test_screener_request_parses_filters():
    req = ScreenerRequest(
        preset="volume_spike",
        filters=[
            {"field": "volume_zscore", "op": ">", "value": 3},
            {"field": "ret_1h", "op": ">=", "value": 0.05},
        ],
    )
    assert len(req.filters) == 2
    assert req.filters[1].op == ">="
