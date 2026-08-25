# 上下文构建
from typing import Annotated, TypedDict, List
from langgraph.graph.message import add_messages

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage, AIMessage


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

    return final_message_list, discard_message_list


def collect_orphan_message_ids(messages: List[BaseMessage]) -> set[str]:
    """
    找出对话消息历史中的“孤儿”工具调用工具消息，返回需要删除的id合集
    "孤儿"消息定义: ai消息携带了tool_calls，但其tool_call_id可能由于
    系统的异常中断而导致没有被后续的ToolMessage全部应答，这类消息直接发给
    模型会触发400: insufficient tool messages following tool_calls
    :param messages: 历史消息列表
    :return: 消息id列表，包括孤儿消息ai_message本身以及属于他的tool_message
    """
    # 构建成功返回的工具调用结果的消息字典
    tool_msg_by_call_id: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_msg_by_call_id[msg.tool_call_id] = msg.id
    # 构建ai消息字典，用来统计每条ai消息发起的tool_call_id的集合
    assistant_tool_ids: dict[str, set[str]] = {}
    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, 'tool_calls', None):
            assistant_tool_ids[msg.id] = {tc["id"] for tc in msg.tool_calls}
    # 构建成功的工具调用集合,仅用字典的key构建合集
    success_tool_calls_set = set(tool_msg_by_call_id)
    # 构建需要删除的助手消息ID合集
    remove_ids: set[str] = set()
    # 遍历助手消息字典
    for msg_id, tc_ids in assistant_tool_ids.items():
        # 集合运算A-B，取出所有属于 A、但不属于 B 的元素。
        # 如果说明该不为空，说明助手消息的调用请求有没有响应的，那么
        # 这条消息应该被删除，
        if tc_ids - success_tool_calls_set:
            remove_ids.add(msg_id)
            # 其对应的tool结果也要一起删除，否则出现无主的tool_result
            for tid in tc_ids:
                if tid in tool_msg_by_call_id:
                    remove_ids.add(tool_msg_by_call_id[tid])
    return remove_ids