"""
LLM Configuration Module for OpenCode Python.

Provides unified configuration for LLM providers including:
- Anthropic Claude
- OpenAI GPT
- Google Gemini
- Azure OpenAI
- Local models (Ollama, LM Studio, etc.)

Configuration is loaded from:
1. Default settings (hardcoded)
2. Environment variables
3. Local config file (local_llm_config.json) - NOT committed to git
"""

import json
import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class LLMProviderConfig:
    """Configuration for an LLM provider."""
    name: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    timeout: int = 600
    max_retries: int = 3
    options: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LLMConfig:
    """Main LLM configuration container."""
    default_provider: str = "anthropic"
    default_model: str = "claude-sonnet-4-20250514"
    providers: dict[str, dict] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        result = {
            "default_provider": self.default_provider,
            "default_model": self.default_model,
            "providers": self.providers
        }
        return result


class LLMConfigManager:
    """
    Manages LLM configuration with support for multiple providers.
    
    Usage:
        config = LLMConfigManager()
        config.load()
        
        # Get Anthropic client
        client = config.get_anthropic_client()
        
        # Get OpenAI client
        client = config.get_openai_client()
        
        # Get config for specific provider
        provider_config = config.get_provider("anthropic")
    """
    
    # Default configurations
    DEFAULT_PROVIDERS = {
        "anthropic": {
            "name": "anthropic",
            "base_url": "https://coding.dashscope.aliyuncs.com/apps/anthropic",
            "api_key_env": "ANTHROPIC_AUTH_TOKEN",
            "default_model": "qwen3.5-plus",
            "timeout": 600,
            "max_retries": 3,
        },
        "openai": {
            "name": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key_env": "OPENAI_API_KEY",
            "default_model": "gpt-4o",
            "timeout": 600,
            "max_retries": 3,
        },
        "google": {
            "name": "google",
            "base_url": None,  # Uses google.genai SDK directly
            "api_key_env": "GOOGLE_API_KEY",
            "default_model": "gemini-2.0-flash",
            "timeout": 600,
            "max_retries": 3,
        },
        "azure": {
            "name": "azure",
            "base_url": "https://{resource}.openai.azure.com",
            "api_key_env": "AZURE_OPENAI_API_KEY",
            "default_model": "gpt-4o",
            "timeout": 600,
            "max_retries": 3,
            "options": {
                "api_version": "2024-02-15-preview",
            }
        },
        "ollama": {
            "name": "ollama",
            "base_url": "http://localhost:11434/v1",
            "api_key_env": None,  # No API key needed for local Ollama
            "default_model": "llama3.1",
            "timeout": 600,
            "max_retries": 3,
        },
        "lmstudio": {
            "name": "lmstudio",
            "base_url": "http://localhost:1234/v1",
            "api_key_env": None,  # No API key needed for LM Studio
            "default_model": "local-model",
            "timeout": 600,
            "max_retries": 3,
        },
    }
    
    LOCAL_CONFIG_PATH = Path(__file__).parent.parent / "local_llm_config.json"
    
    def __init__(self):
        self.config = LLMConfig()
        self._loaded = False
    
    def load(self, config_path: Optional[Path] = None, use_env_override: bool = False) -> "LLMConfigManager":
        """
        Load LLM configuration from local file and environment variables.
        
        Priority (when use_env_override=False, default):
        1. Default settings (lowest)
        2. Local config file (highest)
        
        Priority (when use_env_override=True):
        1. Default settings (lowest)
        2. Environment variables
        3. Local config file (highest)
        
        Args:
            config_path: Path to config file (default: local_llm_config.json)
            use_env_override: If True, environment variables override config file
        """
        # Start with defaults
        self.config.providers = dict(self.DEFAULT_PROVIDERS)
        
        # Load from local config file if exists (higher priority)
        config_file = config_path or self.LOCAL_CONFIG_PATH
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    local_config = json.load(f)
                self._merge_config(local_config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load local LLM config: {e}")
        
        # Apply environment variable overrides only if requested
        if use_env_override:
            self._apply_env_overrides()
        
        self._loaded = True
        return self
    
    def _merge_config(self, data: dict) -> None:
        """Merge configuration from local config file."""
        # Store global api_key for fallback
        global_api_key = data.get("api_key")
        
        # Merge default provider
        if "default_provider" in data:
            self.config.default_provider = data["default_provider"]
        
        # Merge default model
        if "default_model" in data:
            self.config.default_model = data["default_model"]
        
        # Merge providers
        if "providers" in data:
            for provider_name, provider_config in data["providers"].items():
                if provider_name in self.config.providers:
                    # Update existing provider config
                    self.config.providers[provider_name].update(provider_config)
                else:
                    self.config.providers[provider_name] = provider_config
                
                # IMPORTANT: If api_key is directly in config, use it
                # This takes priority over api_key_env
                if "api_key" in provider_config and provider_config["api_key"]:
                    self.config.providers[provider_name]["api_key"] = provider_config["api_key"]
                elif "api_key_env" in provider_config and provider_config["api_key_env"]:
                    # Try to get from environment
                    env_key = os.environ.get(provider_config["api_key_env"])
                    if env_key:
                        self.config.providers[provider_name]["api_key"] = env_key
                    elif global_api_key:
                        # Fallback to global api_key if env var not set
                        self.config.providers[provider_name]["api_key"] = global_api_key
                elif global_api_key:
                    # Use global api_key if provider doesn't have api_key or api_key_env
                    self.config.providers[provider_name]["api_key"] = global_api_key
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        for provider_name, provider_config in self.config.providers.items():
            # Override API key from environment
            api_key_env = provider_config.get("api_key_env")
            if api_key_env:
                env_key = os.environ.get(api_key_env)
                if env_key:
                    provider_config["api_key"] = env_key
            
            # Override base URL from environment
            base_url_env = f"{provider_name.upper()}_BASE_URL"
            env_base_url = os.environ.get(base_url_env)
            if env_base_url:
                provider_config["base_url"] = env_base_url
    
    def get_provider(self, name: str) -> Optional[dict]:
        """Get configuration for a specific provider."""
        return self.config.providers.get(name)
    
    def get_default_provider(self) -> str:
        """Get the default provider name."""
        return self.config.default_provider
    
    def get_default_model(self) -> str:
        """Get the default model name."""
        return self.config.default_model
    
    def get_api_key(self, provider_name: str) -> Optional[str]:
        """Get API key for a provider."""
        provider = self.get_provider(provider_name)
        if not provider:
            return None
        
        # Return api_key directly from provider config
        return provider.get("api_key")
    
    def get_base_url(self, provider_name: str) -> Optional[str]:
        """Get base URL for a provider."""
        provider = self.get_provider(provider_name)
        if not provider:
            return None
        return provider.get("base_url")
    
    def get_model(self, provider_name: str) -> Optional[str]:
        """Get default model for a provider."""
        provider = self.get_provider(provider_name)
        if not provider:
            return None
        return provider.get("default_model")
    
    def create_provider_config(self, provider_name: str) -> Optional[LLMProviderConfig]:
        """Create a LLMProviderConfig object for a provider."""
        provider = self.get_provider(provider_name)
        if not provider:
            return None
        
        return LLMProviderConfig(
            name=provider_name,
            base_url=self.get_base_url(provider_name),
            api_key=self.get_api_key(provider_name),
            model=self.get_model(provider_name),
            timeout=provider.get("timeout", 600),
            max_retries=provider.get("max_retries", 3),
            options=provider.get("options", {})
        )
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary (without API keys for security)."""
        result = self.config.to_dict()
        # Remove API keys from output for security
        for provider in result.get("providers", {}).values():
            if "api_key" in provider:
                provider["api_key"] = "***REDACTED***"
        return result
    
    def save_local_config(self, config_path: Optional[Path] = None, include_api_keys: bool = False) -> None:
        """Save current configuration to local config file."""
        save_path = config_path or self.LOCAL_CONFIG_PATH
        
        config_data = self.config.to_dict()
        if not include_api_keys:
            # Remove API keys for security
            for provider in config_data.get("providers", {}).values():
                provider.pop("api_key", None)
        
        with open(save_path, 'w') as f:
            json.dump(config_data, f, indent=2)
    
    def __repr__(self) -> str:
        return f"LLMConfigManager(default_provider={self.config.default_provider}, providers={list(self.config.providers.keys())})"


# Global instance
_llm_config_manager: Optional[LLMConfigManager] = None


def get_llm_config() -> LLMConfigManager:
    """Get the global LLM configuration manager."""
    global _llm_config_manager
    if _llm_config_manager is None:
        _llm_config_manager = LLMConfigManager()
        _llm_config_manager.load()
    return _llm_config_manager


def reload_llm_config(config_path: Optional[Path] = None) -> LLMConfigManager:
    """Reload LLM configuration from file."""
    global _llm_config_manager
    _llm_config_manager = LLMConfigManager()
    _llm_config_manager.load(config_path)
    return _llm_config_manager


# Convenience functions
def get_provider_config(name: str) -> Optional[dict]:
    """Get configuration for a specific provider."""
    return get_llm_config().get_provider(name)


def get_api_key(provider_name: str) -> Optional[str]:
    """Get API key for a provider."""
    return get_llm_config().get_api_key(provider_name)


def get_base_url(provider_name: str) -> Optional[str]:
    """Get base URL for a provider."""
    return get_llm_config().get_base_url(provider_name)


def get_default_provider() -> str:
    """Get the default provider name."""
    return get_llm_config().get_default_provider()


def get_default_model() -> str:
    """Get the default model name."""
    return get_llm_config().get_default_model()
