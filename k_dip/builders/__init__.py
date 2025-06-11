from typing import Optional

from pydantic import BaseModel

from k_dip.util import assign_config


class BaseBuilder:
    def __init__(self, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)

    def __call__(self, data, *args, **kwargs):
        raise NotImplementedError
