import json

from src.build import BuildRequest, build, element_spells


def test_feca_element_groups():
    groups = element_spells(1, 200)
    assert set(groups) == {'terre', 'feu', 'eau', 'air', 'multi'}
    assert {s.name for s in groups['terre']} >= {'Retour du Bâton', 'Torpeur'}


def test_build_top_two_diverse_builds():
    report = build(BuildRequest('feca', elements=['terre'], top=2, diversite=3), parallel=False)
    json.dumps(report)                                  # serializable for the web interface
    first, second = report['builds']
    assert first['degats_par_tour'] >= second['degats_par_tour'] > 0
    assert len({i['id'] for i in first['items']} - {i['id'] for i in second['items']}) >= 3
    assert first['conditions_ok'] and second['conditions_ok']
    assert first['stats']['PA'] >= 11 and first['stats']['PM'] >= 6
    assert any(s['lancers'] for s in first['sorts'])
