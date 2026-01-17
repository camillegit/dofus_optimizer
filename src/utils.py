import requests
import time
from requests.exceptions import RequestException


def fetch_json(url: str, max_retries: int = 1, retry_delay: float = 2.0):
    """Fetch JSON from a URL with retries."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # Silently ignore 404s as they often indicate non-existent IDs in sparse ranges
                return None
            else:
                print(f"Non-200 status ({response.status_code}) for URL {url}")
        except RequestException as e:
            print(f"Request error for URL {url}: {e}")
        time.sleep(retry_delay)
    # Only log final failure if not due to 404
    if response and response.status_code != 404:
        print(f"Failed to fetch URL {url} after {max_retries} retries.")
    return None