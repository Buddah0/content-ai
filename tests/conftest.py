import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine

# Force test database before importing app (which reads DATABASE_URL at import time)
os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"

from content_ai.api.db_models import Base  # noqa: E402
from content_ai.api.main import app, database  # noqa: E402


@pytest.fixture(scope="function")
async def client():
    # Create tables via synchronous SQLAlchemy
    engine = create_engine("sqlite:///./test_api.db")
    Base.metadata.create_all(engine)
    engine.dispose()

    # Connect the async database used by the app
    await database.connect()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Clean up: drop all tables and disconnect
    engine = create_engine("sqlite:///./test_api.db")
    Base.metadata.drop_all(engine)
    engine.dispose()
    await database.disconnect()
