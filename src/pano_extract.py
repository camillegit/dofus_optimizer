from datetime import datetime

import pandas as pd

from .config import BASE_URL_PANOS, DATA_DIR
from .utils import fetch_all


def parse_pano_data(item_set: dict) -> dict | None:
    """Parse a pano JSON object into a structured dictionary."""
    if not item_set or item_set.get("id") == 666:
        return None

    entry = {
        "id": item_set.get("id"),
        "nom": item_set.get("name", {}).get("fr"),
    }

    # Parse sub-items
    for i, sub_item in enumerate(item_set.get("items", []), start=1):
        if sub_item.get("id"):
            entry[f"item_{i}"] = sub_item["id"]

    # Parse effects by equipped item count (effects[0] is the 1-item tier, values are cumulative)
    for i, effects_group in enumerate(item_set.get("effects", []), start=1):
        for eff in effects_group:
            charac = eff.get("characteristic")
            v_from, v_to = eff.get("from"), eff.get("to")
            if charac and v_from is not None and v_to is not None:
                entry[f"bonus_{i}_characteristic_{charac}"] = max(v_from, v_to)

    return entry


def extract_panos():
    """Fetch and parse all panos (paginated API)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = DATA_DIR / f"dofus_panos_{timestamp}.parquet"

    raw_panos = fetch_all(BASE_URL_PANOS, desc="Fetching Panos")
    all_panos = [entry for entry in map(parse_pano_data, raw_panos) if entry]

    if all_panos:
        pd.DataFrame(all_panos).to_parquet(output_path, index=False)
    print(f"Saved {len(all_panos)} panos to {output_path}")


if __name__ == "__main__":
    extract_panos()
