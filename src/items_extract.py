import pandas as pd
from tqdm import tqdm
from .utils import fetch_json
from .config import BASE_URL_ITEMS, DATA_DIR, MAX_ITEM
from datetime import datetime

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
        "condition": item.get("criterions"),
    }

    # Iterate over each effect in the 'effects' list
    for effect in item.get("effects", []):
        characteristic = effect.get("characteristic")
        from_value = effect.get("from")
        to_value = effect.get("to")

        # Check if both 'from' and 'to' exist, then take the max of both
        if characteristic is not None and from_value is not None and to_value is not None:
            highest_value = max(from_value, to_value)
            # Create a key based on the characteristic value and set its value to the highest of 'from' and 'to'
            entry[f"characteristic_{characteristic}"] = highest_value
    
    return entry


def extract_items(start_id: int = 0, end_id: int = MAX_ITEM):
    """Fetch and parse all item data within ID range."""
    all_items = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = DATA_DIR / f"dofus_items_{timestamp}.parquet"
    successful_items_count = 0

    print(f"Starting extraction for items ({start_id} → {end_id})")

    for item_id in tqdm(range(start_id, end_id), desc="Fetching Items"):
        data = fetch_json(BASE_URL_ITEMS + str(item_id))
        item_entry = parse_item_data(data)
        if item_entry:
            all_items.append(item_entry)
            successful_items_count += 1

    # Save final data
    if all_items:
        df = pd.DataFrame(all_items)
        df.to_parquet(output_path, index=False)
    print(f"Saved {successful_items_count} items to {output_path}")

