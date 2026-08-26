import os
from typing import List, Optional
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage
from prompt_toolkit import print_formatted_text, ANSI

from .config import MEMORY_DIR
from .logger import audit_logger
from .provider import get_provider
from .tools.builtins import BUILTIN_TOOLS
from langchain_core.runnables import RunnableConfig
from .context import AgentState, trim_context_message, collect_orphan_message_ids


def get_system_prompt() -> str:
    system_prompt = "你是 Daru，一个聪明、高效、说话自然的 AI 助手。\n\n"
    return system_prompt


def get_summary_prompt(current_summary: str, discard_text: str) -> str:
    summary_prompt = (f"你是一个负责维护 AI 工作台上下文的后台模块。\n\n"
                      f"【现有的交接文档】\n{current_summary if current_summary else '暂无记录'}\n\n"
                      f"【刚刚过去的旧对话】\n{discard_text}\n\n"
                      f"任务：请仔细阅读旧对话，提取出当前的对话语境和任务进度。\n"
                      f"动作：将新进展与【现有的交接文档】进行无缝融合，输出一份最新的上下文摘要。\n"
                      f"严格警告：只记录'我们在聊什么'、'解决了什么问题'、'得出了什么结论'等。绝对不要记录用户的静态偏好(如姓名、职业、爱好等)，这部分由其他模块负责！\n"
                      f"要求：客观、精简，不要输出任何解释性废话，直接返回最新的记忆文本，总字数不要超过150字")
    return summary_prompt


def get_user_profile_prompt(profile_content: str, user_profile_path: str) -> str:
    user_profile_prompt = (
        f"当您发现用户的偏好发生变化，或出现需要长期记录的重要新事实时，请按以下流程更新档案：\n\n"
        f"1. **对比与融合**：将新信息与下方【当前用户长期画像】中的现有内容进行逐项比对。若新信息与旧条目冲突，以新信息为准进行替换；若为全新事实，则直接追加记录。\n"
        f"2. **保存档案**：将融合后的完整画像（包含未修改的旧内容与更新的新内容），调用写入工具覆盖保存至路径 `{user_profile_path}`，完成持久化更新。\n"
        f"\n\n=============================\n"
        f"【当前用户长期画像 (静态偏好，请以此作为参考基准)】\n"
        f"{profile_content}\n"
        f"=============================\n"
    )
    return user_profile_prompt


def create_agent_app(
        provider_name: str = "openai",
        model_name: str = "gpt-4o-mini",
        tools: Optional[List[BaseTool]] = None,
        checkpointer=None
):
    tools_list = tools or BUILTIN_TOOLS
    tools_node = ToolNode(tools_list)
    llm = get_provider(provider_name=provider_name, model_name=model_name)
    llm_with_tools = llm.bind_tools(tools_list)

    def agent_node(state: AgentState, config: RunnableConfig) -> dict:
        thread_id = config.get("configurable", {}).get("thread_id", "system_default")
        # 系统提示词
        system_prompt = get_system_prompt()

        # 读取用户画像
        profile_path = os.path.join(MEMORY_DIR, "user_profile.md")
        profile_content = "暂无记录"
        if os.path.exists(profile_path):
            with open(profile_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()
                if content:
                    profile_content = content

        # 删除消息id列表
        cleanup_list = []

        # 用户长期记忆提示词
        user_profile_prompt = get_user_profile_prompt(profile_content=profile_content, user_profile_path=profile_path)

        system_prompt += f"\n\n[用户长期记忆]\n{user_profile_prompt}\n\n"

        raw_messages = state["messages"]
        state_updates = {}
        # 孤儿消息清理机制
        orphan_ids = collect_orphan_message_ids(raw_messages)
        if orphan_ids:
            audit_logger.log_event(
                thread_id=thread_id,
                event="orphan_tool_call_cleanup",
                removed_message_ids=sorted(orphan_ids)
            )
            cleanup_list.extend(orphan_ids)
        if raw_messages:
            # 这部分工具消息主要是为了日志记录用的
            recent_tool_messages = []
            for msg in reversed(raw_messages):
                if msg.type == "tool":
                    # recent_tool_messages中的工具消息越在前边越新
                    recent_tool_messages.append(msg)
                else:
                    break
            for msg in reversed(recent_tool_messages):
                audit_logger.log_event(
                    thread_id=thread_id,
                    event="tool_result",
                    tool=msg.name,
                    result_summary=msg.content[:200]
                )

        current_summary = state.get("summary", "")
        # 计算出保留的消息和需要删除的消息
        keep_msgs, discard_msgs = trim_context_message(raw_messages, trigger_turns=10, keep_turns=5)
        # 再根据孤儿消息清理机制得到的ids对保留的消息进行过滤
        if cleanup_list:
            keep_msgs = [msg for msg in keep_msgs if msg.id not in cleanup_list]

        if discard_msgs:
            print_formatted_text(ANSI("\033[K \033[38;5;141m ● 正在更新上下文记忆... \033[0m\n"))
            discard_text = "\n".join(f"{m.type}: {m.content}" for m in discard_msgs if m.content)
            summary_prompt = get_summary_prompt(current_summary, discard_text)
            # 可以替换便宜模型
            new_summary_response = llm.invoke([HumanMessage(content=summary_prompt)])
            active_summary = new_summary_response.content

            # 更新摘要
            state_updates["summary"] = active_summary

            # 从状态机中删除信息
            discard_ids = [m.id for m in discard_msgs if m.id]
            cleanup_list.extend(discard_ids)
        else:
            active_summary = current_summary
        # 构建总的删除消息列表
        if cleanup_list:
            cleanup_cmds = [RemoveMessage(id=idx) for idx in cleanup_list]
            state_updates["messages"] = cleanup_cmds

        if active_summary:
            system_prompt += f"\n\n[近期对话上下文]\n{active_summary}\n\n(注: 这是系统自动生成的近期沟通摘要，请结合它来理解用户的最新问题)"

        total_messages = [SystemMessage(content=system_prompt)] + \
                       [m for m in keep_msgs if not isinstance(m, SystemMessage)]

        for m in total_messages:
            if isinstance(m.content, str):
                m.content = m.content.encode('utf-8', 'ignore').decode('utf-8')

        # 监控，记录即将发送给模型的消息(用于监控token数量)
        audit_logger.log_event(
            thread_id=thread_id,
            event="llm_input",
            message_count=len(total_messages),
        )
        response = llm_with_tools.invoke(total_messages)
        # 解析大模型的回答并记录到日志
        if response.tool_calls:
            for tool_call in response.tool_calls:
                audit_logger.log_event(
                    thread_id=thread_id,
                    event="tool_call",
                    tool=tool_call["name"],
                    args=tool_call["args"],
                )
        elif response.content:
            audit_logger.log_event(
                thread_id=thread_id,
                event="ai_message",
                content=response.content,
            )
        if "messages" not in state_updates:
            state_updates["messages"] = []
        state_updates["messages"].append(response)
        return state_updates

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")

    app = workflow.compile(checkpointer=checkpointer)
    return app
