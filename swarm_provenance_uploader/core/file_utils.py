import hashlib
import base64
from pathlib import Path

def read_file_content(file_path: Path) -> bytes:
    """Reads a file and returns its raw byte content."""
    with file_path.open("rb") as f:
        content = f.read()
    return content

def calculate_sha256(data: bytes) -> str:
     """Calculates SHA256 hash of byte data and returns hex string."""
     return hashlib.sha256(data).hexdigest()

def base64_encode_data(data: bytes) -> str:
     """Base64 encodes byte data and returns UTF-8 decoded string."""
     return base64.b64encode(data).decode('utf-8')

def get_data_size(data: bytes) -> int:
     """Gets the size of byte data."""
     return len(data)
     
def save_bytes_to_file(file_path: Path, data: bytes) -> None:
    """Saves byte data to the specified file_path."""
    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("wb") as f:
        f.write(data)

def base64_decode_data(b64_data: str) -> bytes:
    """Base64 decodes a string and returns bytes."""
    try:
        return base64.b64decode(b64_data)
    except Exception as e: # Catch potential base64 padding errors etc.
        raise ValueError(f"Invalid Base64 data: {e}") from e
