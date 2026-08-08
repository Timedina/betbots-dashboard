"""Testes de caracterização/safety para a camada de execução existente.

Estes testes são deliberadamente independentes da API Betfair. O objetivo é
congelar invariantes importantes antes da refatoração da V2.
"""

import math


def calculate_liability_stake(liability: float, odd: float) -> float:
    """Mesma relação matemática usada pela execução atual: liability/(odd-1)."""
    if odd <= 1:
        raise ValueError("odd must be greater than 1")
    return liability / (odd - 1)


def test_liability_to_stake_basic_case():
    assert math.isclose(calculate_liability_stake(2.0, 3.0), 1.0)


def test_liability_to_stake_preserves_liability_relation():
    liability = 2.0
    odd = 5.0
    stake = calculate_liability_stake(liability, odd)
    assert math.isclose(stake * (odd - 1), liability)


def test_invalid_odd_is_rejected():
    try:
        calculate_liability_stake(2.0, 1.0)
    except ValueError:
        pass
    else:
        raise AssertionError("odds <= 1 devem ser rejeitadas")
