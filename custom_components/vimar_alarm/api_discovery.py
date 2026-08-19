"""Read-only SAI discovery and state access."""
from __future__ import annotations
import re
from .const import PARTITIONS_CONTAINER
from .api_core import VimarContactInput, VimarLogicalZone, VimarPartition, VimarStateSnapshot

class VimarDiscoveryMixin:
    def get_partitions(self) -> list[VimarPartition]:
        rows = self._select(f"SELECT p.ID AS object_id,p.NAME AS object_name,p.OPTIONALP AS optionalp,s.ID AS status_id FROM DPADD_OBJECT container INNER JOIN DPADD_OBJECT_RELATION r ON container.ID=r.PARENTOBJ_ID INNER JOIN DPADD_OBJECT p ON r.CHILDOBJ_ID=p.ID INNER JOIN DPADD_OBJECT_RELATION sr ON p.ID=sr.PARENTOBJ_ID AND sr.RELATION_WEB_TIPOLOGY='BYME_IDXOBJ_RELATION' INNER JOIN DPADD_OBJECT s ON sr.CHILDOBJ_ID=s.ID AND s.NAME='state' WHERE container.NAME='{PARTITIONS_CONTAINER}' AND r.RELATION_WEB_TIPOLOGY='GENERIC_RELATION' AND p.VALUES_TYPE LIKE 'CH_SAI%' ORDER BY p.ID")
        out: list[VimarPartition] = []
        for row in rows:
            match = re.search('(?:^|\\|)index_id=(\\d+)(?:\\||$)', row.get('optionalp', ''))
            if not match:
                continue
            try:
                out.append(VimarPartition(object_id=int(row['object_id']), name=row.get('object_name') or f'Partition {match.group(1)}', index_id=int(match.group(1)), status_id=int(row['status_id'])))
            except (KeyError, ValueError):
                continue
        return out

    def get_contact_inputs(self) -> list[VimarContactInput]:
        """Discover the two raw contact channels of each SAI contact interface."""
        rows = self._select("SELECT fb.ID AS interface_object_id,fb.MIN_VALUE AS device_address,go.ID AS channel_object_id,go.CURRENT_VALUE AS current_value FROM DPADD_OBJECT fb INNER JOIN DPADD_OBJECT_RELATION rel ON fb.ID=rel.PARENTOBJ_ID AND rel.RELATION_WEB_TIPOLOGY='BYME_FBGO_RELATION' INNER JOIN DPADD_OBJECT go ON rel.CHILDOBJ_ID=go.ID WHERE fb.NAME='SAIInterfacciaContatti__2In' AND fb.VALUES_TYPE='CH_SAI' AND go.TYPE='BYMEFBGO' AND go.VALUES_TYPE='8' ORDER BY fb.ID,go.ID")
        per_interface: dict[int, int] = {}
        out: list[VimarContactInput] = []
        for row in rows:
            try:
                interface_id = int(row['interface_object_id'])
                channel_id = int(row['channel_object_id'])
            except (KeyError, ValueError):
                continue
            number = per_interface.get(interface_id, 0) + 1
            per_interface[interface_id] = number
            out.append(VimarContactInput(interface_object_id=interface_id, channel_object_id=channel_id, device_address=row.get('device_address', '').zfill(4), input_number=number))
        return out

    def get_logical_zones(self) -> list[VimarLogicalZone]:
        """Return logical SAI groups/zones as metadata for diagnostics."""
        rows = self._select("SELECT ID,NAME,STATUS_ID,OPTIONALP FROM DPADD_OBJECT WHERE TYPE='BYMEIDX' AND VALUES_TYPE='CH_SAI' AND STATUS_ID>=0 ORDER BY ID")
        out: list[VimarLogicalZone] = []
        for row in rows:
            match = re.search('(?:^|\\|)index_id=(\\d+)(?:\\||$)', row.get('OPTIONALP', ''))
            if not match:
                continue
            try:
                status = int(row.get('STATUS_ID', '-1'))
                out.append(VimarLogicalZone(object_id=int(row['ID']), name=row.get('NAME', ''), index_id=int(match.group(1)), partition_object_id=status if status >= 0 else None))
            except (KeyError, ValueError):
                continue
        return out

    def get_logical_zone_values(self) -> list[dict[str, str]]:
        """Read raw values for logical SAI groups/zones for diagnostics only."""
        return self._select("SELECT ID,NAME,STATUS_ID,CURRENT_VALUE,MIN_VALUE,MAX_VALUE,TYPE,VALUES_TYPE,OPTIONALP FROM DPADD_OBJECT WHERE TYPE='BYMEIDX' AND VALUES_TYPE='CH_SAI' AND STATUS_ID>=0 ORDER BY ID")

    def get_state_snapshot(self, partitions: list[VimarPartition], contact_inputs: list[VimarContactInput]) -> VimarStateSnapshot:
        """Read all alarm and contact current values in one SELECT."""
        ids = [p.status_id for p in partitions]
        ids.extend((c.channel_object_id for c in contact_inputs))
        if not ids:
            return VimarStateSnapshot({}, {})
        id_csv = ','.join((str(value) for value in sorted(set(ids))))
        rows = self._select(f'SELECT ID,CURRENT_VALUE FROM DPADD_OBJECT WHERE ID IN ({id_csv}) ORDER BY ID')
        values = {int(row['ID']): row.get('CURRENT_VALUE', '') for row in rows}
        return VimarStateSnapshot(partition_states={p.object_id: values.get(p.status_id, '') for p in partitions}, contact_states={c.channel_object_id: values.get(c.channel_object_id, '') for c in contact_inputs})

    def get_partition_states(self, partitions: list[VimarPartition]) -> dict[int, str]:
        return self.get_state_snapshot(partitions, []).partition_states
