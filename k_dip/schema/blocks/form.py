from typing import List

from k_dip.schema import BlockTypes
from k_dip.schema.blocks.basetable import BaseTable


class Form(BaseTable):
    block_type: BlockTypes = BlockTypes.Form
    block_description: str = "A form, such as a tax form, that contains fields and labels.  It most likely doesn't have a table structure."
