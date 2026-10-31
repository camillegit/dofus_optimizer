import pytest

from src import conditions
from src.optimizer import Options, build_model, load_data, solve, violated_conditions
from tests.helpers import make_items, make_panos, optimize

FORCE, AGI, PA = 'characteristic_10', 'characteristic_14', 'characteristic_1'


# --- parser / evaluator ---------------------------------------------------------------

def test_parse_precedence_and_parentheses():
    assert conditions.parse('CS>1&CI>2|CA>3') == (
        'or', [('and', [('atom', 'CS', '>', '1'), ('atom', 'CI', '>', '2')]), ('atom', 'CA', '>', '3')])
    assert conditions.parse('CV>1499&(CP<12|CM<6)') == (
        'and', [('atom', 'CV', '>', '1499'), ('or', [('atom', 'CP', '<', '12'), ('atom', 'CM', '<', '6')])])
    assert conditions.parse('') is None and conditions.parse(None) is None


def test_parse_errors():
    with pytest.raises(conditions.ConditionSyntaxError):
        conditions.parse('(CS>1')


def test_evaluate():
    tree = conditions.parse('CS>249|CA>199')
    assert conditions.evaluate(tree, {FORCE: 250}, {}, 0)
    assert not conditions.evaluate(tree, {FORCE: 249, AGI: 199}, {}, 0)
    assert conditions.evaluate(conditions.parse('pk<2&PJ>2,40'), {}, {}, 1)
    assert not conditions.evaluate(conditions.parse('pk<2'), {}, {}, 2)
    assert conditions.unmodelled_atoms(conditions.parse('PJ>2,40|CS>1')) == ['PJ>2,40']


# --- model ----------------------------------------------------------------------------

def test_stat_condition_not_reachable():
    items = make_items([
        {'id': 1, 'type': 7, FORCE: 100, 'condition': 'CS>999'},
        {'id': 2, 'type': 6, FORCE: 50},
    ])
    _, result = optimize(items, weights={FORCE: 1})
    assert result.items == [2]


def test_stat_condition_reachable_with_other_items():
    items = make_items([
        {'id': 1, 'type': 7, FORCE: 100, 'condition': 'CS>249'},
        {'id': 2, 'type': 16, FORCE: 120},
        {'id': 3, 'type': 16, FORCE: 140},
    ])
    # 100 + 140 = 240 < 250: the weapon is not wearable
    assert optimize(items, weights={FORCE: 1})[1].items == [3]
    items.loc[items['id'] == 3, FORCE] = 160
    _, result = optimize(items, weights={FORCE: 1})
    assert sorted(result.items) == [1, 3]


def test_or_condition():
    items = make_items([
        {'id': 1, 'type': 7, FORCE: 100, 'condition': 'CS>499|CA>99'},
        {'id': 2, 'type': 16, AGI: 100},
    ])
    # Only the Agility branch holds (the former implementation required both)
    _, result = optimize(items, weights={FORCE: 1})
    assert sorted(result.items) == [1, 2]
    _, result = optimize(items, weights={FORCE: 1}, base_stats={AGI: -100})
    assert 1 not in result.items


def test_base_stat_condition():
    items = make_items([{'id': 1, 'type': 16, FORCE: 10, 'condition': 'Cs>99'}])
    assert optimize(items, weights={FORCE: 1})[1].items == []
    assert optimize(items, weights={FORCE: 1}, base_stats={FORCE: 100})[1].items == [1]


def test_not_equal_condition():
    items = make_items([
        {'id': 1, 'type': 16, FORCE: 10, PA: 1, 'condition': 'CP!8'},
    ])
    assert optimize(items, weights={FORCE: 1}, base_stats={PA: 7})[1].items == []
    assert optimize(items, weights={FORCE: 1}, base_stats={PA: 6})[1].items == [1]


def test_unmodelled_condition_is_permissive():
    items = make_items([{'id': 1, 'type': 16, FORCE: 10, 'condition': 'PJ>2,40&Qa=123'}])
    assert optimize(items, weights={FORCE: 1})[1].items == [1]


def test_set_bonus_condition_counts_all_bonuses():
    # Two 2-piece sets = 2 set bonuses: incompatible with a 'pk<2' trophy.
    items = make_items([
        {'id': 1, 'type': 16, 'pano': 1, FORCE: 30}, {'id': 2, 'type': 17, 'pano': 1, FORCE: 30},
        {'id': 3, 'type': 11, 'pano': 2, FORCE: 30}, {'id': 4, 'type': 10, 'pano': 2, FORCE: 30},
        {'id': 5, 'type': 151, FORCE: 25, 'condition': 'pk<2'},
    ])
    panos = make_panos([{'id': 1, f'bonus_2_{FORCE}': 10}, {'id': 2, f'bonus_2_{FORCE}': 10}])
    _, result = optimize(items, panos, weights={FORCE: 1})
    # 4 pieces + 2 bonuses = 140 > 3 pieces + 1 bonus + trophy = 125
    assert sorted(result.items) == [1, 2, 3, 4]

    # With a malus on set 2, the trophy is worth it: one set bonus only (pk = 1)
    panos = make_panos([{'id': 1, f'bonus_2_{FORCE}': 10}, {'id': 2, f'bonus_2_{FORCE}': -20}])
    _, result = optimize(items, panos, weights={FORCE: 1})
    assert 5 in result.items and len(result.items) == 4 and result.bonuses == [(1, 2)]


def test_class_condition():
    items = make_items([
        {'id': 1, 'type': 6, FORCE: 100, 'condition': 'PG=6&PS=0'},
        {'id': 2, 'type': 7, FORCE: 50},
    ])
    assert optimize(items, weights={FORCE: 1})[1].items == [1]            # class unknown: permissive
    assert optimize(items, weights={FORCE: 1}, breed=8)[1].items == [2]   # Iop
    assert optimize(items, weights={FORCE: 1}, breed=6)[1].items == [1]   # Ecaflip
    assert conditions.class_id('Écaflip') == conditions.class_id('6') == 6
    with pytest.raises(ValueError):
        conditions.class_id('paladin')


# --- real data ------------------------------------------------------------------------

SCENARIOS = [
    dict(weights={FORCE: 1, 'characteristic_25': 1}, pa=12, pm=6),
    dict(max_level=100, pa=10, pm=5, weights={FORCE: 1, 'characteristic_11': 0.5}),
    dict(max_level=150, no_dofus=True, weights={'characteristic_15': 1, 'characteristic_18': 5, 'characteristic_19': 20}),
    dict(weights={AGI: 1, 'characteristic_13': 1}, pa=11, pm=6),
    dict(weights={'characteristic_11': 1}, pa=12, pm=6, min_stats={FORCE: 400}),
]


@pytest.fixture(scope='module')
def real_data():
    return load_data()


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_real_data_conditions_hold(real_data, scenario):
    model = build_model(*real_data, Options(**scenario))
    result = solve(model)
    assert result.status == 'Optimal'
    assert violated_conditions(model, result) == []


def test_real_data_regression_mama_ayuto(real_data):
    # Previously selected: Rouleau de Mama Ayuto (CS>999) with 820 Force, Enragé majeur (pk<2) with 3 bonuses
    model = build_model(*real_data, Options(**SCENARIOS[0]))
    result = solve(model)
    assert 30859 not in result.items
    if 16196 in result.items:
        assert sum(k - 1 for _, k in result.bonuses) < 2
