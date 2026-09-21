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
from rich.console import Console

console = Console()


def calculate_hashes(file_path: str) -> dict:
    """
    Ingest a file: calculate SHA-256 + MD5 with progress bar,
    early time estimate, and slow-ingestion detection.
    """
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = path.stat().st_size
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()

    chunk_size = 1024 * 1024  # 1 MB
    processed = 0
    start_time = time.perf_counter()

    # Calibration after first 8 MB
    calibration_size = 8 * 1024 * 1024
    expected_total_time = None
    warning_triggered = False
    estimated_seconds = None

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

                chunk_len = len(chunk)
                processed += chunk_len
                progress.update(task, advance=chunk_len)

                # After enough data → calculate and show estimate
                if expected_total_time is None and processed >= calibration_size:
                    elapsed = time.perf_counter() - start_time
                    speed = processed / elapsed  # bytes per second
                    expected_total_time = file_size / speed
                    estimated_seconds = expected_total_time

                    # Human-readable estimate
                    if estimated_seconds < 60:
                        eta_str = f"{estimated_seconds:.1f} seconds"
                    else:
                        eta_str = f"{estimated_seconds / 60:.1f} minutes"

                    progress.console.print(
                        f"[cyan]Estimate:[/cyan] ~{eta_str} remaining "
                        f"(based on current speed)"
                    )

                # Health check
                if expected_total_time and not warning_triggered:
                    elapsed = time.perf_counter() - start_time
                    if elapsed > expected_total_time * 1.8:
                        progress.console.print(
                            "\n[bold yellow]Warning:[/bold yellow] "
                            "Ingestion is significantly slower than expected. "
                            "Possible disk or system issue."
                        )
                        warning_triggered = True

    mime_type, _ = mimetypes.guess_type(str(path))

    return {
        "sha256": sha256.hexdigest(),
        "md5": md5.hexdigest(),
        "size": file_size,
        "mime_type": mime_type or "application/octet-stream",
        "filename": path.name,
        "warning": "slow_ingestion" if warning_triggered else None,
        "estimated_seconds": estimated_seconds,
    }
