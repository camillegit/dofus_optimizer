import pytest

from src.optimizer import point_segments
from tests.helpers import make_items, optimize

FORCE, VITA = 'characteristic_10', 'characteristic_11'
FECA = 1
ITEMS = make_items([{'id': 1, 'type': 16, FORCE: 0}])


def test_point_segments():
    assert point_segments([[0, 1], [100, 2], [200, 3]]) == [(100, 1), (100, 2), (None, 3)]


def test_points_follow_cost_tiers():
    # Level 101: 500 points. Force: 100 (100 pts) + 100 (200 pts) + 66 (198 pts) = 266
    _, result = optimize(ITEMS, weights={FORCE: 1}, breed=FECA, points=True, max_level=101)
    assert result.points[FORCE] == 266


def test_points_marginal_value():
    # Beyond 200 Force a point is worth 1/3 Force < 0.4 for Vitality (1:1)
    _, result = optimize(ITEMS, weights={FORCE: 1, VITA: 0.4}, breed=FECA, points=True, max_level=101)
    assert result.points[FORCE] == 200 and result.points[VITA] == 200


def test_scrolls_and_base_condition():
    items = make_items([{'id': 1, 'type': 16, VITA: 60, 'condition': 'Cs>149'}])
    # Scrolls only: base Force 100, item unavailable
    assert optimize(items, weights={VITA: 1}, scrolls=100)[1].items == []
    # 50 points to reach 150 base Force: 50 Vitality from points + 60 from the item > 100 from points
    model, result = optimize(items, weights={VITA: 1}, scrolls=100, breed=FECA, points=True, max_level=21)
    assert result.items == [1] and result.points[FORCE] == 50 and result.points[VITA] == 50


def test_points_require_class():
    with pytest.raises(ValueError):
        optimize(ITEMS, weights={FORCE: 1}, points=True)
