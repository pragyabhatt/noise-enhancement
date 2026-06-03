import json
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User, Session, ProcessingJob, AuditLog, BenchmarkRun, EvalRun

# ----------------- USER CRUD -----------------

async def get_user_by_username(db: AsyncSession, username: str) -> User:
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, username: str, password_hash: str, role: str) -> User:
    db_user = User(username=username, password_hash=password_hash, role=role)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def list_users(db: AsyncSession, limit: int = 100, offset: int = 0):
    query = select(User).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

# ----------------- SESSION CRUD -----------------

async def create_session(db: AsyncSession, user_id: int, token_jti: str, expires_at) -> Session:
    db_session = Session(user_id=user_id, token_jti=token_jti, expires_at=expires_at)
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)
    return db_session

async def get_session(db: AsyncSession, token_jti: str) -> Session:
    query = select(Session).where(Session.token_jti == token_jti)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def delete_session(db: AsyncSession, token_jti: str) -> bool:
    db_session = await get_session(db, token_jti)
    if db_session:
        await db.delete(db_session)
        await db.commit()
        return True
    return False

# ----------------- PROCESSING JOBS CRUD -----------------

async def create_processing_job(db: AsyncSession, user_id: int, input_path: str, input_hash: str) -> ProcessingJob:
    db_job = ProcessingJob(user_id=user_id, input_path=input_path, input_hash=input_hash, status="pending")
    db.add(db_job)
    await db.commit()
    await db.refresh(db_job)
    return db_job

async def update_processing_job(
    db: AsyncSession, 
    job_id: int, 
    status: str, 
    output_path: str = None, 
    output_hash: str = None, 
    model_version: str = None, 
    metrics_json: dict = None,
    pre_snr_db: float = None,
    post_snr_db: float = None,
    noise_classification: str = None
) -> ProcessingJob:
    query = select(ProcessingJob).where(ProcessingJob.id == job_id)
    result = await db.execute(query)
    db_job = result.scalar_one_or_none()
    if db_job:
        db_job.status = status
        if output_path is not None:
            db_job.output_path = output_path
        if output_hash is not None:
            db_job.output_hash = output_hash
        if model_version is not None:
            db_job.model_version = model_version
        if metrics_json is not None:
            db_job.metrics_json = json.dumps(metrics_json)
            # Auto-extract and populate columns
            if "pre_snr_db" in metrics_json:
                db_job.pre_snr_db = metrics_json["pre_snr_db"]
            if "post_snr_db" in metrics_json:
                db_job.post_snr_db = metrics_json["post_snr_db"]
            if "noise_class" in metrics_json:
                db_job.noise_classification = metrics_json["noise_class"]
        if pre_snr_db is not None:
            db_job.pre_snr_db = pre_snr_db
        if post_snr_db is not None:
            db_job.post_snr_db = post_snr_db
        if noise_classification is not None:
            db_job.noise_classification = noise_classification
        await db.commit()
        await db.refresh(db_job)
    return db_job

async def get_processing_job(db: AsyncSession, job_id: int) -> ProcessingJob:
    query = select(ProcessingJob).where(ProcessingJob.id == job_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def list_processing_jobs(db: AsyncSession, user_id: int = None, limit: int = 50, offset: int = 0):
    query = select(ProcessingJob)
    if user_id is not None:
        query = query.where(ProcessingJob.user_id == user_id)
    query = query.order_by(desc(ProcessingJob.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

# ----------------- AUDIT LOGS CRUD -----------------

async def create_audit_log(
    db: AsyncSession, 
    user_id: int, 
    action: str, 
    input_hash: str = None, 
    output_hash: str = None, 
    model_version: str = None, 
    policy: str = None, 
    details_json: dict = None
) -> AuditLog:
    db_log = AuditLog(
        user_id=user_id,
        action=action,
        input_hash=input_hash,
        output_hash=output_hash,
        model_version=model_version,
        policy=policy,
        details_json=json.dumps(details_json) if details_json else None
    )
    db.add(db_log)
    await db.commit()
    await db.refresh(db_log)
    return db_log

async def list_audit_logs(
    db: AsyncSession, 
    user_id: int = None, 
    action: str = None, 
    limit: int = 100, 
    offset: int = 0
):
    query = select(AuditLog)
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    if action is not None:
        query = query.where(AuditLog.action == action)
    query = query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

# ----------------- BENCHMARK RUNS CRUD -----------------

async def create_benchmark_run(db: AsyncSession, user_id: int, dataset_version: str, results_json: dict) -> BenchmarkRun:
    db_run = BenchmarkRun(
        user_id=user_id,
        dataset_version=dataset_version,
        results_json=json.dumps(results_json)
    )
    db.add(db_run)
    await db.commit()
    await db.refresh(db_run)
    return db_run

async def get_latest_benchmark_run(db: AsyncSession) -> BenchmarkRun:
    query = select(BenchmarkRun).order_by(desc(BenchmarkRun.created_at)).limit(1)
    result = await db.execute(query)
    return result.scalar_one_or_none()

# ----------------- EVAL RUNS CRUD -----------------

async def create_eval_run(db: AsyncSession, user_id: int, manifest_path: str, results_json: dict) -> EvalRun:
    db_run = EvalRun(
        user_id=user_id,
        manifest_path=manifest_path,
        results_json=json.dumps(results_json)
    )
    db.add(db_run)
    await db.commit()
    await db.refresh(db_run)
    return db_run

async def list_eval_runs(db: AsyncSession, limit: int = 50, offset: int = 0):
    query = select(EvalRun).order_by(desc(EvalRun.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
