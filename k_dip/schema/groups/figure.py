from k_dip.schema import BlockTypes
from k_dip.schema.groups.base import Group


class FigureGroup(Group):
    block_type: BlockTypes = BlockTypes.FigureGroup
    block_description: str = "A group that contains a figure and associated captions."
