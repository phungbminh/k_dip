from k_dip.schema import BlockTypes
from k_dip.schema.blocks import Block


class Handwriting(Block):
    block_type: BlockTypes = BlockTypes.Handwriting
    block_description: str = "A region that contains handwriting."
    html: str | None = None
    replace_output_newlines: bool = True

    def assemble_html(self, document, child_blocks, parent_structure):
        if self.html:
            return self.html
        else:
            return super().assemble_html(document, child_blocks, parent_structure)
