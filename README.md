# 🧠🩺 **Sana**: an AI-powered mental health screening agent

## Table of contents
- [🧠🩺 **Sana**: an AI-powered mental health screening agent](#-sana-an-ai-powered-mental-health-screening-agent)
  - [Table of contents](#table-of-contents)
  - [🌎 Overview](#-overview)
    - [💡 Core ideas](#-core-ideas)
  - [🏗️ System architecture](#️-system-architecture)
    - [Agent](#agent)
    - [Access control](#access-control)
    - [Knowledge bases](#knowledge-bases)
    - [Tools](#tools)
      - [Browser control](#browser-control)
      - [MCP](#mcp)
      - [API integrations](#api-integrations)
      - [Browser access](#browser-access)
    - [Memory](#memory)
      - [Privacy-preservation](#privacy-preservation)
    - [Observability](#observability)
    - [🎨 User-facing layer](#-user-facing-layer)
  - [🚀 Deployment](#-deployment)
    - [🛠️ Pre-requisites](#️-pre-requisites)
  - [📄 Resources and references](#-resources-and-references)

## 🌎 Overview
Mental health.
However, access to mental health is often difficult for individuals because of many factors, including lack of knowledge, fear, option paralysis, cost and availability.

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

### Agent

### Access control

### Knowledge bases
One of the main capabilities of the project is to be able to provide online resources (like web articles or documents) to users, that might be related to some of the issues outlined in the initial mental health screening. 

In order to have control over the sources for these online resources (because they need to be very reliable), a knowledge base is used, with multiple data sources that provide these online resources. In this sense, we can use natural language to query a vector store linked to the knowledge base, and retrieve the resources that more closely allign with the query, extracting only the related URL and returning that to the user.

AWS Bedrock offers managed knowledge bases that automatically integrate with different data sources and vector stores to simplify the deployment of these resources. 

For this case, we are linking multiple Web Crawler data sources to the knowledge base, which are able to crawl public pages containing mental health resources, and query them through an Opensearch Serverless vector index. The metadata for the documents generated from the crawler data sources contain the `x-amz-bedrock-kb-source-uri` key, which we can use to return the URL to the user.

### Tools

#### Browser control

#### MCP
AgentCore Gateway is used to expose a managed MCP server with Lambda functions as targets. For Sana, the Gateway is authorized by the same Cognito user pool than the agent, allowing us to forward the `Authentication` header and connect to it. It has a single Lambda function that performs the browser control workflow for searching health care professionals outlined above.

#### API integrations
A vital part of the system is to detect high risk cases and forward contact information to the user. This is managed through an integration with the ThroughLine API, to search for specific hotlines that match the location and topics of the user. 

The free sandbox for this API contains hotlines for the US and New Zealand only, but with full access it could be expanded to include more countries and languages.

#### Browser access
Amazon Nova Act is an AI model (currently in research preview), specifically trained to perform actions within a web browser. 

### Memory

#### Privacy-preservation

### Observability

### 🎨 User-facing layer

## 🚀 Deployment

### 🛠️ Pre-requisites

## 📄 Resources and references