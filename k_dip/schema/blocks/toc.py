from k_dip.schema import BlockTypes
from k_dip.schema.blocks.basetable import BaseTable


class TableOfContents(BaseTable):
    block_type: str = BlockTypes.TableOfContents
    block_description: str = "A table of contents."
