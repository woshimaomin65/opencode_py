# OpenCode Py 项目使用指南

## 项目概述

OpenCode Py 是一个基于 Python 的 AI 辅助编程工具，通过集成大语言模型（LLM）和多种工具来实现智能代码生成和编辑功能。

---

## 目录结构

```
opencode_py/
├── cli/                    # 命令行接口
│   ├── main.py            # CLI 入口点
│   └── commands/          # CLI 命令模块
├── agent/                  # Agent 核心模块
│   ├── agent.py           # Agent 主类
│   └── prompt/            # 提示词模板
├── config/                 # 配置管理
│   └── config.py          # 配置加载和解析
├── llm/                    # LLM 接口层
│   ├── llm.py             # LLM 抽象基类
│   └── providers/         # 不同 LLM 提供商实现
├── provider/               # 模型提供商
│   └── provider.py        # 提供商配置和管理
├── session/                # 会话管理
│   ├── session.py         # 会话状态管理
│   └── prompt.py          # 提示词处理
├── tool/                   # 工具模块
│   ├── tool.py            # 工具基类
│   ├── write.py           # 文件写入工具
│   ├── edit.py            # 文件编辑工具
│   ├── read.py            # 文件读取工具
│   ├── bash.py            # Shell 命令工具
│   └── grep.py            # 代码搜索工具
├── pyproject.toml          # 项目配置
└── llm_config.py          # LLM 配置文件
```

---

## 核心模块说明

### 1. CLI 模块 (`cli/`)

**入口点**: `cli/main.py`

CLI 模块提供命令行接口，用户可以通过命令与 OpenCode 交互。

#### 主要功能：
- 处理用户输入和提示词
- 管理会话状态
- 调用 Agent 执行任务

#### 使用示例：
```bash
# 通过 pip 安装后使用
opencode run "写一个 hello world 程序"

# 或直接运行模块
python -m cli.main run "写一个 hello world 程序"
```

---

### 2. Agent 模块 (`agent/`)

**核心文件**: `agent/agent.py`

Agent 是系统的核心，负责：
- 接收用户提示词
- 调用 LLM 生成响应
- 解析和执行工具调用
- 管理任务执行流程

#### Agent 工作流程：
```
用户提示 → Agent → LLM → 工具调用 → 执行结果 → 最终输出
```

#### 主要方法：
- `run(prompt)`: 运行提示词并返回结果
- `execute_tool(tool_name, args)`: 执行指定工具
- `handle_response(response)`: 处理 LLM 响应

---

### 3. 工具模块 (`tool/`)

工具模块提供多种功能，使 Agent 能够与文件系统和其他系统资源交互。

#### 内置工具：

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `write` | 写入文件 | `filePath`, `content` |
| `edit` | 编辑文件 | `filePath`, `oldString`, `newString`, `replaceAll` |
| `read` | 读取文件 | `filePath` |
| `bash` | 执行 Shell 命令 | `command` |
| `grep` | 搜索代码 | `pattern`, `path` |

#### write 工具示例：
```python
from tool.write import WriteTool, WriteToolConfig

tool = WriteTool(WriteToolConfig(working_dir=Path("/path/to/project")))
result = await tool.execute(ctx, filePath="/path/to/file.py", content="print('hello')")
```

#### edit 工具示例：
```python
from tool.edit import EditTool, EditToolConfig

tool = EditTool(EditToolConfig(working_dir=Path("/path/to/project")))
result = await tool.execute(
    ctx,
    filePath="/path/to/file.py",
    oldString="old code",
    newString="new code"
)
```

---

### 4. 会话管理 (`session/`)

**核心文件**: `session/session.py`, `session/prompt.py`

会话模块负责：
- 管理对话历史
- 处理提示词模板
- 维护上下文状态

#### 主要类：
- `SessionManager`: 管理会话状态和配置
- `PromptHandler`: 处理提示词生成和处理

---

### 5. 配置管理 (`config/`)

**核心文件**: `config/config.py`

配置模块负责：
- 加载项目配置
- 解析环境变量
- 管理 LLM 设置

#### 配置项：
- `model`: LLM 模型名称
- `api_key`: API 密钥
- `base_url`: API 基础 URL
- `temperature`: 温度参数
- `max_tokens`: 最大 token 数

---

### 6. LLM 接口 (`llm/`)

**核心文件**: `llm/llm.py`

LLM 模块提供：
- 统一的 LLM 调用接口
- 支持多个提供商（Anthropic, OpenAI 等）
- 流式响应处理

---

## 使用方法

### 方法一：通过 CLI 使用

1. **安装项目**：
```bash
cd /Users/maomin/programs/vscode/opencode_py
pip install -e .
```

2. **配置 LLM**：
编辑 `llm_config.py` 或设置环境变量：
```bash
export ANTHROPIC_API_KEY="your-api-key"
export OPENAI_API_KEY="your-api-key"
```

3. **运行命令**：
```bash
opencode run "写一个 Python hello world 程序"
```

---

### 方法二：通过 Python API 使用

```python
import sys
sys.path.insert(0, '/Users/maomin/programs/vscode/opencode_py')

from agent.agent import Agent
from config.config import get_config
from session.session import SessionManager

# 获取配置
config = get_config()

# 创建会话管理器
session_manager = SessionManager(config=config)

# 创建 Agent
agent = Agent(config=config, session_manager=session_manager)

# 运行提示词
result = agent.run("写一个 Python hello world 程序")
print(result)
```

---

### 方法三：直接调用工具

```python
from pathlib import Path
from tool.write import WriteTool, WriteToolConfig

# 配置工具
config = WriteToolConfig(working_dir=Path("/output/dir"))
tool = WriteTool(config)

# 执行写入
result = await tool.execute(
    ctx,
    filePath="/output/dir/hello.py",
    content="print('Hello, World!')"
)
```

---

## 配置文件说明

### llm_config.py

```python
LLM_CONFIG = {
    "model": "claude-3-sonnet",
    "api_key": "your-api-key",
    "base_url": "https://api.anthropic.com",
    "temperature": 0.7,
    "max_tokens": 4096,
}
```

### 环境变量

| 变量名 | 说明 |
|--------|------|
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 |
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `LLM_MODEL` | 默认模型名称 |
| `LLM_BASE_URL` | API 基础 URL |

---

## 工具调用流程

1. **用户输入提示词**
2. **Agent 调用 LLM** 生成响应
3. **LLM 返回工具调用请求**
4. **Agent 解析并执行工具**
5. **工具返回执行结果**
6. **Agent 将结果反馈给 LLM**
7. **LLM 生成最终响应**

---

## 扩展开发

### 创建自定义工具

```python
from tool.tool import BaseTool, ToolDefinition, ToolParameter, ToolResult, ToolStatus, ToolContext

class MyCustomTool(BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="my_tool",
            description="My custom tool description",
            parameters=[
                ToolParameter(
                    name="param1",
                    type="string",
                    description="Parameter description",
                    required=True,
                ),
            ],
        )
    
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        param1 = kwargs.get("param1")
        # 实现工具逻辑
        return ToolResult(
            tool_name="my_tool",
            status=ToolStatus.SUCCESS,
            content="Result content",
        )
```

---

## 常见问题

### Q: 如何配置 API 密钥？
A: 可以通过以下方式配置：
- 编辑 `llm_config.py` 文件
- 设置环境变量 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY`

### Q: 如何添加新工具？
A: 继承 `BaseTool` 类，实现 `definition` 属性和 `execute` 方法。

### Q: 如何调试工具执行？
A: 在工具执行前后添加日志输出，或使用 Python 调试器。

---

## 最佳实践

1. **始终使用绝对路径**：工具操作文件时使用绝对路径
2. **处理异常情况**：工具执行时应捕获并处理异常
3. **提供清晰的错误信息**：帮助用户理解问题
4. **记录执行日志**：便于调试和追踪

---

## 版本信息

- **项目名称**: OpenCode Py
- **版本**: 1.0.0
- **Python 要求**: 3.10+
- **许可证**: MIT

---

*本指南最后更新：2026 年 2 月 27 日*
