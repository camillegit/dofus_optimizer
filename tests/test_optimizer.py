import pytest

from src.characteristics import resolve
from src.optimizer import compute_stats, load_data, parse_stat_list
from tests.helpers import make_items, optimize

FORCE, PA = 'characteristic_10', 'characteristic_1'


def test_parse_stat_list():
    assert parse_stat_list(['characteristic_10:200', 'chance=1.5', 'Vitalité:2', 'vita:3', 'pa:1']) == {
        FORCE: 200.0, 'characteristic_13': 1.5, 'characteristic_11': 3.0, PA: 1.0}
    for bad in (['bad'], [':3'], ['forse:1'], ['force:x']):
        with pytest.raises(ValueError):
            parse_stat_list(bad)


def test_resolve_characteristics():
    assert resolve('Agilité') == resolve('agi') == resolve('14') == resolve('characteristic_14') == 'characteristic_14'
    assert resolve('% Critique') == resolve('crit') == 'characteristic_18'


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


def test_highs_matches_cbc(real_data):
    pytest.importorskip('highspy')
    from src.optimizer import Options, build_model, solve
    opts = dict(max_level=100, pa=10, pm=5, weights={FORCE: 1, 'characteristic_11': 0.5})
    objectives = {s: solve(build_model(*real_data, Options(**opts)), solver=s).objective for s in ('cbc', 'highs')}
    assert objectives['cbc'] == pytest.approx(objectives['highs'])
