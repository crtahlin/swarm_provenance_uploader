import requests
from urllib.parse import urljoin

# Define custom exceptions later if needed
# class SwarmApiException(Exception):
#    pass

def purchase_postage_stamp(gateway_url: str, depth: int, amount: int) -> str:
    """
   Purchases a new postage stamp from the Bee Gateway.
   Returns the Stamp ID (batchID).
    """
    headers = {"Content-Type": "application/json"}
    # Bee API uses {depth}/{amount}
    api_path = f"/stamps/{depth}/{amount}"
    url = urljoin(gateway_url, api_path)

    try:
       response = requests.post(url, headers=headers, timeout=20)
       response.raise_for_status() # Raise HTTPError for 4xx/5xx
       response_json = response.json()
       stamp_id = response_json.get("batchID")
       if not stamp_id:
            raise ValueError("API Response missing 'batchID'")
       return stamp_id
    except requests.exceptions.RequestException as e:
        # Wrap network/http errors
        raise ConnectionError(f"Stamp purchase failed: {e}") from e
    except (ValueError, KeyError) as e:
        # Wrap JSON parsing/content errors
       raise ValueError(f"Could not parse stamp purchase response: {e}") from e


def upload_data(gateway_url: str, data_to_upload: bytes, stamp_id: str, content_type: str = "application/json") -> str:
   """
   Uploads byte data to Swarm via Bee Gateway using a stamp_id.
   Returns the Swarm reference hash.
   """
   headers = {
        "Swarm-Postage-Batch-Id": stamp_id,
        "Content-Type": content_type
        }
   api_path = "/bzz"
   url = urljoin(gateway_url, api_path)

   try:
       response = requests.post(url, data=data_to_upload, headers=headers, timeout=60) # Longer timeout for upload
       response.raise_for_status() # Raise HTTPError for 4xx/5xx
       response_json = response.json()
       swarm_hash = response_json.get("reference")
       if not swarm_hash:
            raise ValueError("API Response missing 'reference'")
       return swarm_hash
   except requests.exceptions.RequestException as e:
        # Wrap network/http errors
        raise ConnectionError(f"Swarm upload failed: {e}") from e
   except (ValueError, KeyError) as e:
        # Wrap JSON parsing/content errors
       raise ValueError(f"Could not parse upload response: {e}") from e
