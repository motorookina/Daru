import asyncio

from langchain_core.messages import HumanMessage

from daru.core.bus import task_queue, add_task
from daru.core.agent import create_agent_app


async def agent_worker():
    current_provider = "openai"
    current_model = "deepseek-v4-flash"
    app = create_agent_app(provider_name=current_provider, model_name=current_model)
    print("Daru 引擎已就绪，输入 /exit 退出。")
    while True:
        user_input = await task_queue.get()
        if user_input.lower() in ["/exit", "/quit"]:
            task_queue.task_done()
            break
        inputs = {"messages": [HumanMessage(content=user_input)]}
        try:
            async for event in app.astream(inputs, stream_mode="updates"):
                print(f"event:{event}")
                for node_name, node_data in event.items():
                    print(f"node_name:{node_name}")
                    print(f"node_data:{node_data}")
                    if node_name == "agent":
                        last_msg = node_data["messages"][-1]
                        if getattr(last_msg, "tool_calls", None):
                            for tc in last_msg.tool_calls:
                                print(f"唤醒内置工具:{tc['name']}...")
                        elif last_msg.content:
                            lines = last_msg.content.strip().split("\n")
                            print(f"输出内容:{lines}")
                    elif node_name == "tools":
                        print("内置工具执行完成...")
        except Exception as e:
            print(f"引擎异常:{e}")
        task_queue.task_done()


async def stdin_producer():
    """从控制台读入一行，投递到任务队列。
    生产者,它不断读取你在键盘上敲的内容，封装成任务扔进队列。
    如果后续由外部组件（如 Web UI）调用 add_task 喂队列，可以删除本函数及 main() 里的 producer。
    """
    while True:
        line = await asyncio.to_thread(input, "你> ")
        await add_task(line)
        if line.lower() in ["/exit", "/quit"]:
            break


async def main():
    producer = asyncio.create_task(stdin_producer())
    try:
        await agent_worker()
    finally:
        producer.cancel()


if __name__ == '__main__':
    asyncio.run(main())
