"""Characteristic ids (DofusDB `/characteristics`), command-line aliases and display names."""
import unicodedata

# id -> (alias, display name)
CHARACTERISTICS = {
    -1: ('degats_arme', "Dégâts de l'arme (lignes de dégâts)"),
    1: ('pa', "PA"),
    10: ('force', "Force"),
    11: ('vitalite', "Vitalité"),
    12: ('sagesse', "Sagesse"),
    13: ('chance', "Chance"),
    14: ('agilite', "Agilité"),
    15: ('intelligence', "Intelligence"),
    16: ('dommages', "Dommages"),
    18: ('critique', "% Critique"),
    19: ('portee', "Portée"),
    23: ('pm', "PM"),
    25: ('puissance', "Puissance"),
    26: ('invocations', "Invocations"),
    27: ('esquive_pa', "Esquive PA"),
    28: ('esquive_pm', "Esquive PM"),
    33: ('res_terre_pct', "% Résistance Terre"),
    34: ('res_feu_pct', "% Résistance Feu"),
    35: ('res_eau_pct', "% Résistance Eau"),
    36: ('res_air_pct', "% Résistance Air"),
    37: ('res_neutre_pct', "% Résistance Neutre"),
    40: ('pods', "Pods"),
    44: ('initiative', "Initiative"),
    48: ('prospection', "Prospection"),
    49: ('soins', "Soins"),
    50: ('renvoi', "Dommages renvoyés"),
    54: ('res_terre', "Résistance Terre"),
    55: ('res_feu', "Résistance Feu"),
    56: ('res_eau', "Résistance Eau"),
    57: ('res_air', "Résistance Air"),
    58: ('res_neutre', "Résistance Neutre"),
    69: ('puissance_pieges', "Puissance Pièges"),
    70: ('dommages_pieges', "Dommages Pièges"),
    78: ('fuite', "Fuite"),
    79: ('tacle', "Tacle"),
    82: ('retrait_pa', "Retrait PA"),
    83: ('retrait_pm', "Retrait PM"),
    84: ('dommages_poussee', "Dommages Poussée"),
    85: ('res_poussee', "Résistance Poussée"),
    86: ('dommages_critiques', "Dommages Critiques"),
    87: ('res_critiques', "Résistance Critiques"),
    88: ('dommages_terre', "Dommages Terre"),
    89: ('dommages_feu', "Dommages Feu"),
    90: ('dommages_eau', "Dommages Eau"),
    91: ('dommages_air', "Dommages Air"),
    92: ('dommages_neutre', "Dommages Neutre"),
    120: ('dommages_distance_pct', "% Dommages distance"),
    121: ('res_distance_pct', "% Résistance distance"),
    122: ('dommages_armes_pct', "% Dommages d'armes"),
    123: ('dommages_sorts_pct', "% Dommages aux sorts"),
    124: ('res_melee_pct', "% Résistance mêlée"),
    125: ('dommages_melee_pct', "% Dommages mêlée"),
    140: ('taille', "Taille (%)"),
}

SHORT_ALIASES = {
    'vita': 11, 'sage': 12, 'agi': 14, 'intel': 15, 'do': 16, 'crit': 18, 'po': 19,
    'pui': 25, 'invo': 26, 'ini': 44, 'prospe': 48, 'docri': 86,
}


def _normalize(text):
    text = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode()
    return text.lower().strip().replace(' ', '_').replace('-', '_')


ALIASES = {_normalize(alias): cid for cid, (alias, _) in CHARACTERISTICS.items()}
ALIASES.update({_normalize(name): cid for cid, (_, name) in CHARACTERISTICS.items()})
ALIASES.update(SHORT_ALIASES)


def column(char_id):
    return f"characteristic_{char_id}"


def resolve(key):
    """'force', 'Vitalité', 'vita', '10' or 'characteristic_10' -> 'characteristic_10'."""
    norm = _normalize(key)
    if norm.startswith('characteristic_'):
        norm = norm[len('characteristic_'):]
    if norm.lstrip('-').isdigit():
        return column(int(norm))
    if norm in ALIASES:
        return column(ALIASES[norm])
    raise ValueError(f"Unknown characteristic {key!r} (see --list-stats)")


def display_name(char):
    char_id = int(char.split('_')[1])
    return CHARACTERISTICS.get(char_id, (None, char))[1]


def stats_table():
    """Markdown table of characteristics: id, alias, name."""
    short = {cid: alias for alias, cid in SHORT_ALIASES.items()}
    lines = ["| ID | Alias | Nom |", "| --- | --- | --- |"]
    for cid, (alias, name) in CHARACTERISTICS.items():
        aliases = f"`{alias}`" + (f", `{short[cid]}`" if cid in short else "")
        lines.append(f"| {cid} | {aliases} | {name} |")
    return "\n".join(lines)
