"""Class spells damage: per-spell damage, turn rotation and damage-maximizing stuff search.

Damage of a spell line (Dofus 2 formula, average roll):
    normal   = base * (100 + characteristic + power) / 100 + damage + elemental damage
    critical = base_crit * (100 + characteristic + power) / 100 + damage + elemental damage + critical damage
then multiplied by (100 + % spell damage) / 100 and (100 + % ranged or % melee damage) / 100,
and reduced by the target resistances: (dmg - fixed resistance) * (100 - % resistance) / 100.
Expected damage of a cast = (1 - p) * normal + p * critical, p = min(1, (spell crit + crit) / 100).

The expected damage is bilinear in the stuff (crit x stats, % damage x stats). The search
linearizes it around the current stuff (exact partial derivatives), solves the MILP, updates the
rotation and repeats; every stuff is evaluated with the exact formula and the best one is kept.
"""
import math
from dataclasses import dataclass, field

from pulp import LpAffineExpression, LpVariable

try:
    from . import classes
    from .optimizer import compute_stats, solve
except ImportError:  # run as a script
    import classes
    from optimizer import compute_stats, solve

# element -> (damage effect, life steal effect, characteristic, elemental damage, % resistance, fixed resistance)
ELEMENTS = {
    'terre': (97, 92, 'characteristic_10', 'characteristic_88', 'characteristic_33', 'characteristic_54'),
    'feu': (99, 94, 'characteristic_15', 'characteristic_89', 'characteristic_34', 'characteristic_55'),
    'eau': (96, 91, 'characteristic_13', 'characteristic_90', 'characteristic_35', 'characteristic_56'),
    'air': (98, 93, 'characteristic_14', 'characteristic_91', 'characteristic_36', 'characteristic_57'),
    'neutre': (100, 95, 'characteristic_10', 'characteristic_92', 'characteristic_37', 'characteristic_58'),
}
EFFECT_ELEMENT = {effect: element for element, ids in ELEMENTS.items() for effect in ids[:2]}

POWER, DAMAGE, CRIT, CRIT_DAMAGE = 'characteristic_25', 'characteristic_16', 'characteristic_18', 'characteristic_86'
SPELL_DAMAGE, RANGED_DAMAGE, MELEE_DAMAGE = 'characteristic_123', 'characteristic_120', 'characteristic_125'
PA = 'characteristic_1'

DAMAGE_STATS = sorted({ids[2] for ids in ELEMENTS.values()} | {ids[3] for ids in ELEMENTS.values()}
                      | {POWER, DAMAGE, CRIT, CRIT_DAMAGE, SPELL_DAMAGE, RANGED_DAMAGE, MELEE_DAMAGE})


@dataclass
class Line:
    element: str
    low: int
    high: int
    crit_low: int
    crit_high: int


@dataclass
class Spell:
    id: int
    name: str
    img: str
    pa: int
    crit: int                 # base critical chance (%)
    max_casts: int            # per turn, against a single target (None = unlimited)
    melee: bool
    lines: list = field(default_factory=list)

    @property
    def elements(self):
        return sorted({line.element for line in self.lines})

    @property
    def main_element(self):
        weight = {}
        for line in self.lines:
            weight[line.element] = weight.get(line.element, 0) + line.low + line.high
        return max(weight, key=weight.get)


def damage_lines(effects):
    """Immediate damage / life steal lines: [(element, min, max)]."""
    return [
        (EFFECT_ELEMENT[e['effet']], e['min'], e['max'])
        for e in effects
        if e['effet'] in EFFECT_ELEMENT and e.get('declencheurs') == 'I' and not e.get('duree')
    ]


def class_spells(breed, level):
    """Damage spells of a class available at a character level."""
    spells = []
    for spell in classes.get_class(breed)['sorts']:
        lv = classes.spell_level(spell, level)
        if lv is None:
            continue
        normal = damage_lines(lv['effets'])
        if not normal:
            continue
        critical = damage_lines(lv['effets_critiques']) or normal
        if len(critical) != len(normal):
            critical = normal
        limits = [n for n in (lv['lancers_par_tour'], lv['lancers_par_cible']) if n]
        if lv.get('intervalle'):
            limits.append(1)
        spells.append(Spell(
            id=spell['id'], name=spell['nom'], img=spell.get('img'), pa=lv['pa'], crit=lv['crit'],
            max_casts=min(limits) if limits else None, melee=(lv['po_max'] or 0) <= 1,
            lines=[Line(el, lo, hi, clo, chi) for (el, lo, hi), (_, clo, chi) in zip(normal, critical)],
        ))
    return spells


@dataclass
class Target:
    """Resistances of the target: element -> (% resistance, fixed resistance)."""
    name: str = 'sans résistance'
    resistances: dict = field(default_factory=dict)


def line_damage(base, line, stats, critical):
    _, _, char, elem_damage, _, _ = ELEMENTS[line.element]
    value = base * (100 + stats.get(char, 0) + stats.get(POWER, 0)) / 100
    value += stats.get(DAMAGE, 0) + stats.get(elem_damage, 0)
    if critical:
        value += stats.get(CRIT_DAMAGE, 0)
    return value


def after_target(value, element, target):
    percent, fixed = (target.resistances.get(element, (0, 0)) if target else (0, 0))
    return max(0.0, (value - fixed) * (100 - percent) / 100)


def multiplier(spell, stats):
    distance = stats.get(MELEE_DAMAGE if spell.melee else RANGED_DAMAGE, 0)
    return (100 + stats.get(SPELL_DAMAGE, 0)) / 100 * (100 + distance) / 100


def crit_chance(spell, stats):
    if spell.crit <= 0:
        return 0.0
    return min(1.0, max(0.0, (spell.crit + stats.get(CRIT, 0)) / 100))


def spell_damage(spell, stats, target=None):
    """Per cast: normal / critical (min, max) and expected damage."""
    mult = multiplier(spell, stats)

    def total(critical, pick):
        value = 0.0
        for line in spell.lines:
            base = pick(line)
            raw = line_damage(base, line, stats, critical)
            value += after_target(raw * mult, line.element, target)
        return value

    normal = (total(False, lambda l: l.low), total(False, lambda l: l.high))
    crit = (total(True, lambda l: l.crit_low), total(True, lambda l: l.crit_high))
    p = crit_chance(spell, stats)
    expected = (1 - p) * sum(normal) / 2 + p * sum(crit) / 2
    return {'normal': normal, 'critique': crit, 'chance_critique': p, 'esperance': expected}


def best_rotation(spells, stats, pa, target=None):
    """Turn rotation maximizing expected damage with `pa` action points: {spell id: casts}."""
    pa = int(pa)
    value = {s.id: spell_damage(s, stats, target)['esperance'] for s in spells}
    # Bounded knapsack by dynamic programming over action points
    best = [(0.0, {})] * (pa + 1)
    for spell in spells:
        if spell.pa <= 0:
            continue
        casts = spell.max_casts if spell.max_casts is not None else pa // spell.pa
        for _ in range(casts):
            new = list(best)
            for budget in range(spell.pa, pa + 1):
                prev_value, prev_rot = best[budget - spell.pa]
                candidate = prev_value + value[spell.id]
                if candidate > new[budget][0] + 1e-9:
                    rot = dict(prev_rot)
                    rot[spell.id] = rot.get(spell.id, 0) + 1
                    new[budget] = (candidate, rot)
            best = new
    return max(best, key=lambda b: b[0])[1]


def rotation_damage(spells, rotation, stats, target=None):
    by_id = {s.id: s for s in spells}
    return sum(n * spell_damage(by_id[sid], stats, target)['esperance'] for sid, n in rotation.items())


def gradient(spells, rotation, stats, target=None):
    """Exact partial derivatives of the rotation damage (multilinear in each characteristic)."""
    base = rotation_damage(spells, rotation, stats, target)
    grad = {}
    for char in DAMAGE_STATS:
        shifted = dict(stats)
        shifted[char] = shifted.get(char, 0) + 1
        delta = rotation_damage(spells, rotation, shifted, target) - base
        if abs(delta) > 1e-9:
            grad[char] = delta
    return grad


@dataclass
class DamageResult:
    result: object
    stats: dict
    rotation: dict
    damage: float                       # expected damage of the rotation (worst target if several)
    per_target: dict = field(default_factory=dict)
    spells: list = field(default_factory=list)


def evaluate(model, result, spells, targets):
    stats = compute_stats(model, result, DAMAGE_STATS + [PA])
    per_target = {}
    rotations = {}
    for target in targets:
        rotation = best_rotation(spells, stats, stats[PA], target)
        rotations[target.name] = rotation
        per_target[target.name] = rotation_damage(spells, rotation, stats, target)
    worst = min(per_target, key=per_target.get)
    return DamageResult(result, stats, rotations[worst], per_target[worst], per_target, spells)


def set_objective(model, grads, extra_weights):
    """Objective: worst-case linearized damage over targets (+ secondary weighted stats)."""
    secondary = LpAffineExpression([(model.stat_var(c), w) for c, w in extra_weights.items()])
    if len(grads) == 1:
        linear = LpAffineExpression([(model.stat_var(c), g) for c, g in grads[0].items()])
        model.problem.setObjective(linear + secondary)
        return
    # max t s.t. t <= damage_target for every target (robust stuff)
    worst = model._cache.get('worst_damage')
    if worst is None:
        worst = model._cache['worst_damage'] = LpVariable('worst_damage')
    for name in [c.name for c in model.problem.constraints.values() if c.name and c.name.startswith('Robust_')]:
        del model.problem.constraints[name]
    for k, grad in enumerate(grads):
        expr = LpAffineExpression([(model.stat_var(c), g) for c, g in grad.items()])
        model.problem.addConstraint(worst <= expr, f"Robust_{k}")
    model.problem.setObjective(worst + secondary)


def optimize_damage(model, spells, min_pa, targets=None, extra_weights=None, iterations=8, patience=2,
                    solver='cbc', starts=None, seeds=None):
    """Sequential linearization of the expected rotation damage. Returns the best DamageResult.

    The gradient is taken halfway between the previous linearization point and the new stuff
    (damping against oscillations); stops after `patience` iterations without improvement.
    Several starting points (characteristics of a reference stuff, e.g. the best single-element
    stuffs for a multi-element search) can be given; the best stuff over all runs is returned.
    `seeds` are item lists evaluated as such (characteristic points and exos re-optimized).
    """
    best = None
    for items in (seeds or []):
        current = _evaluate_fixed(model, spells, min_pa, targets or [Target()], extra_weights or {}, solver, items)
        if current is not None and (best is None or current.damage > best.damage):
            best = current
    for start in (starts or [{}]):
        current = _optimize_from(model, spells, min_pa, targets or [Target()], extra_weights or {},
                                 iterations, patience, solver, start)
        if current is not None and (best is None or current.damage > best.damage):
            best = current
    return best


def _evaluate_fixed(model, spells, min_pa, targets, extra_weights, solver, items):
    """Best rotation damage of a given set of items (other decisions re-optimized once)."""
    fixed = set(items)
    saved = {i: (var.lowBound, var.upBound) for i, var in model.item_vars.items()}
    for i, var in model.item_vars.items():
        var.lowBound = var.upBound = 1 if i in fixed else 0
    try:
        return _optimize_from(model, spells, min_pa, targets, extra_weights, 2, 1, solver, {})
    finally:
        for i, var in model.item_vars.items():
            var.lowBound, var.upBound = saved[i]


def _optimize_from(model, spells, min_pa, targets, extra_weights, iterations, patience, solver, start):
    stats = {**model.base_stats, **start}
    best, stall = None, 0
    for _ in range(iterations):
        grads = []
        for target in targets:
            rotation = best_rotation(spells, stats, max(stats.get(PA, 0), min_pa), target)
            grads.append(gradient(spells, rotation, stats, target))
        if not any(grads):
            return None
        set_objective(model, grads, extra_weights)
        result = solve(model, solver=solver)
        if result.status != 'Optimal':
            return DamageResult(result, {}, {}, 0.0)
        current = evaluate(model, result, spells, targets)
        if best is None or current.damage > best.damage + 1e-6:
            best, stall = current, 0
        else:
            stall += 1
            if stall >= patience:
                break
        chars = set(stats) | set(current.stats)
        stats = {c: (stats.get(c, 0) + current.stats.get(c, 0)) / 2 for c in chars}
    return best


def spells_report(spells, stats, rotation, target=None):
    """Rows for display: per spell damage (rounded down like in-game tooltips) and rotation casts."""
    rows = []
    for spell in spells:
        d = spell_damage(spell, stats, target)
        rows.append({
            'id': spell.id, 'nom': spell.name, 'img': spell.img, 'pa': spell.pa,
            'elements': spell.elements,
            'normal': [math.floor(v) for v in d['normal']],
            'critique': [math.floor(v) for v in d['critique']],
            'chance_critique': round(100 * d['chance_critique']),
            'esperance': round(d['esperance'], 1),
            'lancers': rotation.get(spell.id, 0),
        })
    return rows
