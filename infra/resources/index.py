
from pydantic_settings import BaseSettings

from nova_act import NovaAct
from bedrock_agentcore.tools.browser_client import browser_session

class Settings(BaseSettings):
    AWS_REGION: str
    AWS_NOVA_ACT_API_KEY: str

    STARTING_PAGE_URL: str = "https://www.doctoralia.com.mx/"

settings = Settings()

def handler(event: dict, context: dict):
    tool_name: str = context.client_context.custom['bedrockAgentCoreToolName'].split('___')[-1]

    match tool_name:
        case 'search':
            return search(**event)
        case _:
            return {'error': f'Unknown tool: {tool_name}'}
        
def search(query: str):
    try:
        with browser_session(settings.AWS_REGION) as browser:
            ws_url, headers = browser.generate_ws_headers()

            with NovaAct(
                starting_page=settings.STARTING_PAGE_URL,
                nova_act_api_key=settings.AWS_NOVA_ACT_API_KEY,
                cdp_endpoint_url=ws_url,
                cdp_headers=headers
            ) as nova:
                result = nova.act(query)
                return result
    except Exception as e:
        return {'error': str(e)}
