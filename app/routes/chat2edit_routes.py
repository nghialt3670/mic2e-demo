import asyncio
import json
import logging

from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies.chat2edit_dependencies import get_chat2edit_service
from app.schemas.chat2edit_schemas import (
    Chat2EditGenerateRequestModel,
    Chat2EditGenerateResponseModel,
)
from app.schemas.common_schemas import ResponseModel
from app.services.chat2edit_service import Chat2EditService

router = APIRouter(prefix="/chat2edit", tags=["chat2edit"])
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=ResponseModel[Chat2EditGenerateResponseModel])
async def generate(
    request: Chat2EditGenerateRequestModel,
    service: Chat2EditService = Depends(get_chat2edit_service),
):
    return ResponseModel(data=await service.generate(request))


@router.post("/generate/stream")
async def generate_stream(
    request: Chat2EditGenerateRequestModel,
    service: Chat2EditService = Depends(get_chat2edit_service),
):
    """
    Generate response with Server-Sent Events (SSE) for progress streaming.
    Uses a bounded queue to stream progress events to the client.
    """
    
    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from the service's progress queue."""
        try:
            async for event in service.generate_with_progress(request):
                # Format as SSE: data: {json}\n\n
                yield f"data: {json.dumps(event)}\n\n"
                
                # If complete or error, close the stream
                if event.get("type") in ["complete", "error"]:
                    break
                    
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            error_event = {
                "type": "error",
                "message": str(e),
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
