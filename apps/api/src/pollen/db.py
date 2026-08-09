"""MongoDB connection and index registration."""

from __future__ import annotations

import logging

from beanie import init_beanie
from pymongo import AsyncMongoClient

from pollen.components.registry import all_documents

log = logging.getLogger(__name__)


async def connect(mongodb_uri: str) -> AsyncMongoClient:
    """Connect and register every document model.

    ``init_beanie`` also builds the declared indexes — including the unique
    delivery index that the whole idempotency guarantee rests on (ADR 0003).
    Without this call the index does not exist and duplicates go through.

    Beanie 2 uses PyMongo's native async client; Motor is retired.
    """
    client: AsyncMongoClient = AsyncMongoClient(mongodb_uri)
    await init_beanie(
        database=client.get_default_database(),
        document_models=all_documents(),
    )
    log.info("mongo connected, %d document model(s) registered", len(all_documents()))
    return client
