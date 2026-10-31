from tests.helpers import make_items, optimize

FORCE, PA, PM = 'characteristic_10', 'characteristic_1', 'characteristic_23'


def items():
    return make_items([
        {'id': 1, 'type': 16, FORCE: 100},            # hat
        {'id': 2, 'type': 16, FORCE: 40, PA: 1},      # hat with PA
        {'id': 3, 'type': 17, FORCE: 80},             # cape
        {'id': 4, 'type': 82, FORCE: 30},             # shield: no exo
    ])


def test_exo_replaces_a_pa_item():
    # 7 base PA, 8 required: without exo the PA hat is needed
    assert sorted(optimize(items(), weights={FORCE: 1}, pa=8)[1].items) == [2, 3, 4]
    _, result = optimize(items(), weights={FORCE: 1}, pa=8, exos=[PA])
    assert sorted(result.items) == [1, 3, 4] and len(result.exos) == 1


def test_one_exo_per_item_and_max():
    # +2 PA and +1 PM needed, only the hat and the cape accept exos: PA hat + exo PM + exo PA on the cape
    _, result = optimize(items(), weights={FORCE: 1}, pa=9, pm=4, exos=[PA, PM])
    assert sorted(result.items) == [2, 3, 4]
    assert sorted(result.exos) == [(2, PM), (3, PA)]
    _, result = optimize(items(), weights={FORCE: 1}, pa=9, pm=4, exos=[PA, PM], max_exos=1)
    assert result.status == 'Infeasible'


def test_no_exo_on_native_stat():
    _, result = optimize(items(), weights={PA: 1}, exos=[PA])
    assert (2, PA) not in result.exos
