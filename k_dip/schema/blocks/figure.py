from k_dip.schema import BlockTypes
from k_dip.schema.blocks import Block


class Figure(Block):
    block_type: BlockTypes = BlockTypes.Figure
    description: str | None = None
    block_description: str = "A chart or other image that contains data."
    description_markdown: str | None = None  # markdown-rendered HTM

    def assemble_html(self, document, child_blocks, parent_structure):
        child_ref_blocks = [block for block in child_blocks if block.id.block_type == BlockTypes.Reference]
        html = super().assemble_html(document, child_ref_blocks, parent_structure)
        # if self.description:
        #     html += f"<p role='img' data-original-image-id='{self.id}'>Image {self.id} description: {self.description}</p>"
        # return html
        # Append markdown-rendered description below image if available
        if self.description_markdown:
            return html + f"<p role='img' data-original-image-id='{self.id}'>{self.description_markdown}</p>"
        # Fallback to raw description using original format
        if self.description:
            return html + f"<p role='img' data-original-image-id='{self.id}'>Image {self.id} description: {self.description}</p>"
        return html
