# OpenCode Python - 项目迁移文档

## 项目概述

本文档描述了从 TypeScript/JavaScript 版本的 OpenCode 到 Python 版本的迁移过程。

## 原项目结构分析

### 原项目 (`/Users/maomin/programs/vscode/opencode`)

```
opencode/
├── packages/
│   ├── opencode/           # 核心 CLI 和 AI 功能
│   │   └── src/
│   │       ├── index.ts    # 入口文件
│   │       ├── cli/        # 命令行接口
│   │       ├── config/     # 配置管理
│   │       ├── provider/   # AI 提供者
│   │       ├── session/    # 会话管理
│   │       ├── agent/      # AI 代理
│   │       ├── tool/       # 工具系统
│   │       ├── permission/ # 权限管理
│   │       ├── mcp/        # MCP 协议
│   │       ├── acp/        # ACP 协议
│   │       ├── plugin/     # 插件系统
│   │       ├── auth/       # 认证
│   │       ├── project/    # 项目管理
│   │       └── util/       # 工具函数
│   ├── cli/                # CLI 包
│   ├── server/             # 服务器包
│   └── tauri/              # Tauri 桌面应用
├── bunfig.toml             # Bun 配置
├── package.json            # 项目依赖
└── tsconfig.json           # TypeScript 配置
```

### 原项目核心技术栈

- **运行时**: Bun (JavaScript/TypeScript)
- **AI SDK**: Vercel AI SDK
- **Web 框架**: Hono
- **ORM**: Drizzle ORM (SQLite)
- **前端**: SolidJS
- **桌面**: Tauri
- **协议**: MCP (Model Context Protocol), ACP

## Python 项目结构

### 新项目 (`/Users/maomin/programs/vscode/opencode_py`)

```
opencode_py/
├── pyproject.toml          # 项目配置 (PEP 621)
├── README.md               # 项目说明
├── MIGRATION.md            # 迁移文档 (本文件)
├── opencode/
│   ├── __init__.py         # 包入口
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py         # CLI 入口
│   ├── config/
│   │   ├── __init__.py
│   │   └── config.py       # 配置管理
│   ├── provider/
│   │   ├── __init__.py
│   │   └── provider.py     # AI 提供者
│   ├── session/
│   │   ├── __init__.py
│   │   └── session.py      # 会话管理
│   ├── agent/
│   │   ├── __init__.py
│   │   └── agent.py        # AI 代理
│   ├── tool/
│   │   ├── __init__.py
│   │   └── tool.py         # 工具系统
│   ├── permission/
│   │   ├── __init__.py
│   │   └── permission.py   # 权限管理
│   ├── mcp/
│   │   ├── __init__.py
│   │   └── mcp.py          # MCP 协议
│   ├── plugin/
│   ├── auth/
│   ├── project/
│   ├── util/
│   │   ├── __init__.py
│   │   └── util.py         # 工具函数
├── tests/
│   ├── __init__.py
│   └── test_modules.py     # 模块测试
└── data/                   # 数据目录
```

## 模块对照表

| TypeScript 模块 | Python 模块 | 状态 | 说明 |
|----------------|-------------|------|------|
| `src/config/config.ts` | `opencode/config/config.py` | ✅ 完成 | 配置管理 |
| `src/provider/provider.ts` | `opencode/provider/provider.py` | ✅ 完成 | AI 提供者 |
| `src/session/session.ts` | `opencode/session/session.py` | ✅ 完成 | 会话管理 |
| `src/agent/agent.ts` | `opencode/agent/agent.py` | ✅ 完成 | AI 代理 |
| `src/tool/tool.ts` | `opencode/tool/tool.py` | ✅ 完成 | 工具系统 |
| `src/permission/permission.ts` | `opencode/permission/permission.py` | ✅ 完成 | 权限管理 |
| `src/mcp/mcp.ts` | `opencode/mcp/mcp.py` | ✅ 完成 | MCP 协议 |
| `src/cli/` | `opencode/cli/` | ✅ 完成 | CLI 接口 |
| `src/util/` | `opencode/util/` | ✅ 完成 | 工具函数 |

## 技术栈对照

| 功能 | TypeScript | Python |
|------|------------|--------|
| 包管理 | bun/npm | pip/uv |
| 类型系统 | TypeScript | Python typing |
| 异步 | async/await | asyncio |
| AI SDK | Vercel AI SDK | 直接使用提供商 SDK |
| CLI | Commander.js | Click |
| 终端输出 | Custom | Rich |
| 配置格式 | JSON | JSON |
| 测试 | Vitest | pytest |

## 核心模块实现说明

### 1. 配置管理 (Config)

**功能**: 多层级配置加载和合并

**实现要点**:
- 支持远程配置、全局配置、项目配置、目录配置
- 使用 Pydantic 进行配置验证
- 配置合并遵循优先级规则

**Python 特性**:
- 使用 `dataclass` 进行数据结构定义
- 使用 `Pydantic BaseModel` 进行验证

### 2. AI 提供者 (Provider)

**功能**: 统一接口访问多个 AI 服务

**支持的提供者**:
- Anthropic (Claude)
- OpenAI (GPT)
- Google (Gemini)
- OpenAI 兼容接口

**实现要点**:
- 抽象基类定义统一接口
- 每个提供者实现具体 API 调用
- 支持流式和非流式响应

### 3. 工具系统 (Tool)

**功能**: AI 可调用的工具集合

**内置工具**:
- `read`: 读取文件
- `write`: 写入文件
- `edit`: 编辑文件 (SEARCH/REPLACE)
- `shell`: 执行 shell 命令
- `search`: 搜索文件内容

**实现要点**:
- 每个工具实现 `BaseTool` 抽象类
- 工具注册表管理所有可用工具
- 支持工具参数验证

### 4. 会话管理 (Session)

**功能**: 管理 AI 对话历史

**实现要点**:
- JSON 格式持久化存储
-  token 使用追踪
- 支持会话加载和继续

### 5. AI 代理 (Agent)

**功能**: 执行 AI 任务的主循环

**实现要点**:
- 工具调用循环
- 消息历史管理
- 流式响应支持
- 最大迭代次数限制

### 6. 权限管理 (Permission)

**功能**: 控制工具执行权限

**权限级别**:
- `ALLOW`: 自动允许
- `ASK`: 执行前询问
- `DENY`: 拒绝执行

**实现要点**:
- 基于规则的权限系统
- 支持模式匹配 (glob patterns)
- 支持临时权限和持久权限

## 使用示例

### 命令行使用

```bash
# 运行单个提示
opencode run "解释这段代码"

# 交互模式
opencode interactive

# 查看配置
opencode config

# 列出工具
opencode tools
```

### Python API 使用

```python
import asyncio
from opencode import Agent, Config, Session

async def main():
    # 创建代理
    agent = Agent.create(
        model="claude-sonnet-4-20250514",
        provider="anthropic",
        tools=["read", "write", "edit", "shell", "search"],
    )
    
    # 运行任务
    response = await agent.run("创建一个 Python 函数计算斐波那契数列")
    print(response)

asyncio.run(main())
```

## 测试验证

所有核心模块已通过测试验证：

```
============================================================
OpenCode Module Tests
============================================================
✓ Main imports
✓ Config module
✓ Provider module
✓ Tool module
✓ Session module
✓ Agent module
✓ Permission module
✓ MCP module
✓ Util module
============================================================
Results: 8 passed, 0 failed
============================================================
```

## 待完成功能

以下功能在 Python 版本中尚未完全实现：

1. **ACP 协议**: 代理通信协议 (需要进一步分析原实现)
2. **插件系统**: 完整的插件加载和管理
3. **LSP 集成**: 语言服务器协议支持
4. **Web 服务器**: Hono 服务器的 Python 等效实现
5. **Tauri 桌面应用**: Python 桌面应用 (可使用 PyQt 或 Tauri + Python)
6. **认证系统**: 完整的认证和授权

## 环境要求

- Python 3.11+
- 依赖包见 `pyproject.toml`

## 安装和运行

```bash
# 安装依赖
pip install -e .

# 运行测试
python tests/test_modules.py

# 运行 CLI
opencode --help
```

## 后续开发建议

1. **性能优化**: 考虑使用 `uv` 作为包管理器提高安装速度
2. **类型完善**: 添加完整的类型注解和 mypy 检查
3. **文档完善**: 添加 API 文档和使用示例
4. **测试覆盖**: 增加集成测试和端到端测试
5. **插件生态**: 建立插件开发指南和示例
