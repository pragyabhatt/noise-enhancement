import numpy as np
from scipy import signal
import logging

logger = logging.getLogger("eval_metrics")

def resample_audio(data: np.ndarray, orig_fs: int, target_fs: int) -> np.ndarray:
    """
    Resample audio helper using polyphase filtering.
    """
    if orig_fs == target_fs:
        return data
    gcd = np.gcd(orig_fs, target_fs)
    up = target_fs // gcd
    down = orig_fs // gcd
    try:
        return signal.resample_poly(data, up, down)
    except Exception:
        num_samples = int(len(data) * target_fs / orig_fs)
        return signal.resample(data, num_samples)

def compute_seg_snr(clean: np.ndarray, enhanced: np.ndarray, fs: int, frame_ms: float = 20.0) -> float:
    """
    Compute Segmental SNR (SegSNR) between clean and enhanced signals.
    Clipped between -10.0 dB and 35.0 dB per frame, and averaged over speech frames.
    """
    # Ensure signals match in length
    min_len = min(len(clean), len(enhanced))
    clean = clean[:min_len]
    enhanced = enhanced[:min_len]
    
    frame_len = int(frame_ms * 1e-3 * fs)
    if frame_len <= 0 or min_len < frame_len:
        return 0.0
        
    num_frames = min_len // frame_len
    snr_frames = []
    
    # Calculate energy threshold for speech frames (exclude silence)
    clean_frames = clean[:num_frames * frame_len].reshape((num_frames, frame_len))
    enhanced_frames = enhanced[:num_frames * frame_len].reshape((num_frames, frame_len))
    
    energies = np.sum(clean_frames ** 2, axis=1) / frame_len
    max_energy = np.max(energies)
    # Speech threshold: -50 dB from max energy frame
    speech_threshold = max_energy * 1e-5
    
    for i in range(num_frames):
        if energies[i] < speech_threshold:
            continue
            
        c_f = clean_frames[i]
        e_f = enhanced_frames[i]
        
        sig_power = np.sum(c_f ** 2)
        noise_power = np.sum((c_f - e_f) ** 2)
        
        snr = 10 * np.log10(sig_power / (noise_power + 1e-12) + 1e-12)
        snr = max(-10.0, min(35.0, snr))
        snr_frames.append(snr)
        
    if not snr_frames:
        return -10.0
        
    return float(np.mean(snr_frames))

def compute_si_sdr(clean: np.ndarray, enhanced: np.ndarray) -> float:
    """
    Compute Scale-Invariant Signal-to-Distortion Ratio (SI-SDR).
    """
    min_len = min(len(clean), len(enhanced))
    clean = clean[:min_len] - np.mean(clean[:min_len])
    enhanced = enhanced[:min_len] - np.mean(enhanced[:min_len])
    
    # Target projection factor alpha
    dot_product = np.dot(clean, enhanced)
    clean_energy = np.dot(clean, clean) + 1e-12
    alpha = dot_product / clean_energy
    
    # Target signal component
    s_target = alpha * clean
    
    # Noise/distortion component
    e_distortion = enhanced - s_target
    
    target_power = np.dot(s_target, s_target)
    distortion_power = np.dot(e_distortion, e_distortion) + 1e-12
    
    sdr = 10 * np.log10(target_power / distortion_power + 1e-12)
    return float(sdr)

def stft_pure(x: np.ndarray, n_fft: int = 256, hop_length: int = 128) -> np.ndarray:
    """
    Helper to compute STFT of a 1D signal using pure NumPy.
    """
    win = np.hamming(n_fft)
    num_frames = (len(x) - n_fft) // hop_length + 1
    if num_frames <= 0:
        return np.zeros((n_fft // 2 + 1, 0))
    
    frames = np.zeros((num_frames, n_fft))
    for i in range(num_frames):
        start = i * hop_length
        frames[i] = x[start : start + n_fft] * win
        
    # FFT along rows
    spectrogram = np.fft.rfft(frames, axis=1)
    return spectrogram.T

def compute_stoi(clean: np.ndarray, enhanced: np.ndarray, fs: int) -> float:
    """
    Compute Short-Time Objective Intelligibility (STOI).
    Uses pystoi if installed, otherwise runs our pure-NumPy 1/3 octave band implementation.
    """
    # 1. Try to use pystoi if available
    try:
        from pystoi import stoi
        # pystoi expects wideband/narrowband. STOI operates on 10kHz sample rate under the hood.
        return float(stoi(clean, enhanced, fs, extended=False))
    except ImportError:
        pass
        
    # 2. Pure NumPy implementation of STOI
    # Resample signals to 10000 Hz (STOI standard)
    fs_stoi = 10000
    c_10k = resample_audio(clean, fs, fs_stoi)
    e_10k = resample_audio(enhanced, fs, fs_stoi)
    
    min_len = min(len(c_10k), len(e_10k))
    if min_len < 256:
        return 0.0
        
    c_10k = c_10k[:min_len]
    e_10k = e_10k[:min_len]
    
    # Compute STFT: window 256 (25.6 ms), hop 128 (12.8 ms)
    n_fft = 256
    hop = 128
    
    c_spec = stft_pure(c_10k, n_fft, hop)
    e_spec = stft_pure(e_10k, n_fft, hop)
    
    # 15 one-third octave bands spanning 150 Hz to 4300 Hz
    # Each band defined by (start_bin, end_bin)
    # Bins map: freq = bin * 10000 / 256 = bin * 39.06
    bands = [
        (3, 4), (4, 5), (5, 6), (6, 8), (8, 10), (10, 12), (12, 15),
        (15, 19), (19, 24), (24, 30), (30, 38), (38, 48), (48, 61),
        (61, 77), (77, 98)
    ]
    
    num_frames = c_spec.shape[1]
    num_bands = len(bands)
    
    # Compute short-time energy envelopes (octave band representation)
    c_env = np.zeros((num_bands, num_frames))
    e_env = np.zeros((num_bands, num_frames))
    
    for j, (start, end) in enumerate(bands):
        c_env[j, :] = np.sqrt(np.sum(np.abs(c_spec[start:end, :]) ** 2, axis=0))
        e_env[j, :] = np.sqrt(np.sum(np.abs(e_spec[start:end, :]) ** 2, axis=0))
        
    # Group frames into segments of N = 30 frames (384 ms)
    N = 30
    if num_frames < N:
        return 0.0
        
    num_segments = num_frames - N + 1
    corr_sum = 0.0
    total_metrics = 0
    
    for m in range(num_segments):
        for j in range(num_bands):
            c_seg = c_env[j, m : m + N]
            e_seg = e_env[j, m : m + N]
            
            c_energy = np.dot(c_seg, c_seg)
            e_energy = np.dot(e_seg, e_seg)
            
            if c_energy < 1e-10:
                continue
                
            # Normalization factor alpha
            alpha = np.sqrt(c_energy / (e_energy + 1e-12))
            e_norm = e_seg * alpha
            
            # Clip degraded signal to -15 dB of clean signal
            clip_val = c_seg * 0.1778  # 10^(-15/20)
            e_clipped = np.maximum(e_norm, clip_val)
            
            # Correlation coefficient
            c_mean = np.mean(c_seg)
            e_mean = np.mean(e_clipped)
            c_zero = c_seg - c_mean
            e_zero = e_clipped - e_mean
            
            c_var = np.dot(c_zero, c_zero)
            e_var = np.dot(e_zero, e_zero)
            
            if c_var < 1e-10 or e_var < 1e-10:
                corr = 1.0 if c_var == e_var else 0.0
            else:
                corr = np.dot(c_zero, e_zero) / np.sqrt(c_var * e_var + 1e-12)
                
            corr_sum += corr
            total_metrics += 1
            
    if total_metrics == 0:
        return 0.0
        
    stoi_score = corr_sum / total_metrics
    return float(np.clip(stoi_score, 0.0, 1.0))

def compute_pesq(clean: np.ndarray, enhanced: np.ndarray, fs: int) -> float:
    """
    Compute PESQ (Perceptual Evaluation of Speech Quality).
    Attempts to import and use the standard `pesq` library, but falls back
    to an approximation if the library is not installed or raises an error (e.g. on Windows).
    """
    try:
        from pesq import pesq
        # PESQ requires 16000 or 8000 Hz sampling rate
        if fs not in [8000, 16000]:
            target_fs = 16000
            clean_resampled = resample_audio(clean, fs, target_fs)
            enhanced_resampled = resample_audio(enhanced, fs, target_fs)
            fs_pesq = target_fs
        else:
            clean_resampled = clean
            enhanced_resampled = enhanced
            fs_pesq = fs
            
        # Ensure correct type (float32 array)
        clean_resampled = clean_resampled.astype(np.float32)
        enhanced_resampled = enhanced_resampled.astype(np.float32)
        
        mode = 'wb' if fs_pesq == 16000 else 'nb'
        return float(pesq(fs_pesq, clean_resampled, enhanced_resampled, mode))
    except Exception as e:
        # Fallback approximation using a heuristic mapped from STOI and SegSNR.
        # PESQ ranges from -0.5 to 4.5.
        stoi_val = compute_stoi(clean, enhanced, fs)
        seg_snr_val = compute_seg_snr(clean, enhanced, fs)
        # Heuristic formula
        approx = 1.0 + 3.0 * stoi_val + 0.05 * min(20.0, max(-10.0, seg_snr_val))
        return float(np.clip(approx, 1.0, 4.5))
