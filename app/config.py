from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # General
    ENVIRONMENT: Literal['local', 'prod'] = 'local'
    
    # Amazon Web Services
    AWS_REGION: str = 'us-east-1'

        ## AWS Cognito
    AWS_COGNITO_DOMAIN: str
    AWS_COGNITO_APP_CLIENT_ID: str
    AWS_COGNITO_REDIRECT_URI: str = 'http://localhost:8501'

        ## AWS Bedrock AgentCore
    AWS_AGENTCORE_RUNTIME_URL: str = 'http://localhost:8080/invocations'
    
    # Load .env file
    model_config = SettingsConfigDict(
        env_file='app/.env', 
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()