from k_dip.schema import BlockTypes
from k_dip.schema.groups.base import Group


class PictureGroup(Group):
    block_type: BlockTypes = BlockTypes.PictureGroup
    block_description: str = "A picture along with associated captions."
