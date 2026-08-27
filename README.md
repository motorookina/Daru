<h1 align="center">Daru</h1>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python">
  <img src="https://img.shields.io/badge/langgraph-1.x-green" alt="LangGraph">
  <img src="https://img.shields.io/badge/langchain-1.x-green" alt="LangChain">
  <img src="https://img.shields.io/badge/platform-win%20%7C%20linux%20%7C%20mac-lightgrey" alt="Platform">
</p>

Daru 是基于 **LangChain + LangGraph** 构建的提供金融数据服务的 Agent。

- 🔁 **ReAct 循环**：思考 → 调工具 → 观察 → 再思考，由 LangGraph 状态机驱动
- 🏠 **沙盒工位**：Agent 拥有专属 `office` 目录，文件读写与 Shell 执行均被限制在沙盒内
- 🧠 **双规记忆**：长期用户画像 + 对话上下文自动压缩摘要
- ⏰ **定时任务**：Agent 可自主设定闹钟 / 循环提醒，心跳机制到点自动触发
- 🛠️ **技能系统**：以 `SKILL.md` 声明的可插拔技能包，按需动态加载
- 🎨 **终端体验**：炫彩 Banner、思考旋转动画、底部工具栏实时状态

---

## ✨ 特性

- **多模型适配**：一套代码兼容 OpenAI / Anthropic / Ollama，以及阿里云、腾讯云、智谱 Z.AI 等 OpenAI 兼容接口
- **双规记忆机制**
  - *长期画像*：持续沉淀用户静态偏好，写入 `user_profile.md`
  - *短期摘要*：超过 10 轮对话自动触发上下文压缩，动态维护 150 字以内的"交接文档"
- **孤儿消息清理**：自动检测中断遗留的未应答 `tool_call`，防止触发 API 400 错误
- **结构化沙盒安全**
  - 命令白名单（可经 `DARU_ALLOWED_COMMANDS` 扩展）
  - 封禁变量展开、命令替换、重定向越界
  - 解释器仅放行 office 内脚本，禁止 `-c/-e/-m` 内联代码
- **异步事件总线**：生产者-消费者解耦，输入不阻塞处理
- **JSONL 审计日志**：内存队列 + 守护线程异步落盘，全程留痕（含 token 用量、工具调用）
- **会话持久化**：SQLite checkpointer 支持断点恢复

---

## 🏗️ 架构

```
                    ┌────────────────────────────────────────────┐
                    │              终端 REPL (main.py)            │
                    │   用户输入 → asyncio.Queue → agent_worker    │
                    │   Spinner / 底部工具栏 实时反馈              │
                    └────────────────────┬───────────────────────┘
                                         │
                    ┌────────────────────▼───────────────────────┐
                    │            Agent 状态机 (LangGraph)          │
                    │                                             │
                    │        START ──► agent ──► tools_condition  │
                    │                   ▲              │          │
                    │                   └──────────────▼          │
                    │                      tools (ToolNode)       │
                    └────────────────────┬───────────────────────┘
                                         │
        ┌──────────────┬─────────────────┼─────────────────┬──────────────┐
        ▼              ▼                 ▼                 ▼              ▼
 ┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
 │ LLM Factory│ │ 双规记忆    │ │  沙盒工位    │ │  定时任务     │ │  技能系统     │
 │ provider.py│ │ context.py │ │ sandbox.py   │ │ heartbeat.py │ │ skills_loader│
 └────────────┘ └────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

核心数据流：

```
用户输入 → task_queue → agent_worker → Agent(astream)
    ├─ 工具调用 → 沙盒执行 → 返回结果 → 再思考
    └─ 文本回复 → 格式化输出到终端
```

---

## 🚀 快速开始

### 环境要求

- Python **3.10+**
- 任一 LLM API Key（OpenAI / Anthropic / 兼容厂商）或本地 Ollama

### 安装

```bash
git clone <your-repo-url>
cd Daru

# 创建虚拟环境（可选但推荐）
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入你的模型配置
```

### 运行

```bash
python -m entry.main
```

首次启动会自动创建 `workspace/` 工作区目录。看到欢迎 Banner 后即可直接对话：

```
❯ 现在几点？
❯ 每天上午8点提醒我喝牛奶
❯ 帮我把 office 里的 demo.py 跑一下
```

输入 `/exit` 或 `/quit` 退出，记忆会自动固化。

---

## ⚙️ 配置说明

| 环境变量 | 必填 | 说明 |
|---------|:---:|------|
| `DEFAULT_PROVIDER` | ✅ | 默认模型提供商：`openai` / `anthropic` / `aliyun` / `tencent` / `z.ai` / `ollama` / `other` |
| `DEFAULT_MODEL` | ✅ | 默认模型名称，如 `deepseek-v4-flash` |
| `OPENAI_API_KEY` | ✅ | OpenAI 及兼容接口的 API Key（使用 Ollama 时除外） |
| `OPENAI_API_BASE_URL` | ⬜ | OpenAI 兼容 Base URL，不填时自动回落到各厂商官方兼容地址 |
| `ANTHROPIC_API_KEY` | ⬜ | Anthropic 专用 |
| `ANTHROPIC_BASE_URL` | ⬜ | Anthropic 代理地址 |
| `OLLAMA_API_BASE_URL` | ⬜ | Ollama 本地服务地址，默认 `http://localhost:11434` |
| `DARU_ALLOWED_COMMANDS` | ⬜ | 扩展沙盒 Shell 命令白名单（逗号分隔），生效会记入审计日志 |

内置的 OpenAI 兼容接口兜底地址：

| 提供商 | 默认 Base URL |
|--------|--------------|
| 阿里云 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 智谱 Z.AI | `https://open.bigmodel.cn/api/paas/v4` |
| 腾讯混元 | `https://api.hunyuan.cloud.tencent.com/v1` |

---

## 🔧 内置工具

Agent 启动即自动挂载以下工具，可通过自然语言直接调用：

| 工具 | 说明 |
|------|------|
| `get_current_time` | 获取当前系统时间 / 日期 |
| `list_office_files` | 查看 office 工位目录内容 |
| `read_office_file` | 读取工位内文件（超长自动截断） |
| `write_office_file` | 写入 / 追加工位文件（`w` / `a` 模式） |
| `execute_office_shell` | 在工位内执行 Shell 命令（白名单 + 路径越界防护） |
| `schedule_task` | 设定一次性 / 循环定时任务（支持 AM/PM 歧义强制确认） |
| `list_scheduled_tasks` | 查看待执行定时任务列表 |
| `delete_scheduled_task` | 按 ID 删除任务（模糊匹配需二次确认） |
| `modify_scheduled_task` | 修改任务时间 / 内容 |
| `load_skill` | 按名称加载技能包完整指令 |

> 自定义工具：继承 `daru.core.tools.base.DaruBaseTool`，实现 `_run` 方法并挂载到 `BUILTIN_TOOLS` 即可。

---

## 🧠 记忆系统

Daru 采用 **双轨记忆**：

| 维度 | 存储位置 | 触发机制 | 内容 |
|------|---------|---------|------|
| 长期画像 | `workspace/memory/user_profile.md` | 检测到用户偏好变化时更新 | 姓名、语言偏好、交流风格等静态事实 |
| 短期摘要 | LangGraph state `summary` | 对话超 10 轮自动压缩 | "我们在聊什么 / 解决了什么 / 结论是什么" |

此外还有一道**孤儿消息清理**防线：当 Agent 异常中断导致某些 `tool_call` 未被应答时，这些消息会被自动剔除，避免把不完整的调用链发给模型触发 `insufficient tool messages following tool_calls`。

---

## 🛠️ 技能系统 (Skills)

技能以目录形式放在 `workspace/skill/` 下，每个技能是一个含 `SKILL.md` 清单的文件夹：

```
workspace/skill/
└── akshare-pro/
    ├── SKILL.md              # frontmatter: name + description + 完整指令
    ├── scripts/              # 可执行脚本
    └── references/           # 参考文档
```

Agent 启动时自动扫描技能目录并生成技能目录清单注入提示词；当对话命中某技能场景时，Agent 调用 `load_skill` 动态加载完整指令。当前内置技能：`akshare-pro`（AKShare 金融数据下载）、`lixinger-open-skill`（理杏仁开放接口）、`tushare-pro`（Tushare 数据）、`sql-pro`（SQL 存储工作流）。

> 扩展新技能：在 `workspace/skill/` 下新建目录并编写 `SKILL.md` 即可，重启后自动生效。

---

## 🙏 致谢 / Acknowledgements

本项目的前身与核心设计参考自 [CyberClaw](https://github.com/ttguy0707/CyberClaw)（MIT License，作者 [ttguy0707](https://github.com/ttguy0707)），沿用了其中的部分设计理念与代码实现：

- **全行为审计**：JSONL 异步审计日志（`llm_input` / `tool_call` / `tool_result` / `ai_message` / `system_action`）
- **双水位记忆**：长期用户画像（`user_profile.md`）+ 短期对话摘要
- **心跳任务引擎**：定时 / 循环任务触发机制
- **office 沙盒**：路径越界拦截、命令白名单与跨平台适配
- **技能生态**：基于 `SKILL.md` 的可插拔技能加载

Daru 在此基础上将定位聚焦于**金融数据服务**，并新增了skill自动扫描加载（`load_skill`）、孤儿消息清理等能力。

原项目遵循 [MIT License](https://github.com/ttguy0707/CyberClaw/blob/main/LICENSE)，相关版权声明见 [CyberClaw/LICENSE](https://github.com/ttguy0707/CyberClaw/blob/main/LICENSE)。
