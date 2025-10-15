from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from strands.telemetry import StrandsTelemetry

class Settings(BaseSettings):
    # General
    ENVIRONMENT: Literal['local', 'prod'] = 'local'

    # Amazon Web Services
    AWS_REGION: str

    ## AWS Bedrock
    AWS_BEDROCK_MODEL_ID: str = 'global.anthropic.claude-sonnet-4-20250514-v1:0'
    AWS_BEDROCK_TEMPERATURE: float = 0.0
    AWS_BEDROCK_MAX_TOKENS: int = 2048
    
        ### Guardrails
    AWS_BEDROCK_GUARDRAILS_ID: str | None = None
    AWS_BEDROCK_GUARDRAILS_VERSION: str | None = None

    ## AWS Bedrock AgentCore
        ### Memory
    AWS_BEDROCK_AGENTCORE_MEMORY_ID: str | None = None

        ### Gateway
    AWS_BEDROCK_AGENTCORE_GATEWAY_URL: str | None = None
    AWS_BEDROCK_AGENTCORE_GATEWAY_OAUTH_PROVIDER_NAME: str | None = None
    AWS_BEDROCK_AGENTCORE_GATEWAY_OAUTH_SCOPES: list[str] = []
    
    ## AWS Nova
    AWS_NOVA_ACT_API_KEY: str | None = None
    
    # Tool integration
        ## Headway
    HEADWAY_BASE_URL: str = 'https://headway.co'

        ## Google
    GOOGLE_OAUTH_PROVIDER_NAME: str | None = None
    
    # Observability
        ## OpenTelemetry
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = 'sana'

    # Load .env file
    model_config = SettingsConfigDict(
        env_file='sana/.env', 
        env_file_encoding='utf-8',
        extra='ignore'
    )
    
settings = Settings()

if settings.OTEL_ENABLED:
    telemetry = StrandsTelemetry()
    telemetry.setup_otlp_exporter()
    telemetry.setup_meter(enable_otlp_exporter=True)