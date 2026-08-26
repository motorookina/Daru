import os
import json
import asyncio
import calendar
from datetime import datetime, timedelta
from .config import TASK_FILE
from .tools.builtins import tasks_lock


async def pacemaker_loop(task_queue: asyncio.Queue, check_interval: int = 10):
    """
    心跳循环机制: 带并发锁和循环任务续期功能
    :param task_queue: 异步任务队列
    :param check_interval: 心跳间隔
    """
    while True:
        await asyncio.sleep(check_interval)
        # 如果任务文件还未存在，说明还未添加新的任务
        if not os.path.exists(TASK_FILE):
            continue
        now = datetime.now()
        pending_tasks = []  # 待处理任务列表
        triggered_tasks = []  # 已触发任务

        # 线程锁，防止多线程/多协程同时读写文件导致的竞争条件和数据损坏
        with tasks_lock:
            try:
                with open(TASK_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    # 类似的，如果任务文件中还没有写入内容，说明还没有任务
                    if not content:
                        continue
                    tasks = json.loads(content)
            except Exception:
                continue

            if not tasks:
                continue

            for t in tasks:
                try:
                    target_dt = datetime.strptime(t["target_time"], "%Y-%m-%d %H:%M:%S")
                    # 目标触发时间已经过了，那么就把该任务加入到待触发定时任务列表中
                    # 并且如果是循环任务的话就将次数减一，次数耗尽就不再触发
                    if now >= target_dt:
                        triggered_tasks.append(t)
                        repeat_freq = t.get("repeat")
                        if repeat_freq:
                            repeat_count = t.get("repeat_count")
                            # 因为当前的该任务只剩一次触发机会但是这个时间已经过去了，所以就直接跳过了
                            if repeat_count is not None:
                                if repeat_count <= 1:
                                    continue
                                else:
                                    t["repeat_count"] = repeat_count - 1

                            if repeat_freq == "hourly":
                                next_dt = target_dt + timedelta(hours=1)
                            elif repeat_freq == "daily":
                                next_dt = target_dt + timedelta(days=1)
                            elif repeat_freq == "weekly":
                                next_dt = target_dt + timedelta(days=7)
                            elif repeat_freq == "monthly":
                                month = target_dt.month + 1
                                year = target_dt.year
                                if month > 12:
                                    month = 1
                                    year += 1
                                last_day = calendar.monthrange(year, month)[1]
                                day = min(target_dt.day, last_day)
                                next_dt = target_dt.replace(year=year, month=month, day=day)
                            else:
                                continue

                            t["target_time"] = next_dt.strftime("%Y-%m-%d %H:%M:%S")
                            pending_tasks.append(t)
                    else:
                        # 还未到触发时间的任务继续保留在待办列表中
                        pending_tasks.append(t)
                except Exception:
                    pass
            # 将还没到触发时间的任务和续期后的循环任务写回文件，覆盖原有内容
            if triggered_tasks:
                try:
                    with open(TASK_FILE, "w", encoding="utf-8") as f:
                        json.dump(pending_tasks, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass

        for t in triggered_tasks:
            system_msg = (
                f"【系统内部心跳触发】\n"
                f"你设定的定时任务已到期，请立即主动提醒用户或执行动作。\n"
                f"任务内容：{t['description']}"
            )
            await task_queue.put(system_msg)
