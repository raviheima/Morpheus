import hashlib
import mimetypes
from pathlib import Path


def calculate_hashes(file_path: str) -> dict:
    """
    Calculate SHA-256 and MD5 hashes of a file without loading the whole file into memory.
    Returns a dictionary with hashes, size, and mime type.
    """
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256 = hashlib.sha256()
    md5 = hashlib.md5()

    file_size = 0

    with open(path, "rb") as f:
        while chunk := f.read(8192):  # read in 8 KB chunks
            sha256.update(chunk)
            md5.update(chunk)
            file_size += len(chunk)

    mime_type, _ = mimetypes.guess_type(str(path))

    return {
        "sha256": sha256.hexdigest(),
        "md5": md5.hexdigest(),
        "size": file_size,
        "mime_type": mime_type or "application/octet-stream",
        "filename": path.name,
    }
