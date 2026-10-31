from pathlib import Path

BASE_URL_ITEMS = "https://api.dofusdb.fr/items"
BASE_URL_PANOS = "https://api.dofusdb.fr/item-sets"

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "extracted"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

ITEMS_FILE = PROCESSED_DIR / "dofus_items_processed.parquet"
BONUSES_FILE = PROCESSED_DIR / "dofus_panos_processed.parquet"

# ["Chapeau", "Cape", "Anneau", "Amulette", "Baguette", "Bottes", "Ceinture", "Marteau", "Bâton", "Arc",
#  "Dague", "Épée", "Hache", "Faux", "Pelle", "Trophée", "Dofus", "Boucliers"]
# ["Familier", "Montilier", "Dragodinde", "Muldo", "Volkorne"]: a single slot shared by pets and mounts
PET_MOUNT_TYPES = [18, 121, 331, 332, 333]
EQUIP_TYPES = [16, 17, 9, 1, 3, 11, 10, 7, 4, 2, 5, 6, 19, 22, 8, 151, 23, 82] + PET_MOUNT_TYPES

PAGE_SIZE = 50
