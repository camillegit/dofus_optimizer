import pandas as pd
from .config import DATA_DIR, EQUIP_TYPES, PROCESSED_DIR

def preprocess_items():
    """
    This function preprocesses the items data by filtering and cleaning it.
    """
    processed_items_path = PROCESSED_DIR / "dofus_items_processed.parquet"

    items_files = sorted(DATA_DIR.glob("dofus_items*.parquet"))

    if not items_files:
        print("Source file not found: dofus_items*.parquet")
        return

    items_path = items_files[-1]  # pick the latest one (by name)
    df = pd.read_parquet(items_path)

    # Remove duplicates
    df = df.drop_duplicates(subset="id")

    # Filter for equipment types (banned items are filtered by the optimizer)
    df = df[df["type"].isin(EQUIP_TYPES)]

    df.to_parquet(processed_items_path, index=False)
    print(f"Processed items saved to: {processed_items_path}")

def preprocess_panos():
    """
    This function preprocesses the panos data by calculating incremental bonuses.
    """
    processed_panos_path = PROCESSED_DIR / "dofus_panos_processed.parquet"

    panos_files = sorted(DATA_DIR.glob("dofus_panos*.parquet"))

    if not panos_files:
        print("Source file not found: dofus_panos*.parquet")
        return

    panos_path = panos_files[-1]  # pick the latest one (by name)
    df = pd.read_parquet(panos_path)

    # Replace void (NaN) values with 0
    df.fillna(0, inplace=True)

    # Identify all columns related to bonuses
    bonus_columns = [col for col in df.columns if 'bonus' in col]

    # Parse the bonus columns to understand the structure
    bonus_structure = {}
    for col in bonus_columns:
        parts = col.split('_')
        item_count = int(parts[1])  # Extract the number of items (e.g., '2' or '3')
        characteristic = '_'.join(parts[2:])  # Extract the characteristic (e.g., 'characteristic_10')

        if characteristic not in bonus_structure:
            bonus_structure[characteristic] = []
        bonus_structure[characteristic].append((item_count, col))

    # Sort the bonuses for each characteristic by the number of items
    for characteristic, bonuses in bonus_structure.items():
        bonus_structure[characteristic] = sorted(bonuses, key=lambda x: x[0])

    # Compute the incremental bonuses
    for characteristic, bonuses in bonus_structure.items():
        for i in range(1, len(bonuses)):  # Start from the second item (incremental calculation)
            current_item_count, current_col = bonuses[i]
            
            # Sum all the previous bonuses
            previous_sum = sum(df[bonuses[j][1]] for j in range(i))
            
            # Subtract the cumulative previous bonus sum from the current bonus
            df[current_col] = df[current_col] - previous_sum

    df.to_parquet(processed_panos_path, index=False)
    print(f"Processed panos saved to: {processed_panos_path}")


if __name__ == "__main__":
    preprocess_items()
    preprocess_panos()
