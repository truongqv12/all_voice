"""Persistent registry of cloned voices.

Samples live on disk under `<voices_dir>/samples/`; metadata in a JSON index so
enrolled voices survive restarts. On startup the app re-enrols each record into
its owning backend."""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import get_settings


@dataclass
class VoiceRecord:
    id: str
    name: str
    created_at: int
    backend: str
    sample_path: str


class VoiceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.samples_dir = root / "samples"
        self.index_path = root / "registry.json"
        self.samples_dir.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, VoiceRecord] = {}
        self._load()

    def _load(self) -> None:
        if self.index_path.exists():
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
            self._records = {r["id"]: VoiceRecord(**r) for r in raw}

    def _save(self) -> None:
        data = [asdict(r) for r in self._records.values()]
        tmp = self.index_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.index_path)

    def create(self, name: str, sample: bytes, suffix: str, backend: str) -> VoiceRecord:
        voice_id = "voice_" + secrets.token_hex(12)
        sample_path = self.samples_dir / f"{voice_id}{suffix or '.wav'}"
        sample_path.write_bytes(sample)
        record = VoiceRecord(
            id=voice_id,
            name=name,
            created_at=int(time.time()),
            backend=backend,
            sample_path=str(sample_path),
        )
        self._records[voice_id] = record
        self._save()
        return record

    def list(self) -> list[VoiceRecord]:
        return list(self._records.values())

    def get(self, voice_id: str) -> VoiceRecord | None:
        return self._records.get(voice_id)

    def delete(self, voice_id: str) -> bool:
        record = self._records.pop(voice_id, None)
        if record is None:
            return False
        Path(record.sample_path).unlink(missing_ok=True)
        self._save()
        return True


#: Process-wide singleton.
voice_store = VoiceStore(Path(get_settings().voices_dir))
