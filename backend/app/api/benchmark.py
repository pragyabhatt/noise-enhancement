import os
import time
import json
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from scipy.io import wavfile
import numpy as np

from app.api.auth import get_current_user
from app.db.database import get_db
from app.db import crud
from app.config import settings
from app.security.rbac import allow_operator
from app.metrics.baselines import (
    run_passthrough,
    run_wiener,
    run_df2_only,
    run_rnnoise_baseline,
    run_hybrid_pipeline
)
from app.metrics.eval_metrics import compute_seg_snr, compute_stoi, compute_si_sdr

router = APIRouter(prefix="/benchmark", tags=["Benchmark Engine"])

@router.post("/run")
async def run_baselines_benchmark(
    dataset_version: str = Query("catr_radio_v0.1", description="Dataset version to use"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Run baseline speech-enhancement algorithms (Wiener, RNNoise-Sim, DF2-Only, Hybrid, Passthrough)
    on a test audio file, measure performance metrics (SegSNR, STOI, SI-SDR) and execution latency,
    and save the results to the database.
    """
    # Enforce RBAC
    allow_operator(current_user)
    
    # Locate test sample 600
    noisy_wav_name = "noisy_0600.wav"
    ref_wav_name = "ref_0600.wav"
    
    noisy_path = os.path.join(settings.DATA_DIR, dataset_version, "test", noisy_wav_name)
    ref_path = os.path.join(settings.DATA_DIR, dataset_version, "test", ref_wav_name)
    
    if not os.path.exists(noisy_path) or not os.path.exists(ref_path):
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND,
             detail=f"Benchmark audio files not found at: {noisy_path}"
         )
         
    try:
        # Load audio data using scipy
        fs_n, noisy_data = wavfile.read(noisy_path)
        fs_r, ref_data = wavfile.read(ref_path)
        
        # Convert to mono if stereo
        if noisy_data.ndim > 1:
            noisy_data = np.mean(noisy_data, axis=1)
        if ref_data.ndim > 1:
            ref_data = np.mean(ref_data, axis=1)
            
        # Convert to float32 [-1.0, 1.0]
        if noisy_data.dtype == np.int16:
            noisy_data = noisy_data.astype(np.float32) / 32768.0
        if ref_data.dtype == np.int16:
            ref_data = ref_data.astype(np.float32) / 32768.0
            
        baselines = [
            ("Passthrough", run_passthrough, "No processing (noisy baseline)", "N/A"),
            ("Wiener-Only", run_wiener, "Wiener spectral subtraction", "beta=1.5, g_min=0.1"),
            ("RNNoise-Sim", run_rnnoise_baseline, "RNNoise simulated aggressive Wiener", "beta=2.2, g_min=0.05"),
            ("DF2-Only", run_df2_only, "DeepFilterNet2 neural enhancement only", "ONNX streaming, 8k"),
            ("Hybrid-Pipeline", run_hybrid_pipeline, "DEAL Hybrid Pipeline (Wiener + DF2)", "VAD + Wiener + DF2 + Limiter")
        ]
        
        results = []
        
        for name, run_fn, desc_str, params_str in baselines:
            # Measure execution latency
            start_time = time.time()
            enhanced_audio = run_fn(noisy_data, fs=fs_n)
            latency_ms = (time.time() - start_time) * 1000.0
            
            # Compute evaluation metrics
            seg_snr = compute_seg_snr(ref_data, enhanced_audio, fs=fs_n)
            stoi = compute_stoi(ref_data, enhanced_audio, fs=fs_n)
            si_sdr = compute_si_sdr(ref_data, enhanced_audio)
            
            results.append({
                "model": name,
                "description": desc_str,
                "parameters": params_str,
                "seg_snr": round(seg_snr, 2),
                "stoi": round(stoi, 4),
                "si_sdr": round(si_sdr, 2),
                "latency_ms": round(latency_ms, 2)
            })
            
        # Save run to SQLite database
        benchmark_run = await crud.create_benchmark_run(
            db,
            user_id=current_user.id,
            dataset_version=dataset_version,
            results_json={"results": results}
        )
        
        # Create audit log
        await crud.create_audit_log(
            db,
            user_id=current_user.id,
            action="run_benchmark",
            details_json={"benchmark_run_id": benchmark_run.id, "dataset_version": dataset_version}
        )
        
        return {
            "benchmark_run_id": benchmark_run.id,
            "dataset_version": dataset_version,
            "results": results,
            "created_at": benchmark_run.created_at
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Benchmark execution failed: {str(e)}"
        )

@router.get("/results/{id}")
async def get_benchmark_results(
    id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retrieve results of a past benchmark run.
    """
    allow_operator(current_user)
    
    query = crud.select(crud.BenchmarkRun).where(crud.BenchmarkRun.id == id)
    res = await db.execute(query)
    run = res.scalar_one_or_none()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Benchmark run not found."
        )
        
    results = json.loads(run.results_json) if run.results_json else {}
    
    return {
        "benchmark_run_id": run.id,
        "user_id": run.user_id,
        "dataset_version": run.dataset_version,
        "results": results.get("results", []),
        "created_at": run.created_at
    }
