// scripts/download_models.py
"""Utility script to download required ONNX models for the DEAL pipeline.

The script fetches the DeepFilterNet2 model and the speaker embedding model
from predefined URLs and stores them under the ``models/`` directory at the
project root.  It can be invoked manually (e.g. ``python scripts/download_models.py``)
or called from the Docker build stage.
"""
import os
import sys
import hashlib
from pathlib import Path
from urllib.request import urlopen

# ---------------------------------------------------------------------------
# Configuration – replace with the actual model URLs when they become
# available.  For the purpose of this scaffold the URLs are placeholders.
# ---------------------------------------------------------------------------
MODELS = {
    "deepfilternet2.onnx": "https://example.com/models/deepfilternet2.onnx",
    "speaker_embedder.onnx": "https://example.com/models/speaker_embedder.onnx",
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def download(url: str, dest: Path) -> None:
    """Download a file from ``url`` and write it to ``dest``.

    The function streams the content to avoid loading the whole file into
    memory.  A SHA‑256 checksum is printed after download for quick integrity
    verification.
    """
    print(f"Downloading {url} → {dest}")
    with urlopen(url) as response, open(dest, "wb") as out_file:
        while True:
            chunk = response.read(8192)
            if not chunk:
                break
            out_file.write(chunk)
    sha256 = hashlib.sha256(dest.read_bytes()).hexdigest()
    print(f"✅ Saved {dest.name} ({dest.stat().st_size // 1024} KB) – SHA256: {sha256}")


def main() -> int:
    for name, url in MODELS.items():
        dest_path = MODEL_DIR / name
        if dest_path.exists():
            print(f"⚡ {name} already exists, skipping download.")
            continue
        try:
            download(url, dest_path)
        except Exception as e:
            print(f"❌ Failed to download {name}: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
