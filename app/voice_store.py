"""Persistent registry of cloned voices.

Samples live on disk under `<voices_dir>/samples/`; metadata in a JSON index so
enrolled voices survive restarts. On startup the app re-enrols each record into
its owning backend."""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import get_settings


@dataclass
class VoiceRecord:
    id: str
    name: str
    created_at: int
    backend: str
    sample_path: str
    # Enrolment quality knobs, persisted so re-enrolment on restart reproduces
    # the same clone. Defaults keep old registries (missing these keys) valid.
    denoise: bool = True
    use_ref_codes: bool = True
    # Engine-specific enrolment params (e.g. a clone-first engine's ref_text),
    # persisted so restart re-enrols identically. Empty default keeps old
    # registries (missing this key) loading via the same defaulted-field pattern.
    enrol_options: dict = field(default_factory=dict)


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

    def create(
        self,
        name: str,
        sample: bytes,
        suffix: str,
        backend: str,
        denoise: bool = True,
        use_ref_codes: bool = True,
        voice_id: str | None = None,
        enrol_options: dict | None = None,
    ) -> VoiceRecord:
        self._load()
        if not voice_id:
            voice_id = "voice_" + secrets.token_hex(12)

        # If updating an existing voice, clean up any old sample file if suffix changed
        old_record = self._records.get(voice_id)
        sample_path = self.samples_dir / f"{voice_id}{suffix or '.wav'}"
        if old_record and old_record.sample_path != str(sample_path):
            Path(old_record.sample_path).unlink(missing_ok=True)

        sample_path.write_bytes(sample)
        record = VoiceRecord(
            id=voice_id,
            name=name,
            created_at=int(time.time()),
            backend=backend,
            sample_path=str(sample_path),
            denoise=denoise,
            use_ref_codes=use_ref_codes,
            enrol_options=dict(enrol_options or {}),
        )
        self._records[voice_id] = record
        self._save()
        return record

    def list(self) -> list[VoiceRecord]:
        # Re-read from disk so records created by another worker/instance
        # sharing this registry.json are visible (workers cache in memory).
        self._load()
        return list(self._records.values())

    def get(self, voice_id: str) -> VoiceRecord | None:
        self._load()  # pick up cross-worker writes since startup
        return self._records.get(voice_id)

    def delete(self, voice_id: str) -> bool:
        self._load()  # ensure we see (and can remove) cross-worker records
        record = self._records.pop(voice_id, None)
        if record is None:
            return False
        Path(record.sample_path).unlink(missing_ok=True)
        self._save()
        return True


#: Process-wide singleton.
voice_store = VoiceStore(Path(get_settings().voices_dir))
