from k_dip.schema import BlockTypes
from k_dip.schema.groups.base import Group


class TableGroup(Group):
    block_type: BlockTypes = BlockTypes.TableGroup
    block_description: str = "A table along with associated captions."
