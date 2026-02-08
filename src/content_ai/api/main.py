from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from databases import Database
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import delete, insert, select, update
from sqlite3 import IntegrityError

from content_ai.api.db_models import Asset, ConfigPreset, Job, JobStatus, Output, Segment
from content_ai.mission_control import run_mission_control_pipeline
from content_ai.config import resolve_config
from content_ai.presets import (
    CURRENT_SCHEMA_VERSION,
    apply_overrides,
    compute_overrides,
    migrate_overrides,
    resolve_with_preset,
)

# --- CONFIG ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./content_ai.db")
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

database = Database(DATABASE_URL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    yield
    await database.disconnect()


app = FastAPI(lifespan=lifespan)
app.mount("/outputs", StaticFiles(directory=os.path.join(os.getcwd(), "outputs")), name="outputs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIG ENDPOINT ---
@app.get("/config/defaults")
async def get_config_defaults():
    config = resolve_config()
    if hasattr(config, "model_dump"):
        return config.model_dump()
    return config


# --- Pydantic Models for Requests/Responses ---
class JobCreate(BaseModel):
    assetId: str  # noqa: N815
    settings: dict | None = None
    presetId: str | None = None  # noqa: N815


class JobResponse(BaseModel):
    id: str
    status: str
    progress: int
    assetId: str  # noqa: N815


# --- Preset Pydantic Models ---
class PresetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    overrides: dict = Field(default_factory=dict)


class PresetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    overrides: dict | None = None


class PresetResponse(BaseModel):
    id: str
    name: str
    description: str | None
    overrides: dict
    schema_version: int
    createdAt: str  # noqa: N815
    updatedAt: str  # noqa: N815


# --- CONFIG SCHEMA ENDPOINT ---
@app.get("/config/schema")
async def get_config_schema():
    """Return JSON Schema for the config model."""
    from content_ai.models import ContentAIConfig
    return ContentAIConfig.model_json_schema()


# --- MOCK PROCESSING TASK ---


async def process_job_task(job_id: str, settings: dict = None):
    """
    Real processing task that runs the mission control pipeline.
    """
    print(f"Starting job {job_id} with settings: {settings}")

    try:
        # Get Asset
        query = select(Job).where(Job.id == job_id)
        job = await database.fetch_one(query)
        if not job:
            return

        query_asset = select(Asset).where(Asset.id == job.assetId)
        asset = await database.fetch_one(query_asset)
        if not asset:
            return

        # 1. Update status to PROCESSING
        query = (
            update(Job)
            .where(Job.id == job_id)
            .values(status=JobStatus.PROCESSING, progress=0, updatedAt=datetime.utcnow())
        )
        await database.execute(query)

        # Output Dir
        output_dir = os.path.join(os.getcwd(), "outputs", job_id)
        os.makedirs(output_dir, exist_ok=True)

        await database.execute(
            update(Job).where(Job.id == job_id).values(progress=10, updatedAt=datetime.utcnow())
        )

        # Run in thread
        outputs, segments = await asyncio.to_thread(
            run_mission_control_pipeline, asset.path, job_id, output_dir, settings
        )

        await database.execute(
            update(Job).where(Job.id == job_id).values(progress=90, updatedAt=datetime.utcnow())
        )

        # Insert Segments
        for seg in segments:
            seg_id = str(uuid.uuid4())
            q_seg = insert(Segment).values(
                id=seg_id,
                startTime=seg["start"],
                endTime=seg["end"],
                score=seg["score"],
                jobId=job_id,
            )
            await database.execute(q_seg)

        # Insert Outputs
        for out_path in outputs:
            out_id = str(uuid.uuid4())
            out_type = "16:9" if "16_9" in out_path else "9:16"
            # Relativize path for API
            rel_path = os.path.relpath(out_path, os.getcwd())
            q_out = insert(Output).values(id=out_id, path=rel_path, type=out_type, jobId=job_id)
            await database.execute(q_out)

        # Complete
        query = (
            update(Job)
            .where(Job.id == job_id)
            .values(status=JobStatus.COMPLETED, progress=100, updatedAt=datetime.utcnow())
        )
        await database.execute(query)
        print(f"Job {job_id} completed")

    except Exception as e:
        print(f"Job {job_id} failed: {e}")
        import traceback

        traceback.print_exc()
        query = (
            update(Job)
            .where(Job.id == job_id)
            .values(status=JobStatus.FAILED, progress=0, updatedAt=datetime.utcnow())
        )
        await database.execute(query)


# --- API ENDPOINTS ---


@app.get("/")
async def root():
    return {"message": "Content AI Mission Control API", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# --- PRESET ENDPOINTS ---

def _preset_to_response(preset) -> dict:
    """Convert DB preset row to response dict."""
    return {
        "id": preset.id,
        "name": preset.name,
        "description": preset.description,
        "overrides": json.loads(preset.overrides) if preset.overrides else {},
        "schema_version": preset.schema_version,
        "createdAt": preset.createdAt.replace(tzinfo=timezone.utc).isoformat() if preset.createdAt else None,
        "updatedAt": preset.updatedAt.replace(tzinfo=timezone.utc).isoformat() if preset.updatedAt else None,
    }


@app.get("/presets")
async def list_presets():
    """List all presets."""
    query = select(ConfigPreset).order_by(ConfigPreset.name)
    presets = await database.fetch_all(query)
    return [_preset_to_response(p) for p in presets]


@app.post("/presets", status_code=201)
async def create_preset(data: PresetCreate):
    """Create a new preset. Name must be unique (409 if taken)."""
    preset_id = str(uuid.uuid4())
    
    try:
        query = insert(ConfigPreset).values(
            id=preset_id,
            name=data.name,
            description=data.description,
            overrides=json.dumps(data.overrides),
            schema_version=CURRENT_SCHEMA_VERSION,
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow(),
        )
        await database.execute(query)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PRESET_NAME_TAKEN",
                "message": "Preset name already exists",
                "name": data.name,
            },
        )

    # Fetch and return the created preset
    query = select(ConfigPreset).where(ConfigPreset.id == preset_id)
    preset = await database.fetch_one(query)
    return _preset_to_response(preset)


@app.get("/presets/{preset_id}")
async def get_preset(preset_id: str):
    """Get a preset by ID."""
    query = select(ConfigPreset).where(ConfigPreset.id == preset_id)
    preset = await database.fetch_one(query)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    return _preset_to_response(preset)


@app.patch("/presets/{preset_id}")
async def update_preset(preset_id: str, data: PresetUpdate):
    """Update a preset. Renaming to existing name returns 409."""
    # Check preset exists
    query = select(ConfigPreset).where(ConfigPreset.id == preset_id)
    preset = await database.fetch_one(query)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    # Build update values
    update_values = {"updatedAt": datetime.utcnow()}
    if data.name is not None:
        update_values["name"] = data.name
    if data.description is not None:
        update_values["description"] = data.description
    if data.overrides is not None:
        update_values["overrides"] = json.dumps(data.overrides)
    
    try:
        query = update(ConfigPreset).where(ConfigPreset.id == preset_id).values(**update_values)
        await database.execute(query)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PRESET_NAME_TAKEN",
                "message": "Preset name already exists",
                "name": data.name,
            },
        )

    # Fetch and return updated preset
    query = select(ConfigPreset).where(ConfigPreset.id == preset_id)
    preset = await database.fetch_one(query)
    return _preset_to_response(preset)


@app.delete("/presets/{preset_id}")
async def delete_preset(preset_id: str):
    """Delete a preset by ID."""
    query = select(ConfigPreset).where(ConfigPreset.id == preset_id)
    preset = await database.fetch_one(query)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    await database.execute(delete(ConfigPreset).where(ConfigPreset.id == preset_id))
    return {"status": "deleted", "id": preset_id}


@app.post("/presets/{preset_id}/export")
async def export_preset(preset_id: str):
    """Export a preset as a portable JSON object."""
    query = select(ConfigPreset).where(ConfigPreset.id == preset_id)
    preset = await database.fetch_one(query)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    return {
        "name": preset.name,
        "description": preset.description,
        "overrides": json.loads(preset.overrides) if preset.overrides else {},
        "schema_version": preset.schema_version,
    }


@app.post("/presets/import", status_code=201)
async def import_preset(data: dict):
    """Import a preset. Name must be unique (409 if taken)."""
    name = data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Preset name is required")
    
    preset_id = str(uuid.uuid4())
    overrides = data.get("overrides", {})
    description = data.get("description")
    schema_version = data.get("schema_version", 1)
    
    # Migrate if needed
    if schema_version < CURRENT_SCHEMA_VERSION:
        try:
            overrides = migrate_overrides(overrides, schema_version)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif schema_version > CURRENT_SCHEMA_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Preset schema version {schema_version} is newer than supported version {CURRENT_SCHEMA_VERSION}",
        )
    
    try:
        query = insert(ConfigPreset).values(
            id=preset_id,
            name=name,
            description=description,
            overrides=json.dumps(overrides),
            schema_version=CURRENT_SCHEMA_VERSION,
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow(),
        )
        await database.execute(query)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PRESET_NAME_TAKEN",
                "message": "Preset name already exists",
                "name": name,
            },
        )
    
    query = select(ConfigPreset).where(ConfigPreset.id == preset_id)
    preset = await database.fetch_one(query)
    return _preset_to_response(preset)


@app.get("/jobs")
async def list_jobs():
    """List all jobs, most recent first."""
    query = select(Job).order_by(Job.createdAt.desc())
    jobs = await database.fetch_all(query)
    return [
        {
            "id": job.id,
            "status": job.status.value if hasattr(job.status, "value") else job.status,
            "progress": job.progress,
            "createdAt": job.createdAt.replace(tzinfo=timezone.utc).isoformat()
            if job.createdAt
            else None,
            "assetId": job.assetId,
        }
        for job in jobs
    ]


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1]
    asset_id = str(uuid.uuid4())
    filename = f"{asset_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create Asset in DB
    query = insert(Asset).values(
        id=asset_id, filename=file.filename, path=file_path, createdAt=datetime.utcnow()
    )
    await database.execute(query)

    return {"assetId": asset_id, "filename": file.filename}


@app.post("/jobs")
async def create_job(job_data: JobCreate, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())

    # Verify asset exists
    query = select(Asset).where(Asset.id == job_data.assetId)
    asset = await database.fetch_one(query)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # 1. Load defaults
    defaults = resolve_config()
    if hasattr(defaults, "model_dump"):
        defaults_dict = defaults.model_dump()
    else:
        defaults_dict = defaults

    # 2. Load preset overrides if provided
    preset_overrides = None
    if job_data.presetId:
        query = select(ConfigPreset).where(ConfigPreset.id == job_data.presetId)
        preset = await database.fetch_one(query)
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        # Migrate if needed
        raw_overrides = json.loads(preset.overrides) if preset.overrides else {}
        preset_overrides = migrate_overrides(raw_overrides, preset.schema_version)

    # 3. Merge: defaults -> preset -> request overrides
    merged = defaults_dict
    if preset_overrides:
        merged = apply_overrides(merged, preset_overrides)
    if job_data.settings:
        merged = apply_overrides(merged, job_data.settings)

    # 4. Validate merged config
    from content_ai.models import ContentAIConfig
    try:
        validated = ContentAIConfig.from_dict(merged)
        # Start from merged dict to preserve extra top-level keys (e.g. showCaptions,
        # showWatermark) that Pydantic validation would strip, then overlay validated fields.
        resolved_config = dict(merged)
        resolved_config.update(validated.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid config: {e}")

    # 5. Persist job with resolved config snapshot
    config_source = {
        "preset_id": job_data.presetId,
        "request_overrides": job_data.settings,
        "schema_version": CURRENT_SCHEMA_VERSION,
    }
    
    settings_json = json.dumps({
        "resolved_config": resolved_config,
        "config_source": config_source,
    })

    query = insert(Job).values(
        id=job_id,
        assetId=job_data.assetId,
        settings=settings_json,
        status=JobStatus.PENDING,
        progress=0,
        createdAt=datetime.utcnow(),
        updatedAt=datetime.utcnow(),
    )
    await database.execute(query)

    # 6. Trigger Processing with resolved config
    background_tasks.add_task(process_job_task, job_id, resolved_config)

    return {"id": job_id, "status": "PENDING"}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    # Fetch job with segments and outputs
    # Using simple queries for now
    q_job = select(Job).where(Job.id == job_id)
    job = await database.fetch_one(q_job)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    q_segs = select(Segment).where(Segment.jobId == job_id)
    segments = await database.fetch_all(q_segs)

    q_outs = select(Output).where(Output.jobId == job_id)
    outputs = await database.fetch_all(q_outs)

    return {
        "id": job.id,
        "status": job.status.value,
        "progress": job.progress,
        "segments": [{"startTime": s.startTime, "endTime": s.endTime} for s in segments],
        "outputs": [{"type": o.type, "path": o.path} for o in outputs],
    }


@app.get("/jobs/{job_id}/config")
async def get_job_config(job_id: str):
    """Get the resolved config snapshot used for a job."""
    q_job = select(Job).where(Job.id == job_id)
    job = await database.fetch_one(q_job)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.settings:
        settings_data = json.loads(job.settings)
        return {
            "resolved_config": settings_data.get("resolved_config"),
            "config_source": settings_data.get("config_source"),
        }
    return {"resolved_config": None, "config_source": None}


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated data."""
    # Check execution status - for now we just delete from DB
    q_job = select(Job).where(Job.id == job_id)
    job = await database.fetch_one(q_job)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Delete related data
    await database.execute(delete(Output).where(Output.jobId == job_id))
    await database.execute(delete(Segment).where(Segment.jobId == job_id))
    
    # Delete job
    await database.execute(delete(Job).where(Job.id == job_id))
    
    return {"status": "deleted", "id": job_id}


async def event_generator(job_id: str, request: Request) -> AsyncGenerator[str, None]:
    """
    SSE generator that yields job status updates.
    """
    last_progress = -1
    last_status = None

    while True:
        if await request.is_disconnected():
            break

        query = select(Job).where(Job.id == job_id)
        job = await database.fetch_one(query)

        if job:
            if job.progress != last_progress or job.status.value != last_status:
                yield f'data: {{"status": "{job.status.value}", "progress": {job.progress}}}\n\n'
                last_progress = job.progress
                last_status = job.status.value

            if job.status.value in ["COMPLETED", "FAILED"]:
                break

        await asyncio.sleep(0.5)


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    return StreamingResponse(event_generator(job_id, request), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
