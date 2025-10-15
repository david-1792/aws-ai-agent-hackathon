<p align="center">
  <img src="./img/logo.png" height="300" />
</p>

# 🧠 **Sana**: a mental health screening agent

## 📋 Table of contents
- [🧠 **Sana**: a mental health screening agent](#-sana-a-mental-health-screening-agent)
  - [📋 Table of contents](#-table-of-contents)
  - [🌎 Overview](#-overview)
    - [💡 Core ideas](#-core-ideas)
  - [🏗️ System architecture](#️-system-architecture)
    - [🤖 Agent](#-agent)
    - [🚧 Access control](#-access-control)
    - [📚 Knowledge bases](#-knowledge-bases)
    - [🧰 Tools](#-tools)
      - [🛠️ MCP](#️-mcp)
      - [🧘 REST API integrations](#-rest-api-integrations)
      - [🌐 Browser access](#-browser-access)
    - [🧠 Memory](#-memory)
    - [🔍 Observability](#-observability)
    - [🔒 Privacy-preservation](#-privacy-preservation)
    - [🎨 User-facing layer](#-user-facing-layer)
  - [🚀 Deployment](#-deployment)
    - [⏮️ Pre-requisites](#️-pre-requisites)
    - [🏃 Running the scripts](#-running-the-scripts)
    - [🏁 Finishing up the configuration](#-finishing-up-the-configuration)
  - [📄 Resources and references](#-resources-and-references)

## 🌎 Overview
Mental health is a vital part of our overall well-being, affecting how we think, feel, and act. It also influences how we handle stress, relate to others, and make choices. Good mental health is essential at every stage of life, from childhood and adolescence through adulthood. However, access to mental health is often difficult for individuals because of many factors, including lack of knowledge, fear, option paralysis, cost and availability.

The Sana agent looks to aid in starting a mental health therapy process by understanding the mental health state of a person, providing links to resources that can help them understand their feelings and help them connect to mental health care professionals that might be a good fit for them.

Sana does not look to diagnose, treat or directly help patients in their mental health, but rather be an initial layer in the journey of having a good mental health state.

The objective is to make access to mental health an easier process for people, without removing the importance of getting help from a professional, licensed therapist. 

All of the data obtained by Sana is handled in a secure way that will allow it to be functional and usable without compromising sensible data or exposing personal information

### 💡 Core ideas
- Obtain a thorough view of the user's mental health state through screening questions
- Provide access to online resources to help understand related mental health topics and disorders
- Help connect with therapists that might be a good fit based on the screening and context
- Provide access to mental health and crisis help lines in cases of high risk
- Assure the privacy of sensible information and user's personal data

## 🏗️ System architecture
![Cloud architecture diagram](./img/arch.svg)

The cloud architecture is centered around AWS AgentCore and it's various offerings for managing runtimes, memory, tools and identity management.

### 🤖 Agent
The core of the system is the Sana agent, which is deployed in the AgentCore Runtime service. This agent is built using the Strands Agents framework and configured using a dotprompt specification.

The agent is instructed to perform a mental health screening and use its tools to help the user navigate the process of understanding their mental health state and connecting with resources and therapists that might be a good fit for them. It is also instructed to be very careful with the user's data and make sure that it is not exposed or shared in any way and to not diagnose or treat any mental health disorders.

Under the hood, it is using the Claude Sonnet 4 model from Anthropic, through AWS Bedrock, with an AWS Bedrock guardrails integration to help combat prompt injections and make sure that the agent behaves in a safe and responsible way.

### 🚧 Access control
Access control is separated into two, inbound and outbound authentication. 

We use inbound authentication to secure calls to the agent and to the AgentCore Gateway. This is done through an Amazon Cognito user pool, which allows requests to be authenticated using JWT tokens. The agent runtime is configured to use a code grant type, which will allow users to authenticate through a web application and obtain a token to access the agent, while the Gateway is configured to use a client credentials grant type, which will allow machine-to-machine (M2M) authentication for the agent to call the Gateway.

Outbound authentication is managed through AgentCore Identity, which allows us to create OAuth clients that can be used to authenticate requests to external services. In this example, we have both 2-legged OAuth (2LO) clients for M2M authentication and 3-legged OAuth (3LO) clients for user authentication. which will allow the user to authenticate to external services through the agent.

The specifics of the authorization integrations are outlined in the  [Tools](#tools) section.

### 📚 Knowledge bases
One of the main capabilities of the project is to be able to provide online resources (like web articles or documents) to users, that might be related to some of the issues outlined in the initial mental health screening. 

In order to have control over the sources for these online resources (because they need to be very reliable), a knowledge base is used, with multiple data sources that provide these online resources. In this sense, we can use natural language to query a vector store linked to the knowledge base, and retrieve the resources that more closely allign with the query, extracting only the related URL and returning that to the user.

AWS Bedrock offers managed knowledge bases that automatically integrate with different data sources and vector stores to simplify the deployment of these resources.  For this case, we are linking an S3 data source to the knowledge base, containing mental health resources, and query them through an S3 vector index. A metadata file is included for each of the documents, containing the `x-amz-bedrock-kb-source-uri` key, which we can use to return the URL to the user.

This is done so that we can mimic the behavior of the Web Crawler data source, which would be the ideal data source for this use case, but requires an OpenSearch Serverless vector index, which is very expensive to run (minimum of ~$350/month).

### 🧰 Tools

#### 🛠️ MCP
AgentCore Gateway is used to expose a managed MCP server with Lambda functions as targets. For Sana, the Gateway is authorized by the same Cognito user pool than the agent, with a specific client for M2M authorization. This allows us to create an AgentCore Identity 2-legged OAuth client (2LO) and use it to authenticate requests on behalf of the agent. It has a Lambda function as part of its targets that performs the knowledge base search workflow for searching health care resources outlined above.

#### 🧘 REST API integrations
A vital part of the system is to detect high risk cases and forward contact information to the user. This is managed through an integration with the ThroughLine API, to search for specific hotlines that match the location and topics of the user. 

The free sandbox for this API contains hotlines for the US and New Zealand only, but with full access it could be expanded to include more countries and languages.

This API is described through an OpenAPI 3.0 specification file and set up as a target for the AgentCore Gateway, which allows us to discover it as an MCP tool. Authentication to the API is handled through a 2LO AgentCore Identity client, which gets configured using the client identifier and secret provided by ThroughLine, with a `client_credentials` grant type.

Another integration is with the Google API, which is authenticated using a 3LO AgentCore Identity client to schedule appointments with therapists in Google Calendar. Whenever a tool that requires user authentication is called, the agent will provide a link to the user to authenticate and authorize the tool to perform actions on their behalf.

#### 🌐 Browser access
To allow the agent to search for therapists, a browser access tool is exposed using Amazon Nova Act and the AgentCore Browser tool. Nova Act is an AI model (currently in research preview), specifically trained to perform actions within a web browser. AgentCore Browser allows us to very easily set up a remote browser session for Nova Act to connect to, and perform the actions needed to search for therapists.

Nova Act will navigate through the Headway platform, which provides access to a large number of therapists that can be filtered by different parameters, including location, insurance, issues and more. The agent will use the information obtained in the screening to filter the therapists and provide a list of potential matches to the user.

### 🧠 Memory
Management of sessions is handled using AgentCore Memory, which allows us to store information about the user and the conversation in a secure way. Apart from storing short-term memory events, a long-term memory is also configured via a summarization strategy.

### 🔍 Observability
The Strands Agents framework provides built-in observability features through OpenTelemetry (OTEL) that make it very easy to set up an observability pipeline. AgentCore Runtime, where our agent is deployed, has native support for handling OTEL telemetry data through the use of the AWS Distro for OpenTelemetry (ADOT) collector. The telemetry data is visible through the very useful GenAI Observability dashboard in CloudWatch, which provides insights into the agent's performance, session data and metrics.

### 🔒 Privacy-preservation
Since both the memory and the logs/traces can contain very sensible information, it is very important to make sure that not only the data is stored in a secure way, but also that it cannot be traced back to a specific person. This is done by hashing the user identifier and using the hashed value as the identifier for the memory and logs/traces. This way, even if someone has access to the memory or logs/traces, they cannot know the identity of the user.

### 🎨 User-facing layer
To expose our agent, a simple web application is built using Streamlit. This application allows users to authenticate using the Cognito user pool and obtain a JWT token to access the agent. The application also provides a simple interface to interact with the agent, displaying the conversation history and allowing the user to input new messages. To deploy this application, an Amazon Lightsail instance is used, which provides a simple and cost-effective way to run the application.

## 🚀 Deployment

### ⏮️ Pre-requisites
- Have Python 3.12+ installed
- Install the Python [uv package manager](https://docs.astral.sh/uv/getting-started/installation/)
- Install the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) and [configure it](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html) with your credentials
- Turn on [Transaction Search](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Enable-TransactionSearch.html#CloudWatch-Transaction-Search-EnableConsole) in AWS CloudWatch
- [Grant access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-modify.html) to the Anthropic Claude Sonnet 4 model in AWS Bedrock
- Obtain the [ThroughLine API](https://developer.throughlinecare.com/) OAuth parameters
- Create a Google Cloud project, enable the Google Calendar API and create new OAuth credentials.

### 🏃 Running the scripts
To deploy the infrastructure, run the following script from the root of the repository:

```bash
uv run python infra/deploy.py
```

This will deploy all the necessary resources in AWS.

When reaching the step where the AgentCore Runtime is deployed, you will need to push the Docker image to Amazon ECR.
To do this, go to the AWS Console and access the ECR service to find the repository for the project.
Then, follow the instructions to push the Docker image to the repository. Commands should be run from the `sana` folder.

### 🏁 Finishing up the configuration
After the deployment is finished, there are a few manual steps that need to be done to finish the configuration:
- Clone the GitHub repo into the Lightsail instance
- Initialize the Streamlit app in the Lightsail instance (on port 80)
- Add the Lightsail instance static IP address to the Cognito web app client allowed callback and logout URLs
- Create a managed login style and assign it to the web app client

## 📄 Resources and references
- [AWS AgentCore documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [AWS Bedrock documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html)
- [Strands Agents framework documentation](https://strandsagents.com/latest/documentation/docs/)
- [ThroughLine API documentation](https://developer.throughlinecare.com/)
- [Google Calendar API documentation](https://developers.google.com/workspace/calendar/api/guides/overview)
- [Headway platform](https://headway.co/)
- [Amazon Nova Act repository](https://github.com/aws/nova-act)
- [Streamlit documentation](https://docs.streamlit.io/)
- [AgentCore GitHub samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples)