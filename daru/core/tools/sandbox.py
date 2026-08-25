from typing import Any

from pydantic import BaseModel

from daru.core.tools.base import DaruBaseTool
from daru.core.config import OFFICE_DIR

import os


def _get_safe_path(relative_path: str) -> str:
    """
    代码级边界硬约束。
    将模型传入的相对路径转换为绝对路径,并检查其是否越界；
    如果模型试图传入类似"../../etc/passwd"的路径会直接被拦截
    :param relative_path: 相对路径
    :return: 安全绝对路径
    """
    # 将office_dir转换为标准绝对路径
    base_dir = os.path.abspath(OFFICE_DIR)
    # 将目标路径转换为绝对路径
    target_dir = os.path.abspath(os.path.join(base_dir, relative_path))

    # 目标路径必须以office_dir开头，否则直接非法拦截
    if not target_dir.startswith(base_dir):
        raise PermissionError(f"[越权拦截]: 你试图访问沙盒之外的路径 {relative_path}")
    return target_dir


class ListOfficeFilesModel(BaseModel):
    """列举目录下所有文件工具参数模型"""
    sub_dir: str


class ListOfficeFilesTool(DaruBaseTool):
    name: str = "list_office_files"
    description: str = """
    查看你的 office 工位里有哪些文件和文件夹。
    如果 sub_dir 为空，则查看工位根目录。
    """
    args_schema: type[BaseModel] = ListOfficeFilesModel

    def _run(self, **kwargs: Any) -> Any:
        sub_dir = kwargs.get("sub_dir")
        try:
            target_dir = _get_safe_path(sub_dir)
            if not os.path.exists(target_dir):
                return f"目录 {sub_dir} 不存在"
            items = os.listdir(target_dir)
            if not items:
                return f"目录 {sub_dir if sub_dir else 'office'} 为空"

            result = []
            for item in items:
                item_path = os.path.join(target_dir, item)
                item_type = "📁" if os.path.isdir(item_path) else "📄"
                result.append(f"{item_type} {item_path}")
            return "\n".join(result)
        except Exception as e:
            return str(e)


class ReadOfficeFileModel(BaseModel):
    """读工位文件工具的参数模型"""
    filepath: str


class ReadOfficeFileTool(DaruBaseTool):
    name: str = "read_office_file"
    description: str = """读取 office 工位里指定文件的内容。
    filepath 参数应该是相对于 office 的路径，例如 "test.py" 或 "skills/my_skill.py"。
    """
    args_schema: type[BaseModel] = ReadOfficeFileModel

    def _run(self, **kwargs: Any) -> Any:
        filepath = kwargs.get("filepath")
        try:
            target_path = _get_safe_path(filepath)
            if not os.path.exists(target_path):
                return f"路径 {filepath} 下的文件不存在"
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()
                # 防止文件内容太大浪费token，进行截断，不会读取超过10000字符的部分
                # 中文，英文，标点符号都算作一个字符
                if len(content) > 10000:
                    return content[:10000] + "\n\n...[内容过长，已被安全截断]..."
                return content
        except Exception as e:
            return str(e)


class WriteOfficeFileModel(BaseModel):
    """写文件工具参数模型"""
    filepath: str
    content: str
    mode: str = "w"


class WriteOfficeFileTool(DaruBaseTool):
    name: str = "write_office_file"
    description: str = """
    在 office 工位里操作文件内容。
    
    参数说明:
    - filepath: 相对路径，例如 "spider.py" 或 "docs/readme.md"。
    - content: 要写入的具体文本或代码内容。
    - mode: 写入模式。
        - "w" (默认): 【覆盖/新建】模式。如果文件已存在，将彻底清空原内容并写入新内容！
        - "a": 【追加】模式。保留原内容，将新内容追加到文件最末尾（常用于写日志或在文件末尾新增函数）。
        
    ⚠️ 智能体操作规范：
    1. 如果你要修改一个长文件中间的某几行，目前最安全的做法是：读取原文件，在你的内存中完成替换，然后用 "w" 模式把【完整的最新代码】重写进去。
    2. 如果你需要重命名文件或删除文件，请直接使用 execute_office_shell 工具执行 `mv` 或 `rm` 命令。
    3. 禁止编写 与 跳出office工位 相关的任何语言脚本！
    """
    args_schema: type[BaseModel] = WriteOfficeFileModel

    def _run(self, **kwargs: Any) -> Any:
        filepath = kwargs.get("filepath")
        content = kwargs.get("content")
        mode = kwargs.get("mode")
        try:
            target_path = _get_safe_path(filepath)
            if mode not in ["w", "a"]:
                return "[Error] mode参数必须是'w'(覆盖)或'a'(追加)."
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, mode, encoding="utf-8") as f:
                # 如果是追加模式，且内容不是以换行符开头，自动补一个换行，防止代码粘连
                if mode == "a" and not content.startswith("\n"):
                    f.write("\n" + content)
                else:
                    f.write(content)
            action = "覆盖/新建" if mode == "w" else "追加"
            return f" ● 成功以 {action} 模式写入文件：{filepath} (共 {len(content)} 字符)"
        except Exception as e:
            return str(e)