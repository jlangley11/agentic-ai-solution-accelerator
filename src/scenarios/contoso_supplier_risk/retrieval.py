"""Index definitions for the contoso-supplier-risk scenario (FoundryIQ pattern).

The ``schema`` callable is referenced from ``accelerator.yaml`` and is
the single source of truth for the AI Search index shape that sits
underneath the FoundryIQ Knowledge Source + Knowledge Base. The
index is created by ``src/bootstrap.py`` at FastAPI startup; at
runtime the application code does not need the schema -- agents
query the index transparently through the FoundryIQ MCPTool.

The vectorizer + semantic + HNSW shape mirrors the flagship so a
scaffolded scenario is FoundryIQ-ready out of the box. Partners
extend ``fields`` with domain-specific filterables / facetables;
the embedding wiring is intentionally not partner-tunable.
"""
from __future__ import annotations

import os

from azure.search.documents.indexes.models import (
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

# text-embedding-3-small. Changing this invalidates every stored
# vector in the index -- not a partner-tunable parameter.
EMBEDDING_DIMENSIONS = 1536

ALGORITHM_NAME = "accel-hnsw"
VECTORIZER_NAME = "accel-aoai"
PROFILE_NAME = "accel-vector-profile"


def index_definition(name: str) -> SearchIndex:
    """Return the FoundryIQ-shaped index for this scenario.

    Reads two env vars wired by ``infra/modules/container-app.bicep``:
        - ``AZURE_AI_FOUNDRY_OPENAI_ENDPOINT``
        - ``AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT``
    The Search service authenticates as its SystemAssigned MI
    (Cognitive Services OpenAI User on the Foundry account, granted
    in ``main.bicep``); no keys.
    """
    aoai_endpoint = os.environ.get(
        "AZURE_AI_FOUNDRY_OPENAI_ENDPOINT", ""
    )
    embedding_deployment = os.environ.get(
        "AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT",
        "text-embedding-3-small",
    )

    return SearchIndex(
        name=name,
        fields=[
            SimpleField(
                name="id", type=SearchFieldDataType.String, key=True
            ),
            SearchableField(
                name="content", type=SearchFieldDataType.String
            ),
            SearchField(
                name="contentVector",
                type=SearchFieldDataType.Collection(
                    SearchFieldDataType.Single
                ),
                searchable=True,
                vector_search_dimensions=EMBEDDING_DIMENSIONS,
                vector_search_profile_name=PROFILE_NAME,
            ),
            SimpleField(
                name="source",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            # Domain-specific filterables for supplier-risk evidence.
            # `source_system` lets the analyst trace each cited fact back to
            # SharePoint policy / Azure SQL supplier master / Dynamics 365 /
            # ServiceNow / uploaded evidence packets. `category` and
            # `country` enable the risk_scorer to filter to category-matrix
            # and country-risk evidence. `supplier_id` keeps onboarding
            # history queries scoped to the supplier under review.
            SimpleField(
                name="source_system",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(
                name="supplier_id",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SimpleField(
                name="category",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(
                name="country",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
        ],
        vector_search=VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(name=ALGORITHM_NAME)
            ],
            profiles=[
                VectorSearchProfile(
                    name=PROFILE_NAME,
                    algorithm_configuration_name=ALGORITHM_NAME,
                    vectorizer_name=VECTORIZER_NAME,
                )
            ],
            vectorizers=[
                AzureOpenAIVectorizer(
                    vectorizer_name=VECTORIZER_NAME,
                    parameters=AzureOpenAIVectorizerParameters(
                        resource_url=aoai_endpoint,
                        deployment_name=embedding_deployment,
                        model_name="text-embedding-3-small",
                        auth_identity=None,
                    ),
                )
            ],
        ),
        semantic_search=SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name="default",
                    prioritized_fields=SemanticPrioritizedFields(
                        content_fields=[
                            SemanticField(field_name="content")
                        ],
                    ),
                )
            ]
        ),
    )
