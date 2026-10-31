import pytest

from src.optimizer import compute_stats, load_data, parse_stat_list
from tests.helpers import make_items, optimize

FORCE, PA = 'characteristic_10', 'characteristic_1'


def test_parse_stat_list():
    assert parse_stat_list(['characteristic_10:200', 'characteristic_13=1.5', 'bad', ':3']) == {
        'characteristic_10': 200.0, 'characteristic_13': 1.5}


def test_slot_limits():
    items = make_items(
        [{'id': i, 'type': 9, FORCE: 10 * i} for i in range(1, 5)]      # 4 rings
        + [{'id': 10 + i, 'type': t, FORCE: 5 - i} for i, t in enumerate([2, 5, 6])]  # 3 weapons
    )
    _, result = optimize(items, weights={FORCE: 1})
    assert sorted(result.items) == [3, 4, 10]


def test_min_pa_and_infeasible():
    items = make_items([
        {'id': 1, 'type': 16, FORCE: 100},
        {'id': 2, 'type': 16, FORCE: 10, PA: 1},
    ])
    _, result = optimize(items, weights={FORCE: 1}, pa=8)
    assert result.items == [2]

    _, result = optimize(items, weights={FORCE: 1}, pa=9)
    assert result.status == 'Infeasible'


def test_level_filter():
    items = make_items([
        {'id': 1, 'type': 16, 'niveau': 150, FORCE: 100},
        {'id': 2, 'type': 16, 'niveau': 50, FORCE: 10},
    ])
    _, result = optimize(items, weights={FORCE: 1}, max_level=100)
    assert result.items == [2]


@pytest.fixture(scope='module')
def real_data():
    return load_data()


def test_real_data_force_puissance(real_data):
    model, result = optimize(*real_data, weights={FORCE: 1, 'characteristic_25': 1}, pa=12, pm=6)
    assert result.status == 'Optimal'
    stats = compute_stats(model, result, [PA, 'characteristic_23'])
    assert stats[PA] >= 12 and stats['characteristic_23'] >= 6
    assert result.objective > 0
