import copy
from typing import Annotated, List, Optional, Any
from k_dip.builders import BaseBuilder
from k_dip.providers.pdf import PdfProvider
from k_dip.schema import BlockTypes
from k_dip.schema.document import Document
from k_dip.schema.groups import PageGroup
from k_dip.services.vintern import VinternService
from k_dip.logger import get_logger
from k_dip.builders import BaseBuilder
from k_dip.schema import BlockTypes
from k_dip.schema.registry import get_block_class
from k_dip.schema.document import Document
from k_dip.schema.text.span import Span
from k_dip.schema.polygon import PolygonBox
import copy
from typing import Annotated, List, Optional

from ftfy import fix_text
from PIL import Image
from surya.common.surya.schema import TaskNames
from surya.recognition import RecognitionPredictor, OCRResult, TextChar

from k_dip.builders import BaseBuilder
from k_dip.providers.pdf import PdfProvider
from k_dip.schema import BlockTypes
from k_dip.schema.blocks import BlockId
from k_dip.schema.document import Document
from k_dip.schema.groups import PageGroup
from k_dip.schema.registry import get_block_class
from k_dip.schema.text.char import Char
from k_dip.schema.text.line import Line
from k_dip.schema.text.span import Span
from k_dip.settings import settings
from k_dip.schema.polygon import PolygonBox
from k_dip.util import get_opening_tag_type, get_closing_tag_type



logger = get_logger()
class LLMOcrBuilder(BaseBuilder):
    """
    Use LLM to perform OCR on each line region based on existing layout polygons.
    """
    def __init__(self, llm_service: VinternService, config=None):
        super().__init__(config)
        self.llm = llm_service

    def __call__(self, document: Document, provider: PdfProvider) -> Document:
        pages = list(document.pages)
        # Extract high-res page images and rescaled line polygons & IDs
        images, line_polys, line_ids, _ = self._get_line_regions(document, pages, provider)

        # Iterate pages and line regions
        for page, img, polys, ids in zip(pages, images, line_polys, line_ids):
            for poly, lid in zip(polys, ids):
                # Crop region from the page image
                xs, ys = zip(*poly)
                left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
                region = img.crop((left, top, right, bottom))

                # Prompt LLM to extract text
                prompt = (
                    "Extract the exact text from the following image region. "
                    "Return only the raw text, no commentary."
                )
                try:
                    response = self.llm.generate(
                        prompt=prompt,
                        multimodal_input=[region]
                    )
                    text = self._extract_text(response)
                except Exception as e:
                    logger.error(f"LLMOcrBuilder error on line {lid}: {e}")
                    text = ""

                    # build one new Span
                    line_block = page.get_block(lid)
                    SpanClass = get_block_class(BlockTypes.Span)
                    poly_box = PolygonBox(polygon=poly)
                    new_span = SpanClass(
                        text=text + "\n",
                        formats=["plain"],
                        page_id=page.page_id,
                        polygon=poly_box,
                        minimum_position=0,
                        maximum_position=0,
                        font="Unknown",
                        font_weight=0,
                        font_size=0,
                    )
                    # replace spans inside the line
                    self.replace_line_spans(document, page, line_block, [new_span])
        return document

    def _extract_text(self, response: Any) -> str:
        # Handle ChatCompletion-like response
        if hasattr(response, 'choices') and response.choices:
            return response.choices[0].message.content.strip()
        # Handle list of dicts
        if isinstance(response, list) and response:
            first = response[0]
            if isinstance(first, dict):
                return first.get('text', '')
            return str(first)
        return ''

    def _get_line_regions(
        self,
        document: Document,
        pages: List[PageGroup],
        provider: PdfProvider
    ):
        """
        Returns lists of (page_image, line_polygons, line_ids, dummy_original_texts)
        for each page, analogous to OcrBuilder.get_ocr_images_polygons_ids.
        """
        highres_images, highres_polys, line_ids, line_original_texts = [], [], [], []
        for document_page in pages:
            img = document_page.get_image(highres=True)
            page_polys, page_ids = [], []
            page_size = provider.get_page_bbox(document_page.page_id).size
            image_size = img.size

            # Iterate blocks and lines
            for block in document_page.contained_blocks(document):
                # Get all line blocks
                lines = block.contained_blocks(document, [BlockTypes.Line])
                for line in lines:
                    # Rescale line polygon to image coords
                    poly_box = line.polygon.rescale(page_size, image_size).fit_to_bounds((0,0,*image_size))
                    coords = [[int(x), int(y)] for x,y in poly_box.polygon]
                    page_polys.append(coords)
                    page_ids.append(line.id)

            highres_images.append(img)
            highres_polys.append(page_polys)
            line_ids.append(page_ids)
            line_original_texts.append([])
        return highres_images, highres_polys, line_ids, line_original_texts
    def replace_line_spans(
        self, document: Document, page: PageGroup, line: Line, new_spans: List[Span]
    ):
        old_spans = line.contained_blocks(document, [BlockTypes.Span])
        text_ref_matching = {span.text: span.url for span in old_spans if span.url}

        # Insert refs into new spans, since the OCR model does not (cannot) generate these
        final_new_spans = []
        for span in new_spans:
            # Use for copying attributes into new spans
            original_span = copy.deepcopy(span)
            remaining_text = span.text
            while remaining_text:
                matched = False
                for match_text, url in text_ref_matching.items():
                    if match_text in remaining_text:
                        matched = True
                        before, current, after = self.link_and_break_span(
                            original_span, remaining_text, match_text, url
                        )
                        if before:
                            final_new_spans.append(before)
                        final_new_spans.append(current)
                        if after:
                            remaining_text = after.text
                        else:
                            remaining_text = ""  # No more text left
                        # Prevent repeat matches
                        del text_ref_matching[match_text]
                        break
                if not matched:
                    remaining_span = copy.deepcopy(original_span)
                    remaining_span.text = remaining_text
                    final_new_spans.append(remaining_span)
                    break

        # Clear the old spans from the line
        line.structure = []
        for span in final_new_spans:
            page.add_full_block(span)
            line.structure.append(span.id)