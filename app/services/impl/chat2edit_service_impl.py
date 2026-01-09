import asyncio
from typing import Any, AsyncGenerator, Dict, Optional

from chat2edit import Chat2Edit, Chat2EditCallbacks
from chat2edit.models import ExecutionBlock, Message
from chat2edit.prompting.llms import GoogleLlm, Llm, OpenAILlm
from pydantic import TypeAdapter

from app.core.chat2edit.mic2e_context_provider import Mic2eContextProvider
from app.core.chat2edit.mic2e_context_strategy import CONTEXT_TYPE, Mic2eContextStrategy
from app.core.chat2edit.mic2e_prompting_strategy import Mic2ePromptingStrategy
from app.core.chat2edit.models import Image
from app.env import GOOGLE_API_KEY, OPENAI_API_KEY
from app.schemas.chat2edit_schemas import (
    AttachmentModel,
    Chat2EditGenerateRequestModel,
    Chat2EditGenerateResponseModel,
    LlmConfig,
    MessageModel,
)
from app.services.chat2edit_service import Chat2EditService
from app.utils.factories import create_uuid4


class Chat2EditServiceImpl(Chat2EditService):
    """Standalone service implementation - no storage backend needed."""
    
    def __init__(self):
        self._context_provider = Mic2eContextProvider()
        self._context_strategy = Mic2eContextStrategy()
        self._prompting_strategy = Mic2ePromptingStrategy()

    async def generate(
        self, request: Chat2EditGenerateRequestModel
    ) -> Chat2EditGenerateResponseModel:
        """Generate a Chat2Edit response without progress tracking."""

        chat2edit = Chat2Edit(
            llm=self._create_llm(request.llm_config),
            context_provider=self._context_provider,
            context_strategy=self._context_strategy,
            prompting_strategy=self._prompting_strategy,
            config=request.chat2edit_config,
        )

        message = self._create_request_message(request.message)
        context = request.context or {}

        response, cycle, updated_context = await chat2edit.generate(
            message, request.history, context
        )

        return Chat2EditGenerateResponseModel(
            cycle=cycle,
            message=(
                self._create_response_message(response) if response else None
            ),
            context=updated_context,
        )
    
    async def generate_with_progress(
        self, request: Chat2EditGenerateRequestModel
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate a Chat2Edit response with progress events streamed via async generator."""
        
        # Create a bounded queue for progress events
        progress_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        generation_task = None
        
        try:
            # Create callbacks that enqueue progress events
            callbacks = self._create_streaming_callbacks(progress_queue)
            
            chat2edit = Chat2Edit(
                llm=self._create_llm(request.llm_config),
                context_provider=self._context_provider,
                context_strategy=self._context_strategy,
                prompting_strategy=self._prompting_strategy,
                config=request.chat2edit_config,
                callbacks=callbacks,
            )

            message = self._create_request_message(request.message)
            context = request.context or {}
            
            # Start generation in background
            async def run_generation():
                try:
                    response, cycle, updated_context = await chat2edit.generate(
                        message, request.history, context
                    )
                    
                    result = Chat2EditGenerateResponseModel(
                        cycle=cycle,
                        message=(
                            self._create_response_message(response) if response else None
                        ),
                        context=updated_context,
                    )
                    
                    # Enqueue completion event
                    await progress_queue.put({
                        "type": "complete",
                        "message": "Generation completed successfully",
                        "data": result.model_dump(mode="json"),
                    })
                except Exception as e:
                    # Enqueue error event
                    await progress_queue.put({
                        "type": "error",
                        "message": str(e),
                    })
                finally:
                    # Signal end of stream
                    await progress_queue.put(None)
            
            generation_task = asyncio.create_task(run_generation())
            
            # Stream events from queue
            while True:
                event = await progress_queue.get()
                if event is None:  # End of stream
                    break
                yield event
                
        except Exception as e:
            yield {
                "type": "error",
                "message": str(e),
            }
        finally:
            if generation_task and not generation_task.done():
                generation_task.cancel()

    def _create_llm(self, config: LlmConfig) -> Llm:
        if config.provider == "openai":
            llm = OpenAILlm(config.model, **config.params)
            llm.set_api_key(config.api_key or OPENAI_API_KEY)
            return llm
        elif config.provider == "google":
            llm = GoogleLlm(config.model, **config.params)
            llm.set_api_key(config.api_key or GOOGLE_API_KEY)
            return llm
        else:
            raise ValueError(f"Invalid LLM provider: {config.provider}")

    def _create_request_message(self, message: MessageModel) -> Message:
        """Convert MessageModel with inline content to Chat2Edit Message."""
        attachments = [
            TypeAdapter(Image).validate_python(att.content)
            for att in message.attachments
        ]
        return Message(text=message.text, attachments=attachments)

    def _create_response_message(self, message: Message) -> MessageModel:
        """Convert Chat2Edit Message to MessageModel with inline content."""
        attachments = [
            AttachmentModel(
                filename=f"{create_uuid4()}.fig.json",
                content=image.model_dump()
            )
            for image in message.attachments
        ]
        return MessageModel(text=message.text, attachments=attachments)

    def _create_streaming_callbacks(self, progress_queue: asyncio.Queue) -> Chat2EditCallbacks:
        """Create callbacks that enqueue progress events for SSE streaming."""

        def _enqueue_progress(event_type: str, message: Optional[str] = None, data: Optional[Any] = None):
            """Enqueue progress event to be streamed to client."""
            try:
                # Use put_nowait to avoid blocking the callback
                progress_queue.put_nowait({
                    "type": event_type,
                    "message": message,
                    "data": data,
                })
            except asyncio.QueueFull:
                print(f"Warning: Progress queue full, dropping {event_type} event")
            except Exception as e:
                print(f"Error enqueueing {event_type} progress: {e}")

        def on_request(message: Message) -> None:
            _enqueue_progress("request", message="Sending request to LLM...", data=message.model_dump())

        def on_prompt(message: Message) -> None:
            _enqueue_progress("prompt", message="Generating prompt...", data=message.model_dump())

        def on_answer(message: Message) -> None:
            _enqueue_progress("answer", message="Received answer from LLM...", data=message.model_dump())

        def on_extract(code: str) -> None:
            _enqueue_progress("extract", message="Extracting code...", data=code)

        def on_execute(block: ExecutionBlock) -> None:
            block_type = getattr(block, 'type', None) or getattr(block, 'block_type', None) or str(type(block).__name__)
            _enqueue_progress("execute", message=f"Executing: {block_type}", data=block.model_dump())

        return Chat2EditCallbacks(
            on_request=on_request,
            on_prompt=on_prompt,
            on_answer=on_answer,
            on_extract=on_extract,
            on_execute=on_execute,
        )
