
from agent.core.agent import Sana
from bedrock_agentcore import BedrockAgentCoreApp, RequestContext

app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload: dict, context: RequestContext):
    message: str = payload['prompt']
    session_id: str = context.session_id
    auth_token: str = context.request_headers.get('Authorization')

    agent = Sana(session_id=session_id, auth_token=auth_token)

    return agent.stream(message)

if __name__ == '__main__':
    app.run()