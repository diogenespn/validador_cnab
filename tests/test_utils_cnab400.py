import datetime

import pytest

from validators.cnab400.utils import _parse_data_cnab400, _parse_valor_cnab400


@pytest.mark.parametrize(
    "valor, esperado",
    [
        ("150224", datetime.datetime(2024, 2, 15)),
        ("320299", None),
        ("000000", None),
        ("", None),
    ],
)
def test_parse_data_cnab400(valor, esperado):
    assert _parse_data_cnab400(valor) == esperado


@pytest.mark.parametrize(
    "raw, esperado",
    [
        ("", 0),
        ("12345", 12345),
        ("12A45", None),
    ],
)
def test_parse_valor_cnab400(raw, esperado):
    assert _parse_valor_cnab400(raw) == esperado
