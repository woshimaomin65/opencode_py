"""
Provider routes for OpenCode server.

Provides API endpoints for AI provider management:
- List all available providers
- Get provider authentication methods
- Handle OAuth authorization and callback
"""

import logging
from typing import Dict, Any, List, Optional, Set

from fastapi import APIRouter, HTTPException, Path

from opencode.config import get_config
from opencode.provider import ProviderRegistry, get_provider
from opencode.provider.models import ModelsDev
from opencode.provider.auth import ProviderAuth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/provider", tags=["provider"])


class OAuthAuthorizeRequest(BaseModel):
    """Request body for OAuth authorization."""
    method: int


class OAuthCallbackRequest(BaseModel):
    """Request body for OAuth callback."""
    method: int
    code: Optional[str] = None


from pydantic import BaseModel


# GET /provider/ - List providers
@router.get("/")
async def list_providers():
    """
    List providers.
    
    Get a list of all available AI providers, including both available and connected ones.
    """
    try:
        config = await get_config()
        disabled = set(config.disabled_providers or [])
        enabled = set(config.enabled_providers) if config.enabled_providers else None
        
        all_providers = await ModelsDev.get()
        
        # Filter providers based on enabled/disabled settings
        filtered_providers = {}
        for key, value in all_providers.items():
            if (enabled is None or key in enabled) and key not in disabled:
                filtered_providers[key] = value
        
        # Get connected providers
        connected = await ProviderRegistry.list_providers()
        
        # Merge filtered and connected providers
        providers = {**filtered_providers, **connected}
        
        # Get default model for each provider
        defaults = {}
        for provider_id, provider_info in providers.items():
            if hasattr(provider_info, 'models') and provider_info.models:
                models = list(provider_info.models.values()) if isinstance(provider_info.models, dict) else provider_info.models
                if models:
                    sorted_models = sorted(models, key=lambda m: m.id if hasattr(m, 'id') else str(m))
                    defaults[provider_id] = sorted_models[0].id if hasattr(sorted_models[0], 'id') else str(sorted_models[0])
        
        return {
            "all": list(providers.values()),
            "default": defaults,
            "connected": list(connected.keys()),
        }
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /provider/auth - Get provider auth methods
@router.get("/auth")
async def get_provider_auth_methods():
    """
    Get provider auth methods.
    
    Retrieve available authentication methods for all AI providers.
    """
    try:
        methods = await ProviderAuth.methods()
        return methods
    except Exception as e:
        logger.error(f"Error getting provider auth methods: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /provider/{providerID}/oauth/authorize - OAuth authorize
@router.post("/{provider_id}/oauth/authorize")
async def oauth_authorize(
    provider_id: str = Path(..., description="Provider ID"),
    body: OAuthAuthorizeRequest = None,
):
    """
    OAuth authorize.
    
    Initiate OAuth authorization for a specific AI provider to get an authorization URL.
    """
    try:
        result = await ProviderAuth.authorize(
            provider_id=provider_id,
            method=body.method,
        )
        return result.model_dump() if result and hasattr(result, 'model_dump') else result
    except Exception as e:
        logger.error(f"Error authorizing OAuth for provider {provider_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /provider/{providerID}/oauth/callback - OAuth callback
@router.post("/{provider_id}/oauth/callback")
async def oauth_callback(
    provider_id: str = Path(..., description="Provider ID"),
    body: OAuthCallbackRequest = None,
):
    """
    OAuth callback.
    
    Handle the OAuth callback from a provider after user authorization.
    """
    try:
        await ProviderAuth.callback(
            provider_id=provider_id,
            method=body.method,
            code=body.code,
        )
        return True
    except Exception as e:
        logger.error(f"Error handling OAuth callback for provider {provider_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
