from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .base import DaruBaseTool
import ast
import operator
import os
import json
import uuid
import threading

from .sandbox import (
    ListOfficeFilesTool,
    ReadOfficeFileTool,
    WriteOfficeFileTool,
)


class GetCurrentTimeModel(BaseModel):
    """无工具参数也要定义参数模型"""


class GetCurrentTimeTool(DaruBaseTool):
    name: str = "get_current_time"
    description: str = """获取当前的系统时间和日期。当用户询问“现在几点”、“今天星期几”、
    “今天几号”等与当前时间相关的问题时，调用此工具。"""
    args_schema: type[BaseModel] = GetCurrentTimeModel

    def _run(self, **kwargs) -> str:
        now = datetime.now()
        return f"当前本地系统时间为:{now.strftime('%Y-%m-%d %H:%M:%S')}"


BUILTIN_TOOLS = [
    GetCurrentTimeTool(),
    ListOfficeFilesTool(),
    ReadOfficeFileTool(),
    WriteOfficeFileTool(),
]
