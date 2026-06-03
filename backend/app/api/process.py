import os
import io
import time
import base64
import tempfile
import hashlib
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query, status, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from scipy.io import wavfile
import numpy as np

from app.config import settings
from app.db.database import get_db
from app.db import crud
from app.api.auth import get_current_user
from app.security.rbac import allow_operator
from app.security.crypto import encrypt_file, decrypt_data, encrypt_data
from app.metrics.deploy_metrics import estimate_single_channel_snr, compute_dnsmos
from app.core.confidence import calculate_confidence
from app.core.speaker_sim import SpeakerSimilarityChecker
from app.core.noise_classifier import NoiseProfileClassifier
from app.metrics.baselines import run_hybrid_pipeline

router = APIRouter(prefix="/process", tags=["Processing Engine"])

def process_audio_file_sync(noisy_bytes: bytes, filename: str) -> tuple[bytes, dict]:
    """
    Core audio processing logic:
    1. Read noisy audio.
    2. Resample to 8 kHz (core pipeline target rate).
    3. Run Hybrid Pipeline (VAD -> Wiener -> DF2 ONNX -> Limiter).
    4. Compute deploy-time metrics (SNR, DNSMOS, confidence, speaker similarity, noise classification).
    5. Return enhanced WAV bytes and metrics dict.
    """
    start_time = time.time()
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_in:
        temp_in.write(noisy_bytes)
        temp_in_path = temp_in.name
        
    temp_out_path = temp_in_path + "_enhanced.wav"
    
    try:
        # Load audio
        fs, noisy_data = wavfile.read(temp_in_path)
        
        # Convert to mono if stereo
        if noisy_data.ndim > 1:
            noisy_data = np.mean(noisy_data, axis=1)
            
        # Convert to float [-1.0, 1.0]
        if noisy_data.dtype == np.int16:
            noisy_data = noisy_data.astype(np.float32) / 32768.0
        elif noisy_data.dtype == np.float32:
            pass
        else:
            raise ValueError("Unsupported bit depth.")
            
        # Calculate pre-enhancement metrics
        pre_snr = estimate_single_channel_snr(noisy_data)
        pre_sig, pre_bak, pre_ovr = compute_dnsmos(noisy_data, fs)
        
        # Run hybrid pipeline (operates at 8 kHz)
        # 1. Resample to 8kHz first
        from app.core.radio_chain import resample_audio
        noisy_8k = resample_audio(noisy_data, fs, 8000)
        
        # 2. Run the enhancement chain
        enhanced_8k = run_hybrid_pipeline(noisy_8k, fs=8000)
        
        # Save enhanced file to temp path
        wavfile.write(temp_out_path, 8000, enhanced_8k.astype(np.float32))
        
        # Calculate post-enhancement metrics
        post_snr = estimate_single_channel_snr(enhanced_8k)
        post_sig, post_bak, post_ovr = compute_dnsmos(enhanced_8k, 8000)
        
        # VAD speech ratio
        from app.core.vad import VoiceActivityDetector
        vad = VoiceActivityDetector(sample_rate=8000)
        speech_frames = 0
        frame_size = vad.frame_size
        num_frames = len(enhanced_8k) // frame_size
        for f in range(num_frames):
            frame = enhanced_8k[f*frame_size:(f+1)*frame_size]
            if vad.is_speech(frame):
                speech_frames += 1
        vad_ratio = speech_frames / max(1, num_frames)
        
        # 1. Confidence score
        dnsmos_delta = post_ovr - pre_ovr
        # Gain reduction estimation
        gain_db = float(20 * np.log10(np.std(enhanced_8k) / (np.std(noisy_8k) + 1e-12) + 1e-12))
        confidence_val, confidence_status = calculate_confidence(
            blind_snr=post_snr,
            gain_db=gain_db,
            dnsmos_delta=dnsmos_delta,
            vad_ratio=vad_ratio
        )
        
        # 2. Speaker Similarity
        checker = SpeakerSimilarityChecker()
        similarity = checker.calculate_similarity(noisy_8k, enhanced_8k, fs=8000)
        
        # 3. Noise Classification
        classifier = NoiseProfileClassifier()
        noise_info = classifier.classify_noise(noisy_8k, blind_snr=pre_snr)
        
        # Read enhanced bytes
        with open(temp_out_path, "rb") as f:
            enhanced_bytes = f.read()
            
        latency_ms = (time.time() - start_time) * 1000.0
        
        metrics = {
            "pre_snr_db": round(pre_snr, 2),
            "post_snr_db": round(post_snr, 2),
            "snr_improvement_db": round(post_snr - pre_snr, 2),
            "pre_dnsmos": {"sig": pre_sig, "bak": pre_bak, "ovr": pre_ovr},
            "post_dnsmos": {"sig": post_sig, "bak": post_bak, "ovr": post_ovr},
            "dnsmos_improvement_ovr": round(post_ovr - pre_ovr, 2),
            "confidence_score": confidence_val,
            "confidence_status": confidence_status,
            "speaker_similarity": similarity,
            "noise_class": noise_info["class"],
            "noise_probability": noise_info["probability"],
            "noise_explanation": noise_info["explanation"],
            "latency_ms": round(latency_ms, 2)
        }
        
        return enhanced_bytes, metrics
        
    finally:
        for p in [temp_in_path, temp_out_path]:
            if os.path.exists(p):
                os.remove(p)

async def run_async_job(job_id: int, noisy_bytes: bytes, filename: str, db_session_maker):
    """
    Background worker loop for processing long files asynchronously.
    """
    async with db_session_maker() as db:
        try:
            await crud.update_processing_job(db, job_id, status="processing")
            
            # Run processing
            enhanced_bytes, metrics = process_audio_file_sync(noisy_bytes, filename)
            
            # Save files encrypted
            input_hash = hashlib.sha256(noisy_bytes).hexdigest()
            output_hash = hashlib.sha256(enhanced_bytes).hexdigest()
            
            noisy_enc_path = os.path.join(settings.UPLOAD_DIR, f"noisy_{job_id}.wav.enc")
            enhanced_enc_path = os.path.join(settings.UPLOAD_DIR, f"enhanced_{job_id}.wav.enc")
            
            encrypt_file(noisy_enc_path, noisy_bytes)
            encrypt_file(enhanced_enc_path, enhanced_bytes)
            
            # Update database
            await crud.update_processing_job(
                db, 
                job_id, 
                status="completed", 
                output_path=enhanced_enc_path,
                output_hash=output_hash,
                model_version="catr-se-v0.1-hybrid",
                metrics_json=metrics
            )
            
        except Exception as e:
            logger.error(f"Async processing job {job_id} failed: {e}")
            await crud.update_processing_job(db, job_id, status="failed")

@router.post("/file")
async def process_file_sync(
    file: UploadFile = File(..., description="Uploaded noisy WAV file"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Synchronously upload a noisy WAV audio file, process it, and return
    the quality metrics JSON alongside the base64-encoded enhanced WAV file.
    """
    allow_operator(current_user)
    
    if not file.filename.endswith(".wav"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only WAV files are supported."
        )
        
    content = await file.read()
    if len(content) > 10 * 1024 * 1024: # 10 MB limit for synchronous processing
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large for synchronous processing. Please use /process/file/async instead."
        )
        
    try:
        # Run enhancement pipeline
        enhanced_bytes, metrics = process_audio_file_sync(content, file.filename)
        
        # Hashes for compliance
        input_hash = hashlib.sha256(content).hexdigest()
        output_hash = hashlib.sha256(enhanced_bytes).hexdigest()
        
        # Encrypt files to disk
        # Create temp DB job to reserve ID
        job = await crud.create_processing_job(db, user_id=current_user.id, input_path=file.filename, input_hash=input_hash)
        
        noisy_enc_path = os.path.join(settings.UPLOAD_DIR, f"noisy_{job.id}.wav.enc")
        enhanced_enc_path = os.path.join(settings.UPLOAD_DIR, f"enhanced_{job.id}.wav.enc")
        
        encrypt_file(noisy_enc_path, content)
        encrypt_file(enhanced_enc_path, enhanced_bytes)
        
        # Complete job record
        await crud.update_processing_job(
            db, 
            job_id=job.id, 
            status="completed", 
            output_path=enhanced_enc_path,
            output_hash=output_hash,
            model_version="catr-se-v0.1-hybrid",
            metrics_json=metrics
        )
        
        # Create audit log
        await crud.create_audit_log(
            db, 
            user_id=current_user.id, 
            action="process_file_sync",
            input_hash=input_hash,
            output_hash=output_hash,
            model_version="catr-se-v0.1-hybrid",
            policy="enhanced",
            details_json={"job_id": job.id, "filename": file.filename}
        )
        
        # Base64 encode the enhanced audio bytes for transit in JSON
        enhanced_b64 = base64.b64encode(enhanced_bytes).decode("utf-8")
        
        return {
            "job_id": job.id,
            "status": "completed",
            "filename": file.filename,
            "metrics": metrics,
            "audio_base64": enhanced_b64
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio enhancement processing failed: {str(e)}"
        )

@router.post("/file/async", status_code=status.HTTP_202_ACCEPTED)
async def process_file_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Uploaded noisy WAV file"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Asynchronously upload a noisy WAV audio file, trigger background processing,
    and return a job ID immediately for status polling.
    """
    allow_operator(current_user)
    
    if not file.filename.endswith(".wav"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only WAV files are supported."
        )
        
    content = await file.read()
    input_hash = hashlib.sha256(content).hexdigest()
    
    # Save pending job to SQLite
    job = await crud.create_processing_job(db, user_id=current_user.id, input_path=file.filename, input_hash=input_hash)
    
    # Create audit log
    await crud.create_audit_log(
        db, 
        user_id=current_user.id, 
        action="process_file_async_trigger",
        input_hash=input_hash,
        details_json={"job_id": job.id, "filename": file.filename}
    )
    
    # Trigger async worker
    background_tasks.add_task(
        run_async_job, 
        job_id=job.id, 
        noisy_bytes=content, 
        filename=file.filename, 
        db_session_maker=crud.AsyncSessionLocal
    )
    
    return {
        "job_id": job.id,
        "status": "pending",
        "detail": "Job submitted. Poll status using GET /process/jobs/{id}"
    }

@router.get("/jobs/{id}")
async def get_job_status(
    id: int,
    download: bool = Query(False, description="Set to true to download the enhanced WAV file"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve job status, metrics details, or download the decrypted enhanced audio file.
    """
    allow_operator(current_user)
    
    job = await crud.get_processing_job(db, job_id=id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found."
        )
        
    if download:
        if job.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot download file. Job is in '{job.status}' status."
            )
            
        if not job.output_path or not os.path.exists(job.output_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Enhanced audio file not found on disk."
            )
            
        # Decrypt file at rest
        from app.security.crypto import decrypt_file
        try:
            decrypted_bytes = decrypt_file(job.output_path)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Decryption failure: {str(e)}"
            )
            
        # Audit log the download action
        await crud.create_audit_log(
            db, 
            user_id=current_user.id, 
            action="download_job_file",
            output_hash=job.output_hash,
            details_json={"job_id": id}
        )
        
        # Return WAV file
        filename = f"enhanced_{id}.wav"
        return Response(
            content=decrypted_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    # Return JSON Status
    metrics = json.loads(job.metrics_json) if job.metrics_json else None
    
    return {
        "job_id": job.id,
        "status": job.status,
        "input_filename": job.input_path,
        "input_hash": job.input_hash,
        "output_hash": job.output_hash,
        "model_version": job.model_version,
        "metrics": metrics,
        "created_at": job.created_at
    }

@router.get("/jobs")
async def get_jobs_list(
    limit: int = Query(50, ge=1, le=100, description="Max jobs to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List recent audio processing jobs.
    """
    allow_operator(current_user)
    
    count_query = select(func.count(ProcessingJob.id))
    count_res = await db.execute(count_query)
    total_count = count_res.scalar() or 0
    
    jobs = await crud.list_processing_jobs(db, limit=limit, offset=offset)
    
    result = []
    for job in jobs:
        metrics = json.loads(job.metrics_json) if job.metrics_json else None
        result.append({
            "job_id": job.id,
            "status": job.status,
            "input_filename": job.input_path,
            "input_hash": job.input_hash,
            "output_hash": job.output_hash,
            "model_version": job.model_version,
            "pre_snr_db": round(job.pre_snr_db, 2) if job.pre_snr_db is not None else None,
            "post_snr_db": round(job.post_snr_db, 2) if job.post_snr_db is not None else None,
            "noise_classification": job.noise_classification or "unknown",
            "metrics": metrics,
            "created_at": job.created_at
        })
        
    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "jobs": result
    }

@router.get("/jobs/{id}/download")
async def download_job_file_direct(
    id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download the enhanced WAV file directly.
    """
    return await get_job_status(id=id, download=True, current_user=current_user, db=db)
