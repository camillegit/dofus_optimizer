from src.classes import get_class, load_classes, spell_level
from src.conditions import CLASSES


def test_all_classes_present():
    assert set(load_classes()) == set(CLASSES.values())


def test_feca():
    feca = get_class(1)
    assert feca['nom'] == 'Féca'
    assert feca['couts']['characteristic_10'] == [[0, 1], [100, 2], [200, 3], [300, 4]]
    assert feca['couts']['characteristic_12'] == [[0, 3]]
    spell = next(s for s in feca['sorts'] if s['nom'] == 'Retour du Bâton')
    assert spell_level(spell, 1) is None or spell_level(spell, 1)['grade'] == 1
    top = spell_level(spell, 200)
    assert top['pa'] == 3 and any(e['effet'] == 97 for e in top['effets'])
