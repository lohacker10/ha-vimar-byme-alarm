"""Public Vimar By-me SAI API."""
from .api_core import (VimarAlarmError,VimarAlarmConnectionError,VimarAlarmAuthError,VimarAlarmInvalidPin,VimarAlarmEnrollmentError,VimarAlarmPermissionError,VimarAlarmCommandError,VimarPartition,VimarContactInput,VimarLogicalZone,VimarStateSnapshot,VimarApiTransport)
from .api_commands import VimarCommandsMixin
from .api_discovery import VimarDiscoveryMixin
from .api_events import VimarEventsMixin

class VimarAlarmApi(VimarCommandsMixin, VimarDiscoveryMixin, VimarEventsMixin, VimarApiTransport):
    """Combined Vimar Web Server SAI client."""

