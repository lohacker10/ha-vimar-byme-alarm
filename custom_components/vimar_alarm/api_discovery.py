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

    def get_sai_current_state_probe(self) -> list[dict[str, str]]:
        """Read a bounded inventory of SAI-related current-value candidates.

        This probe deliberately omits object names. It does not assign alarm,
        tamper, fault, restore, or memory semantics to any value.
        """
        return self._select(
            "SELECT ID,STATUS_ID,CURRENT_VALUE,MIN_VALUE,MAX_VALUE,TYPE,VALUES_TYPE,OPTIONALP "
            "FROM DPADD_OBJECT "
            "WHERE VALUES_TYPE LIKE 'CH_SAI%' OR TYPE LIKE '%SAI%' OR NAME LIKE 'SAI%' "
            "ORDER BY ID LIMIT 0,500"
        )

    def get_sai_status_target_probe(self) -> list[dict[str, str]]:
        """Read current values of STATUS_ID targets referenced by SAI objects."""
        return self._select(
            "SELECT source.ID AS source_id,source.STATUS_ID AS status_id,"
            "status.CURRENT_VALUE AS status_current_value,"
            "status.MIN_VALUE AS status_min_value,status.MAX_VALUE AS status_max_value,"
            "status.TYPE AS status_type,status.VALUES_TYPE AS status_values_type,"
            "status.OPTIONALP AS status_optionalp "
            "FROM DPADD_OBJECT source "
            "INNER JOIN DPADD_OBJECT status ON source.STATUS_ID=status.ID "
            "WHERE source.STATUS_ID>=0 AND (source.VALUES_TYPE LIKE 'CH_SAI%' "
            "OR source.TYPE LIKE '%SAI%' OR source.NAME LIKE 'SAI%') "
            "ORDER BY source.ID LIMIT 0,500"
        )

    def get_sai_relation_probe(self) -> list[dict[str, str]]:
        """Read outgoing SAI object relations and child values for diagnostics."""
        return self._select(
            "SELECT p.ID AS parent_id,p.NAME AS parent_name,"
            "r.RELATION_WEB_TIPOLOGY AS relation_type,"
            "c.ID AS child_id,c.NAME AS child_name,c.STATUS_ID AS child_status_id,"
            "c.CURRENT_VALUE AS child_current_value,c.MIN_VALUE AS child_min_value,"
            "c.MAX_VALUE AS child_max_value,c.TYPE AS child_type,"
            "c.VALUES_TYPE AS child_values_type,c.OPTIONALP AS child_optionalp "
            "FROM DPADD_OBJECT p "
            "INNER JOIN DPADD_OBJECT_RELATION r ON p.ID=r.PARENTOBJ_ID "
            "INNER JOIN DPADD_OBJECT c ON r.CHILDOBJ_ID=c.ID "
            "WHERE (p.TYPE='BYMEIDX' AND p.VALUES_TYPE='CH_SAI') "
            "OR (p.NAME='SAIInterfacciaContatti__2In' AND p.VALUES_TYPE='CH_SAI') "
            "ORDER BY p.ID,r.RELATION_WEB_TIPOLOGY,c.ID"
        )

    def get_sai_incoming_relation_probe(self) -> list[dict[str, str]]:
        """Read incoming relations for SAI zones/interfaces for diagnostics."""
        return self._select(
            "SELECT c.ID AS child_id,c.NAME AS child_name,"
            "r.RELATION_WEB_TIPOLOGY AS relation_type,"
            "p.ID AS parent_id,p.NAME AS parent_name,p.STATUS_ID AS parent_status_id,"
            "p.CURRENT_VALUE AS parent_current_value,p.MIN_VALUE AS parent_min_value,"
            "p.MAX_VALUE AS parent_max_value,p.TYPE AS parent_type,"
            "p.VALUES_TYPE AS parent_values_type,p.OPTIONALP AS parent_optionalp "
            "FROM DPADD_OBJECT c "
            "INNER JOIN DPADD_OBJECT_RELATION r ON c.ID=r.CHILDOBJ_ID "
            "INNER JOIN DPADD_OBJECT p ON r.PARENTOBJ_ID=p.ID "
            "WHERE (c.TYPE='BYMEIDX' AND c.VALUES_TYPE='CH_SAI') "
            "OR (c.NAME='SAIInterfacciaContatti__2In' AND c.VALUES_TYPE='CH_SAI') "
            "ORDER BY c.ID,r.RELATION_WEB_TIPOLOGY,p.ID"
        )

    def get_sai_status_link_probe(self) -> list[dict[str, str]]:
        """Read objects whose STATUS_ID points at a SAI zone/interface."""
        return self._select(
            "SELECT o.ID,o.NAME,o.STATUS_ID,o.CURRENT_VALUE,o.MIN_VALUE,o.MAX_VALUE,"
            "o.TYPE,o.VALUES_TYPE,o.OPTIONALP "
            "FROM DPADD_OBJECT o "
            "WHERE o.STATUS_ID IN ("
            "SELECT target.ID FROM DPADD_OBJECT target "
            "WHERE (target.TYPE='BYMEIDX' AND target.VALUES_TYPE='CH_SAI') "
            "OR (target.NAME='SAIInterfacciaContatti__2In' "
            "AND target.VALUES_TYPE='CH_SAI')) "
            "ORDER BY o.STATUS_ID,o.ID"
        )

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
