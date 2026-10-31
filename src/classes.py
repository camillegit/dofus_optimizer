"""Access to class data (data/processed/classes.json): characteristic costs and spells."""
import json
from functools import lru_cache
from pathlib import Path

CLASSES_FILE = Path(__file__).resolve().parent.parent / 'data' / 'processed' / 'classes.json'


@lru_cache(maxsize=None)
def load_classes(path=CLASSES_FILE):
    with open(path, encoding='utf-8') as f:
        return {int(k): v for k, v in json.load(f).items()}


def get_class(breed_id):
    return load_classes()[breed_id]


def spell_level(spell, character_level):
    """Highest grade of a spell available at a character level (None if not learnt yet)."""
    available = [lv for lv in spell['niveaux'] if lv['niveau_min'] <= character_level]
    return available[-1] if available else None
