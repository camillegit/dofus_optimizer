import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from pulp import LpMaximize, LpProblem, LpStatus, LpVariable, PULP_CBC_CMD, lpSum

DATA_PROCESSED_DIR = Path(__file__).resolve().parent.parent / 'data' / 'processed'

CHAR_ID_TO_NAME = {
    -1: "dommages Neutre", 10: "Force", 88: "Dommages Terre", 11: "Vitalité",
    92: "Dommages Neutre", 15: "Intelligence", 78: "Fuite", 0: "Arme de chasse",
    18: "% Critique", 14: "Agilité", 79: "Tacle", 23: "PM", 49: "Soins",
    91: "Dommages Air", 12: "Sagesse", 13: "Chance", 48: "Prospection",
    90: "Dommages Eau", 1: "PA", 44: "Initiative", 19: "Portée",
    89: "Dommages Feu", 16: "Dommages", 25: "Puissance", 86: "Dommages Critiques",
    87: "Résistances Critiques", 33: "% Résistance Terre", 26: "Invocations",
    84: "Dommages Poussée", 37: "% Résistance Neutre", 82: "Retrait PA",
    83: "Retrait PM", 34: "% Résistance Feu", 35: "% Résistance Eau",
    36: "% Résistance Air", 58: "Résistances Neutre", 54: "Résistances Terre",
    55: "Résistances Feu", 56: "Résistances Eau", 57: "Résistances Air",
    28: "Esquive PM", 85: "Résistances Poussée", 40: "Pods", 27: "Esquive PA",
    69: "Puissance Pièges", 70: "Dommages Pièges", 50: "Dommages Renvoyés",
    124: "% Résistance mêlée", 121: "% Résistance distance",
    122: "Dommages d'armes", 123: "Dommages aux sorts"
}

EQUIP_TYPES_MAP = {
    16: "Chapeau", 17: "Cape", 9: "Anneau", 1: "Amulette", 3: "Baguette",
    11: "Bottes", 10: "Ceinture", 7: "Marteau", 4: "Bâton", 2: "Arc",
    5: "Dague", 6: "Épée", 19: "Hache", 22: "Faux", 8: "Pelle",
    151: "Trophée", 23: "Dofus", 82: "Boucliers"
}

WEAPON_TYPES = [3, 7, 4, 2, 5, 6, 19, 22, 8]
DOFUS_TROPHY_TYPES = [151, 23]
RING_TYPE = 9
DOFUS_TYPE = 23

BANNED_ITEMS = [2155, 8575, 27265, 27266, 27267, 27268, 27278, 27280, 27282, 27284, 9031, 2447, 6713]

PA, PM = 'characteristic_1', 'characteristic_23'


def load_data(data_dir=DATA_PROCESSED_DIR):
    """Loads items and panoplies data from the data/processed directory."""
    items_df = pd.read_parquet(Path(data_dir) / 'dofus_items_processed.parquet')
    bonuses_df = pd.read_parquet(Path(data_dir) / 'dofus_panos_processed.parquet')

    # Replace NaN values with 0 (except the textual condition column)
    num_cols = items_df.columns.difference(['nom', 'condition'])
    items_df[num_cols] = items_df[num_cols].fillna(0)
    bonuses_df = bonuses_df.fillna(0)
    return items_df, bonuses_df


def parse_stat_list(raw_list):
    """Parses ['characteristic_10:200', 'characteristic_13=100'] into a dict."""
    parsed = {}
    for raw in raw_list:
        if ':' in raw:
            key, value = raw.split(':', 1)
        elif '=' in raw:
            key, value = raw.split('=', 1)
        else:
            continue
        key = key.strip()
        if not key:
            continue
        try:
            parsed[key] = float(value.strip())
        except ValueError:
            continue
    return parsed


@dataclass
class Options:
    min_level: int = 1
    max_level: int = 200
    pa: int = 9
    pm: int = 4
    no_dofus: bool = False
    weights: dict = field(default_factory=dict)
    base_stats: dict = field(default_factory=dict)
    min_stats: dict = field(default_factory=dict)


@dataclass
class Model:
    problem: LpProblem
    items: pd.DataFrame          # filtered items, indexed by id
    bonuses: pd.DataFrame        # panoplies, indexed by id
    item_vars: dict
    bonus_vars: dict             # (set_id, k) -> 1 iff exactly k pieces of the set are worn (k >= 2)
    base_stats: dict
    set_members: dict = field(default_factory=dict)   # set_id -> item ids

    def item_stat(self, char):
        if char not in self.items.columns:
            return {}
        return self.items[char].to_dict()

    def bonus_stat(self, char):
        """(set_id, k) -> cumulative bonus of that tier (tiers are exclusive, not additive)."""
        values = {}
        for (set_id, k) in self.bonus_vars:
            col = f"bonus_{k}_{char}"
            if col in self.bonuses.columns:
                values[(set_id, k)] = self.bonuses.at[set_id, col]
        return values

    def total_stat_expr(self, char):
        item_stat = self.item_stat(char)
        bonus_stat = self.bonus_stat(char)
        return (
            lpSum(var * item_stat.get(i, 0) for i, var in self.item_vars.items())
            + lpSum(var * bonus_stat.get(key, 0) for key, var in self.bonus_vars.items())
            + self.base_stats.get(char, 0)
        )

    def set_bonus_count(self):
        """Number of active set bonuses as counted by the 'pk' condition: sum over sets of (pieces - 1)."""
        return lpSum((k - 1) * var for (_, k), var in self.bonus_vars.items())

    def big_m(self, char):
        total_abs = sum(abs(v) for v in self.item_stat(char).values())
        total_abs += sum(abs(v) for v in self.bonus_stat(char).values())
        total_abs += abs(self.base_stats.get(char, 0))
        return max(100, total_abs + 100)


def filter_items(items_df, opts):
    items_df = items_df[(items_df['niveau'] >= opts.min_level) & (items_df['niveau'] <= opts.max_level)]
    items_df = items_df[~items_df['id'].isin(BANNED_ITEMS)]
    if opts.no_dofus:
        items_df = items_df[items_df['type'] != DOFUS_TYPE]
    return items_df


def add_slot_constraints(model):
    problem, items = model.problem, model.items
    for item_type, group in items.groupby('type'):
        if item_type in WEAPON_TYPES:
            continue
        limit = 1
        if item_type == RING_TYPE:
            limit = 2
        elif item_type in DOFUS_TROPHY_TYPES:
            limit = 6
        problem += lpSum(model.item_vars[i] for i in group.index) <= limit, f"Type_{item_type}_Constraint"

    weapons = items.index[items['type'].isin(WEAPON_TYPES)]
    problem += lpSum(model.item_vars[i] for i in weapons) <= 1, "Grouped_Types_Constraint"

    dofus_trophies = items.index[items['type'].isin(DOFUS_TROPHY_TYPES)]
    problem += lpSum(model.item_vars[i] for i in dofus_trophies) <= 6, "Dofus_Trophy_Combined_Constraint"


def add_set_bonus_constraints(model):
    """Exactly one tier y[s,k] (k = 0..n) is active per set and k equals the number of pieces worn."""
    tiers = defaultdict(dict)
    for (set_id, k), var in model.bonus_vars.items():
        tiers[set_id][k] = var
    for set_id, members in model.set_members.items():
        low = {k: LpVariable(f"bonus_{set_id}_{k}", cat='Binary') for k in (0, 1)}
        set_tiers = {**low, **tiers[set_id]}
        model.problem += lpSum(set_tiers.values()) == 1, f"Bonus_{set_id}_One_Tier"
        model.problem += (
            lpSum(k * var for k, var in set_tiers.items()) == lpSum(model.item_vars[i] for i in members),
            f"Bonus_{set_id}_Pieces"
        )


def add_min_stat_constraints(model, opts):
    model.problem += model.total_stat_expr(PA) >= opts.pa, "Minimum_PA_Constraint"
    model.problem += model.total_stat_expr(PM) >= opts.pm, "Minimum_PM_Constraint"
    for char, minimum in opts.min_stats.items():
        if char in (PA, PM) or char not in model.items.columns:
            continue
        model.problem += model.total_stat_expr(char) >= minimum, f"Minimum_{char}_Constraint"


CONDITION_CODE_TO_CHAR = {
    'W': 'characteristic_12', 'S': 'characteristic_10', 'C': 'characteristic_13',
    'A': 'characteristic_14', 'I': 'characteristic_15', 'P': 'characteristic_1',
    'M': 'characteristic_23', 'V': 'characteristic_11',
}
C_CONDITION_REGEX = re.compile(r'\b(C[A-Za-z0-9]*)\s*(<=|>=|=|<|>)\s*([0-9]+)\b')
PK_CONDITION_REGEX = re.compile(r'\b(Pk)\s*(<=|>=|=|<|>)\s*([0-9]+)\b')
STAT_COND_REGEX = re.compile(r'^C([A-Za-z0-9]+)(<=|>=|=|<|>)(\d+)$')
PK_COND_REGEX = re.compile(r'^(Pk)(<=|>=|=|<|>)(\d+)$')


def extract_conditions(condition_str):
    if not isinstance(condition_str, str):
        return []
    normalized = condition_str.replace("|", "&")
    c_matches = C_CONDITION_REGEX.findall(normalized)
    pk_matches = PK_CONDITION_REGEX.findall(normalized)
    return [f"{var}{op}{val}" for var, op, val in c_matches + pk_matches]


def add_condition_constraints(model):
    problem = model.problem
    condition_to_items = defaultdict(set)
    for item_id, condition_str in model.items['condition'].items():
        for cond in extract_conditions(condition_str):
            condition_to_items[cond].add(item_id)

    for idx, cond in enumerate(sorted(condition_to_items)):
        stat_match = STAT_COND_REGEX.match(cond)
        pk_match = PK_COND_REGEX.match(cond)
        z = LpVariable(f"z_{idx}", cat='Binary')

        if stat_match:
            code, op, value_str = stat_match.groups()
            char = CONDITION_CODE_TO_CHAR.get(code)
            if char is None or char not in model.items.columns:
                continue
            value = int(value_str)
            total = model.total_stat_expr(char)
            M = model.big_m(char)
            if op == '>':
                problem += total >= value + 1 - M * (1 - z), f"Cond_{cond}_min"
            elif op == '>=':
                problem += total >= value - M * (1 - z), f"Cond_{cond}_min"
            elif op == '<':
                problem += total <= value - 1 + M * (1 - z), f"Cond_{cond}_max"
            elif op == '<=':
                problem += total <= value + M * (1 - z), f"Cond_{cond}_max"
            elif op == '=':
                problem += total >= value - M * (1 - z), f"Cond_{cond}_eq_min"
                problem += total <= value + M * (1 - z), f"Cond_{cond}_eq_max"

        elif pk_match:
            _, op, value_str = pk_match.groups()
            value = int(value_str)

            def bonuses_ge(threshold):
                keys = [key for key in model.bonus_vars if key[1] >= threshold]
                return lpSum(model.bonus_vars[key] for key in keys), max(1, len(keys))

            if op == '<':
                total, M = bonuses_ge(value)
                problem += total <= M * (1 - z), f"Cond_{cond}_max"
            elif op == '<=':
                total, M = bonuses_ge(value + 1)
                problem += total <= M * (1 - z), f"Cond_{cond}_max"
            elif op == '>':
                total, M = bonuses_ge(value + 1)
                problem += total >= 1 - M * (1 - z), f"Cond_{cond}_min"
            elif op == '>=':
                total, M = bonuses_ge(value)
                problem += total >= 1 - M * (1 - z), f"Cond_{cond}_min"
            elif op == '=':
                total_lo, M_lo = bonuses_ge(value)
                total_hi, M_hi = bonuses_ge(value + 1)
                problem += total_lo >= 1 - M_lo * (1 - z), f"Cond_{cond}_eq_min"
                problem += total_hi <= M_hi * (1 - z), f"Cond_{cond}_eq_max"
        else:
            continue

        members = [i for i in condition_to_items[cond] if i in model.item_vars]
        if members:
            problem += lpSum(model.item_vars[i] for i in members) <= z * len(members), f"Cond_{cond}_items"


def weighted_objective(model, weights):
    return lpSum(model.total_stat_expr(char) * w for char, w in weights.items()) \
        - sum(model.base_stats.get(char, 0) * w for char, w in weights.items())


def build_model(items_df, bonuses_df, opts):
    items = filter_items(items_df, opts).drop_duplicates('id').set_index('id', drop=False)
    bonuses = bonuses_df.drop_duplicates('id').set_index('id', drop=False)

    item_vars = {i: LpVariable(f"item_{i}", cat='Binary') for i in items.index}

    bonus_vars, set_members = {}, {}
    for set_id, members in items[items['pano'] > 0].groupby('pano').groups.items():
        if set_id not in bonuses.index or len(members) < 2:
            continue
        set_members[set_id] = list(members)
        for k in range(2, len(members) + 1):
            bonus_vars[set_id, k] = LpVariable(f"bonus_{set_id}_{k}", cat='Binary')

    base_stats = dict(opts.base_stats)
    base_stats.setdefault(PA, 7 if opts.max_level >= 100 else 6)
    base_stats.setdefault(PM, 3)

    model = Model(LpProblem("Optimal_Stuff_Combination", LpMaximize), items, bonuses,
                  item_vars, bonus_vars, base_stats, set_members)
    add_slot_constraints(model)
    add_set_bonus_constraints(model)
    add_min_stat_constraints(model, opts)
    add_condition_constraints(model)
    model.problem += weighted_objective(model, opts.weights), "Total_Weighted_Stats"
    return model


@dataclass
class Result:
    status: str
    items: list = field(default_factory=list)       # selected item ids
    bonuses: list = field(default_factory=list)     # selected (set_id, k)
    stats: dict = field(default_factory=dict)       # char -> total value
    objective: float = None


def selected(var):
    return var.value() is not None and var.value() > 0.5


def solve(model, msg=False):
    model.problem.solve(PULP_CBC_CMD(msg=msg))
    status = LpStatus[model.problem.status]
    if status != 'Optimal':
        return Result(status)

    result = Result(status, objective=model.problem.objective.value())
    result.items = [i for i, var in model.item_vars.items() if selected(var)]
    result.bonuses = [key for key, var in model.bonus_vars.items() if selected(var)]
    return result


def compute_stats(model, result, chars):
    totals = {}
    for char in chars:
        item_stat = model.item_stat(char)
        bonus_stat = model.bonus_stat(char)
        totals[char] = (
            sum(item_stat.get(i, 0) for i in result.items)
            + sum(bonus_stat.get(key, 0) for key in result.bonuses)
            + model.base_stats.get(char, 0)
        )
    return totals


def stat_name(char):
    return CHAR_ID_TO_NAME.get(int(char.split('_')[1]), char)


def print_report(model, result, opts, debug_pa_pm=False):
    if result.status != 'Optimal':
        print(f"\nAucune solution trouvée (statut du solveur : {result.status}).")
        return

    print("\nÉquipement optimal:")
    for item_id in result.items:
        item = model.items.loc[item_id]
        print(f"- Item ID: {item_id}, Nom: {item['nom']}, Type: {EQUIP_TYPES_MAP.get(item['type'], 'Unknown Type')}")

    print("\nBonus panoplies:")
    for set_id, k in result.bonuses:
        print(f"- Panoplie: {model.bonuses.at[set_id, 'nom']}, Niveau: {k}")

    stats_to_display = [PA, PM, 'characteristic_19']
    stats_to_display += [c for c in list(opts.weights) + list(model.base_stats) if c not in stats_to_display]
    print("\nStats totales:")
    for char, value in compute_stats(model, result, stats_to_display).items():
        print(f"- {stat_name(char)}: {value}")

    if debug_pa_pm:
        print("\nDebug PA/PM breakdown:")
        for char, label in ((PA, 'PA'), (PM, 'PM')):
            from_items = sum(model.item_stat(char).get(i, 0) for i in result.items)
            from_sets = sum(model.bonus_stat(char).get(key, 0) for key in result.bonuses)
            base = model.base_stats.get(char, 0)
            print(f"- {label} items: {from_items}")
            print(f"- {label} set bonuses: {from_sets}")
            print(f"- {label} base: {base}")
            print(f"- {label} total: {from_items + from_sets + base}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Dofus Stuff Optimizer')
    parser.add_argument('--min-level', type=int, default=1, help='Minimum character level')
    parser.add_argument('--max-level', type=int, default=200, help='Maximum character level')
    parser.add_argument('--pa', type=int, default=9, help='Desired PA')
    parser.add_argument('--pm', type=int, default=4, help='Desired PM')
    parser.add_argument('--no-dofus', action='store_true', help='Exclude Dofus and Trophies')
    parser.add_argument('--weights', nargs='+', default=[], help='List of characteristics and weights (e.g., characteristic_13:1.0)')
    parser.add_argument('--base-stats', nargs='+', default=[], help='Base stats overrides (e.g., characteristic_1:7 characteristic_23:3)')
    parser.add_argument('--debug-pa-pm', action='store_true', help='Print PA/PM contributions (items, set bonuses, base)')
    parser.add_argument('--min-stats', nargs='+', default=[], help='Minimum stats constraints (e.g., characteristic_10:100 characteristic_13:300)')
    parser.add_argument('--solver-log', action='store_true', help='Show the solver log')
    return parser.parse_args(argv)


def options_from_args(args):
    return Options(
        min_level=args.min_level, max_level=args.max_level, pa=args.pa, pm=args.pm,
        no_dofus=args.no_dofus, weights=parse_stat_list(args.weights),
        base_stats=parse_stat_list(args.base_stats), min_stats=parse_stat_list(args.min_stats),
    )


def main(argv=None):
    args = parse_args(argv)
    opts = options_from_args(args)

    print("Loading data...")
    items_df, bonuses_df = load_data()
    print("Data loaded.")

    model = build_model(items_df, bonuses_df, opts)
    print("\nSolving the optimization problem...")
    result = solve(model, msg=args.solver_log)
    print("Problem solved.")
    print_report(model, result, opts, debug_pa_pm=args.debug_pa_pm)
    return 0 if result.status == 'Optimal' else 1


if __name__ == '__main__':
    sys.exit(main())
