# 自定义结构化工具类
from typing import Any, Optional, Type
from langchain_core.tools import BaseTool
from abc import ABC, abstractmethod
import asyncio
from pydantic import BaseModel

class DaruBaseTool(BaseTool,ABC):
    """
    Daru的标准工具类
    如果你的工具需要复杂的初始化逻辑（比如维持一个数据库长连接），
    或者需要保存内部状态，请继承此类并实现 `_run` 方法。
    """
    name: str = ""
    description: str = ""
    args_schema: Optional[Type[BaseModel]] = None

    @abstractmethod
    def _run(self,**kwargs:Any)->Any:
        """工具同步执行逻辑"""
        raise NotImplementedError("子类必须实现该方法_run")

    async def _arun(self,**kwargs:Any)->Any:
        """工具异步执行逻辑，默认回退到同步执行"""
        return await asyncio.to_thread(self._run, **kwargs)