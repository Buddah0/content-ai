import os
import shutil
import uuid
import asyncio
from typing import AsyncGenerator
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import insert, select, update
from databases import Database
from contextlib import asynccontextmanager
from datetime import datetime

from content_ai.api.db_models import Asset, Job, JobStatus, Segment, Output

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

from fastapi.staticfiles import StaticFiles

app = FastAPI(lifespan=lifespan)
app.mount("/outputs", StaticFiles(directory=os.path.join(os.getcwd(), "outputs")), name="outputs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for Requests/Responses ---
class JobCreate(BaseModel):
    assetId: str
    settings: dict | None = None

class JobResponse(BaseModel):
    id: str
    status: str
    progress: int
    assetId: str

# --- MOCK PROCESSING TASK ---
from content_ai.mission_control import run_mission_control_pipeline

async def process_job_task(job_id: str):
    """
    Real processing task that runs the mission control pipeline.
    """
    print(f"Starting job {job_id}")
    
    try:
        # Get Job and Asset
        query = select(Job).where(Job.id == job_id)
        job = await database.fetch_one(query)
        if not job:
            return

        query_asset = select(Asset).where(Asset.id == job.assetId)
        asset = await database.fetch_one(query_asset)
        if not asset:
            return # Should handle error

        # 1. Update status to PROCESSING
        query = update(Job).where(Job.id == job_id).values(status=JobStatus.PROCESSING, progress=0, updatedAt=datetime.utcnow())
        await database.execute(query)
        
        # Output Dir
        output_dir = os.path.join(os.getcwd(), "outputs", job_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # Run Pipeline (Blocking)
        # We can implement progress callbacks later, for now just run it
        # Note: This runs the WHOLE pipeline. Progress updates via database are harder without a callback.
        # But for MVP we can rely on steps.
        
        await database.execute(update(Job).where(Job.id == job_id).values(progress=10, updatedAt=datetime.utcnow()))

        # Run in thread
        # returns [out_16_9, out_9_16], segments
        outputs, segments = await asyncio.to_thread(run_mission_control_pipeline, asset.path, job_id, output_dir)
        
        await database.execute(update(Job).where(Job.id == job_id).values(progress=90, updatedAt=datetime.utcnow()))

        # Insert Segments
        for seg in segments:
            seg_id = str(uuid.uuid4())
            q_seg = insert(Segment).values(
                id=seg_id, 
                startTime=seg["start"], 
                endTime=seg["end"], 
                score=seg["score"], 
                jobId=job_id
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
        query = update(Job).where(Job.id == job_id).values(status=JobStatus.COMPLETED, progress=100, updatedAt=datetime.utcnow())
        await database.execute(query)
        print(f"Job {job_id} completed")
        
    except Exception as e:
        print(f"Job {job_id} failed: {e}")
        import traceback
        traceback.print_exc()
        query = update(Job).where(Job.id == job_id).values(status=JobStatus.FAILED, progress=0, updatedAt=datetime.utcnow())
        await database.execute(query)


# --- API ENDPOINTS ---

@app.get("/")
async def root():
    return {"message": "Content AI Mission Control API", "docs": "/docs", "health": "/health"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

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
    query = insert(Asset).values(id=asset_id, filename=file.filename, path=file_path, createdAt=datetime.utcnow())
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
        
    # Create Job
    query = insert(Job).values(
        id=job_id,
        assetId=job_data.assetId,
        status=JobStatus.PENDING,
        progress=0,
        createdAt=datetime.utcnow(),
        updatedAt=datetime.utcnow()
    )
    await database.execute(query)
    
    # Trigger Processing
    background_tasks.add_task(process_job_task, job_id)
    
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
        "outputs": [{"type": o.type, "path": o.path} for o in outputs]
    }

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
                yield f"data: {{\"status\": \"{job.status.value}\", \"progress\": {job.progress}}}\n\n"
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
