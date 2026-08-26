from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel

from .base import DaruBaseTool

import os
import json
import uuid
import threading

from ..config import TASK_FILE

from .sandbox import (
    ListOfficeFilesTool,
    ReadOfficeFileTool,
    WriteOfficeFileTool,
    ExecuteOfficeShellTool
)

# 线程锁,防止多个线程同时向任务队列中添加或消费任务造成死锁
tasks_lock = threading.Lock()


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


class ScheduleTaskModel(BaseModel):
    """定时任务闹钟工具"""
    target_time: str
    description: str
    repeat: str = None
    repeat_count: int = None


class ScheduleTaskTool(DaruBaseTool):
    name: str = "schedule_task"
    description: str = """
    为一个未来的任务设定闹钟或提醒。
    参数 target_time 必须是严格的格式："YYYY-MM-DD HH:MM:SS"（请先调用 get_current_time 获取当前时间，并在其基础上推算）。
    参数 description 是需要执行的动作或要说的话。
    
    【高级循环功能】：
    - repeat (可选): 设置重复频率。可选值为 "hourly", "daily", "weekly"。如果不重复请留空。
    - repeat_count (可选): 结合 repeat 使用，表示一共需要触发几次。
    
    【案例教学】：
    1. 用户说："以后每天8点提醒我喝牛奶" -> repeat="daily", repeat_count=None (无限循环)
    2. 用户说："接下来的3天，每天提醒我吃药" -> repeat="daily", repeat_count=3 (有限循环)
    3. 用户说："明早8点叫我起床" -> repeat=None, repeat_count=None (单次任务)

    【时间歧义严格确认协议 (AM/PM Ambiguity CRITICAL)】：
    当用户说出的时间存在 12 小时制的模糊性时（例如：只说了“7点”，没明确说早上还是晚上）：
    1. 你必须向用户提问确认是上午还是下午。
    2. 【死命令】：在用户明确回复“上午”或“下午”（或改为24小时制）之前，本工具处于【绝对锁定状态】！
    3. 就算用户发省略号（如“。。”）、发脾气、或者说无关内容，你也【绝对禁止】为了讨好用户而自行猜测时间！
    4. 严禁出现“抱歉多问了”、“默认早上”这种妥协行为。
    5. 如果用户不明确回答，你必须坚定地回复：“抱歉，没有明确上下午，我无权为您设置闹钟。请明确告知时间段。”并立即中止工具调用。
    """
    args_schema: type[BaseModel] = ScheduleTaskModel

    def _run(self, **kwargs: Any) -> Any:
        target_time = kwargs.get("target_time")
        description = kwargs.get("description")
        repeat = kwargs.get("repeat")
        repeat_count = kwargs.get("repeat_count")
        try:
            target_dt = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return "设定失败，时间格式错误，必须严格遵守'YYYY-MM-DD HH:MM:SS'格式"

        now = datetime.now()
        if target_dt <= now:
            return (
                "设定失败：target_time 必须晚于当前时间。"
                f" 当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}，"
                f" 你传入的是：{target_time}"
            )

        with tasks_lock:
            tasks = []
            if os.path.exists(TASK_FILE):
                try:
                    with open(TASK_FILE, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            tasks = json.loads(content)
                except Exception as e:
                    return f"设定失败: 任务队列读取异常:{e}"
            new_task = {
                "id": str(uuid.uuid4())[:8],
                "target_time": target_time,
                "description": description,
                "repeat": repeat,
                "repeat_count": repeat_count,
            }
            tasks.append(new_task)

            try:
                with open(TASK_FILE, "w", encoding="utf-8") as f:
                    json.dump(tasks, f, ensure_ascii=False, indent=2)
            except Exception as e:
                return f"设定失败：任务队列写入异常 {str(e)}"
        msg = f" 任务已成功加入队列。首发时间：{target_time} | 任务：{description}"
        if repeat:
            msg += f" | 循环模式：{repeat} (共 {repeat_count if repeat_count else '无限'} 次)"
        return msg


class ListScheduledTasksModel(BaseModel):
    """当前待处理定时任务列表查询工具参数模型"""


class ListScheduledTasksTool(DaruBaseTool):
    name: str = "list_scheduled_tasks"
    description: str = """
    查看当前所有待处理的定时任务列表。
    当用户询问“我都有哪些任务”、“查一下闹钟”、“刚才定了什么”时调用此工具。
    """
    args_schema: type[BaseModel] = ListScheduledTasksModel

    def _run(self, **kwargs: Any) -> Any:
        with tasks_lock:
            if not os.path.exists(TASK_FILE):
                return "当前没有任何定时任务"
        try:
            with open(TASK_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return "任务列表为空"
                tasks = json.loads(content)
            if not tasks:
                return "当前没有任何定时任务"
            tasks.sort(key=lambda x: x['target_time'])
            res = " 当前待执行任务列表：\n"
            for t in tasks:
                res += f"- [ID: {t['id']}] 时间: {t['target_time']} | 任务: {t['description']}\n"
            return res
        except Exception as e:
            return f"查询失败：{str(e)}"


class DeleteScheduledTaskModel(BaseModel):
    task_id: str  # 任务ID，必填


class DeleteScheduledTaskTool(DaruBaseTool):
    name: str = "delete_scheduled_task"
    description: str = """
    根据任务 ID 取消或删除一个定时任务。
    
    【强制性风险控制协议 (CRITICAL)】：
    删除操作具有不可逆性。
    1. 只要匹配到符合描述的任务数量 > 1。
    2. 无论用户语气多么确定，只要他没提供具体的任务 ID。
    
    【你必须执行的动作】：
    【禁止】在单次回复中针对同一个模糊描述发起多个删除工具调用。
    你必须先列出所有匹配的任务（1. 2. 3.），并询问用户：
    “发现了多个符合条件的提醒（列出列表），为了安全起见，请问是要全部删除，还是只删除其中几个？”
    必须要用户明确给出编号或者说确定全部删除，才能调用此工具！！
    严禁自作主张执行批量删除。
    """
    args_schema: type[BaseModel] = DeleteScheduledTaskModel

    def _run(self, **kwargs) -> str:
        task_id = kwargs.get("task_id")
        if not task_id:
            return "删除失败：缺少 task_id 参数。"

        with tasks_lock:
            if not os.path.exists(TASK_FILE):
                return "删除失败：任务列表文件不存在。"

            try:
                with open(TASK_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    tasks = json.loads(content) if content else []

                new_tasks = [t for t in tasks if t['id'] != task_id]

                if len(new_tasks) == len(tasks):
                    return f"删除失败：未找到 ID 为 {task_id} 的任务。"

                with open(TASK_FILE, "w", encoding="utf-8") as f:
                    json.dump(new_tasks, f, ensure_ascii=False, indent=2)

                return f"任务 [ID: {task_id}] 已成功取消。"
            except Exception as e:
                return f"操作异常：{str(e)}"


class ModifyScheduledTaskModel(BaseModel):
    task_id: str  # 必填
    new_time: Optional[str] = None      # 新时间，格式 "YYYY-MM-DD HH:MM:SS"
    new_description: Optional[str] = None


class ModifyScheduledTaskTool(DaruBaseTool):
    name: str = "modify_scheduled_task"
    description: str = """
    修改现有定时任务的时间或内容。
    
    【强制性风险控制协议 (CRITICAL)】：
    1. 只要用户通过“模糊描述”（如：那个5天的任务、洗澡的任务）来要求修改，而没有直接提供 ID。
    2. 无论用户的话语看起来是单数还是复数（如：“把5天的任务全改了”）。
    3. 只要系统中匹配到的任务数量 > 1。
    
    【你必须执行的动作】：
    禁止直接调用本工具！你必须向用户展示匹配到的所有任务列表，并强制询问：
    “我发现有 [N] 个任务符合描述（列出列表），请问你是要【全部修改】，还是修改其中【某几个】？（请告诉我编号或确认全部）”
    
    必须在用户回复“全部”或者指定了具体编号后，你才能继续操作！修改任务并非小事,这是为了安全！！
"""
    args_schema: type[BaseModel] = ModifyScheduledTaskModel

    def _run(self, **kwargs) -> str:
        task_id = kwargs.get("task_id")
        new_time = kwargs.get("new_time")
        new_description = kwargs.get("new_description")

        if not task_id:
            return "修改失败：缺少 task_id 参数。"

        with tasks_lock:
            if not os.path.exists(TASK_FILE):
                return "修改失败：任务列表为空。"

            try:
                with open(TASK_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    tasks = json.loads(content) if content else []

                found = False
                for t in tasks:
                    if t['id'] == task_id:
                        if new_time:
                            parsed_new_time = datetime.strptime(new_time, "%Y-%m-%d %H:%M:%S")
                            now = datetime.now()
                            if parsed_new_time <= now:
                                return (
                                    "修改失败：new_time 必须晚于当前时间。"
                                    f" 当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}，"
                                    f" 你传入的是：{new_time}"
                                )
                            t['target_time'] = new_time
                        if new_description:
                            t['description'] = new_description
                        found = True
                        break

                if not found:
                    return f"修改失败：未找到 ID 为 {task_id} 的任务。"

                with open(TASK_FILE, "w", encoding="utf-8") as f:
                    json.dump(tasks, f, ensure_ascii=False, indent=2)

                return f"任务 [ID: {task_id}] 已成功更新。"
            except ValueError:
                return "修改失败：时间格式错误。"
            except Exception as e:
                return f"操作异常：{str(e)}"

BUILTIN_TOOLS = [
    GetCurrentTimeTool(),
    ListOfficeFilesTool(),
    ReadOfficeFileTool(),
    WriteOfficeFileTool(),
    ExecuteOfficeShellTool(),
    ScheduleTaskTool(),
    ListScheduledTasksTool(),
    DeleteScheduledTaskTool(),
    ModifyScheduledTaskTool(),
]
