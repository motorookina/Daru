import os
from typing import Any

import yaml
from pydantic import BaseModel

from .base import DaruBaseTool
from ..config import SKILL_DIR
from pathlib import Path

skills: dict[str, dict[str, str]] = {}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    从整个SKILL.md中解析出meta数据字典与SKILL.md中的文档内容
    :param text: SKILL.md整个文件中的内容
    :return: 元数据字典meta与主题内内容body
    """
    lines = text.splitlines(keepends=True)
    # .rstrip("\r\n")的含义是从文本右侧剔除所有回车符\r和换行符\n;
    # 如果lines不存在或经过处理之后的首行不是"---"，说明这不是一个规范的SKILL.md
    if not lines or lines[0].rstrip("\r\n") != "---":
        return {}, text
    # 在一个字符串列表 lines 中，查找第一个内容为 "---" 的行，并返回它在原列表中的索引值；如果找不到，就返回 None
    # 也就是找到meta和body分割的"---"的行号索引
    closing_index = next((idx for idx, line in enumerate(lines[1:], start=1) if line.rstrip("\r\n") == "---"), None)
    if closing_index is None:
        return {}, text

    frontmatter = "".join(lines[1:closing_index])
    body = "".join(lines[closing_index + 1:]).strip()
    try:
        metadata = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError:
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return metadata, body


def _catelog() -> str:
    if not skills:
        return "没有找到skills"
    return "\n".join(
        f"-{skill['name']}: {skill['description']}" for skill in skills.values()
    )


def scan():
    """agent启动时加载一次"""
    skills.clear()
    if not os.path.exists(SKILL_DIR):
        return
    # 将该路径转换为标准绝对路径，作为skills根目录保存
    skills_root = os.path.abspath(SKILL_DIR)
    # manifest 清单文件
    for manifest in sorted(Path(SKILL_DIR).glob("*/SKILL.md")):
        # 如果manifest不是文件或其不属于skills根目录下
        if (not manifest.is_file()) or not manifest.resolve().is_relative_to(skills_root):
            continue
        content = manifest.read_text(encoding="utf-8")
        metadata, body = _parse_frontmatter(content)
        raw_name = metadata.get("name")
        name = raw_name.strip() if isinstance(raw_name, str) else ""
        name = name or manifest.parent.name
        raw_description = metadata.get("description")
        description = (raw_description.strip() if isinstance(raw_description, str) else "")
        # 如果描述不存在，就用正文的首行作为描述
        description = description or body.split("\n")[0]
        description = " ".join(str(description).lstrip("# ").split())
        skills[name] = {
            "name": name,
            "description": description,
            "content": content
        }


def get_skill_category():
    scan()
    skills_category = _catelog()
    return skills_category

def build_skills_prompt(skill_category: str) -> str:
    return f"""可用技能如下：
    {skill_category}
    当某个技能适用时，请调用 load_skill 工具来读取其完整指令。
    """


class LoadSkillModel(BaseModel):
    """skill加载工具参数模型"""
    name: str


class LoadSkillTool(DaruBaseTool):
    name: str = "load_skill"
    description: str = """当某个技能使用时，传入该技能的名称调用该工具以获取该技能的完整说明"""
    args_schema: type[BaseModel] = LoadSkillModel

    def _run(self, **kwargs: Any) -> Any:
        name = kwargs.get("name")
        skill = skills.get(name)
        if skill:
            return skill["content"]
        available = ", ".join(skills) or "None"
        return f"Error: 未知sill'{name}'. 当前可用skills: '{available}'"
