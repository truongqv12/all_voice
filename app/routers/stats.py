"""GET /v1/stats — public live usage gauge (aggregate only, never any IP).

- ``active``: distinct client IPs seen in the trailing presence window
  ("đang dùng" — currently using the app).
- ``total``: distinct client IPs that have ever synthesised/transcribed
  ("đã dùng" — people who have used the service).

Public like ``/v1/models`` (no key needed). The ``COUNT(DISTINCT)`` behind
``total`` runs off the event loop (SQLite is synchronous) and is TTL-cached
inside ``quota.total_users``.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..presence import presence
from ..quota import quota
from ..schemas import UsageStats

router = APIRouter()


@router.get("/stats", response_model=UsageStats, tags=["system"], summary="Thống kê sử dụng")
async def usage_stats(settings: Settings = Depends(get_settings)) -> UsageStats:
    active = presence.active_count(settings.stats_active_window_s)
    total = await anyio.to_thread.run_sync(quota.total_users)
    return UsageStats(active=active, total=total)
