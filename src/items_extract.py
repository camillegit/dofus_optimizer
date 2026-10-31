from datetime import datetime

import pandas as pd

from .config import BASE_URL_ITEMS, DATA_DIR, EQUIP_TYPES
from .utils import fetch_all


def parse_item_data(item: dict) -> dict | None:
    """Parse an item JSON object into a structured dictionary."""
    if not item or item.get("id") == 666:
        return None

    entry = {
        "id": item.get("id"),
        "nom": item.get("name", {}).get("fr"),
        "type": item.get("typeId"),
        "niveau": item.get("level"),
        "pano": item.get("itemSetId"),
        "condition": item.get("criterions") or None,
        "deux_mains": bool(item.get("twoHanded")),
    }

    # Iterate over each effect in the 'effects' list
    for effect in item.get("effects", []):
        characteristic = effect.get("characteristic")
        from_value = effect.get("from")
        to_value = effect.get("to")

        # Check if both 'from' and 'to' exist, then take the max of both
        if characteristic is not None and from_value is not None and to_value is not None:
            entry[f"characteristic_{characteristic}"] = max(from_value, to_value)

    return entry


def extract_items(types=EQUIP_TYPES):
    """Fetch and parse all equipment items (paginated API, filtered by type)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = DATA_DIR / f"dofus_items_{timestamp}.parquet"

    params = [("typeId[$in][]", t) for t in types]
    raw_items = fetch_all(BASE_URL_ITEMS, params, desc="Fetching Items")
    all_items = [entry for entry in map(parse_item_data, raw_items) if entry]

    if all_items:
        pd.DataFrame(all_items).to_parquet(output_path, index=False)
    print(f"Saved {len(all_items)} items to {output_path}")


if __name__ == "__main__":
    extract_items()
