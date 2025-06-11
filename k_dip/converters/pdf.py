import os

from k_dip.services import BaseService

os.environ["TOKENIZERS_PARALLELISM"] = "false"  # disables a tokenizers warning

from collections import defaultdict
from typing import Annotated, Any, Dict, List, Optional, Type, Tuple, Union
import io
from contextlib import contextmanager
import tempfile

from k_dip.processors import BaseProcessor
from k_dip.processors.llm.llm_table_merge import LLMTableMergeProcessor
from k_dip.providers.registry import provider_from_filepath
from k_dip.builders.document import DocumentBuilder
from k_dip.builders.layout import LayoutBuilder
from k_dip.builders.llm_layout import LLMLayoutBuilder
from k_dip.builders.line import LineBuilder
from k_dip.builders.ocr import OcrBuilder
from k_dip.builders.llm_ocr import LLMOcrBuilder
from k_dip.builders.structure import StructureBuilder
from k_dip.converters import BaseConverter
from k_dip.processors.blockquote import BlockquoteProcessor
from k_dip.processors.code import CodeProcessor
from k_dip.processors.debug import DebugProcessor
from k_dip.processors.document_toc import DocumentTOCProcessor
from k_dip.processors.equation import EquationProcessor
from k_dip.processors.footnote import FootnoteProcessor
from k_dip.processors.ignoretext import IgnoreTextProcessor
from k_dip.processors.line_numbers import LineNumbersProcessor
from k_dip.processors.list import ListProcessor
from k_dip.processors.llm.llm_complex import LLMComplexRegionProcessor
from k_dip.processors.llm.llm_form import LLMFormProcessor
from k_dip.processors.llm.llm_image_description import LLMImageDescriptionProcessor
from k_dip.processors.llm.llm_table import LLMTableProcessor
from k_dip.processors.page_header import PageHeaderProcessor
from k_dip.processors.reference import ReferenceProcessor
from k_dip.processors.sectionheader import SectionHeaderProcessor
from k_dip.processors.table import TableProcessor
from k_dip.processors.text import TextProcessor
from k_dip.processors.llm.llm_equation import LLMEquationProcessor
from k_dip.renderers.markdown import MarkdownRenderer
from k_dip.schema import BlockTypes
from k_dip.schema.blocks import Block
from k_dip.schema.registry import register_block_class
from k_dip.util import strings_to_classes
from k_dip.processors.llm.llm_handwriting import LLMHandwritingProcessor
from k_dip.processors.order import OrderProcessor
from k_dip.services.vintern import VinternService
from k_dip.processors.line_merge import LineMergeProcessor
from k_dip.processors.llm.llm_mathblock import LLMMathBlockProcessor
from k_dip.builders.chart_description import ChartDescriptionBuilder

class PdfConverter(BaseConverter):
    """
    A converter for processing and rendering PDF files into Markdown, JSON, HTML and other formats.
    """

    override_map: Annotated[
        Dict[BlockTypes, Type[Block]],
        "A mapping to override the default block classes for specific block types.",
        "The keys are `BlockTypes` enum values, representing the types of blocks,",
        "and the values are corresponding `Block` class implementations to use",
        "instead of the defaults.",
    ] = defaultdict()
    use_llm: Annotated[
        bool,
        "Enable higher quality processing with LLMs.",
    ] = False
    default_processors: Tuple[BaseProcessor, ...] = (
        OrderProcessor,
        LineMergeProcessor,
        BlockquoteProcessor,
        CodeProcessor,
        DocumentTOCProcessor,
        EquationProcessor,
        FootnoteProcessor,
        IgnoreTextProcessor,
        LineNumbersProcessor,
        ListProcessor,
        PageHeaderProcessor,
        SectionHeaderProcessor,
        TableProcessor,
        LLMTableProcessor,
        LLMTableMergeProcessor,
        LLMFormProcessor,
        TextProcessor,
        LLMComplexRegionProcessor,
        LLMImageDescriptionProcessor,
        LLMEquationProcessor,
        LLMHandwritingProcessor,
        LLMMathBlockProcessor,
        ReferenceProcessor,
        DebugProcessor,
    )
    default_llm_service: BaseService = VinternService

    def __init__(
        self,
        artifact_dict: Dict[str, Any],
        processor_list: Optional[List[str]] = None,
        renderer: str | None = None,
        llm_service: str | None = None,
        config=None,
    ):
        super().__init__(config)

        if config is None:
            config = {}

        for block_type, override_block_type in self.override_map.items():
            register_block_class(block_type, override_block_type)

        if processor_list is not None:
            processor_list = strings_to_classes(processor_list)
        else:
            processor_list = self.default_processors

        if renderer:
            renderer = strings_to_classes([renderer])[0]
        else:
            renderer = MarkdownRenderer

        if llm_service:
            llm_service_cls = strings_to_classes([llm_service])[0]
            llm_service = self.resolve_dependencies(llm_service_cls)
        elif config.get("use_llm", False):
            llm_service = self.resolve_dependencies(self.default_llm_service)

        # Inject llm service into artifact_dict so it can be picked up by processors, etc.
        artifact_dict["llm_service"] = llm_service
        self.llm_service = llm_service

        self.artifact_dict = artifact_dict
        self.renderer = renderer

        processor_list = self.initialize_processors(processor_list)
        self.processor_list = processor_list

        self.layout_builder_class = LayoutBuilder
        if self.use_llm:
            self.layout_builder_class = LLMLayoutBuilder

    @contextmanager
    def filepath_to_str(self, file_input: Union[str, io.BytesIO]):
        temp_file = None
        try:
            if isinstance(file_input, str):
                yield file_input
            else:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".pdf"
                ) as temp_file:
                    if isinstance(file_input, io.BytesIO):
                        file_input.seek(0)
                        temp_file.write(file_input.getvalue())
                    else:
                        raise TypeError(
                            f"Expected str or BytesIO, got {type(file_input)}"
                        )

                yield temp_file.name
        finally:
            if temp_file is not None and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)

    def build_document(self, filepath: str):
        print("pdf.py")
        provider_cls = provider_from_filepath(filepath)
        layout_builder = self.resolve_dependencies(self.layout_builder_class)
        line_builder = self.resolve_dependencies(LineBuilder)
        # ocr_builder = self.resolve_dependencies(OcrBuilder)
        if self.config.get("use_llm_ocr", False):
            llm_service = self.resolve_dependencies(self.default_llm_service)
            ocr_builder = LLMOcrBuilder(llm_service, self.config)
            #ocr_builder = self.resolve_dependencies(LLMOcrBuilder)
        else:
            ocr_builder = self.resolve_dependencies(OcrBuilder)


        provider = provider_cls(filepath, self.config)

        # chart_builder = ChartDescriptionBuilder(
        #     self.resolve_dependencies(self.default_llm_service)
        # )
        #
        # document = DocumentBuilder(self.config)(
        #     provider, layout_builder, line_builder, ocr_builder, chart_builder
        # )
        # inject ChartDescriptionBuilder only if CLI --chart-desc bật
        extra_builders = []
        print(self.config.get("chart_desc", False))
        if self.config.get("chart_desc", False):
            chart_builder = ChartDescriptionBuilder(
                self.resolve_dependencies(self.default_llm_service)
            )
            extra_builders.append(chart_builder)

        document = DocumentBuilder(self.config)(
            provider, layout_builder, line_builder, ocr_builder, *extra_builders
        )
        structure_builder_cls = self.resolve_dependencies(StructureBuilder)
        structure_builder_cls(document)

        #processor_list = [p for p in self.processor_list if not isinstance(p, OcrErrorDetectionProcessor)]

        for processor in self.processor_list:
            #print(processor.__class__.__name__)
            processor(document)


        return document

    def __call__(self, filepath: str | io.BytesIO):
        with self.filepath_to_str(filepath) as temp_path:
            document = self.build_document(temp_path)
            renderer = self.resolve_dependencies(self.renderer)
            rendered = renderer(document)
        return rendered
