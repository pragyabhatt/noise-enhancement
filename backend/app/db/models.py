import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="operator")  # operator, analyst, admin
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    jobs = relationship("ProcessingJob", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    benchmark_runs = relationship("BenchmarkRun", back_populates="user", cascade="all, delete-orphan")
    eval_runs = relationship("EvalRun", back_populates="user", cascade="all, delete-orphan")

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_jti = Column(String, unique=True, index=True, nullable=False)  # JWT token unique identifier
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending, processing, completed, failed
    input_path = Column(String, nullable=False)
    output_path = Column(String, nullable=True)
    input_hash = Column(String, nullable=True)
    output_hash = Column(String, nullable=True)
    model_version = Column(String, nullable=True)
    metrics_json = Column(Text, nullable=True)  # JSON string of SNR, STOI, SI-SDR, confidence, etc.
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="jobs")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String, nullable=False)  # login, process_file, stream, benchmark, audit_view, user_create, etc.
    input_hash = Column(String, nullable=True)
    output_hash = Column(String, nullable=True)
    model_version = Column(String, nullable=True)
    policy = Column(String, nullable=True)  # passthrough, dry-mix, enhanced
    details_json = Column(Text, nullable=True)  # encrypted at rest details (or JSON containing extra metadata)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    dataset_version = Column(String, nullable=False)
    results_json = Column(Text, nullable=False)  # benchmark average results JSON
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="benchmark_runs")

class EvalRun(Base):
    __tablename__ = "eval_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    manifest_path = Column(String, nullable=False)
    results_json = Column(Text, nullable=False)  # batch evaluation results JSON
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="eval_runs")
