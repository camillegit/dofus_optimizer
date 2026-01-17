from pathlib import Path

BASE_URL_ITEMS = "https://api.dofusdb.fr/items/"
BASE_URL_PANOS = "https://api.dofusdb.fr/item-sets/"

DATA_DIR = Path("data/extracted")
DATA_DIR.mkdir(parents=True, exist_ok=True)

MAX_ITEM = 50000
MAX_PANO = 1500

ITEMS_FILE = Path("data/processed/dofus_items_processed.parquet")
BONUSES_FILE = Path("data/processed/dofus_panos_processed.parquet")
