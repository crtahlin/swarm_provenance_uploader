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
