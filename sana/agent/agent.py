from pathlib import Path
from collections.abc import AsyncGenerator
import uuid
import yaml

import jwt

from strands import Agent
from strands.tools.mcp import MCPClient
from strands.session import SessionManager
from strands.models import BedrockModel

from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig

from mcp.client.streamable_http import streamablehttp_client

from opentelemetry import baggage, context

from sana.core.config import settings

class Sana:
    def __init__(
        self,
        session_id: str | None,
        auth_token: str | None
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.auth_token = auth_token

        self.tools: list = []
        self._load_tools()

        self.actor_id: str = 'anonymous'
        if 'sub' in (claims := self._parse_claims(self.auth_token)):
            self.actor_id = claims['sub']

        self._load_observability()

        self.session_manager: SessionManager | None = None
        self._load_memory()

        prompt_metadata, self.prompt = self._load_prompt('system')

        self.model_id = prompt_metadata.get('model', settings.AWS_BEDROCK_MODEL_ID)
        self.temperature = prompt_metadata.get('temperature', settings.AWS_BEDROCK_TEMPERATURE)
        self.max_tokens = prompt_metadata.get('max_tokens', settings.AWS_BEDROCK_MAX_TOKENS)

        self.model = BedrockModel(
            model_id=self.model_id,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            guardrail_id=settings.AWS_BEDROCK_GUARDRAILS_ID,
            guardrail_version=settings.AWS_BEDROCK_GUARDRAILS_VERSION,
            region_name=settings.AWS_REGION,
            streaming=True
        )

        self.agent = Agent(
            name='Sana',
            description='A mental health screening assistant',
            model=self.model,
            tools=self.tools,
            system_prompt=self.prompt,
            session_manager=self.session_manager,
            callback_handler=None
        )

    def _load_tools(self) -> None:
        from strands_tools.current_time import current_time
        self.tools.append(current_time)

        if settings.AWS_BEDROCK_KNOWLEDGE_BASE_ID:
            from sana.agent.tools import search
            self.tools.append(search)

        if settings.AWS_BEDROCK_AGENTCORE_GATEWAY_URL:
            try:
                mcp_client = MCPClient(
                    lambda: streamablehttp_client(
                        settings.AWS_BEDROCK_AGENTCORE_GATEWAY_URL,
                        headers={'Authorization': self.auth_token}
                    )
                )

                mcp_client.start()
            except Exception as e:
                raise RuntimeError(f'failed to initialize MCPClient: {e}')
            
            self.tools.extend(mcp_client.list_tools_sync())
    
    def _load_observability(self) -> None:
        if not settings.OTEL_ENABLED:
            return
    
        baggage_context = baggage.set_baggage('actor.id', self.actor_id)
        baggage_context = baggage.set_baggage('session.id', self.session_id, context=baggage_context)
        context.attach(baggage_context)

    def _load_memory(self) -> None:
        if not settings.AWS_BEDROCK_AGENTCORE_MEMORY_ID:
            return
        
        namespace_config: dict = {
            '/': RetrievalConfig(top_k=3)
        }

        memory_config = AgentCoreMemoryConfig(
            memory_id=settings.AWS_BEDROCK_AGENTCORE_MEMORY_ID,
            retrieval_config=namespace_config,
            session_id=self.session_id,
            actor_id=self.actor_id,
        )

        self.session_manager = AgentCoreMemorySessionManager(
            region_name=settings.AWS_REGION,
            agentcore_memory_config=memory_config
        )

    def _load_prompt(self, prompt_name: str) -> tuple[dict, str]:
        prompt_path = Path(__file__).parent / 'prompts' / f'{prompt_name}.prompt'

        if not prompt_path.exists():
            raise FileNotFoundError()
        
        with open(prompt_path, 'r') as file:
            content = file.read()

        parts = content.split('---')
        if len(parts) < 3:
            return {}, content.strip()
        
        prompt = parts[-1].strip()
        try:
            metadata = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            return {}, prompt
        
        return metadata if isinstance(metadata, dict) else {}, prompt
    
    def _parse_claims(self, token: str) -> dict:
        if not token:
            return {}

        try:
            token: str = token.split(' ')[-1]
            claims = jwt.decode(token, options={"verify_signature": False})
            return claims
        except Exception as e:
            raise RuntimeError(f'jwt.decode failed: {e}')

    async def stream(self, message: str) -> AsyncGenerator[str, None]:
        using_tool: bool = False

        try:
            async for event in self.agent.stream_async(message):
                if 'data' in event:
                    if using_tool:
                        using_tool = False
                    yield event["data"]
        except Exception as e:
            yield f'error: {e}'