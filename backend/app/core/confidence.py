import numpy as np
import logging

logger = logging.getLogger("confidence")

def calculate_confidence(
    blind_snr: float,
    gain_db: float,
    dnsmos_delta: float,
    vad_ratio: float
) -> tuple[float, str]:
    """
    Calculate speech enhancement confidence score (0.0 to 1.0) and status.
    blind_snr: Estimated SNR of enhanced signal (dB).
    gain_db: Total attenuation applied (dB).
    dnsmos_delta: Improvement in DNSMOS overall score (post - pre).
    vad_ratio: Percentage of frames containing active speech.
    
    Returns (score, status) where status is:
        - 'OK' (score >= 0.70)
        - 'DEGRADED' (0.40 <= score < 0.70)
        - 'UNRELIABLE' (score < 0.40)
    """
    # 1. Normalize blind SNR (map -5dB..25dB to 0..1)
    snr_norm = np.clip((blind_snr + 5.0) / 30.0, 0.0, 1.0)
    
    # 2. Normalize gain level (we penalize excessive attenuation which indicates severe noise or artifacts)
    # Map 0dB..30dB to 1..0
    gain_norm = np.clip(1.0 - (np.abs(gain_db) / 30.0), 0.0, 1.0)
    
    # 3. Normalize DNSMOS improvement (map -0.5..1.5 to 0..1)
    dnsmos_norm = np.clip((dnsmos_delta + 0.5) / 2.0, 0.0, 1.0)
    
    # 4. Normalize VAD ratio (very low speech ratio indicates background noise or gating artifacts)
    # Map 0%..20% speech to 0..1, keep at 1.0 above 20%
    vad_norm = np.clip(vad_ratio / 0.20, 0.0, 1.0)
    
    # Weighted average:
    # 35% SNR, 25% DNSMOS improvement, 25% Gain level, 15% VAD speech presence
    score = 0.35 * snr_norm + 0.25 * dnsmos_norm + 0.25 * gain_norm + 0.15 * vad_norm
    
    # Safety clamp
    score = float(np.clip(score, 0.0, 1.0))
    
    # Determine classification status
    if score >= 0.70:
        status_label = "OK"
    elif score >= 0.40:
        status_label = "DEGRADED"
    else:
        status_label = "UNRELIABLE"
        
    return round(score, 3), status_label
