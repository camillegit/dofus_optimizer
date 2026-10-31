import time

import requests
from requests.exceptions import RequestException
from tqdm import tqdm

from .config import PAGE_SIZE

session = requests.Session()


def fetch_json(url: str, params=None, max_retries: int = 3, retry_delay: float = 2.0):
    """Fetch JSON from a URL with retries. Returns None on 404 or after repeated failures."""
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                return None
            print(f"Non-200 status ({response.status_code}) for URL {url}")
        except RequestException as e:
            print(f"Request error for URL {url}: {e}")
        if attempt < max_retries:
            time.sleep(retry_delay * attempt)
    print(f"Failed to fetch URL {url} after {max_retries} attempts.")
    return None


def fetch_all(url: str, params=None, desc: str = "Fetching"):
    """Fetch every record of a paginated DofusDB (Feathers) endpoint."""
    params = list((params or {}).items()) if isinstance(params, dict) else list(params or [])
    records, skip, total = [], 0, None
    with tqdm(desc=desc) as progress:
        while total is None or skip < total:
            page = fetch_json(url, params + [("$limit", PAGE_SIZE), ("$skip", skip)])
            if page is None:
                raise RuntimeError(f"Could not fetch {url} at offset {skip}")
            total = page["total"]
            progress.total = total
            data = page["data"]
            if not data:
                break
            records.extend(data)
            skip += len(data)
            progress.update(len(data))
    return records
