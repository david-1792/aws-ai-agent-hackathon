from typing import Literal
from pathlib import Path
from time import sleep
from urllib import parse
import json
import uuid

from pydantic_settings import BaseSettings, SettingsConfigDict

import boto3
from botocore.exceptions import ClientError

# Settings
class Settings(BaseSettings):
    # General
    APP_NAME: str = 'sana'
    FRONTEND_URL: str = 'http://localhost:8501'
    ENVIRONMENT: Literal['local', 'prod'] = 'local'

    # Amazon Web Services (AWS)
    AWS_REGION: str

        ## Amazon Nova Act
    AWS_NOVA_ACT_API_KEY: str

    # OAuth 2.0 Providers
        ## ThroughLine
    THROUGHLINE_CLIENT_ID: str
    THROUGHLINE_CLIENT_SECRET: str
    THROUGHLINE_ISSUER: str = 'https://api.findahelpline.com'
    THROUGHLINE_TOKEN_ENDPOINT: str = 'https://api.findahelpline.com/oauth/token'

        ## Google
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    # Load .env file
    model_config = SettingsConfigDict(
        env_file='infra/.env', 
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()

print(f'Deploying {settings.APP_NAME} in {settings.ENVIRONMENT} environment to AWS region {settings.AWS_REGION}...')

# boto3 clients
sts = boto3.client('sts', region_name=settings.AWS_REGION)
agentcore = boto3.client('bedrock-agentcore-control', region_name=settings.AWS_REGION)
bedrock = boto3.client('bedrock', region_name=settings.AWS_REGION)
bedrock_agents = boto3.client('bedrock-agent', region_name=settings.AWS_REGION)
cognito = boto3.client('cognito-idp', region_name=settings.AWS_REGION)
_lambda = boto3.client('lambda', region_name=settings.AWS_REGION)
iam = boto3.client('iam', region_name=settings.AWS_REGION)
ecr = boto3.client('ecr', region_name=settings.AWS_REGION)
s3 = boto3.client('s3', region_name=settings.AWS_REGION)
s3v = boto3.client('s3vectors', region_name=settings.AWS_REGION)
lightsail = boto3.client('lightsail', region_name=settings.AWS_REGION)

# Common variables
account_id: str = sts.get_caller_identity()['Account']
prefix: str = f'{settings.APP_NAME}-{settings.ENVIRONMENT}'
random_suffix: str = uuid.uuid4().hex[:6]

def main() -> None:
    memory = agentcore.create_memory(
        name=f'{prefix}-memory'.replace('-', '_'),
        description='Memory for the Sana application',
        eventExpiryDuration=90,
        memoryStrategies=[
            {
                'summaryMemoryStrategy': {
                    'name': 'summaries',
                    'description': 'Stores summaries of user sessions',
                    'namespaces': [
                        '/summaries/{actorId}/{sessionId}',
                    ]
                },
            },
            {
                'userPreferenceMemoryStrategy': {
                    'name': 'preferences',
                    'description': 'Stores the user preferences',
                    'namespaces': ['/preferences/{actorId}']
                }
            },
        ]
    )

    memory_id: str = memory['memory']['id']
    memory_arn: str = memory['memory']['arn']
    print(f'Created AgentCore Memory: {memory_id}')

    # AgentCore Identity
    ## Cognito
    user_pool = cognito.create_user_pool(
        PoolName=f'{prefix}-user-pool',
        UserPoolTier='ESSENTIALS',
        DeletionProtection='INACTIVE',
        AutoVerifiedAttributes=['email'],
        UsernameAttributes=['email'],
        MfaConfiguration='OFF',
        UsernameConfiguration={
            'CaseSensitive': False
        }
    )

    user_pool_id: str = user_pool['UserPool']['Id']
    user_pool_discovery_url: str = f'https://cognito-idp.{settings.AWS_REGION}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration'

    print(f'Created Cognito user pool: {user_pool_id}')

    cognito.create_user_pool_domain(
        Domain=f'{prefix}-{random_suffix}',
        UserPoolId=user_pool_id,
        ManagedLoginVersion=2
    )

    user_pool_domain: str = f'https://{prefix}-{random_suffix}.auth.{settings.AWS_REGION}.amazoncognito.com'

    print(f'Created Cognito user pool domain: {user_pool_domain}')

    web_client = cognito.create_user_pool_client(
        ClientName=f'{prefix}-web',
        UserPoolId=user_pool_id,
        GenerateSecret=False,
        SupportedIdentityProviders=['COGNITO'],
        AllowedOAuthFlowsUserPoolClient=True,
        AllowedOAuthScopes=['openid', 'email', 'profile'],
        AllowedOAuthFlows=['code'],
        CallbackURLs=[settings.FRONTEND_URL],
        LogoutURLs=[settings.FRONTEND_URL],
    )

    web_client_id: str = web_client['UserPoolClient']['ClientId']
    print(f'Created Cognito user pool web client: {web_client_id}')

    cognito.create_resource_server(
        UserPoolId=user_pool_id,
        Identifier=f'{prefix}-m2m',
        Name=f'{prefix}-m2m',
        Scopes=[
            {
                'ScopeName': 'invoke',
                'ScopeDescription': 'Scope to invoke the AgentCore Gateway'
            }
        ]
    )

    print('Created Cognito M2M resource server')

    cognito_m2m_scope: str = f'{prefix}-m2m/invoke'

    m2m_client = cognito.create_user_pool_client(
        ClientName=f'{prefix}-m2m',
        UserPoolId=user_pool_id,
        GenerateSecret=True,
        SupportedIdentityProviders=['COGNITO'],
        AllowedOAuthFlowsUserPoolClient=True,
        ExplicitAuthFlows=['ALLOW_REFRESH_TOKEN_AUTH'],
        AllowedOAuthScopes=[cognito_m2m_scope],
        AllowedOAuthFlows=['client_credentials'],
    )

    m2m_client_id: str = m2m_client['UserPoolClient']['ClientId']
    m2m_client_secret: str = m2m_client['UserPoolClient']['ClientSecret']

    print(f'Created Cognito user pool M2M client: {m2m_client_id}')

    ## OAuth 2.0 providers
    cognito_m2m_oauth_provider_name: str = f'{prefix}-cognito-m2m'
    agentcore.create_oauth2_credential_provider(
        name=cognito_m2m_oauth_provider_name,
        credentialProviderVendor='CustomOauth2',
        oauth2ProviderConfigInput={
            'customOauth2ProviderConfig': {
                'clientId': m2m_client_id,
                'clientSecret': m2m_client_secret,
                'oauthDiscovery': {
                    'discoveryUrl': user_pool_discovery_url
                }
            }
        }
    )

    print(f'Created AgentCore Identity OAuth2 Cognito provider: {cognito_m2m_oauth_provider_name}')

    throughline_oauth_provider_name: str = f'{prefix}-throughline'
    throughline_oauth_provider = agentcore.create_oauth2_credential_provider(
        name=throughline_oauth_provider_name,
        credentialProviderVendor='CustomOauth2',
        oauth2ProviderConfigInput={
            'customOauth2ProviderConfig': {
                'clientId': settings.THROUGHLINE_CLIENT_ID,
                'clientSecret': settings.THROUGHLINE_CLIENT_SECRET,
                'oauthDiscovery': {
                    'authorizationServerMetadata': {
                        'issuer': settings.THROUGHLINE_ISSUER,
                        'authorizationEndpoint': 'https://example.com',
                        'tokenEndpoint': settings.THROUGHLINE_TOKEN_ENDPOINT,
                        'responseTypes': ['client_credentials']
                    }
                }
            }
        }
    )

    throughline_oauth_provider_arn: str = throughline_oauth_provider['credentialProviderArn']
    print(f'Created AgentCore Identity OAuth2 ThroughLine provider: {throughline_oauth_provider_name}')

    google_oauth_provider_name: str = f'{prefix}-google'
    agentcore.create_oauth2_credential_provider(
        name=google_oauth_provider_name,
        credentialProviderVendor='GoogleOauth2',
        oauth2ProviderConfigInput={
            'googleOauth2ProviderConfig': {
                'clientId': settings.GOOGLE_CLIENT_ID,
                'clientSecret': settings.GOOGLE_CLIENT_SECRET
            }
        }
    )

    print(f'Created AgentCore Identity OAuth2 Google provider: {google_oauth_provider_name}')

    # Knowledge base
    data_source_bucket_name: str = f'{prefix}-{random_suffix}-data-source'
    data_source_bucket_arn: str = f'arn:aws:s3:::{data_source_bucket_name}'

    s3.create_bucket(
        Bucket=data_source_bucket_name
    )
    print(f'Created S3 data source bucket: {data_source_bucket_name}')

    ## Populate vector store with data
    content_path = Path(__file__).parent / 'resources' / 'knowledge-base'

    file_paths: list[Path] = [p for p in content_path.glob('**/*') if p.is_file()]

    for file_path in file_paths:
        with open(file_path, 'rb') as f:
            s3.upload_fileobj(f, data_source_bucket_name, str(file_path.relative_to(content_path)))

    print(f'Uploaded {len(file_paths)} files to S3 data source bucket')

    vector_bucket_name: str = f'{prefix}-vector-bucket'

    s3v.create_vector_bucket(
        vectorBucketName=vector_bucket_name
    )

    print(f'Created S3 vector bucket: {vector_bucket_name}')

    vector_index_name: str = f'{prefix}-vector-index'

    s3v.create_index(
        vectorBucketName=vector_bucket_name,
        indexName=vector_index_name,
        dataType='float32',
        dimension=1024,
        distanceMetric='euclidean',
        metadataConfiguration={
            'nonFilterableMetadataKeys': [
                'S3VECTORS-EMBED-SRC-CONTENT',
                'AMAZON_BEDROCK_TEXT',
                'AMAZON_BEDROCK_METADATA'
            ]
        }
    )

    vector_index_arn: str = f'arn:aws:s3vectors:{settings.AWS_REGION}:{account_id}:bucket/{vector_bucket_name}/index/{vector_index_name}'

    print(f'Created S3 vector index: {vector_index_name}')

    titan_v2_arn: str = f'arn:aws:bedrock:{settings.AWS_REGION}::foundation-model/amazon.titan-embed-text-v2:0'

    knowledge_base_role_name: str = f'{prefix}-knowledge-base-role'
    knowledge_base_role = iam.create_role(
        RoleName=knowledge_base_role_name,
        Description='Role for the Sana knowledge base',
        AssumeRolePolicyDocument=json.dumps({
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Principal': {
                        'Service': 'bedrock.amazonaws.com'
                    },
                    'Action': 'sts:AssumeRole'
                }
            ]
        })
    )

    knowledge_base_role_arn: str = knowledge_base_role['Role']['Arn']
    print(f'Created knowledge base role: {knowledge_base_role_name}')

    knowledge_base_policy_name: str = f'{prefix}-knowledge-base-policy'
    knowledge_base_policy = iam.create_policy(
        PolicyName=knowledge_base_policy_name,
        Description='Policy for the Sana knowledge base role',
        PolicyDocument=json.dumps({
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Action': [
                        'bedrock:InvokeModel'
                    ],
                    'Resource': [titan_v2_arn]
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        's3:GetObject',
                        's3:ListBucket'
                    ],
                    'Resource': [
                        data_source_bucket_arn,
                        f'{data_source_bucket_arn}/*'
                    ]
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        's3vectors:GetIndex',
                        's3vectors:QueryVectors',
                        's3vectors:PutVectors',
                        's3vectors:GetVectors',
                        's3vectors:DeleteVectors'
                    ],
                    'Resource': [vector_index_arn]
                }
            ]
        })
    )

    knowledge_base_policy_arn: str = knowledge_base_policy['Policy']['Arn']
    print(f'Created knowledge base policy: {knowledge_base_policy_name}')

    iam.attach_role_policy(
        RoleName=knowledge_base_role_name,
        PolicyArn=knowledge_base_policy_arn
    )

    print('Waiting 10s for IAM role propagation...')
    sleep(10)

    knowledge_base = bedrock_agents.create_knowledge_base(
        name=f'{prefix}-knowledge-base',
        description='Knowledge base for the Sana application',
        roleArn=knowledge_base_role_arn,
        knowledgeBaseConfiguration={
            'type': 'VECTOR',
            'vectorKnowledgeBaseConfiguration': {
                'embeddingModelArn': titan_v2_arn,
                'embeddingModelConfiguration': {    
                    'bedrockEmbeddingModelConfiguration': {
                        'dimensions': 1024,
                        'embeddingDataType': 'FLOAT32'
                    }
                }
            }
        },
        storageConfiguration={
            'type':'S3_VECTORS',
            's3VectorsConfiguration': {
                'indexArn': vector_index_arn,
            }
        }
    )

    knowledge_base_id: str = knowledge_base['knowledgeBase']['knowledgeBaseId']
    knowledge_base_arn: str = knowledge_base['knowledgeBase']['knowledgeBaseArn']

    print(f'Created knowledge base: {knowledge_base_id}')

    data_source = bedrock_agents.create_data_source(
        name=f'{prefix}-data-source',
        description='Data source for the Sana application',
        knowledgeBaseId=knowledge_base_id,
        dataDeletionPolicy='DELETE',
        dataSourceConfiguration={
            'type': 'S3',
            's3Configuration': {
                'bucketArn': data_source_bucket_arn,
            }
        }
    )

    data_source_id: str = data_source['dataSource']['dataSourceId']
    print(f'Created data source: {data_source_id}')

    bedrock_agents.start_ingestion_job(
        description='Initial ingestion job for the Sana knowledge base',
        knowledgeBaseId=knowledge_base_id,
        dataSourceId=data_source_id
    )

    print('Started knowledge base sync job.')

    # Guardrails
    guardrails = bedrock.create_guardrail(
        name=f'{prefix}-guardrail',
        description='Guardrails for the Sana application',
        contentPolicyConfig={
            'filtersConfig': [
                {
                    'type': 'PROMPT_ATTACK',
                    'inputStrength': 'HIGH',
                    'outputStrength': 'NONE',
                    'inputModalities': ['TEXT'],
                    'inputAction': 'BLOCK',
                    'inputEnabled': True,
                    'outputEnabled': False
                },
            ],
            'tierConfig': {
                'tierName': 'CLASSIC'
            }
        },
        sensitiveInformationPolicyConfig={
            'piiEntitiesConfig': [
                {
                    'type': 'ADDRESS',
                    'action': 'ANONYMIZE',
                    'inputEnabled': True,
                    'outputEnabled': False
                },
            ],
        },
        contextualGroundingPolicyConfig={
            'filtersConfig': [
                {
                    'type': 'GROUNDING',
                    'threshold': 0.7,
                    'action': 'BLOCK',
                    'enabled': True
                },
            ]
        },
        blockedInputMessaging='Sorry, I cannot respond to this. Please try again with a different message.',
        blockedOutputsMessaging='Sorry, I cannot respond to this. Please try again with a different message.',
    )

    guardrail_id: str = guardrails['guardrailId']
    guardrail_arn: str = guardrails['guardrailArn']

    print(f'Created guardrail: {guardrail_id}')

    guardrail_version = bedrock.create_guardrail_version(
        guardrailIdentifier=guardrail_id,
        description='Initial version for the Sana guardrails'
    )

    guardrail_version_id: str = guardrail_version['version']

    print(f'Created guardrail version: {guardrail_version_id}')

    # AgentCore Gateway
    ## Lambda function
    resource_lambda_role_name: str = f'{prefix}-resource-lambda-role'
    resource_lambda_role = iam.create_role(
        RoleName=resource_lambda_role_name,
        Description='Role for the resource Lambda function',
        AssumeRolePolicyDocument=json.dumps({
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Principal': {
                        'Service': 'lambda.amazonaws.com'
                    },
                    'Action': 'sts:AssumeRole'
                }
            ]
        })
    )
    
    resource_lambda_role_arn: str = resource_lambda_role['Role']['Arn']
    print(f'Created resource Lambda role: {resource_lambda_role_name}')

    resource_lambda_policy = iam.create_policy(
        PolicyName=f'{prefix}-resource-lambda-policy',
        Description='Policy for the resource Lambda function',
        PolicyDocument=json.dumps({
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Action': [
                        'logs:CreateLogGroup',
                        'logs:CreateLogStream',
                        'logs:PutLogEvents'
                    ],
                    'Resource': '*'
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        'bedrock:Retrieve'
                    ],
                    'Resource': knowledge_base_arn
                }
            ]
        })
    )

    resource_lambda_policy_name = resource_lambda_policy['Policy']['PolicyName']
    resource_lambda_policy_arn = resource_lambda_policy['Policy']['Arn']

    print(f'Created resource Lambda policy: {resource_lambda_policy_name}')
    
    iam.attach_role_policy(
        RoleName=resource_lambda_role_name,
        PolicyArn=resource_lambda_policy_arn
    )

    print(f'Attached resource Lambda policy to role {resource_lambda_role_name}. Waiting for IAM role propagation...')
    sleep(10)

    with open(Path(__file__).parent / 'resources' / 'gateway' / 'resources-target' / 'package.zip', 'rb') as f:
        resource_lambda_code: bytes = f.read()

    resource_lambda_function_name: str = f'{prefix}-resource-function'
    resource_lambda = _lambda.create_function(
        FunctionName=resource_lambda_function_name,
        Description='Lambda function to provide mental health resources',
        Role=resource_lambda_role_arn,
        Runtime='python3.13',
        Handler='index.handler',
        Architectures=['arm64'],
        Timeout=30,
        MemorySize=128,
        Code={'ZipFile': resource_lambda_code},
        Environment={
            'Variables': {
                'AWS_BEDROCK_KNOWLEDGE_BASE_ID': knowledge_base_id
            }
        }
    )

    resource_lambda_arn: str = resource_lambda['FunctionArn']
    print(f'Created resource Lambda function: {resource_lambda_function_name}')

    ## Gateway and targets
    gateway_role_name: str = f'{prefix}-gateway-role'
    gateway_role = iam.create_role(
        RoleName=gateway_role_name,
        Description='Role for the Sana AgentCore Gateway',
        AssumeRolePolicyDocument=json.dumps({
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Principal': {
                        'Service': 'bedrock-agentcore.amazonaws.com'
                    },
                    'Action': 'sts:AssumeRole'
                }
            ]
        })
    )

    gateway_role_arn: str = gateway_role['Role']['Arn']
    print(f'Created gateway role: {gateway_role_name}')

    gateway_policy_name: str = f'{prefix}-gateway-role-policy'
    gateway_policy = iam.create_policy(
        PolicyName=gateway_policy_name,
        Description='Policy for the Sana AgentCore Gateway role',
        PolicyDocument=json.dumps({
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Action': [
                        'lambda:InvokeFunction'
                    ],
                    'Resource': resource_lambda_arn
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        'bedrock-agentcore:*Gateway*',
                        'bedrock-agentcore:*WorkloadIdentity*',
                        'bedrock-agentcore:*CredentialProvider*',
                        'bedrock-agentcore:*Token*',
                        'bedrock-agentcore:*Access*',
                        
                    ],
                    'Resource': 'arn:aws:bedrock-agentcore:*:*:*gateway*'
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        'secretsmanager:GetSecretValue'
                    ],
                    'Resource': '*'
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        'bedrock-agentcore:GetWorkloadAccessToken'
                    ],
                    'Resource': '*'
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        'bedrock-agentcore:GetResourceOauth2Token'
                    ],
                    'Resource': '*'
                }
            ]
        })
    )

    gateway_policy_arn: str = gateway_policy['Policy']['Arn']
    print(f'Created gateway policy: {gateway_policy_name}')

    iam.attach_role_policy(
        RoleName=gateway_role_name,
        PolicyArn=gateway_policy_arn
    )
    print(f'Attached gateway policy to role {gateway_role_name}. Waiting for IAM role propagation...')
    sleep(10)

    gateway = agentcore.create_gateway(
        name=f'{prefix}-gateway',
        description='MCP-based gateway for the Sana application',
        roleArn=gateway_role_arn,
        protocolType='MCP',
        protocolConfiguration={
            'mcp': {
                'searchType': 'SEMANTIC'
            }
        },
        authorizerType='CUSTOM_JWT',
        authorizerConfiguration={
            'customJWTAuthorizer': {
                'discoveryUrl': user_pool_discovery_url,
                'allowedClients': [m2m_client_id]
            }
        }
    )

    gateway_id: str = gateway['gatewayId']
    gateway_url: str = gateway['gatewayUrl']

    print(f'Created AgentCore Gateway: {gateway_id}')
    
    print('Waiting 10s for Gateway to be fully available...')
    sleep(10)

    resources_target_tool_schema_path = Path(__file__).parent / 'resources' / 'gateway' / 'resources-target' / 'tools.json'

    with open(resources_target_tool_schema_path, 'r') as f:
        resources_target_tool_schema = json.load(f)

    resource_function_target = agentcore.create_gateway_target(
        name='resource-function',
        description='Target for the mental health resource Lambda function',
        gatewayIdentifier=gateway_id,
        targetConfiguration={
            'mcp': {
                'lambda': {
                    'lambdaArn': resource_lambda_arn,
                    'toolSchema': {
                        'inlinePayload': resources_target_tool_schema
                    }
                }
            }
        },
        credentialProviderConfigurations=[
            {
                'credentialProviderType': 'GATEWAY_IAM_ROLE',
            },
        ]
    )
    
    resource_function_target_id: str = resource_function_target['targetId']

    print(f'Created AgentCore Gateway target for resource Lambda function: {resource_function_target_id}')

    throughline_openapi_schema_path = Path(__file__).parent / 'resources' / 'gateway' / 'helplines-target' / 'openapi.json'

    with open(throughline_openapi_schema_path, 'r') as f:
        throughline_openapi_schema = f.read()

    throughline_api_target = agentcore.create_gateway_target(
        name='throughline-rest-api',
        description='Target for the ThroughLine helpline REST API',
        gatewayIdentifier=gateway_id,
        targetConfiguration={
            'mcp': {
                'openApiSchema': {
                    'inlinePayload': throughline_openapi_schema
                }
            }
        },
        credentialProviderConfigurations=[
            {
                'credentialProviderType': 'OAUTH',
                'credentialProvider': {
                    'oauthCredentialProvider': {
                        'providerArn': throughline_oauth_provider_arn,
                        'scopes': []
                    }
                }
            },
        ]
    )

    throughline_api_target_id: str = throughline_api_target['targetId']

    print(f'Created AgentCore Gateway target for ThroughLine API: {throughline_api_target_id}')

    # AgentCore Runtime
    repository_name: str = f'{prefix}-runtime'
    repository = ecr.create_repository(
        repositoryName=repository_name,
    )

    repository_uri: str = repository['repository']['repositoryUri']
    repository_arn: str = repository['repository']['repositoryArn']

    print(f'Created ECR repository: {repository_name}. Please push the Docker image to {repository_uri}...')

    found_image: bool = False
    while not found_image:
        try:
            ecr.describe_images(
                repositoryName=repository_name,
                imageIds=[{'imageTag': 'latest'}]
            )

            found_image = True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ImageNotFoundException':
                print(f'Waiting for image with tag latest in ECR repository {repository_name}...')
                sleep(10)
                continue
            raise e

    runtime_role_name: str = f'{prefix}-runtime-role'
    runtime_role = iam.create_role(
        RoleName=runtime_role_name,
        Description='Role for the Sana AgentCore Runtime',
        AssumeRolePolicyDocument=json.dumps({
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Principal': {
                        'Service': 'bedrock-agentcore.amazonaws.com'
                    },
                    'Action': 'sts:AssumeRole'
                }
            ]
        })
    )

    runtime_role_arn: str = runtime_role['Role']['Arn']
    print(f'Created runtime role: {runtime_role_name}')

    runtime_policy_name: str = f'{prefix}-runtime-role-policy'
    runtime_policy = iam.create_policy(
        PolicyName=runtime_policy_name,
        Description='Policy for the Sana AgentCore Runtime role',
        PolicyDocument=json.dumps({
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Action': [
                        'ecr:BatchGetImage',
                        'ecr:GetDownloadUrlForLayer'
                    ],
                    'Resource': [repository_arn + '*']
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        'ecr:GetAuthorizationToken',
                    ],
                    'Resource': ['*']
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        'bedrock-agentcore:GetResourceOauth2Token',
				        'secretsmanager:GetSecretValue',
                    ],
                    'Resource': ['*']
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        'bedrock-agentcore:StartBrowserSession',
				        'bedrock-agentcore:StopBrowserSession',
                        'bedrock-agentcore:ListBrowserSessions',
                        'bedrock-agentcore:ListBrowsers',
                        'bedrock-agentcore:GetBrowser',
                        'bedrock-agentcore:GetBrowserSession',
                        'bedrock-agentcore:UpdateBrowserStream',
                        'bedrock-agentcore:ConnectBrowserAutomationStream',
                        'bedrock-agentcore:ConnectBrowserLiveViewStream'
                    ],
                    'Resource': ['*']
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:ApplyGuardrail"
                    ],
                    "Resource": [guardrail_arn]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:ListEvents",
                        "bedrock-agentcore:CreateEvent"
                    ],
                    "Resource": [memory_arn]
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        'logs:CreateLogGroup',
                        'logs:CreateLogStream',
                        'logs:PutLogEvents',
                        'logs:DescribeLogStreams',
                        'logs:DescribeLogGroups',
                        'cloudwatch:PutMetricData',
                        'xray:PutTraceSegments',
                        'xray:PutTelemetryRecords',
                        'xray:GetSamplingRules',
                        'xray:GetSamplingTargets'
                    ],
                    'Resource': ['*']
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        'bedrock-agentcore:GetWorkloadAccessToken',
                        'bedrock-agentcore:GetWorkloadAccessTokenForJWT',
                        'bedrock-agentcore:GetWorkloadAccessTokenForUserId'
                    ],
                    'Resource': [
                        f'arn:aws:bedrock-agentcore:{settings.AWS_REGION}:{account_id}:workload-identity-directory/default',
                        f'arn:aws:bedrock-agentcore:{settings.AWS_REGION}:{account_id}:workload-identity-directory/default/workload-identity/{prefix}-runtime-*'
                    ]
                },
                {
                    'Effect': 'Allow',
                    'Action': [
                        'bedrock:InvokeModel',
                        'bedrock:InvokeModelWithResponseStream'
                    ],
                    'Resource': [
                        'arn:aws:bedrock:*::foundation-model/*',
                        f'arn:aws:bedrock:{settings.AWS_REGION}:{account_id}:*'
                    ]
                }
            ]
        })
    )

    runtime_policy_arn: str = runtime_policy['Policy']['Arn']
    print(f'Created runtime policy: {runtime_policy_name}')

    iam.attach_role_policy(
        RoleName=runtime_role_name,
        PolicyArn=runtime_policy_arn
    )

    print(f'Attached runtime policy to role {runtime_role_name}. Waiting for IAM role propagation...')
    sleep(10)

    runtime = agentcore.create_agent_runtime(
        agentRuntimeName=f'{prefix}-runtime'.replace('-', '_'),
        description='Runtime for the Sana application',
        roleArn=runtime_role_arn,
        networkConfiguration={'networkMode': 'PUBLIC'},
        protocolConfiguration={'serverProtocol': 'HTTP'},
        agentRuntimeArtifact={
            'containerConfiguration': {
                'containerUri': f'{repository_uri}:latest',
            }
        },
        authorizerConfiguration={
            'customJWTAuthorizer': {
                'discoveryUrl': user_pool_discovery_url,
                'allowedClients': [
                    web_client_id,
                ]
            }
        },
        requestHeaderConfiguration={
            'requestHeaderAllowlist': [
                'Authorization'
            ]
        },
        environmentVariables={
            'ENVIRONMENT': settings.ENVIRONMENT,
            'AWS_REGION': settings.AWS_REGION,
            'AWS_BEDROCK_GUARDRAILS_ID': guardrail_id,
            'AWS_BEDROCK_GUARDRAILS_VERSION': guardrail_version_id,
            'AWS_BEDROCK_AGENTCORE_MEMORY_ID': memory_id,
            'AWS_BEDROCK_AGENTCORE_GATEWAY_URL': gateway_url,
            'AWS_BEDROCK_AGENTCORE_GATEWAY_OAUTH_PROVIDER_NAME': cognito_m2m_oauth_provider_name,
            'AWS_NOVA_ACT_API_KEY': settings.AWS_NOVA_ACT_API_KEY,
            'GOOGLE_OAUTH_PROVIDER_NAME': google_oauth_provider_name,
            'OTEL_ENABLED': 'true',
            'OTEL_SERVICE_NAME': prefix
        }
    )

    runtime_id: str = runtime['agentRuntimeId']
    escaped_agent_arn: str = parse.quote(runtime['agentRuntimeArn'], safe='')
    runtime_url: str = f'https://bedrock-agentcore.{settings.AWS_REGION}.amazonaws.com/runtimes/${escaped_agent_arn}/invocations?qualifier=DEFAULT'

    print(f'Created AgentCore Runtime: {runtime_id} with URL {runtime_url}')

    print('App environment variable script:')
    
    app_env_var_script = f'''
    #!/bin/bash    
    touch .env && \
    echo "ENVIRONMENT={settings.ENVIRONMENT}" >> .env && \
    echo "AWS_REGION={settings.AWS_REGION}" >> .env && \
    echo "AWS_COGNITO_DOMAIN={user_pool_domain}" >> .env && \
    echo "AWS_COGNITO_APP_CLIENT_ID={web_client_id}" >> .env && \
    echo "AWS_COGNITO_REDIRECT_URI={settings.FRONTEND_URL}" >> .env && \
    echo "AWS_AGENTCORE_RUNTIME_URL={runtime_url}" >> .env '''

    print(app_env_var_script)

    if settings.ENVIRONMENT != 'prod':
        print('Skipping Lightsail deployment for non-prod environment.')
        return
    
    ## Streamlit app
    instance_name: str = f'{prefix}-instance'
    lightsail.create_instances(
        instanceNames=[instance_name],
        availabilityZone=f'{settings.AWS_REGION}a',
        blueprintId='ubuntu_24_04',
        bundleId='nano_3_0'
    )

    print(f'Created Lightsail instance: {instance_name}')
    print('Waiting 60s for instance to be fully available...')
    sleep(60)

    static_ip_name: str = f'{prefix}-static-ip'
    lightsail.allocate_static_ip(
        staticIpName=static_ip_name
    )

    print(f'Created Lightsail static IP: {static_ip_name}')
    lightsail.attach_static_ip(
        staticIpName=static_ip_name,
        instanceName=instance_name
    )
    print(f'Attached static IP {static_ip_name} to instance {instance_name}')

if __name__ == '__main__':
    main()
    print('Deployment complete.')