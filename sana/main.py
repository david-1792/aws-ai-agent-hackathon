from sana.agent import Sana
from bedrock_agentcore import BedrockAgentCoreApp, RequestContext

app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload: dict, context: RequestContext):
    print(payload)
    message: str = payload['prompt']
    session_id: str = context.session_id
    
    if not (
        (headers := context.request_headers)
        and 'Authorization' in headers
    ):
        return {'error': 'Missing Authorization header'}

    auth_token: str = headers['Authorization']

    agent = Sana(session_id=session_id, auth_token=auth_token)

    return agent.stream(message)

if __name__ == '__main__':
    app.run()