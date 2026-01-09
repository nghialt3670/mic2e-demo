from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any

from app.schemas.chat2edit_schemas import (
    Chat2EditGenerateRequestModel,
    Chat2EditGenerateResponseModel,
)


class Chat2EditService(ABC):
    @abstractmethod
    async def generate(
        self, request: Chat2EditGenerateRequestModel
    ) -> Chat2EditGenerateResponseModel:
        pass
    
    @abstractmethod
    async def generate_with_progress(
        self, request: Chat2EditGenerateRequestModel
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate response with progress events streamed via async generator."""
        pass