import os
import tempfile
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from scipy.io import wavfile
import numpy as np

from app.api.auth import get_current_user
from app.metrics.deploy_metrics import estimate_single_channel_snr, compute_dnsmos
from app.db.database import get_db
from app.db import crud

router = APIRouter(prefix="/metrics", tags=["Metrics Calculation"])

@router.post("/deploy")
async def calculate_deploy_metrics(
    file: UploadFile = File(..., description="Uploaded noisy speech audio (.wav)"),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
) -> Dict[str, Any]:
    """
    Calculate blind (reference-free) deploy metrics for an uploaded noisy speech recording.
    """
    if not file.filename.endswith(".wav"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only WAV files are supported."
        )
        
    # Read file content safely
    content = await file.read()
    if len(content) > 25 * 1024 * 1024: # 25 MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum limit of 25 MB."
        )
        
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
        temp_wav.write(content)
        temp_path = temp_wav.name
        
    try:
        # Load audio using scipy
        fs, data = wavfile.read(temp_path)
        
        # Check channels, convert to mono if stereo
        if data.ndim > 1:
            data = np.mean(data, axis=1)
            
        # Convert to float [-1.0, 1.0]
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.float32:
            pass
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported bit depth. Please upload a standard 16-bit PCM WAV file."
            )
            
        # Compute blind SNR
        blind_snr = estimate_single_channel_snr(data)
        
        # Compute DNSMOS
        sig, bak, ovr = compute_dnsmos(data, fs)
        
        # Audit log the metrics query
        # Hash input file for compliance auditing
        import hashlib
        input_hash = hashlib.sha256(content).hexdigest()
        
        await crud.create_audit_log(
            db, 
            user_id=current_user.id, 
            action="calculate_deploy_metrics",
            input_hash=input_hash,
            details_json={
                "filename": file.filename,
                "duration_seconds": len(data) / fs,
                "sampling_rate": fs
            }
        )
        
        return {
            "filename": file.filename,
            "blind_snr_db": round(blind_snr, 2),
            "dnsmos_sig": sig,
            "dnsmos_bak": bak,
            "dnsmos_ovr": ovr
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process audio metrics: {str(e)}"
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
