import requests
from urllib.parse import urljoin
import json
from typing import Optional

def purchase_postage_stamp(gateway_url: str, amount: int, depth: int) -> str:
    headers = {"Content-Type": "application/json"}
    api_path = f"/stamps/{amount}/{depth}"
    url = urljoin(gateway_url, api_path)

    print(f"\n--- DEBUG: Attempting Stamp Purchase ---")
    print(f"URL: POST {url}")
    print(f"Headers: {headers}")
    print(f"-------------------------------------\n")

    try:
        response = requests.post(url, headers=headers, timeout=120) # Increased timeout
        print(f"DEBUG: Stamp Purchase Response Status: {response.status_code}")
        response.raise_for_status()
        response_json = response.json()
        stamp_id = response_json.get("batchID")
        if not stamp_id:
             raise ValueError("API Response missing 'batchID' from purchase")
        print(f"DEBUG: Successfully purchased Stamp ID: {stamp_id}")
        return stamp_id
    except requests.exceptions.RequestException as e:
        print(f"ERROR_DETAIL: Stamp purchase request failed. URL: {url}, Error: {e}")
        raise ConnectionError(f"Stamp purchase failed for URL {url}: {e}") from e
    except (ValueError, KeyError) as e:
        response_text_debug = response.text if 'response' in locals() else 'N/A'
        print(f"ERROR_DETAIL: Could not parse stamp purchase response. URL: {url}, Response Text: {response_text_debug}, Error: {e}")
        raise ValueError(f"Could not parse stamp purchase response from URL {url}: {e}") from e


def get_stamp_info(gateway_url: str, stamp_id: str) -> Optional[dict]:
    """
    Retrieves information about a given postage stamp batch.
    Returns the JSON response as a dict if successful (and stamp exists),
    or None if the stamp is not found (404), or raises an error for other issues.
    """
    api_path = f"/stamps/{stamp_id.lower()}" # Ensure stamp_id is lowercase for the GET request
    url = urljoin(gateway_url, api_path)

    print(f"--- DEBUG: Checking Stamp Info ---")
    print(f"URL: GET {url}")
    print(f"--------------------------------\n")

    try:
        response = requests.get(url, timeout=10) # Shorter timeout for GET
        print(f"DEBUG: Get Stamp Info Response Status: {response.status_code}")
        if response.status_code == 404:
            print(f"DEBUG: Stamp {stamp_id} not found (404).")
            return None # Stamp does not exist (yet)
        response.raise_for_status() # Raise HTTPError for other 4xx/5xx
        stamp_details = response.json()
        # Basic validation of expected fields (optional but good)
        if not all(k in stamp_details for k in ("batchID", "usable", "depth", "amount")):
            raise ValueError(f"Stamp info response for {stamp_id} missing expected fields.")
        return stamp_details
    except requests.exceptions.RequestException as e:
        print(f"ERROR_DETAIL: Request to get stamp info failed. URL: {url}, Error: {e}")
        # Decide if you want to re-raise or return a specific indicator of failure
        raise ConnectionError(f"Failed to get stamp info for {stamp_id} from URL {url}: {e}") from e
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        response_text_debug = response.text if 'response' in locals() else 'N/A'
        print(f"ERROR_DETAIL: Could not parse stamp info response. URL: {url}, Response Text: {response_text_debug}, Error: {e}")
        raise ValueError(f"Could not parse stamp info for {stamp_id} from URL {url}: {e}") from e


# ... (upload_data function as before, with its own debug prints) ...
def upload_data(gateway_url: str, data_to_upload: bytes, stamp_id: str, content_type: str = "application/json") -> str:
    actual_stamp_id_for_header = stamp_id.lower()
    headers = {
         "Swarm-Postage-Batch-Id": actual_stamp_id_for_header,
         "Content-Type": content_type
         }
    api_path = "/bzz"
    url = urljoin(gateway_url, api_path)

    print(f"\n--- DEBUG: Attempting Data Upload ---")
    print(f"URL: POST {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    data_preview = data_to_upload.decode('utf-8', errors='replace') if isinstance(data_to_upload, bytes) else str(data_to_upload)
    print(f"Data (first 200 chars): {data_preview[:200]}{'...' if len(data_preview) > 200 else ''}")
    print(f"-----------------------------------\n")

    try:
        response = requests.post(url, data=data_to_upload, headers=headers, timeout=60)
        print(f"DEBUG: Data Upload Response Status: {response.status_code}")
        response.raise_for_status()
        response_json = response.json()
        swarm_hash = response_json.get("reference")
        if not swarm_hash:
             raise ValueError("API Response missing 'reference' from upload")
        print(f"DEBUG: Successfully uploaded. Swarm Reference: {swarm_hash}")
        return swarm_hash
    except requests.exceptions.RequestException as e:
        print(f"ERROR_DETAIL: Data upload request failed. URL: {url}, Headers: {headers}, Error: {e}")
        raise ConnectionError(f"Swarm upload failed for URL {url}: {e}") from e
    except (ValueError, KeyError) as e:
        response_text_debug = response.text if 'response' in locals() else 'N/A'
        print(f"ERROR_DETAIL: Could not parse upload response. URL: {url}, Status: {response.status_code if 'response' in locals() else 'N/A'}, Response Text: {response_text_debug[:500]}..., Error: {e}")
        raise ValueError(f"Could not parse upload response from URL {url}: {e}") from e
