# 上下文构建
from typing import Annotated, TypedDict, List
from langgraph.graph.message import add_messages

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage


class AgentState(TypedDict):
    """存储对话历史,自动添加最新对话"""
    messages: Annotated[List[BaseMessage], add_messages]

    summary: str  # 历史对话压缩后的摘要


def trim_context_message(messages: List[BaseMessage],
                         trigger_turns=8,
                         keep_turns=4) -> tuple[list[BaseMessage], list[BaseMessage]]:
    """按照完整的用户回合（一条Human消息到下一条Human消息）"""
    # 获取第一条系统消息(系统提示词，这个部分不能和其他消息一起压缩)
    first_system = next((m for m in messages if isinstance(m, SystemMessage)), None)
    # 获取非系统消息列表，该列表可以用于压缩历史消息
    non_system_msgs = [m for m in messages if not isinstance(m, SystemMessage)]
    if not non_system_msgs:
        return ([first_system] if first_system else []), []
    turns: list[list[BaseMessage]] = []
    current_turn: list[BaseMessage] = []
    # 将消息；列表组合成回合列表
    for msg in non_system_msgs:
        if isinstance(msg, HumanMessage):
            if current_turn:
                turns.append(current_turn)
            current_turn = [msg]
        else:
            if current_turn:
                current_turn.append(msg)

    # 保存最后一个回合
    if current_turn:
        turns.append(current_turn)

    # 计算总回合数
    total_turns_size = len(turns)

    # 还不够触发压缩的回合数
    if total_turns_size < trigger_turns:
        return ([first_system] if first_system else []) + non_system_msgs, []

    # 最近的回合数,保留的部分，该部分需要和系统提示词拼接
    recent_turns = turns[-keep_turns:]
    # 需要丢弃的回合数
    discard_turns = turns[:-keep_turns]

    # 将保留回合和系统提示词拼接
    final_message_list: list[BaseMessage] = []
    if first_system:
        final_message_list.append(first_system)
    for turn in recent_turns:
        final_message_list.extend(turn)

    discard_message_list: list[BaseMessage] = []
    for turn in discard_turns:
        discard_message_list.extend(turn)

    return final_message_list,discard_message_list