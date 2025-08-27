from agents import Agent, Runner
from openai import AsyncAzureOpenAI
from agents import set_default_openai_client
from azure.identity import ChainedTokenCredential, AzureCliCredential, ManagedIdentityCredential, get_bearer_token_provider
from agents import set_default_openai_api

scope = "api://trapi/.default"
credential = get_bearer_token_provider(
    ChainedTokenCredential(
        AzureCliCredential(),
        ManagedIdentityCredential(),
    ),
    scope,
)

prompt = "You are processing a markdown file. Split it into semantically meaningful chunks. Each chunk should be less than 500 tokens, preserve Markdown formatting, and include the section headers it belongs to. Also generate a short title for each chunk."

api_version = '2024-12-01-preview'  # Ensure this is a valid API version see: https://learn.microsoft.com/en-us/azure/ai-services/openai/api-version-deprecation#latest-ga-api-release
deployment_name = 'o3_2025-04-16'  # Ensure this is a valid deployment name see https://aka.ms/trapi/models for the deployment name
instance = 'gcr/shared' # See https://aka.ms/trapi/models for the instance name
endpoint = f'https://trapi.research.microsoft.com/{instance}/openai/deployments/{deployment_name}'

token = credential()

# text read from knowledge_base_3.md
filename = "knowledge_base_3.md"
with open(filename, encoding="utf-8", errors="replace") as f:
    text = f.read()


client = AsyncAzureOpenAI(
    api_key=token,
    base_url=endpoint,
    api_version=api_version,
)
set_default_openai_client(client, use_for_tracing=False)
set_default_openai_api("chat_completions")

agent = Agent(name="Assistant", instructions=prompt)

result = Runner.run_sync(agent, text)
print(result.final_output)

