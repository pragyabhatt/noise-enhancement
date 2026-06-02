import os
import json
import tempfile
import csv
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from scipy.io import wavfile
import numpy as np

from app.api.auth import get_current_user
from app.db.database import get_db
from app.db import crud
from app.metrics.eval_metrics import compute_seg_snr, compute_stoi, compute_si_sdr
from app.security.crypto import encrypt_file, decrypt_file
from app.config import settings

router = APIRouter(prefix="/eval", tags=["Evaluation System"])

@router.post("/batch")
async def run_batch_evaluation(
    noisy_files: List[UploadFile] = File(..., description="List of noisy speech files"),
    ref_files: List[UploadFile] = File(..., description="List of matching clean reference files"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Upload batches of noisy WAVs and reference clean WAVs.
    Computes SegSNR, STOI, and SI-SDR metrics for matched pairs.
    """
    # 1. Map reference files by filename for easy matching
    ref_map = {f.filename: f for f in ref_files}
    
    evaluation_results = []
    
    # Audit trail details
    input_hashes = []
    
    # Create temporary folder
    with tempfile.TemporaryDirectory() as tmpdir:
        for noisy_file in noisy_files:
            filename = noisy_file.filename
            
            # Find matching clean file
            # Match rules: exact filename, or replace 'noisy' with 'ref'/'clean'
            matched_ref = None
            possible_names = [
                filename,
                filename.replace("noisy", "ref"),
                filename.replace("noisy", "clean"),
                filename.replace("noisy", "ref_clean"),
            ]
            for p_name in possible_names:
                if p_name in ref_map:
                    matched_ref = ref_map[p_name]
                    break
                    
            if not matched_ref:
                # If no direct match, try matching prefix or substring
                for r_name in ref_map.keys():
                    if r_name.split(".")[0] in filename or filename.split(".")[0] in r_name:
                        matched_ref = ref_map[r_name]
                        break
            
            if not matched_ref:
                continue # Skip unmatched files
                
            # Process pair
            noisy_content = await noisy_file.read()
            ref_content = await matched_ref.read()
            
            import hashlib
            input_hashes.append(hashlib.sha256(noisy_content).hexdigest())
            
            # Save to temporary paths to read with scipy
            noisy_path = os.path.join(tmpdir, f"noisy_{filename}")
            ref_path = os.path.join(tmpdir, f"ref_{matched_ref.filename}")
            
            with open(noisy_path, "wb") as f:
                f.write(noisy_content)
            with open(ref_path, "wb") as f:
                f.write(ref_content)
                
            try:
                fs_n, noisy_data = wavfile.read(noisy_path)
                fs_r, ref_data = wavfile.read(ref_path)
                
                # Convert to mono if multi-channel
                if noisy_data.ndim > 1:
                    noisy_data = np.mean(noisy_data, axis=1)
                if ref_data.ndim > 1:
                    ref_data = np.mean(ref_data, axis=1)
                    
                # Convert to float [-1.0, 1.0]
                if noisy_data.dtype == np.int16:
                    noisy_data = noisy_data.astype(np.float32) / 32768.0
                if ref_data.dtype == np.int16:
                    ref_data = ref_data.astype(np.float32) / 32768.0
                    
                # Calculate metrics
                seg_snr = compute_seg_snr(ref_data, noisy_data, fs=fs_n)
                stoi = compute_stoi(ref_data, noisy_data, fs=fs_n)
                si_sdr = compute_si_sdr(ref_data, noisy_data)
                
                evaluation_results.append({
                    "noisy_filename": filename,
                    "ref_filename": matched_ref.filename,
                    "seg_snr": round(seg_snr, 2),
                    "stoi": round(stoi, 4),
                    "si_sdr": round(si_sdr, 2)
                })
            except Exception as e:
                logger.error(f"Error in batch eval for {filename}: {e}")
                continue
                
    if not evaluation_results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No matching noisy/reference speech pairs could be identified by filename."
        )
        
    # Save the run to SQL
    eval_run = await crud.create_eval_run(
        db, 
        user_id=current_user.id, 
        manifest_path="batch_upload", 
        results_json={"results": evaluation_results}
    )
    
    # Audit log
    await crud.create_audit_log(
        db, 
        user_id=current_user.id, 
        action="run_batch_evaluation",
        input_hash=",".join(input_hashes[:3]), # Log first few hashes for audit integrity
        details_json={"eval_run_id": eval_run.id, "pairs_count": len(evaluation_results)}
    )
    
    return {
        "eval_run_id": eval_run.id,
        "pairs_evaluated": len(evaluation_results),
        "results": evaluation_results
    }

@router.get("/report/{run_id}")
async def export_evaluation_report(
    run_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate and download a CSV report for a batch evaluation run.
    """
    # Verify evaluation run exists
    query = crud.select(crud.EvalRun).where(crud.EvalRun.id == run_id)
    result = await db.execute(query)
    eval_run = result.scalar_one_or_none()
    
    if not eval_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found."
        )
        
    results_data = json.loads(eval_run.results_json)
    rows = results_data.get("results", [])
    
    # Write report CSV file
    filename = f"eval_report_{run_id}.csv"
    export_path = os.path.join(settings.EXPORT_DIR, filename)
    
    # Create CSV content
    temp_csv_file = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    temp_csv_path = temp_csv_file.name
    temp_csv_file.close()
    
    try:
        with open(temp_csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Noisy Filename", "Reference Filename", "SegSNR (dB)", "STOI (0-1)", "SI-SDR (dB)"])
            for row in rows:
                writer.writerow([
                    row["noisy_filename"],
                    row["ref_filename"],
                    row["seg_snr"],
                    row["stoi"],
                    row["si_sdr"]
                ])
                
        # Read raw CSV data and encrypt it at rest
        with open(temp_csv_path, "rb") as f:
            csv_bytes = f.read()
            
        encrypt_file(export_path, csv_bytes)
        
    finally:
        if os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)
            
    # Audit log the report generation
    await crud.create_audit_log(
        db, 
        user_id=current_user.id, 
        action="export_eval_report",
        output_hash=hashlib.sha256(csv_bytes).hexdigest() if 'csv_bytes' in locals() else None,
        details_json={"eval_run_id": run_id}
    )
    
    # Decrypt and return report for download (secure transit)
    decrypted_report = decrypt_file(export_path)
    
    return Response(
        content=decrypted_report,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
