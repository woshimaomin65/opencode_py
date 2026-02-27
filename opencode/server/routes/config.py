"""
Configuration routes for OpenCode server.

Provides API endpoints for configuration management:
- Get and update configuration
- List configured providers
"""

import logging
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException

from ..config import Config, get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])


# GET /config/ - Get configuration
@router.get("/")
async def get_configuration():
    """
    Get configuration.
    
    Retrieve the current OpenCode configuration settings and preferences.
    """
    try:
        config = await get_config()
        return config.model_dump() if hasattr(config, 'model_dump') else config
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# PATCH /config/ - Update configuration
@router.patch("/")
async def update_configuration(body: Dict[str, Any]):
    """
    Update configuration.
    
    Update OpenCode configuration settings and preferences.
    """
    try:
        config = await Config.update(body)
        return config.model_dump() if hasattr(config, 'model_dump') else config
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /config/providers - List config providers
@router.get("/providers")
async def list_config_providers():
    """
    List config providers.
    
    Get a list of all configured AI providers and their default models.
    """
    try:
        from ..provider import ProviderRegistry, get_provider
        
        providers_dict = await ProviderRegistry.list_providers()
        
        # Get default model for each provider
        defaults = {}
        for provider_id, provider_info in providers_dict.items():
            if hasattr(provider_info, 'models') and provider_info.models:
                models = list(provider_info.models.values()) if isinstance(provider_info.models, dict) else provider_info.models
                if models:
                    # Sort and get first model as default
                    sorted_models = sorted(models, key=lambda m: m.id if hasattr(m, 'id') else str(m))
                    defaults[provider_id] = sorted_models[0].id if hasattr(sorted_models[0], 'id') else str(sorted_models[0])
        
        # Convert to list format
        providers_list = []
        for provider_id, provider_info in providers_dict.items():
            if hasattr(provider_info, 'model_dump'):
                providers_list.append(provider_info.model_dump())
            else:
                providers_list.append(provider_info)
        
        return {
            "providers": providers_list,
            "default": defaults,
        }
    except Exception as e:
        logger.error(f"Error listing config providers: {e}")
        raise HTTPException(status_code=400, detail=str(e))
