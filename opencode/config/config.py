"""
Configuration module for OpenCode.

Handles loading and merging configuration from multiple sources:
- Remote configuration
- Global configuration (~/.opencode.json)
- Project configuration (.opencode.json)
- Directory-specific configurations
- Managed configuration
- LLM configuration (llm_config.py)
"""

import json
import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel, Field

# Import LLM configuration
from ..llm_config import get_llm_config, LLMConfigManager


@dataclass
class ProviderConfig:
    """Configuration for an AI provider."""
    name: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    options: dict = field(default_factory=dict)


@dataclass
class ToolConfig:
    """Configuration for a tool."""
    name: str
    enabled: bool = True
    options: dict = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    model: str
    provider: Optional[str] = None
    tools: list[str] = field(default_factory=list)
    system_prompt: Optional[str] = None


@dataclass
class PluginConfig:
    """Configuration for a plugin."""
    name: str
    enabled: bool = True
    options: dict = field(default_factory=dict)


class ConfigData(BaseModel):
    """Pydantic model for configuration validation."""
    providers: dict[str, dict] = Field(default_factory=dict)
    agents: dict[str, dict] = Field(default_factory=dict)
    tools: dict[str, dict] = Field(default_factory=dict)
    plugins: dict[str, dict] = Field(default_factory=dict)
    rules: list[str] = Field(default_factory=list)
    ignore: list[str] = Field(default_factory=list)
    mcp: dict[str, Any] = Field(default_factory=dict)
    acp: dict[str, Any] = Field(default_factory=dict)
    custom_instructions: Optional[str] = None
    

class Config:
    """
    Configuration manager for OpenCode.
    
    Loads and merges configuration from multiple sources with priority:
    1. Remote configuration (lowest priority)
    2. Global configuration (~/.opencode.json)
    3. Project configuration (.opencode.json in project root)
    4. Directory configurations (.opencode/ directories)
    5. Managed configuration (highest priority)
    6. LLM configuration (from llm_config.py)
    """
    
    GLOBAL_CONFIG_PATH = Path.home() / ".opencode.json"
    PROJECT_CONFIG_NAME = ".opencode.json"
    DIRECTORY_CONFIG_NAME = ".opencode"
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self._config_data: ConfigData = ConfigData()
        self._loaded_paths: list[Path] = []
        self._llm_config: Optional[LLMConfigManager] = None
        
    def load(self) -> "Config":
        """Load configuration from all sources."""
        # Load LLM configuration first
        self._load_llm_config()
        
        # Load in order of priority (lowest to highest)
        self._load_remote_config()
        self._load_global_config()
        self._load_project_config()
        self._load_directory_configs()
        self._load_managed_config()
        
        return self
    
    def _load_llm_config(self) -> None:
        """Load LLM configuration from llm_config.py."""
        try:
            self._llm_config = get_llm_config()
            # Merge LLM providers into config
            for provider_name, provider_config in self._llm_config.config.providers.items():
                if provider_name not in self._config_data.providers:
                    self._config_data.providers[provider_name] = {
                        "name": provider_name,
                        "model": provider_config.get("default_model"),
                        "base_url": provider_config.get("base_url"),
                    }
                    # Add API key if available (will be redacted in output)
                    api_key = self._llm_config.get_api_key(provider_name)
                    if api_key:
                        self._config_data.providers[provider_name]["api_key"] = api_key
        except Exception as e:
            print(f"Warning: Failed to load LLM config: {e}")
    
    def _load_remote_config(self) -> None:
        """Load remote configuration (if configured)."""
        # TODO: Implement remote config loading
        pass
    
    def _load_global_config(self) -> None:
        """Load global configuration from ~/.opencode.json."""
        if self.GLOBAL_CONFIG_PATH.exists():
            try:
                with open(self.GLOBAL_CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                self._merge_config(data)
                self._loaded_paths.append(self.GLOBAL_CONFIG_PATH)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load global config: {e}")
    
    def _load_project_config(self) -> None:
        """Load project configuration from .opencode.json."""
        project_config_path = self.project_root / self.PROJECT_CONFIG_NAME
        if project_config_path.exists():
            try:
                with open(project_config_path, 'r') as f:
                    data = json.load(f)
                self._merge_config(data)
                self._loaded_paths.append(project_config_path)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load project config: {e}")
    
    def _load_directory_configs(self) -> None:
        """Load directory-specific configurations."""
        # Walk through directories and load .opencode/ configs
        config_dir = self.project_root / self.DIRECTORY_CONFIG_NAME
        if config_dir.exists() and config_dir.is_dir():
            for config_file in config_dir.glob("*.json"):
                try:
                    with open(config_file, 'r') as f:
                        data = json.load(f)
                    self._merge_config(data)
                    self._loaded_paths.append(config_file)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Failed to load directory config {config_file}: {e}")
    
    def _load_managed_config(self) -> None:
        """Load managed configuration (highest priority)."""
        # TODO: Implement managed config loading
        pass
    
    def _merge_config(self, data: dict) -> None:
        """Merge configuration data with existing config."""
        # Merge providers
        if "providers" in data:
            self._config_data.providers.update(data["providers"])
        
        # Merge agents
        if "agents" in data:
            self._config_data.agents.update(data["agents"])
        
        # Merge tools
        if "tools" in data:
            self._config_data.tools.update(data["tools"])
        
        # Merge plugins
        if "plugins" in data:
            self._config_data.plugins.update(data["plugins"])
        
        # Merge rules
        if "rules" in data:
            self._config_data.rules.extend(data["rules"])
        
        # Merge ignore patterns
        if "ignore" in data:
            self._config_data.ignore.extend(data["ignore"])
        
        # Merge MCP config
        if "mcp" in data:
            self._config_data.mcp.update(data["mcp"])
        
        # Merge ACP config
        if "acp" in data:
            self._config_data.acp.update(data["acp"])
        
        # Override custom instructions (last one wins)
        if "custom_instructions" in data:
            self._config_data.custom_instructions = data["custom_instructions"]
    
    def get_provider(self, name: str) -> Optional[dict]:
        """Get provider configuration by name."""
        return self._config_data.providers.get(name)
    
    def get_agent(self, name: str) -> Optional[dict]:
        """Get agent configuration by name."""
        return self._config_data.agents.get(name)
    
    def get_tool(self, name: str) -> Optional[dict]:
        """Get tool configuration by name."""
        return self._config_data.tools.get(name)
    
    def get_plugin(self, name: str) -> Optional[dict]:
        """Get plugin configuration by name."""
        return self._config_data.plugins.get(name)
    
    @property
    def providers(self) -> dict[str, dict]:
        """Get all provider configurations."""
        return self._config_data.providers
    
    @property
    def agents(self) -> dict[str, dict]:
        """Get all agent configurations."""
        return self._config_data.agents
    
    @property
    def tools(self) -> dict[str, dict]:
        """Get all tool configurations."""
        return self._config_data.tools
    
    @property
    def plugins(self) -> dict[str, dict]:
        """Get all plugin configurations."""
        return self._config_data.plugins
    
    @property
    def rules(self) -> list[str]:
        """Get all rules."""
        return self._config_data.rules
    
    @property
    def ignore_patterns(self) -> list[str]:
        """Get all ignore patterns."""
        return self._config_data.ignore
    
    @property
    def custom_instructions(self) -> Optional[str]:
        """Get custom instructions."""
        return self._config_data.custom_instructions
    
    @property
    def mcp_config(self) -> dict:
        """Get MCP configuration."""
        return self._config_data.mcp
    
    @property
    def acp_config(self) -> dict:
        """Get ACP configuration."""
        return self._config_data.acp
    
    @property
    def llm_config(self) -> Optional[LLMConfigManager]:
        """Get LLM configuration manager."""
        return self._llm_config
    
    def get_llm_api_key(self, provider: str) -> Optional[str]:
        """Get API key for an LLM provider."""
        if self._llm_config:
            return self._llm_config.get_api_key(provider)
        return None
    
    def get_llm_base_url(self, provider: str) -> Optional[str]:
        """Get base URL for an LLM provider."""
        if self._llm_config:
            return self._llm_config.get_base_url(provider)
        return None
    
    def get_llm_model(self, provider: str) -> Optional[str]:
        """Get default model for an LLM provider."""
        if self._llm_config:
            return self._llm_config.get_model(provider)
        return None
    
    def get_default_llm_provider(self) -> str:
        """Get default LLM provider."""
        if self._llm_config:
            return self._llm_config.get_default_provider()
        return "anthropic"
    
    def get_default_llm_model(self) -> str:
        """Get default LLM model."""
        if self._llm_config:
            return self._llm_config.get_default_model()
        return "claude-sonnet-4-20250514"
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return self._config_data.model_dump()
    
    def save(self, path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        save_path = path or (self.project_root / self.PROJECT_CONFIG_NAME)
        with open(save_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def __repr__(self) -> str:
        return f"Config(project_root={self.project_root}, loaded_paths={len(self._loaded_paths)})"
