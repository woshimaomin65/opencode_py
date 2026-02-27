# OpenCode Python LLM 配置指南

## 📋 概述

本项目使用统一的 LLM 配置系统，支持多种 AI 提供者：
- Anthropic (Claude)
- OpenAI (GPT)
- Google (Gemini)
- Azure OpenAI
- Ollama (本地模型)
- LM Studio (本地模型)

## 🔧 配置文件

### 1. 本地配置文件（不上传到 Git）

创建 `local_llm_config.json` 文件在项目根目录：

```json
{
  "default_provider": "anthropic",
  "default_model": "claude-sonnet-4-20250514",
  "providers": {
    "anthropic": {
      "name": "anthropic",
      "base_url": "https://api.anthropic.com",
      "api_key_env": "ANTHROPIC_API_KEY",
      "default_model": "claude-sonnet-4-20250514",
      "timeout": 600,
      "max_retries": 3
    },
    "openai": {
      "name": "openai",
      "base_url": "https://api.openai.com/v1",
      "api_key_env": "OPENAI_API_KEY",
      "default_model": "gpt-4o",
      "timeout": 600,
      "max_retries": 3
    }
  }
}
```

**注意**: 此文件已添加到 `.gitignore`，不会被上传到 Git。

### 2. 环境变量

也可以通过环境变量配置：

```bash
# Anthropic
export ANTHROPIC_API_KEY=your_api_key_here

# OpenAI
export OPENAI_API_KEY=your_api_key_here

# Google
export GOOGLE_API_KEY=your_api_key_here

# Azure
export AZURE_OPENAI_API_KEY=your_api_key_here

# 自定义 Base URL
export ANTHROPIC_BASE_URL=https://api.anthropic.com
export OPENAI_BASE_URL=https://api.openai.com/v1
```

### 3. 直接代码配置

```python
from llm_config import LLMConfigManager

config = LLMConfigManager()
config.load()

# 获取提供者配置
anthropic_config = config.get_provider("anthropic")
api_key = config.get_api_key("anthropic")
base_url = config.get_base_url("anthropic")
model = config.get_model("anthropic")

# 获取默认值
default_provider = config.get_default_provider()
default_model = config.get_default_model()
```

## 📖 使用示例

### 使用 Provider 模块

```python
from provider import get_provider, get_default_provider

# 使用默认提供者（从配置读取）
provider = get_default_provider()

# 使用特定提供者
anthropic = get_provider("anthropic")
openai = get_provider("openai")

# 自定义配置
custom_provider = get_provider(
    provider_type="anthropic",
    model="claude-opus-4-20250514",
    api_key="your_custom_key",  # 可选，会覆盖配置
)
```

### 使用 Config 模块

```python
from config import Config

config = Config()
config.load()

# 获取 LLM 配置
llm_config = config.llm_config

# 获取 API 密钥
api_key = config.get_llm_api_key("anthropic")

# 获取默认提供者
default_provider = config.get_default_llm_provider()
default_model = config.get_default_llm_model()
```

### 在 Agent 中使用

```python
from agent import Agent
from config import Config

# 加载配置
config = Config()
config.load()

# 创建 Agent（会自动使用配置的提供者）
agent = Agent(
    project_root="/path/to/project",
    config=config,
)

# 运行 Agent
result = await agent.run("请帮我分析这个代码库")
```

## 🔐 安全建议

1. **不要硬编码 API 密钥**: 使用环境变量或本地配置文件
2. **本地配置文件不上传**: `local_llm_config.json` 已在 `.gitignore` 中
3. **使用 .env 文件**: 可以创建 `.env.local` 存储敏感信息
4. **定期轮换密钥**: 定期更新 API 密钥

## 📝 配置优先级

配置加载优先级（从高到低）：

1. **显式参数**: 代码中直接传入的参数
2. **本地配置文件**: `local_llm_config.json`
3. **环境变量**: 如 `ANTHROPIC_API_KEY`
4. **默认设置**: 内置的默认配置

## 🌐 提供者配置说明

### Anthropic

```json
{
  "anthropic": {
    "name": "anthropic",
    "base_url": "https://api.anthropic.com",
    "api_key_env": "ANTHROPIC_API_KEY",
    "default_model": "claude-sonnet-4-20250514",
    "timeout": 600,
    "max_retries": 3
  }
}
```

### OpenAI

```json
{
  "openai": {
    "name": "openai",
    "base_url": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY",
    "default_model": "gpt-4o",
    "timeout": 600,
    "max_retries": 3
  }
}
```

### Google

```json
{
  "google": {
    "name": "google",
    "base_url": null,
    "api_key_env": "GOOGLE_API_KEY",
    "default_model": "gemini-2.0-flash",
    "timeout": 600,
    "max_retries": 3
  }
}
```

### Ollama (本地)

```json
{
  "ollama": {
    "name": "ollama",
    "base_url": "http://localhost:11434/v1",
    "api_key_env": null,
    "default_model": "llama3.1",
    "timeout": 600,
    "max_retries": 3
  }
}
```

### LM Studio (本地)

```json
{
  "lmstudio": {
    "name": "lmstudio",
    "base_url": "http://localhost:1234/v1",
    "api_key_env": null,
    "default_model": "local-model",
    "timeout": 600,
    "max_retries": 3
  }
}
```

## 🔍 调试

### 查看当前配置

```python
from llm_config import get_llm_config

config = get_llm_config()
print(config.to_dict())
```

### 重新加载配置

```python
from llm_config import reload_llm_config

config = reload_llm_config()  # 重新加载本地配置文件
```

### 检查 API 密钥

```python
from llm_config import get_api_key

key = get_api_key("anthropic")
if key:
    print("API key is configured")
else:
    print("API key is missing!")
```

## 📚 相关文件

- `llm_config.py` - LLM 配置管理核心模块
- `local_llm_config.json` - 本地配置文件（不上传）
- `config/config.py` - 通用配置模块（集成 LLM 配置）
- `provider/provider.py` - 提供者模块（使用 LLM 配置）
- `.gitignore` - Git 忽略规则（包含本地配置）

## 🆘 故障排除

### 问题：API 密钥未找到

**解决方案**:
1. 检查环境变量是否设置：`echo $ANTHROPIC_API_KEY`
2. 检查 `local_llm_config.json` 是否存在
3. 检查 `api_key_env` 字段是否正确

### 问题：配置未生效

**解决方案**:
1. 确保调用 `config.load()` 加载配置
2. 检查配置文件 JSON 格式是否正确
3. 查看是否有语法错误

### 问题：模型名称错误

**解决方案**:
1. 检查 `default_model` 配置是否正确
2. 确认提供者支持该模型
3. 查看提供者文档确认模型名称

---

*最后更新：2024*
