"""Public Vimar By-me SAI API."""
from .api_core import (VimarAlarmError,VimarAlarmConnectionError,VimarAlarmAuthError,VimarAlarmInvalidPin,VimarAlarmEnrollmentError,VimarAlarmPermissionError,VimarAlarmCommandError,VimarPartition,VimarContactInput,VimarLogicalZone,VimarStateSnapshot,VimarApiTransport)
from .api_commands import VimarCommandsMixin
from .api_discovery import VimarDiscoveryMixin

class VimarAlarmApi(VimarCommandsMixin, VimarDiscoveryMixin, VimarApiTransport):
    """Combined Vimar Web Server SAI client."""

