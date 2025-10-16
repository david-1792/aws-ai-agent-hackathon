import logging

from sana.core.context import SanaContext
from sana.core.models import Actor
from sana.agent import Sana

logger = logging.getLogger(__name__)

async def agent_task(
    message: str,
    session_id: str,
    actor: Actor | None
) -> None:
    if not (queue := SanaContext.get_queue()):
        raise RuntimeError('No response queue found in context')
    
    if not (gateway_token := SanaContext.get_gateway_token()):
        raise RuntimeError('No gateway token found in context')

    try:
        if not (agent := SanaContext.get_agent()):
            logger.info(f'Initializing agent for session: {session_id} and actor: {actor}')

            agent = Sana(
                session_id=session_id,
                gateway_token=gateway_token,
                actor=actor
            )

            SanaContext.set_agent(agent)
        async for chunk in agent.stream(message):
            await queue.put(chunk)
    except Exception as e:
        logger.error(f'Agent execution failed: {e}')
        await queue.put(f'error: {e}')
    finally:
        await queue.finish()