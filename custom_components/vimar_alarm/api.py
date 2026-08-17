"""Minimal Vimar 01946 By-me SAI client.

Verified on firmware 2.11.

The SAI PIN is transient: it is accepted as a method argument, sent only to the
SAI authentication/command calls, and is never persisted or logged.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import ssl
import time
from typing import Any
import xml.etree.ElementTree as ET

import requests
from requests import adapters

from .const import PARTITIONS_CONTAINER, STATE_ARMED, STATE_DISARMED


class VimarAlarmError(Exception):
    """Base error."""


class VimarAlarmConnectionError(VimarAlarmError):
    """Connection/protocol error."""


class VimarAlarmAuthError(VimarAlarmError):
    """Web Server username/password error."""


class VimarAlarmInvalidPin(VimarAlarmError):
    """Invalid SAI PIN."""


class VimarAlarmEnrollmentError(VimarAlarmError):
    """SAI enrollment incomplete."""


class VimarAlarmPermissionError(VimarAlarmError):
    """PIN has no grant for a partialization."""


class VimarAlarmCommandError(VimarAlarmError):
    """Command failed."""


@dataclass(frozen=True, slots=True)
class VimarPartition:
    object_id: int
    name: str
    index_id: int
    status_id: int


class VimarHTTPAdapter(adapters.HTTPAdapter):
    """TLS compatibility copied from the approach used by home-assistant-vimar."""

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> Any:
        ctx = ssl.create_default_context()
        ctx.options &= ~ssl.OP_NO_TLSv1_3 & ~ssl.OP_NO_TLSv1_2 & ~ssl.OP_NO_TLSv1_1
        ctx.minimum_version = ssl.TLSVersion.TLSv1
        ctx.check_hostname = False
        ctx.set_ciphers("AES256-SHA")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _find_xml(root: ET.Element, name: str) -> ET.Element | None:
    for node in root.iter():
        if node.tag.split("}")[-1] == name:
            return node
    return None


def _xml_text(root: ET.Element, name: str, default: str = "") -> str:
    node = _find_xml(root, name)
    return default if node is None or node.text is None else node.text.strip()


def _parse_sql_payload(payload: str | None) -> list[dict[str, str]]:
    if not payload:
        return []
    keys: list[str] = []
    rows: list[dict[str, str]] = []
    for raw in payload.splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        prefix, values = line.split(":", 1)
        prefix = prefix.strip()
        if prefix in {"Response", "NextRows"}:
            continue
        values = values.strip()
        parts = values[1:-1].split("','") if len(values) >= 2 and values[0] == "'" and values[-1] == "'" else [values]
        if prefix == "Row000001":
            keys = parts
        elif keys:
            rows.append({keys[i]: value for i, value in enumerate(parts[: len(keys)])})
    return rows


def _escape_sql(sql: str) -> str:
    return (
        sql.replace("&", "&amp;")
        .replace('"', "&apos;")
        .replace("'", "&apos;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _assert_select(sql: str) -> str:
    q = sql.strip().rstrip(";").strip()
    if not re.match(r"^SELECT\b", q, re.IGNORECASE):
        raise ValueError("Only SELECT is allowed")
    if ";" in q or "--" in q or "/*" in q or re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|MERGE|CALL|"
        r"EXEC|EXECUTE|INTO|OUTFILE|LOAD|SET|GRANT|REVOKE)\b",
        q,
        re.IGNORECASE,
    ):
        raise ValueError("Unsafe SQL rejected")
    return q


class VimarAlarmApi:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        port: int = 443,
        verify_ssl: bool = False,
        timeout: int = 8,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self._session_id: str | None = None

    @property
    def base_url(self) -> str:
        return f"https://{self.host}:{self.port}"

    def _session(self) -> requests.Session:
        s = requests.Session()
        s.trust_env = False
        s.mount("https://", VimarHTTPAdapter())
        return s

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        try:
            with self._session() as session:
                response = session.request(
                    method,
                    f"{self.base_url}{path}",
                    params=params,
                    data=body,
                    headers=headers,
                    verify=self.verify_ssl,
                    timeout=(max(2, self.timeout // 2), self.timeout),
                )
                response.raise_for_status()
                return response.text
        except requests.RequestException as err:
            # Never include the URL/body in the exception: they can contain secrets.
            raise VimarAlarmConnectionError(
                f"Vimar connection failed ({type(err).__name__})"
            ) from err

    @staticmethod
    def _parse_xml(text: str) -> ET.Element:
        try:
            return ET.fromstring(text)
        except ET.ParseError as err:
            raise VimarAlarmConnectionError("Invalid XML from Vimar") from err

    def login(self) -> None:
        root = self._parse_xml(
            self._request(
                "GET",
                "/vimarbyweb/modules/system/user_login.php",
                params={
                    "sessionid": "",
                    "username": self.username,
                    "password": self.password,
                    "remember": "0",
                    "op": "login",
                },
            )
        )
        result = _xml_text(root, "result")
        if result and result != "0":
            raise VimarAlarmAuthError("Vimar rejected the Web Server credentials")
        sid = _xml_text(root, "sessionid")
        if not sid:
            raise VimarAlarmAuthError("Vimar login returned no session id")
        self._session_id = sid

    def _ensure_login(self) -> None:
        if not self._session_id:
            self.login()

    def _soap(self, inner: str) -> ET.Element:
        self._ensure_login()
        envelope = (
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
            f"<soapenv:Body>{inner}</soapenv:Body></soapenv:Envelope>"
        )
        return self._parse_xml(
            self._request(
                "POST",
                "/cgi-bin/dpadws",
                body=envelope,
                headers={
                    "SOAPAction": "dbSoapRequest",
                    "SOAPServer": "",
                    "Content-Type": 'text/xml; charset="UTF-8"',
                    "Expect": "",
                },
            )
        )

    def _select_once(self, sql: str) -> tuple[str, list[dict[str, str]]]:
        statement = _escape_sql(_assert_select(sql))
        root = self._soap(
            '<service-databasesocketoperation xmlns="urn:xmethods-dpadws">'
            "<payload>NO-PAYLOAD</payload>"
            "<hashcode>NO-HASCHODE</hashcode>"
            "<optionals>NO-OPTIONAL</optionals>"
            "<callsource>WEB-DOMUSPAD_SOAP</callsource>"
            f"<sessionid>{self._session_id}</sessionid>"
            "<waittime>5</waittime>"
            "<function>DML-SQL</function>"
            "<type>SELECT</type>"
            f"<statement>{statement}</statement>"
            f"<statement-len>{len(statement)}</statement-len>"
            "</service-databasesocketoperation>"
        )
        payload = _find_xml(root, "payload")
        return (
            _xml_text(root, "result"),
            _parse_sql_payload(payload.text if payload is not None else None),
        )

    def _select(self, sql: str) -> list[dict[str, str]]:
        result, rows = self._select_once(sql)
        if result.startswith("LGMG"):
            self._session_id = None
            self.login()
            result, rows = self._select_once(sql)
        if result and result != "DPCM-0000":
            raise VimarAlarmConnectionError(f"Vimar SELECT failed: {result}")
        return rows

    def get_partitions(self) -> list[VimarPartition]:
        rows = self._select(
            "SELECT p.ID AS object_id,p.NAME AS object_name,p.OPTIONALP AS optionalp,"
            "s.ID AS status_id "
            "FROM DPADD_OBJECT container "
            "INNER JOIN DPADD_OBJECT_RELATION r ON container.ID=r.PARENTOBJ_ID "
            "INNER JOIN DPADD_OBJECT p ON r.CHILDOBJ_ID=p.ID "
            "INNER JOIN DPADD_OBJECT_RELATION sr ON p.ID=sr.PARENTOBJ_ID "
            "AND sr.RELATION_WEB_TIPOLOGY='BYME_IDXOBJ_RELATION' "
            "INNER JOIN DPADD_OBJECT s ON sr.CHILDOBJ_ID=s.ID AND s.NAME='state' "
            f"WHERE container.NAME='{PARTITIONS_CONTAINER}' "
            "AND r.RELATION_WEB_TIPOLOGY='GENERIC_RELATION' "
            "AND p.VALUES_TYPE LIKE 'CH_SAI%' ORDER BY p.ID"
        )
        out: list[VimarPartition] = []
        for row in rows:
            match = re.search(r"(?:^|\|)index_id=(\d+)(?:\||$)", row.get("optionalp", ""))
            if not match:
                continue
            try:
                out.append(
                    VimarPartition(
                        object_id=int(row["object_id"]),
                        name=row.get("object_name") or f"Partition {match.group(1)}",
                        index_id=int(match.group(1)),
                        status_id=int(row["status_id"]),
                    )
                )
            except (KeyError, ValueError):
                continue
        return out

    def get_partition_states(self, partitions: list[VimarPartition]) -> dict[int, str]:
        if not partitions:
            return {}
        ids = ",".join(str(p.status_id) for p in partitions)
        rows = self._select(
            f"SELECT ID,CURRENT_VALUE FROM DPADD_OBJECT WHERE ID IN ({ids}) ORDER BY ID"
        )
        status_values = {int(row["ID"]): row.get("CURRENT_VALUE", "") for row in rows}
        return {p.object_id: status_values.get(p.status_id, "") for p in partitions}

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
        return _xml_text(root, "result"), _xml_text(root, "partializationgrants")

    def get_sai_grants(self, pin: str | None) -> str:
        code = self._validate_pin(pin)
        result, grants = self._grants_once(code)
        if result.startswith("LGMG"):
            self._session_id = None
            self.login()
            result, grants = self._grants_once(code)
        try:
            code_number = int(result.split("-", 1)[1])
        except (IndexError, ValueError) as err:
            raise VimarAlarmCommandError("Unexpected SAI authentication response") from err
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

    def _setvalue_once(self, partition: VimarPartition, value: str, pin: str) -> str:
        # Firmware 2.11 web UI passes the transient authenticated PIN as hashcode.
        # Do not log this body.
        root = self._soap(
            '<service-runonelement xmlns="urn:xmethods-dpadws">'
            f"<payload>{value}</payload>"
            f"<hashcode>{pin}</hashcode>"
            "<optionals>NO-OPTIONALS</optionals>"
            "<callsource>WEB</callsource>"
            f"<sessionid>{self._session_id}</sessionid>"
            "<waittime>5</waittime>"
            f"<idobject>{partition.object_id}</idobject>"
            "<operation>SETVALUE</operation>"
            "</service-runonelement>"
        )
        return _xml_text(root, "result")

    def set_partition_state(
        self, partition: VimarPartition, *, armed: bool, pin: str | None
    ) -> None:
        code = self._validate_pin(pin)
        grants = self.get_sai_grants(code)
        if not self._has_grant(grants, partition.index_id):
            raise VimarAlarmPermissionError(
                f"PIN has no grant for partition {partition.name}"
            )

        target = STATE_ARMED if armed else STATE_DISARMED
        result = self._setvalue_once(partition, target, code)
        if result.startswith("LGMG"):
            self._session_id = None
            self.login()
            grants = self.get_sai_grants(code)
            if not self._has_grant(grants, partition.index_id):
                raise VimarAlarmPermissionError(
                    f"PIN has no grant for partition {partition.name}"
                )
            result = self._setvalue_once(partition, target, code)

        if result and result != "DPCM-0000":
            raise VimarAlarmCommandError(f"Vimar SETVALUE failed: {result}")

        # Confirm real state; do not use optimistic UI state for an alarm.
        for _ in range(12):
            current = self.get_partition_states([partition]).get(partition.object_id)
            if current == target:
                return
            time.sleep(0.5)
        raise VimarAlarmCommandError(
            f"Partition {partition.name} did not reach the requested state"
        )

    def test_connection(self) -> list[VimarPartition]:
        self.login()
        return self.get_partitions()
