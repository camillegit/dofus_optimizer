import pytest

from tests.helpers import make_items, make_panos, optimize

FORCE, VITA = 'characteristic_10', 'characteristic_11'


def three_piece_set():
    """Set 7: 3 pieces (10 Force each); tier 2 gives +50 Force, tier 3 trades it for Vitality."""
    items = make_items([
        {'id': 1, 'type': 16, 'pano': 7, FORCE: 10},
        {'id': 2, 'type': 17, 'pano': 7, FORCE: 10},
        {'id': 3, 'type': 11, 'pano': 7, FORCE: 10},
        {'id': 4, 'type': 11, FORCE: 5},               # out-of-set boots
    ])
    panos = make_panos([{'id': 7, f'bonus_2_{FORCE}': 50, f'bonus_3_{VITA}': 100}])
    return items, panos


def test_tier_three_replaces_tier_two():
    # Wearing the 3 pieces gives only the tier-3 bonus (no Force): 2 pieces + other boots is better.
    items, panos = three_piece_set()
    model, result = optimize(items, panos, weights={FORCE: 1})
    assert result.objective == 75
    assert sorted(result.items) == [1, 2, 4]
    assert result.bonuses == [(7, 2)]


def test_active_tier_matches_items_worn():
    items, panos = three_piece_set()
    model, result = optimize(items, panos, weights={VITA: 1, FORCE: 0.01})
    assert sorted(result.items) == [1, 2, 3]
    assert result.bonuses == [(7, 3)]
    assert result.objective == pytest.approx(100.3)


def test_negative_bonus_cannot_be_skipped():
    # A malus tier is imposed as soon as the pieces are worn.
    items = make_items([
        {'id': 1, 'type': 16, 'pano': 8, FORCE: 40},
        {'id': 2, 'type': 17, 'pano': 8, FORCE: 40},
    ])
    panos = make_panos([{'id': 8, f'bonus_2_{FORCE}': -60}])
    _, result = optimize(items, panos, weights={FORCE: 1})
    assert len(result.items) == 1 and result.objective == 40
