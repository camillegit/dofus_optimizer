"""Parsing and evaluation of Dofus item conditions (DofusDB `criterions`).

Grammar: `&` binds tighter than `|`, parentheses group, atoms are `<code><op><value>`
(e.g. `CS>399`, `pk<2`, `PJ>2,40`).
"""
import re
import unicodedata

TOKEN_REGEX = re.compile(r'\s*(?:(\()|(\))|(&)|(\|)|([A-Za-z]+)\s*(<=|>=|!=|=|<|>|!|~)\s*([^&|()]*))')

# C<upper>: total characteristic; C<lower>: base characteristic (points invested, without equipment)
STAT_CODES = {
    'W': 'characteristic_12', 'S': 'characteristic_10', 'C': 'characteristic_13',
    'A': 'characteristic_14', 'I': 'characteristic_15', 'P': 'characteristic_1',
    'M': 'characteristic_23', 'V': 'characteristic_11',
}
SET_BONUS_CODES = ('pk', 'PK')
CLASS_CODE = 'PG'

# DofusDB breed ids (condition PG=<id>)
CLASSES = {
    'feca': 1, 'osamodas': 2, 'enutrof': 3, 'sram': 4, 'xelor': 5, 'ecaflip': 6,
    'eniripsa': 7, 'iop': 8, 'cra': 9, 'sadida': 10, 'sacrieur': 11, 'pandawa': 12,
    'roublard': 13, 'zobal': 14, 'steamer': 15, 'eliotrope': 16, 'huppermage': 17,
    'ouginak': 18, 'forgelance': 20,
}


def class_id(name_or_id):
    """'Écaflip', 'ecaflip' or '6' -> 6."""
    key = unicodedata.normalize('NFKD', str(name_or_id)).encode('ascii', 'ignore').decode().lower().strip()
    if key.isdigit() and int(key) in CLASSES.values():
        return int(key)
    if key in CLASSES:
        return CLASSES[key]
    raise ValueError(f"Unknown class {name_or_id!r} (expected one of: {', '.join(CLASSES)})")


class ConditionSyntaxError(ValueError):
    pass


def tokenize(text):
    tokens, pos = [], 0
    text = text.strip()
    while pos < len(text):
        match = TOKEN_REGEX.match(text, pos)
        if not match or match.end() == pos:
            raise ConditionSyntaxError(f"Cannot parse condition {text!r} at {pos}")
        lpar, rpar, and_, or_, code, op, value = match.groups()
        if code:
            tokens.append(('atom', code, op, value.strip()))
        else:
            tokens.append(lpar or rpar or and_ or or_)
        pos = match.end()
    return tokens


def parse(text):
    """Returns None (no condition) or a tree: ('and'|'or', [children]) / ('atom', code, op, value)."""
    if not isinstance(text, str) or not text.strip():
        return None
    tokens = tokenize(text)
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def take():
        nonlocal pos
        pos += 1
        return tokens[pos - 1]

    def expr():
        children = [term()]
        while peek() == '|':
            take()
            children.append(term())
        return children[0] if len(children) == 1 else ('or', children)

    def term():
        children = [factor()]
        while peek() == '&':
            take()
            children.append(factor())
        return children[0] if len(children) == 1 else ('and', children)

    def factor():
        token = take() if peek() is not None else None
        if token == '(':
            node = expr()
            if peek() != ')':
                raise ConditionSyntaxError(f"Missing ')' in {text!r}")
            take()
            return node
        if isinstance(token, tuple):
            return token
        raise ConditionSyntaxError(f"Unexpected token {token!r} in {text!r}")

    tree = expr()
    if pos != len(tokens):
        raise ConditionSyntaxError(f"Trailing tokens in {text!r}")
    return tree


def atom_kind(code):
    """'total' / 'base' (characteristic), 'set_bonus', 'class' or None (not modelled, considered satisfied)."""
    if code in SET_BONUS_CODES:
        return 'set_bonus'
    if code == CLASS_CODE:
        return 'class'
    if len(code) == 2 and code[0] == 'C' and code[1].upper() in STAT_CODES:
        return 'total' if code[1].isupper() else 'base'
    return None


def atom_char(code):
    return STAT_CODES[code[1].upper()]


def compare(lhs, op, rhs):
    return {
        '<': lhs < rhs, '<=': lhs <= rhs, '>': lhs > rhs, '>=': lhs >= rhs,
        '=': lhs == rhs, '!': lhs != rhs, '!=': lhs != rhs,
    }[op]


def evaluate(tree, total_stats, base_stats, set_bonus_count, breed=None):
    """Evaluates a parsed condition against final stats. Unmodelled atoms are considered satisfied,
    as well as class conditions when no class (breed) is given."""
    if tree is None:
        return True
    kind = tree[0]
    if kind in ('and', 'or'):
        results = (evaluate(c, total_stats, base_stats, set_bonus_count, breed) for c in tree[1])
        return all(results) if kind == 'and' else any(results)

    _, code, op, value = tree
    atom = atom_kind(code)
    if atom is None or op == '~' or (atom == 'class' and breed is None):
        return True
    rhs = int(value)
    if atom == 'class':
        return compare(breed, op, rhs)
    if atom == 'set_bonus':
        return compare(set_bonus_count, op, rhs)
    stats = total_stats if atom == 'total' else base_stats
    return compare(stats.get(atom_char(code), 0), op, rhs)


def unmodelled_atoms(tree, breed=None):
    """Atoms of a condition that are not checked (jobs, quests, class when unknown...)."""
    if tree is None:
        return []
    if tree[0] in ('and', 'or'):
        return [atom for child in tree[1] for atom in unmodelled_atoms(child, breed)]
    _, code, op, value = tree
    kind = atom_kind(code)
    unchecked = kind is None or op == '~' or (kind == 'class' and breed is None)
    return [f"{code}{op}{value}"] if unchecked else []
