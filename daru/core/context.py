# 上下文构建
from typing import Annotated, TypedDict, List
from langgraph.graph.message import add_messages

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """存储对话历史,自动添加最新对话"""
    messages:Annotated[List[BaseMessage],add_messages]