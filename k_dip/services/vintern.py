import base64
import json
import time
from io import BytesIO
from typing import List, Union

import openai
import PIL
from openai import APITimeoutError, RateLimitError
from k_dip.logger import get_logger
from k_dip.schema.blocks import Block
from k_dip.services import BaseService
from pydantic import BaseModel

logger = get_logger()

class VinternService(BaseService):
    """
    Service for using the OpenAI-like Chat API with support for text and multiple images.
    Sends each image in a separate request loop to respect single-image limits, aggregates responses.
    """
    openai_base_url: str = "http://192.168.1.28:9000/v1"
    openai_model: str = "5CD-AI/Vintern-3B-beta"
    openai_api_key: str = None

    def image_to_base64(self, image: PIL.Image.Image) -> str:
        """
        Convert PIL Image to base64-encoded WEBP string.
        """
        image_bytes = BytesIO()
        image.save(image_bytes, format="WEBP")
        return base64.b64encode(image_bytes.getvalue()).decode("utf-8")

    def prepare_images(
        self,
        images: Union[PIL.Image.Image, List[PIL.Image.Image]]
    ) -> List[dict]:
        """
        Prepare a list of multimodal image content dicts for each image.
        """
        if isinstance(images, PIL.Image.Image):
            images = [images]
        payloads = []
        for img in images:
            data = self.image_to_base64(img)
            payloads.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/webp;base64,{data}"}
            })
        return payloads

    def __call__(
        self,
        prompt: str,
        image: PIL.Image.Image | List[PIL.Image.Image],
        block: Block,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None,
    ) -> List[dict]:
        """
        Send prompt and images to OpenAI-like API. If multiple images, send one per request.
        Returns list of parsed JSON outputs.
        """
        # set defaults
        max_retries = max_retries or self.max_retries
        timeout = timeout or self.timeout
        # prepare client and images
        client = self.get_client()
        images = self.prepare_images(image)
        responses = []
        total_tokens = 0
        request_count = 0

        # helper to build message content list
        def build_message_content(img_payload: dict) -> List[dict]:
            # order: image then text
            return [img_payload, {"type": "text", "text": prompt}]

        # if no images, send one text-only request
        if not images:
            messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
            try:
                resp = client.beta.chat.completions.parse(
                    extra_headers={
                        "X-Title": "Marker",
                        "HTTP-Referer": "https://github.com/VikParuchuri/marker",
                    },
                    model=self.openai_model,
                    messages=messages,
                    timeout=timeout,
                    response_format=response_schema,
                )
                text = resp.choices[0].message.content
                tokens = resp.usage.total_tokens
                block.update_metadata(llm_tokens_used=tokens, llm_request_count=1)
                return [json.loads(text)]
            except (APITimeoutError, RateLimitError) as e:
                logger.error(f"OpenAIService error: {e}")
                return []

        # loop for each image
        for idx, img_payload in enumerate(images):
            request_count += 1
            tries = 0
            while tries < max_retries:
                try:
                    messages = [{"role": "user", "content": build_message_content(img_payload)}]
                    resp = client.beta.chat.completions.parse(
                        extra_headers={
                            "X-Title": "Marker",
                            "HTTP-Referer": "https://github.com/VikParuchuri/marker",
                        },
                        model=self.openai_model,
                        messages=messages,
                        timeout=timeout,
                        response_format=response_schema,
                    )
                    text = resp.choices[0].message.content
                    tokens = resp.usage.total_tokens
                    total_tokens += tokens
                    logger.info(text)
                    responses.append(text)
                    # break retry loop
                    break
                except (APITimeoutError, RateLimitError) as e:
                    tries += 1
                    wait = tries * self.retry_wait_time
                    logger.warning(f"Retry {tries}/{max_retries} after error: {e}")
                    time.sleep(wait)
                except Exception as e:
                    logger.error(f"OpenAIService unexpected error: {e}")
                    break
        # update block metadata once after all requests
        block.update_metadata(llm_tokens_used=total_tokens, llm_request_count=request_count)
        return responses

    def get_client(self) -> openai.OpenAI:
        """
        Instantiate and return an OpenAI client with configured base URL and key.
        """
        return openai.OpenAI(
            api_key=self.openai_api_key,
            base_url=self.openai_base_url,
        )

    def generate(
            self,
            prompt: str,
            multimodal_input: List[PIL.Image.Image] = None,
            **kwargs
    ) -> List[dict]:
        """
        Generate content by sending prompt and optional images to OpenAI.
        If multiple images provided, sends one per request.
        :param prompt: text prompt
        :param multimodal_input: list of PIL.Image.Image
        :return: list of parsed JSON responses
        """
        client = self.get_client()
        images = self.prepare_images(multimodal_input) if multimodal_input else []
        responses = []
        total_tokens = 0
        request_count = 0

        # Helper to build messages content
        def build_messages(img_payload=None):
            content = []
            if img_payload:
                content.append(img_payload)
            content.append({"type": "text", "text": prompt})
            return [{"role": "user", "content": content}]

        # Single text-only request
        if not images:
            messages = build_messages()
            resp = client.chat.completions.create(
                model=self.openai_model,
                messages=messages,
                timeout=self.timeout,
                **kwargs
            )
            text = resp.choices[0].message.content
            total_tokens += resp.usage.total_tokens
            return [json.loads(text)]

        # Loop over each image
        for img_payload in images:
            request_count += 1
            for attempt in range(self.max_retries):
                try:
                    messages = build_messages(img_payload)
                    print(messages)
                    resp = client.chat.completions.create(
                        model=self.openai_model,
                        messages=messages,
                        timeout=self.timeout,
                        **kwargs
                    )
                    #print(resp)
                    text = resp.choices[0].message.content
                    logger.info(text)
                    responses.append(text)
                    total_tokens += resp.usage.total_tokens
                    break
                except (APITimeoutError, RateLimitError) as e:
                    wait = (attempt + 1) * self.retry_wait_time
                    logger.warning(f"VinternService retry {attempt + 1}/{self.max_retries}: {e}")
                    time.sleep(wait)
                except Exception as e:
                    raise
                    logger.error(f"VinternService unexpected error: {e}")
                    break

        return responses