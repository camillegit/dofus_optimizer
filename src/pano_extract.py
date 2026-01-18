import pandas as pd
from tqdm import tqdm
from .utils import fetch_json
from .config import BASE_URL_PANOS, DATA_DIR, MAX_PANO
from datetime import datetime

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

    # Parse effects by equipped item count
    for i, effects_group in enumerate(item_set.get("effects", []), start=1):
        for eff in effects_group:
            charac = eff.get("characteristic")
            v_from, v_to = eff.get("from"), eff.get("to")
            if charac and v_from is not None and v_to is not None:
                entry[f"bonus_{i}_characteristic_{charac}"] = max(v_from, v_to)

    return entry


def extract_panos(start_id: int = 0, end_id: int = MAX_PANO):
    """Fetch and parse all pano data within ID range."""
    all_panos = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = DATA_DIR / f"dofus_panos_{timestamp}.parquet"
    successful_panos_count = 0

    print(f"Starting extraction for panos ({start_id} → {end_id})")

    for pano_id in tqdm(range(start_id, end_id), desc="Fetching Panos"):
        data = fetch_json(BASE_URL_PANOS + str(pano_id))
        pano_entry = parse_pano_data(data)
        if pano_entry:
            all_panos.append(pano_entry)
            successful_panos_count += 1


    # Save final data
    if all_panos:
        df = pd.DataFrame(all_panos)
        df.to_parquet(output_path, index=False)
    print(f"Saved {successful_panos_count} panos to {output_path}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pano", type=int, default=MAX_PANO)
    args = parser.parse_args()
    extract_panos(end_id=args.max_pano)
