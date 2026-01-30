from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Enum, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import enum

Base = declarative_base()

class JobStatus(enum.Enum):
    PENDING = "PENDING"
    UPLOADING = "UPLOADING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    ENCODING = "ENCODING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Asset(Base):
    __tablename__ = "Asset"
    id = Column(String, primary_key=True)
    filename = Column(String)
    path = Column(String)
    createdAt = Column(DateTime, default=datetime.utcnow)

class Job(Base):
    __tablename__ = "Job"
    id = Column(String, primary_key=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    progress = Column(Integer, default=0)
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    assetId = Column(String, ForeignKey("Asset.id"))
    settings = Column(String, nullable=True) # JSON string of settings used

class Segment(Base):
    __tablename__ = "Segment"
    id = Column(String, primary_key=True)
    startTime = Column(Float)
    endTime = Column(Float)
    score = Column(Float)
    label = Column(String, nullable=True)
    jobId = Column(String, ForeignKey("Job.id"))

class Output(Base):
    __tablename__ = "Output"
    id = Column(String, primary_key=True)
    path = Column(String)
    type = Column(String) # "16:9" or "9:16"
    jobId = Column(String, ForeignKey("Job.id"))
