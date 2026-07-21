"""Index definitions for the Sales Research & Outreach scenario.

The ``schema`` callable is referenced from ``accelerator.yaml`` and is the
single source of truth for the AI Search index shape. ``src/provisioning.py``
calls it before serving (through the self-host startup shim or provisioning
CLI) to create/update the index; at runtime the app only needs the index
*name* to query.

Index shape (vector + semantic + AAD vectorizer):
    - ``id`` (key)
    - ``content`` (searchable string)
    - ``contentVector`` (Edm.Single collection, 1536 dims, cosine HNSW)
    - ``source``, ``company_name``, ``industry``, ``last_refreshed``
      (filterable / facetable / sortable as before)

Vector wiring (FoundryIQ pattern):
    - HNSW algorithm config ``accel-hnsw`` (default cosine).
    - Vectorizer ``accel-aoai`` of kind ``azureOpenAI`` whose ``parameters``
      point at the Foundry account's OpenAI inference endpoint and the
      ``text-embedding-3-small`` deployment provisioned by ``foundry.bicep``.
      ``auth_identity=None`` means the AI Search service authenticates as its
      own SystemAssigned MI; ``main.bicep`` grants that MI the
      ``Cognitive Services OpenAI User`` role on the Foundry account so
      query-time vectorization works without keys.
    - Profile ``accel-vector-profile`` binds the algorithm to the vectorizer.

Bootstrap embeds seed docs at provision time so ``contentVector`` is
populated for the initial corpus; the same vectorizer fires at query time
when the FoundryIQ Knowledge Base runs a vector query through the
project-level MCP connection.
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

# Embedding dimension for text-embedding-3-small. Hard-coded because changing
# it would invalidate every stored vector in the index — a redeploy only
# concern, not a partner-tunable parameter.
EMBEDDING_DIMENSIONS = 1536

ALGORITHM_NAME = "accel-hnsw"
VECTORIZER_NAME = "accel-aoai"
PROFILE_NAME = "accel-vector-profile"


def index_definition(name: str) -> SearchIndex:
    """Return the ``accounts`` index definition.

    The scenario manifest passes the configured index name (defaults to
    ``accounts``) so partners can rename without touching this file.

    The vectorizer reads two env vars at bootstrap time:
        - ``AZURE_AI_FOUNDRY_OPENAI_ENDPOINT`` (e.g. ``https://fdy....openai.azure.com``)
        - ``AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT`` (e.g. ``text-embedding-3-small``)
    Both are wired by ``infra/modules/container-app.bicep`` so the schema
    callable resolves them deterministically inside the Container App.
    """
    aoai_endpoint = os.environ.get("AZURE_AI_FOUNDRY_OPENAI_ENDPOINT", "")
    embedding_deployment = os.environ.get(
        "AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
    )

    return SearchIndex(
        name=name,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchField(
                name="contentVector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=EMBEDDING_DIMENSIONS,
                vector_search_profile_name=PROFILE_NAME,
            ),
            SimpleField(
                name="source", type=SearchFieldDataType.String, filterable=True
            ),
            SearchableField(
                name="company_name",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SearchableField(
                name="industry",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(
                name="last_refreshed",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
                sortable=True,
            ),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name=ALGORITHM_NAME)],
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
                        # auth_identity=None -> Search service uses its
                        # SystemAssigned MI, which has Cognitive Services
                        # OpenAI User on the Foundry account (granted in
                        # main.bicep). No keys.
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
                        content_fields=[SemanticField(field_name="content")],
                        keywords_fields=[
                            SemanticField(field_name="company_name"),
                            SemanticField(field_name="industry"),
                        ],
                    ),
                )
            ]
        ),
    )
