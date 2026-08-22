import asyncio

# 初始化任务队列
task_queue=asyncio.Queue()

# 向任务队列中添加任务
async def add_task(content:str):
    await task_queue.put(content)