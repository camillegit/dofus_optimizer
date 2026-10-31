import pytest

from src.damage import (Line, Spell, Target, best_rotation, class_spells, gradient, optimize_damage,
                        rotation_damage, spell_damage)
from src.optimizer import Options, build_model
from tests.helpers import make_items, make_panos

FORCE, POWER, DO, CRIT, DOCRI, SPELLS_PCT = ('characteristic_10', 'characteristic_25', 'characteristic_16',
                                              'characteristic_18', 'characteristic_86', 'characteristic_123')


def spell(**kw):
    defaults = dict(id=1, name='Coup', img=None, pa=3, crit=10, max_casts=2, melee=False,
                    lines=[Line('terre', 10, 20, 15, 25)])
    return Spell(**{**defaults, **kw})


def test_spell_damage_formula():
    d = spell_damage(spell(), {FORCE: 100, DO: 5, DOCRI: 10, CRIT: 40})
    assert d['normal'] == (25, 45)                    # 10*2+5, 20*2+5
    assert d['critique'] == (45, 65)                  # 15*2+5+10, 25*2+5+10
    assert d['chance_critique'] == pytest.approx(0.5)
    assert d['esperance'] == pytest.approx(0.5 * 35 + 0.5 * 55)


def test_multiplier_and_resistances():
    target = Target('cible', {'terre': (50, 5)})
    d = spell_damage(spell(crit=0), {FORCE: 100, SPELLS_PCT: 10}, target)
    # (20 * 1.1 - 5) * 0.5 = 8.5 ; (40 * 1.1 - 5) * 0.5 = 19.5
    assert d['normal'] == pytest.approx((8.5, 19.5))
    assert d['chance_critique'] == 0


def test_rotation_knapsack():
    a = spell(id=1, pa=3, max_casts=2, lines=[Line('terre', 100, 100, 100, 100)], crit=0)
    b = spell(id=2, pa=4, max_casts=1, lines=[Line('terre', 150, 150, 150, 150)], crit=0)
    assert best_rotation([a, b], {}, 7) == {1: 1, 2: 1}
    assert best_rotation([a, b], {}, 6) == {1: 2}


def test_gradient_is_exact_partial_derivative():
    s = spell(crit=0)
    grad = gradient([s], {1: 2}, {FORCE: 100})
    assert grad[FORCE] == pytest.approx(2 * 15 / 100)     # 2 casts * average base / 100
    assert grad[POWER] == pytest.approx(grad[FORCE])
    assert grad['characteristic_16'] == pytest.approx(2)


def test_feca_spells():
    spells = {s.name: s for s in class_spells(1, 200)}
    assert spells['Retour du Bâton'].elements == ['terre']
    assert spells['Langueur'].main_element == 'feu'
    assert all(s.pa > 0 for s in spells.values())


def test_optimize_damage_picks_best_exact_damage():
    # 7 base PA: 2 casts. Force hat: 0.5*16 + 0.5*96 = 56 per cast ; critical hat (100%): 60 per cast
    s = spell(crit=50, max_casts=3, lines=[Line('terre', 10, 10, 60, 60)])
    items = make_items([
        {'id': 1, 'type': 16, FORCE: 60},
        {'id': 2, 'type': 16, CRIT: 50},
    ])
    model = build_model(items, make_panos([{'id': 0}]), Options(pa=0, pm=0))
    best = optimize_damage(model, [s], 7)
    assert best.result.items == [2]
    assert best.rotation == {1: 2}
    assert best.damage == pytest.approx(120)
