from typing import Annotated

import boto3
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    AWS_BEDROCK_KNOWLEDGE_BASE_ID: str

settings = Settings()

class Resource(BaseModel):
    url: Annotated[str, Field(...)]

def search_resources(
    query: str,
    limit: int = 5
) -> list[Resource]:
    url_set: set[str] = set()
    bedrock = boto3.client('bedrock-agent-runtime')

    done: bool = False
    while not done:
        params: dict = {
            'knowledgeBaseId': settings.AWS_BEDROCK_KNOWLEDGE_BASE_ID,
            'retrievalQuery': {'text': query},
            'maxResults': limit,
            'retrievalConfiguration': {
                'vectorSearchConfiguration': {
                    'numberOfResults': limit
                }
            }
        }

        if url_set:
            params['retrievalConfiguration']['vectorSearchConfiguration']['filter'] = {
                'notIn': {
                    'key': 'x-amz-bedrock-kb-source-uri',
                    'value': list(url_set)
                }
            }

        response = bedrock.retrieve(**params)

        for document in response['retrievalResults']:
            url_set.add(document['metadata']['x-amz-bedrock-kb-source-uri'])
            if len(url_set) >= limit:
                done = True
                break

    return [Resource(url=url) for url in list(url_set)]
        
def handler(event: dict, context: dict):    
    full_tool_name: str = context.client_context.custom['bedrockAgentCoreToolName']
    tool_name: str = full_tool_name.split('___')[-1]
    
    match tool_name:
        case 'search-resources':
            return search_resources(**event)
        case _:
            return {'error': f'Unknown tool: {tool_name}'}
