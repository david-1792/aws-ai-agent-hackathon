import boto3
from strands.tools import tool

from sana.core.config import settings

@tool
def search(
    query: str,
    max_results: int = 3
) -> list[str]:
    """
    """

    url_set: set[str] = set()
    bedrock = boto3.client('bedrock-agent-runtime')

    done: bool = False
    while not done:
        params: dict = {
            'knowledgeBaseId': settings.AWS_BEDROCK_KNOWLEDGE_BASE_ID,
            'retrievalQuery': {'text': query},
            'maxResults': max_results,
            'retrievalConfiguration': {
                'vectorSearchConfiguration': {
                    'numberOfResults': max_results
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
            if len(url_set) >= max_results:
                done = True
                break

    return list(url_set)

