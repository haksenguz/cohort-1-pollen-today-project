"""Test fixtures.

Integration tests need a real MongoDB, not a mock: the whole idempotency claim
is that the DATABASE refuses a duplicate. A fake that accepts two identical
inserts would pass a test that proves nothing.

Point MONGODB_TEST_URI at any mongod. Tests that need it skip cleanly when it
is unreachable, rather than failing and looking like a code fault.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from beanie import init_beanie
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from pollen.components.registry import all_documents

TEST_URI = os.environ.get("MONGODB_TEST_URI", "mongodb://127.0.0.1:27017/pollen_test")


@pytest_asyncio.fixture
async def mongo() -> AsyncIterator[AsyncMongoClient]:
    client: AsyncMongoClient = AsyncMongoClient(TEST_URI, serverSelectionTimeoutMS=2000)

    try:
        await client.admin.command("ping")
    except PyMongoError:
        await client.close()
        pytest.skip(f"no MongoDB at {TEST_URI} — set MONGODB_TEST_URI to run these")

    db = client.get_default_database()
    # allow_index_dropping keeps the declared indexes authoritative between runs.
    await init_beanie(database=db, document_models=all_documents(), allow_index_dropping=True)

    for name in await db.list_collection_names():
        await db[name].delete_many({})

    yield client
    await client.close()
