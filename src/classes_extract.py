"""Extracts classes (breeds): characteristic point costs and class spells, into data/processed/classes.json."""
import json

from .config import BASE_URL, CLASSES_FILE, PROCESSED_DIR
from .utils import fetch_all

STAT_COST_FIELDS = {
    'statsPointsForStrength': 'characteristic_10',
    'statsPointsForIntelligence': 'characteristic_15',
    'statsPointsForChance': 'characteristic_13',
    'statsPointsForAgility': 'characteristic_14',
    'statsPointsForVitality': 'characteristic_11',
    'statsPointsForWisdom': 'characteristic_12',
}


def parse_effect(effect):
    low, high = effect.get('diceNum', 0), effect.get('diceSide', 0)
    return {
        'effet': effect.get('effectId'),
        'min': low,
        'max': max(low, high),
        'duree': effect.get('duration', 0),
        'declencheurs': effect.get('triggers'),
        'cibles': effect.get('targetMask'),
    }


def parse_level(level):
    return {
        'grade': level['grade'],
        'niveau_min': level.get('minPlayerLevel', 0),
        'pa': level.get('apCost'),
        'po_min': level.get('minRange'),
        'po_max': level.get('range'),
        'crit': level.get('criticalHitProbability', 0),
        'lancers_par_tour': level.get('maxCastPerTurn', 0),
        'lancers_par_cible': level.get('maxCastPerTarget', 0),
        'intervalle': level.get('minCastInterval', 0),
        'effets': [parse_effect(e) for e in level.get('effects', [])],
        'effets_critiques': [parse_effect(e) for e in level.get('criticalEffect', [])],
    }


def chunks(values, size=40):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def extract_classes():
    breeds = fetch_all(f"{BASE_URL}/breeds", desc="Fetching classes")
    spell_ids = sorted({sid for b in breeds for sid in b.get('breedSpellsId', [])})

    spells, levels = {}, {}
    for ids in chunks(spell_ids):
        params = [("id[$in][]", i) for i in ids]
        for spell in fetch_all(f"{BASE_URL}/spells", params, desc="Fetching spells"):
            spells[spell['id']] = spell
        params = [("spellId[$in][]", i) for i in ids]
        for level in fetch_all(f"{BASE_URL}/spell-levels", params, desc="Fetching spell levels"):
            levels.setdefault(level['spellId'], []).append(parse_level(level))

    classes = {}
    for breed in breeds:
        classes[breed['id']] = {
            'id': breed['id'],
            'nom': breed['shortName']['fr'],
            'img': breed.get('img'),
            'couts': {char: breed.get(field, [[0, 1]]) for field, char in STAT_COST_FIELDS.items()},
            'sorts': [
                {
                    'id': sid,
                    'nom': spells[sid]['name']['fr'],
                    'img': spells[sid].get('img'),
                    'niveaux': sorted(levels.get(sid, []), key=lambda lv: lv['grade']),
                }
                for sid in breed.get('breedSpellsId', []) if sid in spells
            ],
        }

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    CLASSES_FILE.write_text(json.dumps(classes, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f"Saved {len(classes)} classes and {len(spells)} spells to {CLASSES_FILE}")


if __name__ == "__main__":
    extract_classes()
