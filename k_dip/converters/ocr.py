from typing import Tuple

from k_dip.builders.document import DocumentBuilder
from k_dip.builders.line import LineBuilder
from k_dip.builders.ocr import OcrBuilder
from k_dip.converters.pdf import PdfConverter
from k_dip.processors import BaseProcessor
from k_dip.processors.equation import EquationProcessor
from k_dip.providers.registry import provider_from_filepath
from k_dip.renderers.ocr_json import OCRJSONRenderer
from k_dip.services.vintern import VinternService


class OCRConverter(PdfConverter):
    default_processors: Tuple[BaseProcessor, ...] = (EquationProcessor,)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.config:
            self.config = {}

        self.config["format_lines"] = True
        self.renderer = OCRJSONRenderer

    def build_document(self, filepath: str):
        print("ocr.py")
        provider_cls = provider_from_filepath(filepath)
        layout_builder = self.resolve_dependencies(self.layout_builder_class)
        line_builder = self.resolve_dependencies(LineBuilder)
        ocr_builder = self.resolve_dependencies(OcrBuilder)
        document_builder = DocumentBuilder(self.config)

        provider = provider_cls(filepath, self.config)
        document = document_builder(provider, layout_builder, line_builder, ocr_builder)

        for processor in self.processor_list:
            processor(document)

        return document

    def __call__(self, filepath: str):
        document = self.build_document(filepath)
        renderer = self.resolve_dependencies(self.renderer)
        return renderer(document)
