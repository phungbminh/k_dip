from k_dip.schema import BlockTypes
from k_dip.schema.blocks.basetable import BaseTable


class Table(BaseTable):
    block_type: BlockTypes = BlockTypes.Table
    block_description: str = "A table of data, like a results table.  It will be in a tabular format."
