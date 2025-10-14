from typing import TypedDict
import os

import boto3

bedrock = boto3.client('bedrock-agent-runtime')

try:
    AWS_BEDROCK_KNOWLEDGE_BASE_ID = os.environ['AWS_BEDROCK_KNOWLEDGE_BASE_ID']
except KeyError as e:
    raise RuntimeError(f'Missing environment variable: {e}')

class Resource(TypedDict):
    url: str

class ResourceList(TypedDict):
    resources: list[Resource]

def search_resources(
    query: str,
    limit: int = 5
) -> ResourceList:
    url_set: set[str] = set()

    for _ in range(limit):
        params: dict = {
            'knowledgeBaseId': AWS_BEDROCK_KNOWLEDGE_BASE_ID,
            'retrievalQuery': {'text': query},
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
                break
        else:
            continue
        break

    return ResourceList(resources=[Resource(url=url) for url in list(url_set)])
        
def handler(event: dict, context: dict):
    full_tool_name: str = context.client_context.custom['bedrockAgentCoreToolName']
    tool_name: str = full_tool_name.split('___')[-1]
    
    match tool_name:
        case 'search-resources':
            return search_resources(**event)
        case _:
            return {'error': f'Unknown tool: {tool_name}'}