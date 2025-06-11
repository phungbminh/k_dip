from functools import cache
from typing import Tuple, List

from k_dip.builders.document import DocumentBuilder
from k_dip.builders.line import LineBuilder
from k_dip.builders.ocr import OcrBuilder
from k_dip.converters.pdf import PdfConverter
from k_dip.processors import BaseProcessor
from k_dip.processors.llm.llm_complex import LLMComplexRegionProcessor
from k_dip.processors.llm.llm_form import LLMFormProcessor
from k_dip.processors.llm.llm_table import LLMTableProcessor
from k_dip.processors.llm.llm_table_merge import LLMTableMergeProcessor
from k_dip.processors.table import TableProcessor
from k_dip.providers.registry import provider_from_filepath
from k_dip.schema import BlockTypes


class TableConverter(PdfConverter):
    default_processors: Tuple[BaseProcessor, ...] = (
        TableProcessor,
        LLMTableProcessor,
        LLMTableMergeProcessor,
        LLMFormProcessor,
        LLMComplexRegionProcessor,
    )
    converter_block_types: List[BlockTypes] = (BlockTypes.Table, BlockTypes.Form, BlockTypes.TableOfContents)

    def build_document(self, filepath: str):
        provider_cls = provider_from_filepath(filepath)
        layout_builder = self.resolve_dependencies(self.layout_builder_class)
        line_builder = self.resolve_dependencies(LineBuilder)
        ocr_builder = self.resolve_dependencies(OcrBuilder)
        document_builder = DocumentBuilder(self.config)
        document_builder.disable_ocr = True

        provider = provider_cls(filepath, self.config)
        document = document_builder(provider, layout_builder, line_builder, ocr_builder)

        for page in document.pages:
            page.structure = [p for p in page.structure if p.block_type in self.converter_block_types]

        for processor in self.processor_list:
            processor(document)

        return document

    def __call__(self, filepath: str):
        document = self.build_document(filepath)
        renderer = self.resolve_dependencies(self.renderer)
        return renderer(document)