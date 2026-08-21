from typing import List, Optional
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage
from .provider import get_provider
from .tools.builtins import BUILTIN_TOOLS
from langchain_core.runnables import RunnableConfig
from .context import AgentState


def get_system_prompt() -> str:
    system_prompt = "你是 Daru，一个聪明、高效、说话自然的 AI 助手。\n\n"
    return system_prompt

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
        raw_messages = state["messages"]
        system_prompt = get_system_prompt()
        state_updates = {}
        system_message = SystemMessage(content=system_prompt)
        total_messages = [system_message] + [m for m in raw_messages if not isinstance(m, SystemMessage)]
        for m in total_messages:
            if isinstance(m.content, str):
                m.content = m.content.encode('utf-8', 'ignore').decode('utf-8')
        response = llm_with_tools.invoke(total_messages)
        if "messages" not in state_updates:
            state_updates["messages"] = []
        state_updates["messages"].append(response)
        return state_updates

    workflow=StateGraph(AgentState)
    workflow.add_node("agent",agent_node)
    workflow.add_node("tools",tools_node)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent",tools_condition)
    workflow.add_edge("tools", "agent")

    app=workflow.compile(checkpointer=checkpointer)
    return app