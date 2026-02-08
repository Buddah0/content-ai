"""Tests for preset API endpoints and 409 Conflict handling."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="function")
async def test_create_preset_success(client: AsyncClient):
    """Creating a preset with unique name should succeed."""
    response = await client.post(
        "/presets",
        json={"name": "Test Preset", "description": "A test preset", "overrides": {"detection": {"rms_threshold": 0.2}}}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Preset"
    assert data["overrides"]["detection"]["rms_threshold"] == 0.2


@pytest.mark.asyncio(loop_scope="function")
async def test_create_preset_duplicate_returns_409(client: AsyncClient):
    """Creating a preset with existing name should return 409 Conflict."""
    # Create first preset
    await client.post("/presets", json={"name": "Duplicate Test", "overrides": {}})
    
    # Try to create duplicate
    response = await client.post("/presets", json={"name": "Duplicate Test", "overrides": {}})
    assert response.status_code == 409
    data = response.json()
    assert data["detail"]["code"] == "PRESET_NAME_TAKEN"
    assert data["detail"]["name"] == "Duplicate Test"


@pytest.mark.asyncio(loop_scope="function")
async def test_rename_preset_to_existing_returns_409(client: AsyncClient):
    """Renaming a preset to an existing name should return 409 Conflict."""
    # Create two presets
    res1 = await client.post("/presets", json={"name": "Preset A", "overrides": {}})
    res2 = await client.post("/presets", json={"name": "Preset B", "overrides": {}})
    preset_b_id = res2.json()["id"]
    
    # Try to rename B to A
    response = await client.patch(f"/presets/{preset_b_id}", json={"name": "Preset A"})
    assert response.status_code == 409
    data = response.json()
    assert data["detail"]["code"] == "PRESET_NAME_TAKEN"


@pytest.mark.asyncio(loop_scope="function")
async def test_import_preset_duplicate_returns_409(client: AsyncClient):
    """Importing a preset with existing name should return 409 Conflict."""
    # Create preset
    await client.post("/presets", json={"name": "Import Test", "overrides": {}})
    
    # Try to import with same name
    response = await client.post(
        "/presets/import",
        json={"name": "Import Test", "overrides": {}, "schema_version": 1}
    )
    assert response.status_code == 409
    data = response.json()
    assert data["detail"]["code"] == "PRESET_NAME_TAKEN"
