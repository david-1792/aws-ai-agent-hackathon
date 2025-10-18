from pathlib import Path
from collections.abc import AsyncGenerator
import hashlib
import logging

import yaml

from strands import Agent
from strands.tools.mcp import MCPClient
from strands.session import SessionManager
from strands.models import BedrockModel

from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig

from mcp.client.streamable_http import streamablehttp_client

from opentelemetry import baggage, context

from sana.core.config import settings
from sana.core.models import Actor

from sana.agent.tools import tool_map

logger = logging.getLogger(__name__)

class Sana:
    def __init__(
        self, *,
        session_id: str,
        gateway_token: str,
        actor: Actor,
    ) -> None:
        self.session_id = session_id 
        self.gateway_token = gateway_token
        self.actor = actor

        self.actor_id_hash: str = hashlib.md5(self.actor.id.encode('utf-8')).hexdigest()

        self.tools: list = []
        self._load_tools()

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

        self._load_user_context()

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
        # Basic tools
        from strands_tools.current_time import current_time
        self.tools.append(current_time)
        
        # Therapist search tool
        if settings.AWS_NOVA_ACT_API_KEY:
            from sana.agent.tools.therapists import search_therapists
            self.tools.append(search_therapists)
        else:
            logger.warning('No Nova Act API key configured, skipping therapists tool setup...')

        # Calendar management tool
        if settings.GOOGLE_OAUTH_PROVIDER_NAME:
            from sana.agent.tools.calendar import GoogleCalendarTools
            calendar = GoogleCalendarTools()
            self.tools.extend(calendar.tools)
        else:
            logger.warning('No Google OAuth provider configured, skipping calendar tool setup...')

        # AgentCore Gateway MCP tools
        if not settings.AWS_BEDROCK_AGENTCORE_GATEWAY_URL:
            logger.warning('No AgentCore Gateway URL configured, skipping MCP tool setup...')
            return
        
        try:
            mcp_client = MCPClient(
                lambda: streamablehttp_client(
                    settings.AWS_BEDROCK_AGENTCORE_GATEWAY_URL,
                    headers={'Authorization': self.gateway_token}
                )
            )

            mcp_client.start()
        except Exception as e:
            raise RuntimeError(f'failed to initialize MCPClient: {e}')
        
        self.tools.extend(mcp_client.list_tools_sync())
    
    def _load_observability(self) -> None:
        if not settings.OTEL_ENABLED:
            logger.warning('OpenTelemetry is not enabled, skipping observability setup...')
            return

        baggage_context = baggage.set_baggage('actor.id', self.actor_id_hash)
        baggage_context = baggage.set_baggage('session.id', self.session_id, context=baggage_context)
        context.attach(baggage_context)

    def _load_memory(self) -> None:
        if not settings.AWS_BEDROCK_AGENTCORE_MEMORY_ID:
            logger.warning('No AgentCore Memory ID configured, skipping memory setup...')
            return
        
        # Long-term memory configuration
        namespace_config: dict = {
            '/summary/{actorId}/{sessionId}': RetrievalConfig(top_k=3),
            '/preferences/{actorId}': RetrievalConfig(top_k=3),
        }

        memory_config = AgentCoreMemoryConfig(
            memory_id=settings.AWS_BEDROCK_AGENTCORE_MEMORY_ID,
            retrieval_config=namespace_config,
            session_id=self.session_id,
            actor_id=self.actor_id_hash,
        )

        self.session_manager = AgentCoreMemorySessionManager(
            region_name=settings.AWS_REGION,
            agentcore_memory_config=memory_config
        )

    def _load_prompt(self, prompt_name: str) -> tuple[dict, str]:
        # Load dotprompt file
        prompt_path = Path(__file__).parent / 'prompts' / f'{prompt_name}.prompt'

        if not prompt_path.exists():
            logger.error(f'Prompt file not found: {prompt_path}')
            raise FileNotFoundError(f'Prompt file not found: {prompt_path}')
        
        with open(prompt_path, 'r') as file:
            content = file.read()

        parts = content.split('---')
        if len(parts) < 3:
            return {}, content.strip()
        
        # Load prompt metadata from YAML section
        prompt = parts[-1].strip()
        try:
            metadata = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            logger.error(f'Error parsing YAML metadata: {e}')
            return {}, prompt
        
        return metadata if isinstance(metadata, dict) else {}, prompt

    def _load_user_context(self) -> None:
        self.prompt = self.prompt.replace('{{country}}', self.actor.country)
        self.prompt = self.prompt.replace('{{zip_code}}', self.actor.zip_code)
        self.prompt = self.prompt.replace('{{timezone}}', self.actor.timezone)

    async def stream(self, message: str) -> AsyncGenerator[str, None]:
        using_tool: bool = False
        current_tool_name: str | None = None

        try:
            async for event in self.agent.stream_async(message):
                if 'data' in event:
                    if using_tool:
                        using_tool = False
                        
                    yield event["data"]
                elif 'current_tool_use' in event:
                    if not using_tool or current_tool_name != event['current_tool_use']['name']:
                        using_tool = True
                        current_tool_name = event['current_tool_use']['name']
                        tool_message: str = tool_map.get(current_tool_name, 'Performing tool action...')

                        yield f'\n\n>{tool_message}\n\n'

        except Exception as e:
            yield f'error: {e}'