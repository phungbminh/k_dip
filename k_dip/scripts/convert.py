import atexit
import os

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = (
    "1"  # Transformers uses .isin for a simple op, which is not supported on MPS
)
os.environ["IN_STREAMLIT"] = "true"  # Avoid multiprocessing inside surya

import math
import traceback

import click
import torch.multiprocessing as mp
from tqdm import tqdm
import gc

from k_dip.config.parser import ConfigParser
from k_dip.config.printer import CustomClickPrinter
from k_dip.logger import configure_logging, get_logger
from k_dip.models import create_model_dict
from k_dip.output import output_exists, save_output
from k_dip.settings import settings

configure_logging()
logger = get_logger()


def worker_init(model_dict):
    if model_dict is None:
        model_dict = create_model_dict()

    global model_refs
    model_refs = model_dict

    # Ensure we clean up the model references on exit
    atexit.register(worker_exit)


def worker_exit():
    global model_refs
    try:
        del model_refs
    except Exception:
        pass


def process_single_pdf(args):
    fpath, cli_options = args
    config_parser = ConfigParser(cli_options)

    out_folder = config_parser.get_output_folder(fpath)
    base_name = config_parser.get_base_filename(fpath)
    if cli_options.get("skip_existing") and output_exists(out_folder, base_name):
        return

    converter_cls = config_parser.get_converter_cls()
    config_dict = config_parser.generate_config_dict()
    config_dict["disable_tqdm"] = True

    try:
        if cli_options.get("debug_print"):
            logger.debug(f"Converting {fpath}")
        converter = converter_cls(
            config=config_dict,
            artifact_dict=model_refs,
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
            llm_service=config_parser.get_llm_service(),
        )
        rendered = converter(fpath)
        out_folder = config_parser.get_output_folder(fpath)
        save_output(rendered, out_folder, base_name)
        if cli_options.get("debug_print"):
            logger.debug(f"Converted {fpath}")
        del rendered
        del converter
    except Exception as e:
        logger.error(f"Error converting {fpath}: {e}")
        traceback.print_exc()
    finally:
        gc.collect()


@click.command(cls=CustomClickPrinter)
@click.argument("in_folder", type=str)
@click.option("--chunk_idx", type=int, default=0, help="Chunk index to convert")
@click.option(
    "--num_chunks",
    type=int,
    default=1,
    help="Number of chunks being processed in parallel",
)
@click.option(
    "--max_files", type=int, default=None, help="Maximum number of pdfs to convert"
)
@click.option(
    "--workers", type=int, default=5, help="Number of worker processes to use."
)
@click.option(
    "--skip_existing",
    is_flag=True,
    default=False,
    help="Skip existing converted files.",
)
@click.option(
    "--debug_print", is_flag=True, default=False, help="Print debug information."
)
@click.option(
    "--max_tasks_per_worker",
    type=int,
    default=10,
    help="Maximum number of tasks per worker process.",
)
@click.option("--chart_desc", "chart_desc", is_flag=True, default=False, help="Enable LLM-based chart description (ChartDescriptionBuilder).")

@click.option("--use-llm-ocr", "use_llm_ocr", is_flag=True, default=False, help="Use LLM to OCR each text region instead of traditional OCR" )


@ConfigParser.common_options
def convert_cli(in_folder: str, **kwargs):
    in_folder = os.path.abspath(in_folder)
    files = [os.path.join(in_folder, f) for f in os.listdir(in_folder)]
    files = [f for f in files if os.path.isfile(f)]

    # Handle chunks if we're processing in parallel
    # Ensure we get all files into a chunk
    chunk_size = math.ceil(len(files) / kwargs["num_chunks"])
    start_idx = kwargs["chunk_idx"] * chunk_size
    end_idx = start_idx + chunk_size
    files_to_convert = files[start_idx:end_idx]

    # Limit files converted if needed
    if kwargs["max_files"]:
        files_to_convert = files_to_convert[: kwargs["max_files"]]

    # Disable nested multiprocessing
    kwargs["disable_multiprocessing"] = True

    total_processes = min(len(files_to_convert), kwargs["workers"])

    try:
        mp.set_start_method("spawn")  # Required for CUDA, forkserver doesn't work
    except RuntimeError:
        raise RuntimeError(
            "Set start method to spawn twice. This may be a temporary issue with the script. Please try running it again."
        )

    if settings.TORCH_DEVICE == "mps" or settings.TORCH_DEVICE_MODEL == "mps":
        model_dict = None
    else:
        model_dict = create_model_dict()
        for k, v in model_dict.items():
            v.model.share_memory()

    logger.info(
        f"Converting {len(files_to_convert)} pdfs in chunk {kwargs['chunk_idx'] + 1}/{kwargs['num_chunks']} with {total_processes} processes and saving to {kwargs['output_dir']}"
    )
    task_args = [(f, kwargs) for f in files_to_convert]

    with mp.Pool(
        processes=total_processes,
        initializer=worker_init,
        initargs=(model_dict,),
        maxtasksperchild=kwargs["max_tasks_per_worker"],
    ) as pool:
        pbar = tqdm(total=len(task_args), desc="Processing PDFs", unit="pdf")
        for _ in pool.imap_unordered(process_single_pdf, task_args):
            pbar.update(1)
        pbar.close()

    # Delete all CUDA tensors
    del model_dict
