import hashlib
import mimetypes
import time
from pathlib import Path
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
    FileSizeColumn,
)


def calculate_hashes(file_path: str) -> dict:
    """
    Calculate SHA-256 and MD5 of a file with a live progress bar.
    Shows speed and estimated time remaining.
    """
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = path.stat().st_size
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()

    chunk_size = 1024 * 1024  # 1 MB chunks (good balance)

    with Progress(
        TextColumn("[bold blue]Ingesting..."),
        BarColumn(bar_width=40),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        FileSizeColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
        transient=False,
    ) as progress:

        task = progress.add_task("hashing", total=file_size)

        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256.update(chunk)
                md5.update(chunk)
                progress.update(task, advance=len(chunk))

    mime_type, _ = mimetypes.guess_type(str(path))

    return {
        "sha256": sha256.hexdigest(),
        "md5": md5.hexdigest(),
        "size": file_size,
        "mime_type": mime_type or "application/octet-stream",
        "filename": path.name,
    }
