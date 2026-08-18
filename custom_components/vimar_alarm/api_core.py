"""Core transport and shared types for Vimar By-me SAI."""
from __future__ import annotations
from dataclasses import dataclass
import re
import ssl
import threading
from typing import Any
import xml.etree.ElementTree as ET
import requests
from requests import adapters
from .const import STATE_ARMED, STATE_DISARMED

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
    """One Vimar SAI partialization."""
    object_id: int
    name: str
    index_id: int
    status_id: int

@dataclass(frozen=True, slots=True)
class VimarContactInput:
    """One raw contact input exposed by a two-input SAI contact interface."""
    interface_object_id: int
    channel_object_id: int
    device_address: str
    input_number: int

@dataclass(frozen=True, slots=True)
class VimarLogicalZone:
    """Logical SAI zone metadata discovered from DPADD_OBJECT."""
    object_id: int
    name: str
    index_id: int
    partition_object_id: int | None

@dataclass(frozen=True, slots=True)
class VimarStateSnapshot:
    """All current values needed by Home Assistant entities."""
    partition_states: dict[int, str]
    contact_states: dict[int, str]

class VimarHTTPAdapter(adapters.HTTPAdapter):
    """TLS compatibility copied from the approach used by home-assistant-vimar."""

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> Any:
        ctx = ssl.create_default_context()
        ctx.options &= ~ssl.OP_NO_TLSv1_3 & ~ssl.OP_NO_TLSv1_2 & ~ssl.OP_NO_TLSv1_1
        ctx.minimum_version = ssl.TLSVersion.TLSv1
        ctx.check_hostname = False
        ctx.set_ciphers('AES256-SHA')
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

def _find_xml(root: ET.Element, name: str) -> ET.Element | None:
    for node in root.iter():
        if node.tag.split('}')[-1] == name:
            return node
    return None

def _xml_text(root: ET.Element, name: str, default: str='') -> str:
    node = _find_xml(root, name)
    return default if node is None or node.text is None else node.text.strip()

def _parse_sql_payload(payload: str | None) -> list[dict[str, str]]:
    if not payload:
        return []
    keys: list[str] = []
    rows: list[dict[str, str]] = []
    for raw in payload.splitlines():
        line = raw.strip()
        if not line or ':' not in line:
            continue
        prefix, values = line.split(':', 1)
        prefix = prefix.strip()
        if prefix in {'Response', 'NextRows'}:
            continue
        values = values.strip()
        parts = values[1:-1].split("','") if len(values) >= 2 and values[0] == "'" and (values[-1] == "'") else [values]
        if prefix == 'Row000001':
            keys = parts
        elif keys:
            rows.append({keys[i]: value for i, value in enumerate(parts[:len(keys)])})
    return rows

def _escape_sql(sql: str) -> str:
    return sql.replace('&', '&amp;').replace('"', '&apos;').replace("'", '&apos;').replace('<', '&lt;').replace('>', '&gt;')

def _assert_select(sql: str) -> str:
    """Fail closed if any database write accidentally reaches this client."""
    q = sql.strip().rstrip(';').strip()
    if not re.match('^SELECT\\b', q, re.IGNORECASE):
        raise ValueError('Only SELECT is allowed')
    if ';' in q or '--' in q or '/*' in q or re.search('\\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|MERGE|CALL|EXEC|EXECUTE|INTO|OUTFILE|LOAD|SET|GRANT|REVOKE)\\b', q, re.IGNORECASE):
        raise ValueError('Unsafe SQL rejected')
    return q

class VimarApiTransport:
    def __init__(self, host: str, username: str, password: str, *, port: int=443, verify_ssl: bool=False, timeout: int=8) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self._session_id: str | None = None
        self._lock = threading.RLock()

    @property
    def base_url(self) -> str:
        return f'https://{self.host}:{self.port}'

    def _session(self) -> requests.Session:
        session = requests.Session()
        session.trust_env = False
        session.mount('https://', VimarHTTPAdapter())
        return session

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None=None, body: str | None=None, headers: dict[str, str] | None=None) -> str:
        try:
            with self._session() as session:
                response = session.request(method, f'{self.base_url}{path}', params=params, data=body, headers=headers, verify=self.verify_ssl, timeout=(max(2, self.timeout // 2), self.timeout))
                response.raise_for_status()
                return response.text
        except requests.RequestException as err:
            raise VimarAlarmConnectionError(f'Vimar connection failed ({type(err).__name__})') from err

    @staticmethod
    def _parse_xml(text: str) -> ET.Element:
        try:
            return ET.fromstring(text)
        except ET.ParseError as err:
            raise VimarAlarmConnectionError('Invalid XML from Vimar') from err

    def login(self) -> None:
        with self._lock:
            root = self._parse_xml(self._request('GET', '/vimarbyweb/modules/system/user_login.php', params={'sessionid': '', 'username': self.username, 'password': self.password, 'remember': '0', 'op': 'login'}))
            result = _xml_text(root, 'result')
            if result and result != '0':
                raise VimarAlarmAuthError('Vimar rejected the Web Server credentials')
            sid = _xml_text(root, 'sessionid')
            if not sid:
                raise VimarAlarmAuthError('Vimar login returned no session id')
            self._session_id = sid

    def _ensure_login(self) -> None:
        if not self._session_id:
            self.login()

    def _soap(self, inner: str) -> ET.Element:
        self._ensure_login()
        envelope = f'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>{inner}</soapenv:Body></soapenv:Envelope>'
        return self._parse_xml(self._request('POST', '/cgi-bin/dpadws', body=envelope, headers={'SOAPAction': 'dbSoapRequest', 'SOAPServer': '', 'Content-Type': 'text/xml; charset="UTF-8"', 'Expect': ''}))

    def _select_once(self, sql: str) -> tuple[str, list[dict[str, str]]]:
        statement = _escape_sql(_assert_select(sql))
        root = self._soap(f'<service-databasesocketoperation xmlns="urn:xmethods-dpadws"><payload>NO-PAYLOAD</payload><hashcode>NO-HASCHODE</hashcode><optionals>NO-OPTIONAL</optionals><callsource>WEB-DOMUSPAD_SOAP</callsource><sessionid>{self._session_id}</sessionid><waittime>5</waittime><function>DML-SQL</function><type>SELECT</type><statement>{statement}</statement><statement-len>{len(statement)}</statement-len></service-databasesocketoperation>')
        payload = _find_xml(root, 'payload')
        return (_xml_text(root, 'result'), _parse_sql_payload(payload.text if payload is not None else None))

    def _select(self, sql: str) -> list[dict[str, str]]:
        with self._lock:
            result, rows = self._select_once(sql)
            if result.startswith('LGMG'):
                self._session_id = None
                self.login()
                result, rows = self._select_once(sql)
            if result and result != 'DPCM-0000':
                raise VimarAlarmConnectionError(f'Vimar SELECT failed: {result}')
            return rows

