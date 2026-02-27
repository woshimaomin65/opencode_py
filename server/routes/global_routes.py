"""
Global routes for OpenCode server.

Provides API endpoints for global server operations:
- Health check
- Global event streaming (SSE)
- Global configuration
- Server disposal
"""

import logging
import asyncio
import json
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from global_path import get_data_path
from bus import Bus, BusEvent
from installation import VERSION
from config import Config, get_config, update_global_config
from project import get_project_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/global", tags=["global"])


# Define global disposed event
GlobalDisposedEvent = BusEvent.define("global.disposed", type(None))


# GET /global/health - Get health
@router.get("/health")
async def get_health():
    """
    Get health.
    
    Get health information about the OpenCode server.
    """
    try:
        return {"healthy": True, "version": VERSION}
    except Exception as e:
        logger.error(f"Error getting health: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /global/event - Get global events (SSE)
@router.get("/event")
async def get_global_events():
    """
    Get global events.
    
    Subscribe to global events from the OpenCode system using server-sent events.
    """
    logger.info("Global event client connected")
    
    async def event_generator():
        # Send initial connection event
        yield f"data: {json.dumps({'payload': {'type': 'server.connected', 'properties': {}}})}\n\n"
        
        # Event handler
        async def handler(event: Dict[str, Any]):
            yield f"data: {json.dumps(event)}\n\n"
        
        # Subscribe to events
        subscription = Bus.subscribe_all(lambda e: asyncio.create_task(handle_event(e)))
        
        async def handle_event(event: Dict[str, Any]):
            # This will be called from the subscription
            pass
        
        # Send heartbeat every 30 seconds to prevent timeout
        heartbeat_interval = 30
        
        try:
            while True:
                await asyncio.sleep(heartbeat_interval)
                yield f"data: {json.dumps({'payload': {'type': 'server.heartbeat', 'properties': {}}})}\n\n"
        except asyncio.CancelledError:
            logger.info("Global event client disconnected")
            # Cleanup subscription
            Bus.clear()
            raise
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# GET /global/config - Get global configuration
@router.get("/config")
async def get_global_config():
    """
    Get global configuration.
    
    Retrieve the current global OpenCode configuration settings and preferences.
    """
    try:
        config = await Config.get_global()
        return config.model_dump() if hasattr(config, 'model_dump') else config
    except Exception as e:
        logger.error(f"Error getting global configuration: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# PATCH /global/config - Update global configuration
@router.patch("/config")
async def update_global_configuration(body: Dict[str, Any]):
    """
    Update global configuration.
    
    Update global OpenCode configuration settings and preferences.
    """
    try:
        config = await update_global_config(body)
        return config.model_dump() if hasattr(config, 'model_dump') else config
    except Exception as e:
        logger.error(f"Error updating global configuration: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /global/dispose - Dispose instance
@router.post("/dispose")
async def dispose_instance():
    """
    Dispose instance.
    
    Clean up and dispose all OpenCode instances, releasing all resources.
    """
    try:
        project_manager = get_project_manager()
        await project_manager.dispose_all()
        
        # Emit global disposed event
        Bus.publish(
            GlobalDisposedEvent,
            {
                "directory": "global",
                "payload": {
                    "type": GlobalDisposedEvent.type,
                    "properties": {},
                },
            }
        )
        
        return True
    except Exception as e:
        logger.error(f"Error disposing instances: {e}")
        raise HTTPException(status_code=400, detail=str(e))
