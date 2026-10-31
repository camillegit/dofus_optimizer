"""Item prices (kamas) from a user CSV file: `id` or `nom`, and `prix`.

Exo prices can be given with the names `exo pa`, `exo pm`, `exo po`... (any characteristic alias).
"""
import csv
import unicodedata

try:
    from . import characteristics
except ImportError:  # run as a script
    import characteristics


def _normalize(text):
    text = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode()
    return ' '.join(text.lower().split())


def read_rows(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        sample = f.read(2048)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=';,\t')
        return [{k.strip().lower(): (v or '').strip() for k, v in row.items() if k} for row in csv.DictReader(f, dialect=dialect)]


def load_prices(path, items_df):
    """Returns (item prices {id: kamas}, exo prices {char: kamas}, unmatched names)."""
    by_name = {_normalize(n): i for i, n in zip(items_df['id'], items_df['nom']) if isinstance(n, str)}
    ids = set(items_df['id'])
    prices, exo_prices, unmatched = {}, {}, []
    for row in read_rows(path):
        raw_price = row.get('prix', '').replace(' ', '').replace(' ', '')
        if not raw_price:
            continue
        price = float(raw_price)
        key = row.get('id') or row.get('nom', '')
        name = _normalize(row.get('nom', ''))
        if name.startswith('exo '):
            exo_prices[characteristics.resolve(name[4:])] = price
        elif str(key).isdigit() and int(key) in ids:
            prices[int(key)] = price
        elif name in by_name:
            prices[by_name[name]] = price
        else:
            unmatched.append(row.get('nom') or key)
    return prices, exo_prices, unmatched


def load_owned(path, items_df):
    """Owned items (one id or name per line, or a CSV with `id` / `nom`): their cost is 0."""
    by_name = {_normalize(n): i for i, n in zip(items_df['id'], items_df['nom']) if isinstance(n, str)}
    owned = set()
    with open(path, encoding='utf-8-sig') as f:
        for line in f:
            value = line.strip().split(';')[0].split(',')[0].strip()
            if not value or value.lower() in ('id', 'nom'):
                continue
            if value.isdigit():
                owned.add(int(value))
            elif _normalize(value) in by_name:
                owned.add(by_name[_normalize(value)])
    return owned
