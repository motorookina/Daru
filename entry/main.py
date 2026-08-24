import os
import time
import asyncio
import random

from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.styles import Style
from prompt_toolkit.application import get_app

from langchain_core.messages import HumanMessage

from daru.core.bus import task_queue
from daru.core.agent import create_agent_app
from daru.core.config import DB_PATH


def clear_screen():
    # 调用清空屏幕的命令，win的是cls，其他系统的是clear
    os.system('cls' if os.name == 'nt' else 'clear')


def type_line(text: str, delay: float = 0.008):
    for ch in text:
        print(ch, end='', flush=True)
        time.sleep(delay)
    print()


def print_banner():
    clear_screen()

    MAIN = '\033[38;5;39m'  # 亮蓝色（主色调）
    ACCENT = '\033[38;5;27m'  # 深蓝色（辅助色）
    SILVER = '\033[38;5;250m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    WHITE = '\033[37m'

    logo = f"""{MAIN}{BOLD}
 ____   ___  _  __ _   _ 
|  _ \ |_ _|| |/ /| | | |
| |_) | | | | ' / | | | |
|  _ <  | | | . \ | |_| |
|_| \_\|___||_|\_\ \___/ 
                          
{RESET}"""

    sub_title = f"{WHITE}{BOLD} 欢迎来到 {ACCENT}{BOLD}RiKu{RESET}{WHITE}{BOLD} !  {RESET}"

    quote = "Every thing is the choice of Steins;Gate."
    meta = f" {SILVER}✦{RESET} {MAIN}{quote}{RESET}"

    tip = (
        f"{ACCENT} ✦ {RESET}"
        f"{SILVER}{ACCENT}{BOLD}RiKu{RESET} 已完成启动。输入命令开始，输入 {ACCENT}/exit{RESET}{SILVER} 退出。{RESET}\n"
    )

    print(logo)
    type_line(sub_title)
    print()
    time.sleep(0.12)
    type_line(meta)
    print()
    type_line(tip)


def cprint(text="", end="\n"):
    print_formatted_text(ANSI(str(text)), end=end)


# 主入口函数
async def async_main():
    print_banner()
    current_provider = "openai"
    current_model = "deepseek-v4-flash"

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    async with AsyncSqliteSaver.from_conn_string(DB_PATH) as memory:
        app = create_agent_app(provider_name=current_provider, model_name=current_model)
        config = {"configurable": {"thead_id": "local_geek_master"}}

        class SpinnerState:
            """旋转器状态"""
            action_words = [
                "Thinking...",
                "Working...",
                "Tuturu..."
            ]
            current_words = []
            is_spinning = False  # 是否正在旋转，默认旋转状态为关闭
            start_time = 0
            frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
            is_tool_calling = False  # 是否有工具调用
            tool_msg = ""  # 工具调用表述

        spinner = SpinnerState()

        def get_bottom_toolbar():
            """界面刷新由 PromptSession 的 bottom_toolbar 和
            定时 invalidate() 驱动
            """
            if not spinner.is_spinning:
                return ANSI("")
            elapsed = time.time() - spinner.start_time
            # 如果包含工具调用，显示工具消息
            if spinner.is_tool_calling:
                display_msg = spinner.tool_msg
            # 否则根据事件索引显示动作词
            else:
                time_idx = int(elapsed) % len(spinner.current_words)
                display_msg = f"{spinner.current_words[time_idx]}"
            # 根据时间索引计算旋转帧索引
            idx_frame = int(elapsed * 12) % len(spinner.frames)
            current_frame = spinner.frames[idx_frame]
            return ANSI(
                f"  \033[38;5;51m{current_frame}\033[0m \033[38;5;250m{display_msg}\033[0m \033[38;5;141m[{elapsed:.1f}s]\033[0m")

        prompt_message = ANSI("  \033[38;5;51m❯\033[0m ")
        # 当输入框为空时，显示一个灰色的占位文字（输入...），提示用户该输入什么。
        placeholder_text = ANSI("\033[3m\033[38;5;242m In... \033[0m")

        async def agent_worker():
            """消费者，监听任务队列，随时处理，一旦拿到用户输入就开始启动agent进行思考和处理，"""
            while True:
                user_input = await task_queue.get()
                if user_input.lower() in ["/exit", "/quit"]:
                    task_queue.task_done()
                    break

                spinner.current_words = spinner.action_words.copy()
                # 将动作列表中的内容随机打乱
                random.shuffle(spinner.current_words)
                spinner.start_time = time.time()
                spinner.is_spinning = True
                spinner.is_tool_calling = False

                inputs = {"messages": [HumanMessage(content=user_input)]}
                try:
                    async for event in app.astream(inputs, config=config, stream_mode="updates"):
                        for node_name, node_data in event.items():
                            if node_name == "agent":
                                last_msg = node_data["messages"][-1]
                                if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                                    for tc in last_msg.tool_calls:
                                        spinner.is_tool_calling = True
                                        spinner.tool_msg = f"唤醒内置工具: {tc['name']}..."
                                        cprint(f"  ●\033[38;5;51m Tool Call: \033[0m{tc['name']}")
                                        cprint('')
                                elif last_msg.content:
                                    # 如果没有工具调用，说明已经得到了一个loop的的结果，所以要
                                    # 暂时停掉思考帧动画，并输出结论
                                    spinner.is_spinning = False
                                    lines = last_msg.content.strip().split("\n")
                                    if lines:
                                        formatted_out = f"  \033[38;5;141m❯\033[0m \033[38;5;250m{lines[0]}"
                                        for line in lines[1:]:
                                            formatted_out += f"\n {line}"
                                        formatted_out += "\033[0m"
                                        cprint(formatted_out)
                            # 因为agent节点如果要调用节点，会打印工具调用相关的信息，然后进入tool_node
                            # 进行工具调用，为了显示agent还在工作，会让is_tool_calling设置为false
                            # 继续显示Thinking的动画。
                            elif node_name != "agent":
                                spinner.is_tool_calling = False
                except Exception as e:
                    spinner.is_spinning = False
                    cprint(f"  \033[31m[ ⚠️ 引擎异常 : {e} ]\033[0m")
                spinner.is_spinning = False
                cprint()  # 空出舒适的行距
                task_queue.task_done()

        async def user_input_loop():
            """单开一行的用户输入循环，等待用户输入"""
            custom_style = Style.from_dict({
                'bottom-toolbar': 'bg:default fg:default noreverse',
            })

            # 创建一个交互式会话的配置实例。
            session = PromptSession(
                # 管底部状态栏显示什么。传入的是函数名（不加括号），每次屏幕刷新时
                # 自动调用这个函数，把返回值（你写的旋转动画 + 计时器）画在输入框的最底部。
                bottom_toolbar=get_bottom_toolbar,
                style=custom_style,
                erase_when_done=True,
                reserve_space_for_menu=0
            )

            # 重绘定时器
            async def redraw_timer():
                while True:
                    # 只要旋转状态还在继续
                    if spinner.is_spinning:
                        try:
                            # 官方的重绘接口，调用它，框架会在下一个时间循环中重绘整个UI。
                            get_app().invalidate()
                        except Exception:
                            pass
                    await asyncio.sleep(0.08)

            # 将这个协程对象包装成一个独立的后台任务，并立即调度到异步事件循环中执行，
            # 并将
            redraw_task = asyncio.create_task(redraw_timer())

            while True:
                try:
                    # 异步输入方法，挂起当前协程，等待用户在终端输入内容并按下回车
                    # 与同步输入方法不同，它允许事件循环在等待用户输入时执行其他任务。
                    # prompt_message是显示在输入框前边的提示文字
                    # placeholder是输入框为空时的灰色占位字符
                    user_input=await session.prompt_async(prompt_message,placeholder=placeholder_text)

                    user_input=user_input.strip()
                    # 用户可能输入为空，直接敲击了回车，这时候应当直接跳到下一个循环
                    if not user_input:
                        continue
                    padded_bubble = f"  ❯ {user_input}    "
                    cprint(f"\033[48;2;38;38;38m\033[38;5;255m{padded_bubble}\033[0m\n")

                    # 将用户输入加入消息队列
                    await task_queue.put(user_input)
                    if user_input.lower() in ["/exit", "/quit"]:
                        cprint("  \033[38;5;141m✦ 记忆已固化，RiKu 进入休眠。\033[0m")
                        break
                except (KeyboardInterrupt,EOFError):
                    cprint("\n  \033[38;5;141m✦ 强制中断，CyberClaw 进入休眠。\033[0m")
                    await task_queue.put("/exit")
                    break
            redraw_task.cancel()

        with patch_stdout():
            worker = asyncio.create_task(agent_worker())
            await user_input_loop()
            await task_queue.join()
            worker.cancel()

def main():
    asyncio.run(async_main())


if __name__ == '__main__':
    main()