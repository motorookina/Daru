import os
import json
import threading
import queue
import atexit
from datetime import datetime, timezone


# 内存队列+守护线程
class JSONLEventLogger:
    # 单例模式
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, log_dir: str = "logs"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_logger(log_dir)
            return cls._instance

    def _init_logger(self, log_dir: str):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        # 无界内存队列，用于缓冲日志事件
        self.log_queue = queue.Queue()
        self.work_thead = threading.Thread(target=self._write_loop,daemon=True)
        self.work_thead.start()
        # 确保程序被关闭时，队列里剩下的日志能被写完。
        # 当该程序退出之前，必须要调用对应的方法。
        atexit.register(self.shutdown)

    def _write_loop(self):
        """后台循环线程，盯紧队列，有日志就写，没日志就阻塞休眠"""
        while True:
            log_item = self.log_queue.get()
            if not log_item:
                self.log_queue.task_done()
                break
            try:
                thread_id = log_item.get("thread_id", "system_default")
                safe_id = "".join(c for c in thread_id if c.isalnum() or c in "-_") or "default"
                """在 .jsonl 文件中（JSON Lines，每行一个独立JSON）：
                {"user": "你好", "assistant": "嗨！", "time": "10:01"}
                {"user": "天气", "assistant": "晴天", "time": "10:02"}
                {"user": "再见", "assistant": "拜拜", "time": "10:03"}
                区别于普通json文件，必须用[]将多个json括起来
                [
                  {"user": "你好", "assistant": "嗨！", "time": "10:01"},
                  {"user": "天气", "assistant": "晴天", "time": "10:02"},
                  {"user": "再见", "assistant": "拜拜", "time": "10:03"}
                ]
                """
                file_path = os.path.join(self.log_dir, f"{safe_id}.jsonl")
                with open(file_path,"a",encoding="utf-8") as f:
                    f.write(json.dumps(log_item,ensure_ascii=False)+"\n")
            except Exception as e:
                print(f"[Logger Error] 异步写入日志失败: {e}")
            finally:
                self.log_queue.task_done()

    # 前台调用的埋点方法
    def log_event(self,thread_id:str,event:str,**kwargs):
        now_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        log_item={
            "ts":now_utc,
            "thread_id":thread_id,
            "event":event,
            **kwargs
        }
        self.log_queue.put(log_item)

    def shutdown(self):
        # 发送毒丸信号，让线程内的循环终止，线程准备自然消亡
        self.log_queue.put(None)
        # 阻塞主线程，等待日志队列全空时才最终退出
        self.log_queue.join()

audit_logger=JSONLEventLogger()