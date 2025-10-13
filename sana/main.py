from asyncio import Task, create_task
import logging
import uuid

from pydantic import validate_call

from bedrock_agentcore import BedrockAgentCoreApp, RequestContext

from sana.core.task import agent_task
from sana.core.auth import get_gateway_token
from sana.core.context import SanaContext
from sana.core.queue import StreamingQueue
from sana.core.models import InvokePayload

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

@app.entrypoint
@validate_call
async def invoke(payload: InvokePayload, context: RequestContext):
    # Initialize context if needed
    if not SanaContext.get_gateway_token():
        logger.info('Initializing gateway token context')
        SanaContext.set_gateway_token(get_gateway_token())
        
    if not (queue := SanaContext.get_queue()):
        logger.info('Initializing queue context')
        queue = StreamingQueue()
        SanaContext.set_queue(queue)

    # Set a default session identifier if not provided
    session_id: str = context.session_id or str(uuid.uuid4())

    task: Task = create_task(
        agent_task(
            message=payload.prompt,
            session_id=session_id,
            actor=payload.actor  
        )
    )

    async def stream_output():
        async for item in queue.stream():
            yield item
        await task
    
    return stream_output()

if __name__ == '__main__':
    app.run()