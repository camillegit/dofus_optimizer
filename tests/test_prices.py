import pytest

from src.optimizer import Options, build_model, pareto_front, solve
from src.prices import load_owned, load_prices
from tests.helpers import make_items, make_panos

FORCE, PA = 'characteristic_10', 'characteristic_1'


def items():
    return make_items([
        {'id': 1, 'type': 16, 'nom': 'Coiffe chère', FORCE: 100},
        {'id': 2, 'type': 16, 'nom': 'Coiffe moyenne', FORCE: 60},
        {'id': 3, 'type': 16, 'nom': 'Coiffe gratuite', FORCE: 10},
        {'id': 4, 'type': 17, 'nom': 'Cape', FORCE: 50},
    ])


@pytest.fixture
def price_file(tmp_path):
    path = tmp_path / 'prix.csv'
    path.write_text("nom;prix\nCoiffe chère;1 000 000\ncoiffe MOYENNE;200000\nCape;300000\nexo pa;5000000\nInconnu;3\n",
                    encoding='utf-8')
    return path


def model_with(prices, **opts):
    return build_model(items(), make_panos([{'id': 0}]), Options(pa=0, pm=0, prices=prices, **opts))


def test_load_prices(price_file):
    prices, exo_prices, unmatched = load_prices(price_file, items())
    assert prices == {1: 1_000_000, 2: 200_000, 4: 300_000}
    assert exo_prices == {PA: 5_000_000}
    assert unmatched == ['Inconnu']


def test_budget(price_file):
    prices, _, _ = load_prices(price_file, items())
    result = solve(model_with(prices, weights={FORCE: 1}, budget=600_000))
    assert sorted(result.items) == [2, 4] and result.cost == 500_000
    result = solve(model_with(prices, weights={FORCE: 1}, budget=600_000, owned={1}))
    assert sorted(result.items) == [1, 4] and result.cost == 300_000


def test_unknown_price_excluded(price_file):
    prices, _, _ = load_prices(price_file, items())
    result = solve(model_with(prices, weights={FORCE: 1}, budget=0, unknown_price='exclure'))
    assert result.items == []
    result = solve(model_with(prices, weights={FORCE: 1}, budget=0))
    assert result.items == [3]


def test_exo_cost(price_file):
    prices, exo_prices, _ = load_prices(price_file, items())
    model = build_model(items(), make_panos([{'id': 0}]),
                        Options(pa=8, pm=0, prices=prices, exo_prices=exo_prices, exos=[PA], weights={FORCE: 1}))
    assert solve(model).cost == 1_300_000 + 5_000_000


def test_pareto_front(price_file):
    prices, _, _ = load_prices(price_file, items())
    model = model_with(prices, weights={FORCE: 1})
    front = pareto_front(model, 6, lambda: solve(model), lambda r: r.objective)
    costs = [c for c, _, _ in front]
    values = [v for _, v, _ in front]
    assert costs == sorted(costs, reverse=True) and values == sorted(values, reverse=True)
    assert front[0][1] == pytest.approx(150, abs=0.01) and front[-1][0] == 0
    assert 'Budget' not in model.problem.constraints


def test_load_owned(tmp_path):
    path = tmp_path / 'stuff.txt'
    path.write_text("id\n1\nCape\ninconnu\n", encoding='utf-8')
    assert load_owned(path, items()) == {1, 4}
