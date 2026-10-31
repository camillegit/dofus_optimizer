import pandas as pd

from src.optimizer import Options, build_model, solve


def make_items(rows):
    """rows: dicts with id, type, and optional niveau/pano/condition/characteristic_*."""
    defaults = {'nom': None, 'niveau': 1, 'pano': -1, 'condition': None}
    df = pd.DataFrame([{**defaults, 'nom': f"item {r['id']}", **r} for r in rows])
    num_cols = df.columns.difference(['nom', 'condition'])
    df[num_cols] = df[num_cols].fillna(0)
    return df


def make_panos(rows):
    """rows: dicts with id and bonus_<k>_characteristic_<c> cumulative values."""
    return pd.DataFrame([{'nom': f"pano {r['id']}", **r} for r in rows]).fillna(0)


def optimize(items, panos=None, **opts):
    panos = panos if panos is not None else make_panos([{'id': 0}])
    opts.setdefault('pa', 0)
    opts.setdefault('pm', 0)
    model = build_model(items, panos, Options(**opts))
    return model, solve(model)
