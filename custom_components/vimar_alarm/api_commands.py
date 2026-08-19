"""SAI authentication, explicit commands, and read-only history."""

from __future__ import annotations

import re
import time

from .api_core import (
    VimarAlarmCommandError,
    VimarAlarmEnrollmentError,
    VimarAlarmInvalidPin,
    VimarAlarmPermissionError,
    VimarPartition,
    _xml_text,
)
from .const import STATE_ARMED, STATE_DISARMED


class VimarCommandsMixin:
    @staticmethod
    def _validate_pin(pin: str | None) -> str:
        if pin is None or not re.fullmatch(r"\d{5}", pin):
            raise VimarAlarmInvalidPin("SAI PIN must contain exactly 5 digits")
        return pin

    def _grants_once(self, pin: str) -> tuple[str, str]:
        root = self._soap(
            '<service-vimarsaigetusergrants xmlns="urn:xmethods-dpadws">'
            "<payload>NO-PAYLOAD</payload>"
            "<hashcode>NO-HASCHODE</hashcode>"
            "<optionals>NO-OPTIONAL</optionals>"
            "<callsource>WEB-DOMUSPAD_SOAP</callsource>"
            f"<sessionid>{self._session_id}</sessionid>"
            "<waittime>5</waittime>"
            f"<pin>{pin}</pin>"
            "</service-vimarsaigetusergrants>"
        )
        return (_xml_text(root, "result"), _xml_text(root, "partializationgrants"))

    def get_sai_grants(self, pin: str | None) -> str:
        with self._lock:
            code = self._validate_pin(pin)
            result, grants = self._grants_once(code)
            if result.startswith("LGMG"):
                self._session_id = None
                self.login()
                result, grants = self._grants_once(code)
            try:
                code_number = int(result.split("-", 1)[1])
            except (IndexError, ValueError) as err:
                raise VimarAlarmCommandError(
                    "Unexpected SAI authentication response"
                ) from err
            if code_number == 2223:
                raise VimarAlarmInvalidPin("Invalid Vimar SAI PIN")
            if code_number == 2224:
                raise VimarAlarmEnrollmentError("Vimar SAI enrollment incomplete")
            if code_number != 0:
                raise VimarAlarmCommandError(
                    f"Vimar SAI authentication failed with code {code_number}"
                )
            return grants

    @staticmethod
    def _has_grant(grants: str, index_id: int) -> bool:
        pos = index_id - 1
        return 0 <= pos < len(grants) and grants[pos] == "1"

    def _setvalue_once(
        self,
        partition: VimarPartition,
        value: str,
        pin: str,
        *,
        optionals: str = "NO-OPTIONALS",
    ) -> str:
        root = self._soap(
            '<service-runonelement xmlns="urn:xmethods-dpadws">'
            f"<payload>{value}</payload>"
            f"<hashcode>{pin}</hashcode>"
            f"<optionals>{optionals}</optionals>"
            "<callsource>WEB</callsource>"
            f"<sessionid>{self._session_id}</sessionid>"
            "<waittime>5</waittime>"
            f"<idobject>{partition.object_id}</idobject>"
            "<operation>SETVALUE</operation>"
            "</service-runonelement>"
        )
        return _xml_text(root, "result")

    def _verify_partition_targets(
        self, partitions: list[VimarPartition], target: str
    ) -> None:
        for _ in range(12):
            states = self.get_partition_states(partitions)
            if all(states.get(partition.object_id) == target for partition in partitions):
                return
            time.sleep(0.5)
        raise VimarAlarmCommandError(
            "Not all partitions reached the requested state"
        )

    def set_partition_state(
        self,
        partition: VimarPartition,
        *,
        armed: bool,
        pin: str | None,
    ) -> None:
        self.set_multiple_partition_states([partition], armed=armed, pin=pin)

    def set_multiple_partition_states(
        self,
        partitions: list[VimarPartition],
        *,
        armed: bool,
        pin: str | None,
    ) -> None:
        """Set partializations using the same batch pattern as the Vimar Web UI.

        Vimar 01946 firmware 2.11 sends selected partializations in descending
        SAI index order. Every command except the last uses SYNCDB; the final
        command uses NO-OPTIONALS. A single-partition command therefore keeps
        using NO-OPTIONALS.
        """
        with self._lock:
            if not partitions:
                return

            code = self._validate_pin(pin)
            grants = self.get_sai_grants(code)
            denied = [
                partition.name
                for partition in partitions
                if not self._has_grant(grants, partition.index_id)
            ]
            if denied:
                raise VimarAlarmPermissionError(
                    "PIN has no grant for: " + ", ".join(denied)
                )

            target = STATE_ARMED if armed else STATE_DISARMED
            current = self.get_partition_states(partitions)
            pending = [
                partition
                for partition in partitions
                if current.get(partition.object_id) != target
            ]
            pending.sort(key=lambda partition: partition.index_id, reverse=True)

            for position, partition in enumerate(pending):
                optionals = (
                    "SYNCDB"
                    if position < len(pending) - 1
                    else "NO-OPTIONALS"
                )
                result = self._setvalue_once(
                    partition,
                    target,
                    code,
                    optionals=optionals,
                )
                if result.startswith("LGMG"):
                    self._session_id = None
                    self.login()
                    grants = self.get_sai_grants(code)
                    if not self._has_grant(grants, partition.index_id):
                        raise VimarAlarmPermissionError(
                            f"PIN has no grant for partition {partition.name}"
                        )
                    result = self._setvalue_once(
                        partition,
                        target,
                        code,
                        optionals=optionals,
                    )

                if result and result != "DPCM-0000":
                    raise VimarAlarmCommandError(
                        f"Vimar SETVALUE failed for {partition.name}: {result}"
                    )

            self._verify_partition_targets(partitions, target)

    def get_recent_sai_events(
        self, limit: int = 100
    ) -> list[dict[str, str]]:
        """Read recent SAI log rows without room/user-defined display names."""
        safe_limit = min(max(int(limit), 1), 500)
        return self._select(
            "SELECT ID,TIMESTAMP,ZONE_ID,ZONE_NUMBER,"
            "PARTIALIZATION_ID,PARTIALIZATION_NUMBER,"
            "DEVICE_ID,DEVICE_ADDRESS,MESSAGE,EVENT_TYPE,CATEGORY "
            "FROM DPADD_BYME_LOG "
            "WHERE CATEGORY='SAI' "
            f"ORDER BY TIMESTAMP DESC LIMIT 0,{safe_limit}"
        )

    def get_nonstandard_sai_events(
        self, limit: int = 200
    ) -> list[dict[str, str]]:
        """Read historical SAI rows whose event class is not normal 0/1.

        These rows are useful for identifying alarm, tamper, fault, and restore
        semantics without deliberately generating an alarm. Display-name
        columns are intentionally omitted from diagnostics.
        """
        safe_limit = min(max(int(limit), 1), 500)
        return self._select(
            "SELECT ID,TIMESTAMP,ZONE_ID,ZONE_NUMBER,"
            "PARTIALIZATION_ID,PARTIALIZATION_NUMBER,"
            "DEVICE_ID,DEVICE_ADDRESS,MESSAGE,EVENT_TYPE,CATEGORY "
            "FROM DPADD_BYME_LOG "
            "WHERE CATEGORY='SAI' AND EVENT_TYPE NOT IN (0,1) "
            f"ORDER BY TIMESTAMP DESC LIMIT 0,{safe_limit}"
        )

    def get_sai_event_summary(self) -> list[dict[str, str]]:
        """Summarize all historical SAI event classes using read-only SQL."""
        return self._select(
            "SELECT MESSAGE,EVENT_TYPE,COUNT(*) AS event_count,"
            "MIN(TIMESTAMP) AS first_timestamp,"
            "MAX(TIMESTAMP) AS last_timestamp "
            "FROM DPADD_BYME_LOG "
            "WHERE CATEGORY='SAI' "
            "GROUP BY MESSAGE,EVENT_TYPE "
            "ORDER BY MESSAGE,EVENT_TYPE"
        )

    def test_connection(self) -> list[VimarPartition]:
        self.login()
        return self.get_partitions()
