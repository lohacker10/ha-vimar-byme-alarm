"""Read-only live SAI event access."""

from __future__ import annotations


class VimarEventsMixin:
    """Read SAI event-log deltas without assigning unrelated semantics."""

    def get_latest_sai_event_id(self) -> int:
        """Return the newest retained SAI log ID, or zero when the log is empty."""
        rows = self._select(
            "SELECT ID FROM DPADD_BYME_LOG "
            "WHERE CATEGORY='SAI' ORDER BY ID DESC LIMIT 0,1"
        )
        if not rows:
            return 0
        try:
            return int(rows[0].get("ID", "0"))
        except (TypeError, ValueError):
            return 0

    def get_sai_events_after(
        self, event_id: int, limit: int = 500
    ) -> list[dict[str, str]]:
        """Return SAI rows newer than an already observed numeric log ID."""
        safe_event_id = max(int(event_id), 0)
        safe_limit = min(max(int(limit), 1), 500)
        return self._select(
            "SELECT ID,TIMESTAMP,ZONE_ID,ZONE_NUMBER,"
            "PARTIALIZATION_ID,PARTIALIZATION_NUMBER,"
            "DEVICE_ID,DEVICE_ADDRESS,MESSAGE,EVENT_TYPE,CATEGORY "
            "FROM DPADD_BYME_LOG "
            f"WHERE CATEGORY='SAI' AND ID>{safe_event_id} "
            f"ORDER BY ID ASC LIMIT 0,{safe_limit}"
        )
