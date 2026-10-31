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
    This function preprocesses the panos data (cumulative bonus per number of pieces worn).
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

    # Bonus columns keep the cumulative value of each tier (bonus_<k>_characteristic_<c>):
    # in game, the k-pieces tier replaces the lower ones.

    df.to_parquet(processed_panos_path, index=False)
    print(f"Processed panos saved to: {processed_panos_path}")


if __name__ == "__main__":
    preprocess_items()
    preprocess_panos()
