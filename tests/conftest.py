import pytest
import os
from httpx import AsyncClient, ASGITransport
from content_ai.api.main import app

@pytest.fixture(scope="function")
async def client():
    # Initialize DB
    from sqlalchemy import create_engine
    from content_ai.api.db_models import Base
    db_url = os.getenv('DATABASE_URL', 'sqlite:///./test_api.db')
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
