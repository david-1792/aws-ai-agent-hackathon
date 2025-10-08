
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Amazon Web Services
    AWS_REGION: str = 'us-east-1'

    ## AWS Bedrock
    AWS_BEDROCK_MODEL_ID: str = 'amazon.nova-micro-v1:0'
    AWS_BEDROCK_TEMPERATURE: float = 0.0
    AWS_BEDROCK_MAX_TOKENS: int = 2048
    
    ### Guardrails
    AWS_BEDROCK_GUARDRAILS_ID: str | None = None
    AWS_BEDROCK_GUARDRAILS_VERSION: str | None = None

    ### Knowledge base
    AWS_BEDROCK_KNOWLEDGE_BASE_ID: str | None = None

    ## AWS Bedrock AgentCore
    ### Memory
    AWS_BEDROCK_AGENTCORE_MEMORY_ID: str | None = None

    ### Gateway
    AWS_BEDROCK_AGENTCORE_GATEWAY_URL: str | None = None

    # Observability
    ## OpenTelemetry
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = 'sana'

settings = Settings()