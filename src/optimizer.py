import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from pulp import HiGHS, LpAffineExpression, LpMaximize, LpProblem, LpStatus, LpVariable, PULP_CBC_CMD, lpSum

try:
    from . import characteristics, conditions
except ImportError:  # run as a script: python src/optimizer.py
    import characteristics
    import conditions

DATA_PROCESSED_DIR = Path(__file__).resolve().parent.parent / 'data' / 'processed'

EQUIP_TYPES_MAP = {
    16: "Chapeau", 17: "Cape", 9: "Anneau", 1: "Amulette", 3: "Baguette",
    11: "Bottes", 10: "Ceinture", 7: "Marteau", 4: "Bâton", 2: "Arc",
    5: "Dague", 6: "Épée", 19: "Hache", 22: "Faux", 8: "Pelle",
    151: "Trophée", 23: "Dofus", 82: "Boucliers",
    18: "Familier", 121: "Montilier", 331: "Dragodinde", 332: "Muldo", 333: "Volkorne",
}

WEAPON_TYPES = [3, 7, 4, 2, 5, 6, 19, 22, 8]
DOFUS_TROPHY_TYPES = [151, 23]
PET_MOUNT_TYPES = [18, 121, 331, 332, 333]
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
    """Parses ['force:200', 'vita=1.5', 'characteristic_13:100'] into {'characteristic_10': 200.0, ...}."""
    parsed = {}
    for raw in raw_list:
        key, sep, value = raw.replace('=', ':', 1).partition(':')
        if not sep or not key.strip():
            raise ValueError(f"Expected <characteristic>:<value>, got {raw!r}")
        try:
            parsed[characteristics.resolve(key)] = float(value.strip())
        except ValueError as e:
            raise ValueError(f"{e} in {raw!r}") from None
    return parsed


@dataclass
class Options:
    min_level: int = 1
    max_level: int = 200
    pa: int = 9
    pm: int = 4
    no_dofus: bool = False
    no_pet: bool = False
    weights: dict = field(default_factory=dict)
    base_stats: dict = field(default_factory=dict)
    min_stats: dict = field(default_factory=dict)
    breed: int = None            # character class (DofusDB breed id), for PG conditions


@dataclass
class Model:
    problem: LpProblem
    items: pd.DataFrame          # filtered items, indexed by id
    bonuses: pd.DataFrame        # panoplies, indexed by id
    item_vars: dict
    bonus_vars: dict             # (set_id, k) -> 1 iff exactly k pieces of the set are worn (k >= 2)
    base_stats: dict
    set_members: dict = field(default_factory=dict)   # set_id -> item ids
    breed: int = None
    _cache: dict = field(default_factory=dict, repr=False)

    def item_stat(self, char):
        """item id -> value, non-zero values only."""
        key = ('item', char)
        if key not in self._cache:
            column = self.items[char] if char in self.items.columns else pd.Series(dtype=float)
            self._cache[key] = column[column != 0].to_dict()
        return self._cache[key]

    def bonus_stat(self, char):
        """(set_id, k) -> cumulative bonus of that tier (tiers are exclusive, not additive), non-zero only."""
        key = ('bonus', char)
        if key not in self._cache:
            values = {}
            for (set_id, k) in self.bonus_vars:
                col = f"bonus_{k}_{char}"
                if col in self.bonuses.columns and self.bonuses.at[set_id, col] != 0:
                    values[(set_id, k)] = self.bonuses.at[set_id, col]
            self._cache[key] = values
        return self._cache[key]

    def total_stat_expr(self, char):
        terms = [(self.item_vars[i], v) for i, v in self.item_stat(char).items()]
        terms += [(self.bonus_vars[key], v) for key, v in self.bonus_stat(char).items()]
        return LpAffineExpression(terms, constant=self.base_stats.get(char, 0))

    def stat_var(self, char):
        """Continuous variable equal to the total of a characteristic (defined once, keeps constraints sparse)."""
        key = ('var', char)
        if key not in self._cache:
            low, high = self.stat_bounds(char)
            var = LpVariable(f"total_{char}", low, high)
            self.problem += var == self.total_stat_expr(char), f"Total_{char}"
            self._cache[key] = var
        return self._cache[key]

    def set_bonus_count(self):
        """Number of active set bonuses as counted by the 'pk' condition: sum over sets of (pieces - 1)."""
        return lpSum((k - 1) * var for (_, k), var in self.bonus_vars.items())

    def set_bonus_count_var(self):
        key = ('var', 'set_bonus_count')
        if key not in self._cache:
            var = LpVariable("total_set_bonus_count", 0, sum(len(m) - 1 for m in self.set_members.values()))
            self.problem += var == self.set_bonus_count(), "Total_set_bonus_count"
            self._cache[key] = var
        return self._cache[key]

    def stat_bounds(self, char):
        """Lower/upper bounds of the total of a characteristic over all feasible stuffs."""
        item_values = list(self.item_stat(char).values())
        tiers = defaultdict(list)
        for (set_id, _), value in self.bonus_stat(char).items():
            tiers[set_id].append(value)
        base = self.base_stats.get(char, 0)
        low = base + sum(min(0, v) for v in item_values) + sum(min(0, *v) for v in tiers.values())
        high = base + sum(max(0, v) for v in item_values) + sum(max(0, *v) for v in tiers.values())
        return low, high


def filter_items(items_df, opts):
    items_df = items_df[(items_df['niveau'] >= opts.min_level) & (items_df['niveau'] <= opts.max_level)]
    items_df = items_df[~items_df['id'].isin(BANNED_ITEMS)]
    # Game master items, not obtainable
    items_df = items_df[~items_df['nom'].fillna('').str.endswith('(MJ)')]
    if opts.no_dofus:
        items_df = items_df[items_df['type'] != DOFUS_TYPE]
    if opts.no_pet:
        items_df = items_df[~items_df['type'].isin(PET_MOUNT_TYPES)]
    return items_df


def add_slot_constraints(model):
    problem, items = model.problem, model.items
    for item_type, group in items.groupby('type'):
        if item_type in WEAPON_TYPES or item_type in PET_MOUNT_TYPES:
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

    # Pets, petsmounts and mounts share a single slot
    pets_mounts = items.index[items['type'].isin(PET_MOUNT_TYPES)]
    problem += lpSum(model.item_vars[i] for i in pets_mounts) <= 1, "Pet_Mount_Constraint"


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


class ConditionBuilder:
    """Turns parsed conditions into binary indicators v such that v = 1 implies the condition holds.

    An indicator is True/False when the data alone decides the condition. Conditions on jobs,
    quests... (and class when it is not given) are not modelled and are considered satisfied.
    """

    def __init__(self, model):
        self.model = model
        self.atoms = {}
        self.count = 0

    def new_var(self, kind):
        self.count += 1
        return LpVariable(f"cond_{kind}_{self.count}", cat='Binary')

    def indicator(self, tree):
        if tree is None:
            return True
        if tree[0] == 'atom':
            return self.atom(*tree[1:])
        return self.combine(tree[0], [self.indicator(child) for child in tree[1]])

    def combine(self, kind, children):
        neutral = kind == 'and'          # True is neutral for 'and', False for 'or'
        if any(c is (not neutral) for c in children):
            return not neutral
        children = [c for c in children if c is not neutral]
        if len(children) <= 1:
            return children[0] if children else neutral
        var = self.new_var(kind)
        if kind == 'and':
            for c in children:
                self.model.problem += var <= c
        else:
            self.model.problem += var <= lpSum(children)
        return var

    def atom(self, code, op, value):
        key = (code, op, value)
        if key not in self.atoms:
            self.atoms[key] = self.build_atom(code, op, value)
        return self.atoms[key]

    def build_atom(self, code, op, value):
        kind = conditions.atom_kind(code)
        if kind is None or op == '~' or (kind == 'class' and self.model.breed is None):
            return True
        if kind == 'class':
            return conditions.compare(self.model.breed, op, int(value))
        if kind == 'base':
            return conditions.compare(self.model.base_stats.get(conditions.atom_char(code), 0), op, int(value))
        if kind == 'set_bonus':
            expr = self.model.set_bonus_count_var()
            bounds = (0, sum(len(m) - 1 for m in self.model.set_members.values()))
        else:
            char = conditions.atom_char(code)
            expr, bounds = self.model.stat_var(char), self.model.stat_bounds(char)
        return self.comparison(expr, bounds, op, int(value))

    def comparison(self, expr, bounds, op, value):
        """Indicator of `expr <op> value` for an integer-valued expression within bounds."""
        if op in ('!', '!='):
            return self.combine('or', [self.comparison(expr, bounds, '<', value),
                                       self.comparison(expr, bounds, '>', value)])
        if op == '=':
            return self.combine('and', [self.comparison(expr, bounds, '>=', value),
                                        self.comparison(expr, bounds, '<=', value)])
        low, high = bounds
        if op in ('>', '>='):
            threshold = value + 1 if op == '>' else value
            if low >= threshold:
                return True
            if high < threshold:
                return False
            var = self.new_var('ge')
            self.model.problem += expr >= threshold - (threshold - low) * (1 - var)
            return var
        threshold = value - 1 if op == '<' else value
        if high <= threshold:
            return True
        if low > threshold:
            return False
        var = self.new_var('le')
        self.model.problem += expr <= threshold + (high - threshold) * (1 - var)
        return var


def add_condition_constraints(model):
    builder = ConditionBuilder(model)
    for item_id, text in model.items['condition'].items():
        indicator = builder.indicator(conditions.parse(text))
        if indicator is True:
            continue
        model.problem += model.item_vars[item_id] <= (0 if indicator is False else indicator), f"Cond_item_{item_id}"


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
                  item_vars, bonus_vars, base_stats, set_members, opts.breed)
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


SOLVERS = {'cbc': PULP_CBC_CMD, 'highs': HiGHS}


def solve(model, msg=False, solver='cbc'):
    model.problem.solve(SOLVERS[solver](msg=msg))
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


def set_bonus_count(result):
    return sum(k - 1 for _, k in result.bonuses)


def violated_conditions(model, result):
    """Independent check: selected items whose condition does not hold on the final stats."""
    totals = compute_stats(model, result, sorted(set(conditions.STAT_CODES.values())))
    return [
        item_id for item_id in result.items
        if not conditions.evaluate(conditions.parse(model.items.at[item_id, 'condition']),
                                   totals, model.base_stats, set_bonus_count(result), model.breed)
    ]


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
        print(f"- {characteristics.display_name(char)}: {value}")

    print("\nConditions d'équipement:")
    violated = violated_conditions(model, result)
    if violated:
        for item_id in violated:
            print(f"- NON RESPECTÉE : {model.items.at[item_id, 'nom']} ({model.items.at[item_id, 'condition']})")
    else:
        print(f"- Conditions de caractéristiques respectées (bonus de panoplie actifs : {set_bonus_count(result)})")
    for item_id in result.items:
        atoms = conditions.unmodelled_atoms(conditions.parse(model.items.at[item_id, 'condition']), model.breed)
        if atoms:
            print(f"- À vérifier en jeu : {model.items.at[item_id, 'nom']} ({', '.join(atoms)})")

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
    parser.add_argument('--no-pet', action='store_true', help='Exclude pets and mounts')
    parser.add_argument('--weights', nargs='+', default=[], help='Characteristics and weights (e.g., force:1 vita:0.5 or characteristic_10:1)')
    parser.add_argument('--base-stats', nargs='+', default=[], help='Base stats overrides (e.g., force:200 pa:7)')
    parser.add_argument('--debug-pa-pm', action='store_true', help='Print PA/PM contributions (items, set bonuses, base)')
    parser.add_argument('--min-stats', nargs='+', default=[], help='Minimum stats constraints (e.g., force:100 chance:300)')
    parser.add_argument('--list-stats', action='store_true', help='List characteristic ids and aliases, then exit')
    parser.add_argument('--classe', help="Character class (e.g. iop, 'Écaflip' or its id), for class-restricted items")
    parser.add_argument('--solver', choices=sorted(SOLVERS), default='cbc', help='MILP solver (highs requires: pip install highspy)')
    parser.add_argument('--solver-log', action='store_true', help='Show the solver log')
    args = parser.parse_args(argv)
    try:
        args.options = options_from_args(args)
    except ValueError as e:
        parser.error(str(e))
    return args


def options_from_args(args):
    return Options(
        min_level=args.min_level, max_level=args.max_level, pa=args.pa, pm=args.pm,
        no_dofus=args.no_dofus, no_pet=args.no_pet, weights=parse_stat_list(args.weights),
        base_stats=parse_stat_list(args.base_stats), min_stats=parse_stat_list(args.min_stats),
        breed=conditions.class_id(args.classe) if args.classe else None,
    )


def main(argv=None):
    args = parse_args(argv)
    opts = args.options
    if args.list_stats:
        print(characteristics.stats_table())
        return 0

    print("Loading data...")
    items_df, bonuses_df = load_data()
    print("Data loaded.")

    model = build_model(items_df, bonuses_df, opts)
    print("\nSolving the optimization problem...")
    result = solve(model, msg=args.solver_log, solver=args.solver)
    print("Problem solved.")
    print_report(model, result, opts, debug_pa_pm=args.debug_pa_pm)
    return 0 if result.status == 'Optimal' else 1


if __name__ == '__main__':
    sys.exit(main())
