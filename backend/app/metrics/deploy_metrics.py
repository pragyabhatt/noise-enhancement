import numpy as np
from scipy import signal
import logging

logger = logging.getLogger("deploy_metrics")

def estimate_single_channel_snr(signal_data: np.ndarray, frame_size: int = 320) -> float:
    """
    Estimate the Signal-to-Noise Ratio (SNR) of a single-channel speech signal without a clean reference.
    Uses percentile-based energy estimation across short frames.
    """
    if len(signal_data) < frame_size:
        return 0.0
        
    num_frames = len(signal_data) // frame_size
    # Reshape and compute energy per frame
    frames = np.reshape(signal_data[:num_frames * frame_size], (num_frames, frame_size))
    energies = np.sum(frames ** 2, axis=1) / frame_size
    energies = np.clip(energies, 1e-12, None)
    energies_db = 10 * np.log10(energies)
    
    # 90th percentile represents active speech level
    speech_level_db = np.percentile(energies_db, 90)
    # 10th percentile represents quiet noise floor level
    noise_level_db = np.percentile(energies_db, 10)
    
    snr = float(speech_level_db - noise_level_db)
    return max(-20.0, min(40.0, snr))

def compute_dnsmos(signal_data: np.ndarray, fs: int) -> tuple[float, float, float]:
    """
    Microsoft DNSMOS P.835 Reference-Free Speech Quality Scoring Approximation.
    Returns (SIG, BAK, OVR) scores on a scale of [1.0, 5.0]:
        SIG: Speech Quality MOS
        BAK: Background Noise Intrusiveness MOS
        OVR: Overall quality MOS
    """
    # 1. Resample to 16kHz standard for DNSMOS computations
    if fs != 16000:
        gcd = np.gcd(fs, 16000)
        up = 16000 // gcd
        down = fs // gcd
        try:
            signal_data = signal.resample_poly(signal_data, up, down)
        except Exception:
            num_samples = int(len(signal_data) * 16000 / fs)
            signal_data = signal.resample(signal_data, num_samples)
            
    # 2. Extract energy features
    frame_size = 320 # 20 ms frame at 16 kHz
    if len(signal_data) < frame_size:
        return 3.0, 3.0, 3.0
        
    num_frames = len(signal_data) // frame_size
    frames = np.reshape(signal_data[:num_frames * frame_size], (num_frames, frame_size))
    energies = np.sum(frames ** 2, axis=1) / frame_size
    energies = np.clip(energies, 1e-12, None)
    energies_db = 10 * np.log10(energies)
    
    speech_level_db = np.percentile(energies_db, 90)
    noise_level_db = np.percentile(energies_db, 10)
    estimated_snr = float(speech_level_db - noise_level_db)
    
    # 3. Sigmoidal modeling of P.835 quality scores
    # SIG: Speech Quality MOS [1.0, 5.0]
    sig_val = 1.2 + 3.8 / (1.0 + np.exp(-0.16 * (estimated_snr - 5.0)))
    sig_val = max(1.0, min(5.0, sig_val))
    
    # BAK: Background noise intrusiveness [1.0, 5.0]
    bak_val = 1.0 + 4.0 / (1.0 + np.exp(-0.21 * (estimated_snr - 0.0)))
    bak_val = max(1.0, min(5.0, bak_val))
    
    # OVR: Overall quality [1.0, 5.0]
    ovr_val = 1.1 + 3.9 / (1.0 + np.exp(-0.18 * (estimated_snr - 3.0)))
    ovr_val = max(1.0, min(5.0, ovr_val))
    
    return round(sig_val, 2), round(bak_val, 2), round(ovr_val, 2)
