import os
import io
import traceback
import tempfile
import base64
from contextlib import asynccontextmanager
import re
import click
from pydantic import BaseModel, Field
from fastapi import FastAPI, Form, File, UploadFile

from k_dip.config.parser import ConfigParser
from k_dip.output import text_from_rendered
from k_dip.converters.pdf import PdfConverter
from k_dip.models import create_model_dict
from k_dip.settings import settings

# Global model artifacts
app_data = {}
# Directory for uploads
UPLOAD_DIRECTORY = "./uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app_data["models"] = create_model_dict()
    yield
    app_data.clear()

app = FastAPI(title="Convert PDF to Markdown API", lifespan=lifespan)

class ConvertResponse(BaseModel):
    success: bool
    format: str | None = None
    output: str | None = None
    images: dict[str, str] | None = None
    metadata: dict | None = None
    error: str | None = None

@app.post("/k_dip/api/v1/convert", response_model=ConvertResponse)
async def convert(
    file: UploadFile = File(..., media_type="application/pdf"),
    output_format: str = Form("markdown"),
    use_llm: bool = Form(False),
    chart_desc: bool = Form(False),
):
    """
    Convert a PDF to Markdown/JSON/HTML.
    - file: PDF file upload
    - output_format: 'markdown', 'json', or 'html'
    - use_llm: enable LLM-based processors
    - chart_desc: generate chart descriptions
    """
    try:
        contents = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            pdf_path = tmp.name

        # Build config with selected options
        params = {
            "filepath": pdf_path,
            "output_format": output_format,
            "use_llm": use_llm,
            "chart_desc": chart_desc,
            #"page_range": None,
        }
        parser = ConfigParser(params)
        config = parser.generate_config_dict()
        config["pdftext_workers"] = 1

        # Initialize and run converter
        converter = PdfConverter(
            config=config,
            artifact_dict=app_data["models"],
            processor_list=parser.get_processors(),
            renderer=parser.get_renderer(),
            llm_service=parser.get_llm_service(),
        )
        rendered = converter(pdf_path)
        text, _, images = text_from_rendered(rendered)
        metadata = rendered.metadata
    except Exception as e:
        traceback.print_exc()
        return ConvertResponse(success=False, error=str(e))
    finally:
        if 'pdf_path' in locals() and os.path.exists(pdf_path):
            os.remove(pdf_path)

    # Encode images
    # encoded = {}
    # for key, img in images.items():
    #     buf = io.BytesIO()
    #     img.save(buf, format=settings.OUTPUT_IMAGE_FORMAT)
    #     encoded[key] = base64.b64encode(buf.getvalue()).decode(settings.OUTPUT_ENCODING)
        # Convert literal '\n' sequences into actual newlines

    #text = text.encode('utf-8').decode('unicode_escape')
    #text = text.replace('\\n', '\n')
    return ConvertResponse(
        success=True,
        format=output_format,
        output=text,
        images=None,
        metadata=metadata,
    )

@click.command()
@click.option("--host", default="0.0.0.0", help="Server host")
@click.option("--port", default=8000, type=int, help="Server port")
@click.option("--reload", is_flag=True, help="Enable auto reload")
def server_cli(host: str, port: int, reload: bool):
    import uvicorn
    uvicorn.run(app, host=host, port=port, reload=reload)

if __name__ == "__main__":
    server_cli()
