"""
Simple async JSON-file persistence for price history, stock status, and notification cooldowns.
Each monitor gets its own files inside the data/ directory.
"""
import asyncio
import json
import os
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

_lock = asyncio.Lock()


def _path(filename: str) -> Path:
    return DATA_DIR / filename


async def load(filename: str) -> dict:
    """Load JSON from data/<filename>, returning {} if missing."""
    p = _path(filename)
    if not p.exists():
        return {}
    async with _lock:
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return {}


async def save(filename: str, data: dict) -> None:
    """Atomically write data to data/<filename>."""
    p = _path(filename)
    tmp = p.with_suffix(".tmp")
    async with _lock:
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(p)


# ── Cooldown helpers ──────────────────────────────────────────────────────────

async def is_on_cooldown(filename: str, key: str, cooldown_seconds: int) -> bool:
    """Return True if key was notified within the last cooldown_seconds."""
    data = await load(filename)
    last = data.get(key, 0)
    return (time.time() - last) < cooldown_seconds


async def mark_notified(filename: str, key: str) -> None:
    """Record the current timestamp as the last notification time for key."""
    data = await load(filename)
    data[key] = time.time()
    await save(filename, data)
