from contextvars import ContextVar

from sana.agent import Sana
from sana.core.queue import StreamingQueue

class SanaContext:
    _gateway_token: str | None = None
    _google_token: str | None = None
    _queue: StreamingQueue | None = None
    _agent: Sana | None = None

    _gateway_token_ctx: ContextVar[str | None] = ContextVar('gateway_token', default=None)
    _google_token_ctx: ContextVar[str | None] = ContextVar('google_token', default=None)
    _queue_ctx: ContextVar[StreamingQueue | None] = ContextVar('queue', default=None)
    _agent_ctx: ContextVar[Sana | None] = ContextVar('agent', default=None)

    @classmethod
    def get_gateway_token(cls) -> str | None:
        if cls._gateway_token:
            return cls._gateway_token
        try:
            return cls._gateway_token_ctx.get()
        except LookupError:
            return None
        
    @classmethod
    def set_gateway_token(cls, token: str) -> None:
        cls._gateway_token = token
        cls._gateway_token_ctx.set(token)

    @classmethod
    def get_google_token(cls) -> str | None:
        if cls._google_token:
            return cls._google_token
        try:
            return cls._google_token_ctx.get()
        except LookupError:
            return None
        
    @classmethod
    def set_google_token(cls, token: str) -> None:
        cls._google_token = token
        cls._google_token_ctx.set(token)
        
    @classmethod
    def get_queue(cls) -> StreamingQueue | None:
        if cls._queue:
            return cls._queue
        try:
            return cls._queue_ctx.get()
        except LookupError:
            return None
        
    @classmethod
    def set_queue(cls, queue: StreamingQueue) -> None:
        cls._queue = queue
        cls._queue_ctx.set(queue)

    @classmethod
    def get_agent(cls) -> Sana | None:
        if cls._agent:
            return cls._agent
        try:
            return cls._agent_ctx.get()
        except LookupError:
            return None

    @classmethod
    def set_agent(cls, agent: Sana) -> None:
        cls._agent = agent
        cls._agent_ctx.set(agent)
