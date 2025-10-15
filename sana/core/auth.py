from bedrock_agentcore.identity import requires_access_token

from sana.core.config import settings
from sana.core.context import SanaContext

@requires_access_token(
    provider_name=settings.AWS_BEDROCK_AGENTCORE_GATEWAY_OAUTH_PROVIDER_NAME,
    scopes=settings.AWS_BEDROCK_AGENTCORE_GATEWAY_OAUTH_SCOPES,
    auth_flow='M2M'
)
def get_gateway_token(access_token: str) -> str:
    return access_token

async def on_auth_url(url: str) -> None:
    if (queue := SanaContext.get_queue()):
        await queue.put(f'\n\n:blue-badge[You must allow us to access your Google account using [this link]({url}).]\n\n')

GOOGLE_SCOPES: list[str] = ['https://www.googleapis.com/auth/calendar']

@requires_access_token(
    provider_name=settings.GOOGLE_OAUTH_PROVIDER_NAME,
    scopes=GOOGLE_SCOPES,
    auth_flow='USER_FEDERATION',
    on_auth_url=on_auth_url,
    force_authentication=True
)
def get_google_token(access_token: str) -> str:
    return access_token