"""
Provider module for OpenCode.

Handles AI provider integration including:
- Anthropic (Claude)
- OpenAI (GPT)
- Google (Gemini)
- AWS Bedrock
- Groq
- And other providers via OpenAI-compatible API

Configuration is loaded from llm_config.py which supports:
- Default settings
- Environment variables
- Local config file (local_llm_config.json)
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Optional, AsyncIterator
from dataclasses import dataclass
from enum import Enum

# Import LLM configuration
from ..llm_config import get_llm_config, LLMConfigManager


class ProviderType(Enum):
    """Supported provider types."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    AWS_BEDROCK = "aws-bedrock"
    GROQ = "groq"
    OPENAI_COMPATIBLE = "openai-compatible"
    OLLAMA = "ollama"


@dataclass
class Message:
    """A message in a conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    images: Optional[list[str]] = None  # Base64 encoded images


@dataclass
class ToolCall:
    """A tool call from the model."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result from a tool execution."""
    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class Response:
    """Response from a provider."""
    content: str
    tool_calls: list[ToolCall] = None
    model: str = ""
    usage: dict[str, int] = None
    
    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []
        if self.usage is None:
            self.usage = {}


class BaseProvider(ABC):
    """Abstract base class for all providers."""
    
    _llm_config: Optional[LLMConfigManager] = None
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        options: Optional[dict] = None,
        provider_name: str = "anthropic",
    ):
        self.provider_name = provider_name
        self._init_llm_config()
        
        # Use config values if not provided
        self.model = model or self._get_config_model(provider_name)
        self.api_key = api_key or self._get_config_api_key(provider_name)
        self.base_url = base_url or self._get_config_base_url(provider_name)
        self.options = options or self._get_config_options(provider_name)
    
    def _init_llm_config(self) -> None:
        """Initialize LLM config if not already done."""
        if BaseProvider._llm_config is None:
            BaseProvider._llm_config = get_llm_config()
    
    def _get_config_model(self, provider_name: str) -> Optional[str]:
        """Get model from LLM config."""
        if self._llm_config:
            return self._llm_config.get_model(provider_name)
        return None
    
    def _get_config_api_key(self, provider_name: str) -> Optional[str]:
        """Get API key from LLM config."""
        if self._llm_config:
            return self._llm_config.get_api_key(provider_name)
        return None
    
    def _get_config_base_url(self, provider_name: str) -> Optional[str]:
        """Get base URL from LLM config."""
        if self._llm_config:
            return self._llm_config.get_base_url(provider_name)
        return None
    
    def _get_config_options(self, provider_name: str) -> dict:
        """Get options from LLM config."""
        if self._llm_config:
            provider = self._llm_config.get_provider(provider_name)
            if provider:
                return provider.get("options", {})
        return {}
    
    @abstractmethod
    def _get_default_api_key(self) -> Optional[str]:
        """Get the default API key from environment."""
        pass
    
    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> Response:
        """Complete a conversation."""
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream a completion."""
        pass


class AnthropicProvider(BaseProvider):
    """Anthropic Claude provider."""
    
    def _get_default_api_key(self) -> Optional[str]:
        return os.environ.get("ANTHROPIC_API_KEY")
    
    async def complete(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> Response:
        """Complete using Anthropic API."""
        try:
            from anthropic import AsyncAnthropic
            
            client = AsyncAnthropic(api_key=self.api_key, base_url=self.base_url)
            
            # Convert messages to Anthropic format
            system_message = None
            anthropic_messages = []
            
            for msg in messages:
                if msg.role == "system":
                    system_message = msg.content
                else:
                    anthropic_messages.append({
                        "role": msg.role,
                        "content": msg.content,
                    })
            
            # Build request
            request = {
                "model": self.model,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "messages": anthropic_messages,
            }
            
            if system_message:
                request["system"] = system_message
            
            if tools:
                request["tools"] = tools
            
            # Add optional parameters
            for key in ["temperature", "top_p", "top_k"]:
                if key in kwargs:
                    request[key] = kwargs[key]
            
            response = await client.messages.create(**request)
            
            # Parse response
            content = ""
            tool_calls = []
            
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    ))
            
            return Response(
                content=content,
                tool_calls=tool_calls,
                model=response.model,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )
            
        except ImportError:
            raise RuntimeError("Anthropic package not installed. Install with: pip install anthropic")
    
    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream using Anthropic API."""
        try:
            from anthropic import AsyncAnthropic
            
            client = AsyncAnthropic(api_key=self.api_key, base_url=self.base_url)
            
            # Convert messages
            system_message = None
            anthropic_messages = []
            
            for msg in messages:
                if msg.role == "system":
                    system_message = msg.content
                else:
                    anthropic_messages.append({
                        "role": msg.role,
                        "content": msg.content,
                    })
            
            # Build request
            request = {
                "model": self.model,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "messages": anthropic_messages,
            }
            
            if system_message:
                request["system"] = system_message
            
            if tools:
                request["tools"] = tools
            
            # Stream
            async with client.messages.stream(**request) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except ImportError:
            raise RuntimeError("Anthropic package not installed. Install with: pip install anthropic")


class OpenAIProvider(BaseProvider):
    """OpenAI GPT provider."""
    
    def _get_default_api_key(self) -> Optional[str]:
        return os.environ.get("OPENAI_API_KEY")
    
    async def complete(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> Response:
        """Complete using OpenAI API."""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            
            # Convert messages
            openai_messages = []
            for msg in messages:
                openai_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })
            
            # Build request
            request = {
                "model": self.model,
                "messages": openai_messages,
            }
            
            if tools:
                request["tools"] = [{"type": "function", "function": t} for t in tools]
                request["tool_choice"] = "auto"
            
            # Add optional parameters
            for key in ["temperature", "top_p", "max_tokens"]:
                if key in kwargs:
                    request[key] = kwargs[key]
            
            response = await client.chat.completions.create(**request)
            
            # Parse response
            choice = response.choices[0]
            content = choice.message.content or ""
            tool_calls = []
            
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    ))
            
            return Response(
                content=content,
                tool_calls=tool_calls,
                model=response.model,
                usage={
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                },
            )
            
        except ImportError:
            raise RuntimeError("OpenAI package not installed. Install with: pip install openai")
    
    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream using OpenAI API."""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            
            # Convert messages
            openai_messages = []
            for msg in messages:
                openai_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })
            
            # Build request
            request = {
                "model": self.model,
                "messages": openai_messages,
                "stream": True,
            }
            
            if tools:
                request["tools"] = [{"type": "function", "function": t} for t in tools]
            
            # Stream
            stream = await client.chat.completions.create(**request)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except ImportError:
            raise RuntimeError("OpenAI package not installed. Install with: pip install openai")


class GoogleProvider(BaseProvider):
    """Google Gemini provider."""
    
    def _get_default_api_key(self) -> Optional[str]:
        return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    
    async def complete(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> Response:
        """Complete using Google Generative AI API."""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key)
            
            # Create model
            model = genai.GenerativeModel(self.model)
            
            # Convert messages to Gemini format
            # Gemini uses a simpler conversation format
            chat = model.start_chat(history=[])
            
            # Get the last user message for generation
            last_user_message = None
            for msg in reversed(messages):
                if msg.role == "user":
                    last_user_message = msg.content
                    break
            
            if not last_user_message:
                raise ValueError("No user message found")
            
            response = await model.generate_content_async(
                last_user_message,
                generation_config=genai.types.GenerationConfig(
                    temperature=kwargs.get("temperature", 0.7),
                    max_output_tokens=kwargs.get("max_tokens", 4096),
                ),
            )
            
            return Response(
                content=response.text,
                model=self.model,
            )
            
        except ImportError:
            raise RuntimeError("Google Generative AI package not installed. Install with: pip install google-generativeai")
    
    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream using Google Generative AI API."""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)
            
            # Get the last user message
            last_user_message = None
            for msg in reversed(messages):
                if msg.role == "user":
                    last_user_message = msg.content
                    break
            
            if not last_user_message:
                raise ValueError("No user message found")
            
            response = model.generate_content(
                last_user_message,
                stream=True,
            )
            
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        except ImportError:
            raise RuntimeError("Google Generative AI package not installed. Install with: pip install google-generativeai")


class ProviderRegistry:
    """Registry for managing providers."""
    
    _providers: dict[str, type[BaseProvider]] = {
        ProviderType.ANTHROPIC.value: AnthropicProvider,
        ProviderType.OPENAI.value: OpenAIProvider,
        ProviderType.GOOGLE.value: GoogleProvider,
    }
    
    @classmethod
    def register(cls, name: str, provider_class: type[BaseProvider]) -> None:
        """Register a new provider type."""
        cls._providers[name] = provider_class
    
    @classmethod
    def get(cls, name: str) -> Optional[type[BaseProvider]]:
        """Get a provider class by name."""
        return cls._providers.get(name)
    
    @classmethod
    def create(
        cls,
        provider_type: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        options: Optional[dict] = None,
    ) -> BaseProvider:
        """Create a provider instance."""
        provider_class = cls.get(provider_type)
        if not provider_class:
            raise ValueError(f"Unknown provider type: {provider_type}")
        
        return provider_class(
            model=model,
            api_key=api_key,
            base_url=base_url,
            options=options,
        )


# Convenience function
def get_provider(
    provider_type: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    options: Optional[dict] = None,
) -> BaseProvider:
    """
    Get a provider instance with configuration from llm_config.
    
    Configuration priority:
    1. Explicit arguments (highest)
    2. LLM config (local_llm_config.json)
    3. Environment variables
    4. Default values (lowest)
    
    Args:
        provider_type: Provider type (anthropic, openai, google, etc.)
        model: Model name (optional, uses config default if not provided)
        api_key: API key (optional, uses config/env if not provided)
        base_url: Base URL (optional, uses config if not provided)
        options: Additional options (optional, merges with config)
    
    Returns:
        Provider instance configured with the specified settings
    """
    # Get LLM config for defaults
    llm_config = get_llm_config()
    
    # Use config values if not explicitly provided
    if model is None:
        model = llm_config.get_model(provider_type)
    
    if api_key is None:
        api_key = llm_config.get_api_key(provider_type)
    
    if base_url is None:
        base_url = llm_config.get_base_url(provider_type)
    
    # Merge options with config options
    config_options = llm_config.get_provider(provider_type)
    if config_options and "options" in config_options:
        merged_options = {**config_options["options"], **(options or {})}
        options = merged_options if options else config_options["options"]
    
    return ProviderRegistry.create(
        provider_type=provider_type,
        model=model,
        api_key=api_key,
        base_url=base_url,
        options=options,
    )


def get_default_provider() -> BaseProvider:
    """
    Get the default provider from llm_config.
    
    Returns:
        Default provider instance
    """
    llm_config = get_llm_config()
    default_type = llm_config.get_default_provider()
    return get_provider(default_type)


def list_available_providers() -> list[str]:
    """
    List all available providers from llm_config.
    
    Returns:
        List of provider names
    """
    llm_config = get_llm_config()
    return list(llm_config.config.providers.keys())
