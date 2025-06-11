# k_dip/k_dip/builders/chart_description.py
import json
import base64
import logging
from io import BytesIO
from typing import List
from PIL import Image
from k_dip.logger import get_logger
from k_dip.schema.document import Document
from k_dip.services.vintern import VinternService  # hoặc custom của bạn
from k_dip.builders import BaseBuilder
from k_dip.schema import BlockTypes
from k_dip.schema.document import Document


logger = get_logger()

class ChartDescriptionBuilder:

    def __init__(self, llm_service: VinternService):
        self.llm = llm_service

    def image_to_base64(self, img: Image.Image) -> str:
        bio = BytesIO()
        img.save(bio, format="PNG")
        return base64.b64encode(bio.getvalue()).decode()

    def __call__(self, document: Document, provider) -> Document:
        # Iterate through each page and blocks
        for page in document.pages:
            for block in page.current_children:
                if block.block_type in (BlockTypes.Picture, BlockTypes.Figure):
                    try:
                        # Extract high-resolution image if available
                        img = block.get_image(document, highres=True)
                        if img is None:
                            continue
                        prompt = ("""
                            Bạn là một trợ lý AI chuyên phân tích các biểu đồ như chart, histogram về số liệu. Kiểm tra hình ảnh đầu vào có phải là một biểu đồ sso liệu không.
                            Nếu là một biểu đồ thì thực hiện các yêu cầu sau:
                                - Mô tả một cách chi tiết biểu đồ với câu mở đầu là "Biểu đồ bên dưới..."
                                - Tích xuất các số liệu có trong biểu đồ (nếu có) và trình bày dưới dạng MARKDOWN TABLE 
                            Nếu không phải là biểu đồ hãy trả về chuỗi rỗng """

                        )
                        responses = self.llm.generate(prompt=prompt, multimodal_input=[img])

                        # Extract text from LLM response
                        desc = ""
                        if responses:
                            first = responses[0]
                            if isinstance(first, dict):
                                desc = first.get("description") or first.get("text", "")
                            else:
                                desc = str(first)
                            desc = desc.strip()
                            # Only assign Markdown-rendered description HTML
                            try:
                                import markdown as _md
                                md_html = _md.markdown(desc)
                            except ImportError:
                                md_html = f"<p>{desc}</p>"
                            setattr(block, "description_markdown", md_html)
                            logger.info(f"ChartDescriptionBuilder: set description_markdown for block {block.id}")
                    except Exception as e:
                        logger.error(f"ChartDescriptionBuilder error on block {block.id}: {e}")
        return document

