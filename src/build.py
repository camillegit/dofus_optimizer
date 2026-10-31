"""Best builds for a class: one damage-optimized stuff per element (and multi-element).

Example:
    python -m src.build feca --niveau 200 --exo pa pm --top 2
"""
import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field

from pulp import lpSum

from . import characteristics, classes, conditions, prices
from .damage import DAMAGE_STATS, ELEMENTS, Target, class_spells, optimize_damage, spells_report
from .optimizer import (EQUIP_TYPES_MAP, PA, PM, PRIMARY_STATS, Options, base_stats_of, build_model,
                        compute_stats, load_data, set_bonus_count, violated_conditions)

VITA = 'characteristic_11'
RES_PERCENT = [ids[4] for ids in ELEMENTS.values()]

# Secondary objective added to the damage per turn
PROFILES = {
    'degats': {},
    'equilibre': {VITA: 0.5},
    'tank': {VITA: 1.0, **{char: 30.0 for char in RES_PERCENT}},
}

TARGETS = {
    'aucune': [Target()],
    # Worst case over targets resisting one element each: favours stuffs that stay good everywhere
    'robuste': [Target(f"résistante {el}", {el: (30, 0)}) for el in ('terre', 'feu', 'eau', 'air')],
}

DISPLAY_STATS = [PA, PM, 'characteristic_19', VITA] + PRIMARY_STATS[:4] + [
    'characteristic_25', 'characteristic_16', 'characteristic_18', 'characteristic_86',
    'characteristic_88', 'characteristic_89', 'characteristic_90', 'characteristic_91', 'characteristic_92',
    'characteristic_123', 'characteristic_120', 'characteristic_125', 'characteristic_12',
    'characteristic_26', 'characteristic_44'] + RES_PERCENT


@dataclass
class BuildRequest:
    classe: str
    niveau: int = 200
    pa: int = 11
    pm: int = 6
    elements: list = field(default_factory=list)     # empty: every element of the class + multi
    exos: list = field(default_factory=list)
    max_exos: int = None
    parchemins: int = 100
    points: bool = True
    profil: str = 'degats'
    cible: str = 'aucune'
    top: int = 1
    diversite: int = 3
    no_dofus: bool = False
    no_pet: bool = False
    prix: str = None            # CSV file of prices
    possede: str = None         # file of owned items
    budget: float = None


def to_python(value):
    if hasattr(value, 'item'):
        return value.item()
    if isinstance(value, dict):
        return {str(k): to_python(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_python(v) for v in value]
    return value


def element_spells(breed, level):
    spells = class_spells(breed, level)
    groups = {}
    for spell in spells:
        groups.setdefault(spell.main_element, []).append(spell)
    if len(groups) > 1:
        groups['multi'] = spells
    return groups


def describe(model, best, spells, request, element, rank):
    result = best.result
    stats = compute_stats(model, result, sorted(set(DISPLAY_STATS) | set(DAMAGE_STATS)))
    items = []
    for item_id in result.items:
        item = model.items.loc[item_id]
        items.append({
            'id': item_id, 'nom': item['nom'], 'type': EQUIP_TYPES_MAP.get(item['type'], '?'),
            'type_id': item['type'], 'niveau': item['niveau'], 'img': item.get('img'),
            'exo': next((characteristics.display_name(c) for i, c in result.exos if i == item_id), None),
            'a_verifier': conditions.unmodelled_atoms(conditions.parse(item['condition']), model.breed),
        })
    return to_python({
        'element': element,
        'rang': rank,
        'degats_par_tour': round(best.damage, 1),
        'degats_par_cible': {k: round(v, 1) for k, v in best.per_target.items()},
        'items': items,
        'panoplies': [{'nom': model.bonuses.at[s, 'nom'], 'pieces': k} for s, k in result.bonuses],
        'points': {characteristics.display_name(c): v for c, v in result.points.items() if v},
        'stats': {characteristics.display_name(c): stats[c] for c in DISPLAY_STATS if stats.get(c)},
        'sorts': sorted(spells_report(spells, best.stats, best.rotation),
                        key=lambda r: (-r['lancers'], -r['esperance'])),
        'cout': result.cost,
        'conditions_ok': not violated_conditions(model, result),
        'bonus_panoplie_actifs': set_bonus_count(result),
    })


def build_element(args):
    """Builds for one element. Returns (build descriptions, characteristics of each stuff)."""
    request, element, spells, starts, seeds = args
    items_df, bonuses_df = load_data()
    breed = conditions.class_id(request.classe)
    opts = Options(
        max_level=request.niveau, pa=request.pa, pm=request.pm, no_dofus=request.no_dofus,
        no_pet=request.no_pet, breed=breed, points=request.points, scrolls=request.parchemins,
        exos=[characteristics.resolve(c) for c in request.exos], max_exos=request.max_exos,
        budget=request.budget,
    )
    if request.prix:
        opts.prices, opts.exo_prices, _ = prices.load_prices(request.prix, items_df)
    if request.possede:
        opts.owned = prices.load_owned(request.possede, items_df)
    model = build_model(items_df, bonuses_df, opts)
    builds, stuff_stats = [], []
    for rank in range(1, request.top + 1):
        best = optimize_damage(model, spells, request.pa, TARGETS[request.cible], PROFILES[request.profil],
                               starts=starts, seeds=seeds if rank == 1 else None)
        if best is None or best.result.status != 'Optimal':
            break
        builds.append(describe(model, best, spells, request, element, rank))
        stuff_stats.append((to_python(best.stats), [int(i) for i in best.result.items]))
        # Next build: at least `diversite` different items
        chosen = best.result.items
        model.problem += (lpSum(model.item_vars[i] for i in chosen) <= len(chosen) - request.diversite,
                          f"Diversity_{rank}")
    return builds, stuff_stats


def build(request, parallel=True):
    breed = conditions.class_id(request.classe)
    groups = element_spells(breed, request.niveau)
    if request.elements:
        groups = {e: s for e, s in groups.items() if e in request.elements}
    multi = groups.pop('multi', None)
    jobs = [(request, element, spells, None, None) for element, spells in groups.items()]
    if parallel and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=min(len(jobs), 5)) as pool:
            results = list(pool.map(build_element, jobs))
    else:
        results = [build_element(job) for job in jobs]
    if multi is not None:
        # Multi-element search, linearized from scratch and from the two best single-element stuffs
        ranked = sorted(((b['degats_par_tour'], st) for r in results for b, st in zip(*r)), key=lambda x: -x[0])
        starts = [{}] + [stats for _, (stats, _) in ranked[:2]]
        seeds = [items for _, (_, items) in ranked[:2]]
        results.append(build_element((request, 'multi', multi, starts, seeds)))
    builds = sorted((b for r in results for b in r[0]), key=lambda b: -b['degats_par_tour'])
    return {
        'classe': classes.get_class(breed)['nom'],
        'classe_id': breed,
        'classe_img': classes.get_class(breed).get('img'),
        'parametres': to_python(request.__dict__),
        'builds': builds,
    }


def print_build(b):
    print(f"\n=== {b['element'].upper()} (#{b['rang']}) : {b['degats_par_tour']:.0f} dégâts par tour ===")
    if len(b['degats_par_cible']) > 1:
        print("  par cible : " + ", ".join(f"{k} {v:.0f}" for k, v in b['degats_par_cible'].items()))
    if b['cout'] is not None:
        print(f"Coût : {b['cout']:,.0f} kamas".replace(',', '\u202f'))
    print("Équipement :")
    for item in b['items']:
        exo = f"  [exo {item['exo']}]" if item['exo'] else ""
        check = f"  (à vérifier : {', '.join(item['a_verifier'])})" if item['a_verifier'] else ""
        print(f"  - {item['type']:<11} {item['nom']}{exo}{check}")
    if b['panoplies']:
        print("Panoplies : " + ", ".join(f"{p['nom']} ({p['pieces']})" for p in b['panoplies']))
    if b['points']:
        print("Points : " + ", ".join(f"{k} {v}" for k, v in b['points'].items()))
    print("Stats : " + ", ".join(f"{k} {v:g}" for k, v in b['stats'].items()))
    print("Sorts (dégâts par lancer, normal / critique, espérance) :")
    for s in b['sorts']:
        casts = f"x{s['lancers']}" if s['lancers'] else "  "
        print(f"  {casts:>3} {s['nom']:<22} {s['pa']} PA  {s['normal'][0]}-{s['normal'][1]}"
              f" / {s['critique'][0]}-{s['critique'][1]} ({s['chance_critique']}% crit)  ~{s['esperance']:.0f}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Meilleurs builds d'une classe (dégâts des sorts)")
    parser.add_argument('classe', help="Classe (ex. feca, iop, 'Écaflip')")
    parser.add_argument('--niveau', type=int, default=200)
    parser.add_argument('--pa', type=int, default=11)
    parser.add_argument('--pm', type=int, default=6)
    parser.add_argument('--element', nargs='+', default=[], choices=list(ELEMENTS) + ['multi'],
                        help="Éléments à optimiser (par défaut : tous ceux de la classe + multi)")
    parser.add_argument('--exo', nargs='+', default=[], help='Exos autorisés, ex. pa pm po')
    parser.add_argument('--max-exo', type=int)
    parser.add_argument('--parchemins', type=int, default=100)
    parser.add_argument('--sans-points', action='store_true', help='Ne pas optimiser les points de caractéristiques')
    parser.add_argument('--profil', choices=list(PROFILES), default='degats')
    parser.add_argument('--cible', choices=list(TARGETS), default='aucune')
    parser.add_argument('--top', type=int, default=1, help='Nombre de builds par élément')
    parser.add_argument('--diversite', type=int, default=3, help="Items différents entre deux builds d'un même élément")
    parser.add_argument('--no-dofus', action='store_true')
    parser.add_argument('--no-pet', action='store_true')
    parser.add_argument('--prix', help='Fichier CSV de prix (colonnes id ou nom, et prix)')
    parser.add_argument('--possede', help='Fichier des items possédés (coût nul)')
    parser.add_argument('--budget', type=float, help='Budget maximal en kamas (nécessite --prix)')
    parser.add_argument('--json', action='store_true', help='Sortie JSON')
    args = parser.parse_args(argv)
    if args.budget is not None and not args.prix:
        parser.error('--budget nécessite --prix')
    try:
        conditions.class_id(args.classe)
        for c in args.exo:
            characteristics.resolve(c)
    except ValueError as e:
        parser.error(str(e))
    return BuildRequest(
        classe=args.classe, niveau=args.niveau, pa=args.pa, pm=args.pm, elements=args.element,
        exos=args.exo, max_exos=args.max_exo, parchemins=args.parchemins, points=not args.sans_points,
        profil=args.profil, cible=args.cible, top=args.top, diversite=args.diversite,
        no_dofus=args.no_dofus, no_pet=args.no_pet, prix=args.prix, possede=args.possede, budget=args.budget,
    ), args.json


def main(argv=None):
    request, as_json = parse_args(argv)
    report = build(request)
    if as_json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    print(f"{report['classe']} niveau {request.niveau} — {request.pa} PA / {request.pm} PM, profil {request.profil}, "
          f"cible {request.cible}")
    print("\nClassement :")
    for b in report['builds']:
        print(f"  {b['element']:<7} #{b['rang']} {b['degats_par_tour']:>8.0f} dégâts/tour")
    for b in report['builds']:
        print_build(b)
    return 0


if __name__ == '__main__':
    sys.exit(main())
