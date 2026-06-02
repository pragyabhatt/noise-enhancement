import numpy as np
from app.core.vad import VoiceActivityDetector
from app.core.wiener import WienerFilter
from app.core.enhancer_df2 import DeepFilterNet2Enhancer
from app.core.limiter import PeakLimiter

def run_passthrough(noisy: np.ndarray, fs: int = 8000) -> np.ndarray:
    """
    Passthrough baseline (no processing).
    """
    return noisy

def run_wiener(noisy: np.ndarray, fs: int = 8000) -> np.ndarray:
    """
    Wiener Filter-only baseline.
    """
    vad = VoiceActivityDetector(sample_rate=fs)
    wiener = WienerFilter(sample_rate=fs)
    limiter = PeakLimiter(sample_rate=fs)
    
    out = np.zeros_like(noisy)
    frame_size = vad.frame_size
    num_frames = len(noisy) // frame_size
    
    for f in range(num_frames):
        start = f * frame_size
        end = start + frame_size
        frame = noisy[start:end]
        
        is_speech = vad.is_speech(frame)
        enhanced = wiener.process_frame(frame, is_speech)
        limited = limiter.process_frame(enhanced)
        out[start:end] = limited
        
    return out

def run_df2_only(noisy: np.ndarray, fs: int = 8000) -> np.ndarray:
    """
    DeepFilterNet2-only baseline.
    """
    enhancer = DeepFilterNet2Enhancer(sample_rate=fs)
    limiter = PeakLimiter(sample_rate=fs)
    
    out = np.zeros_like(noisy)
    frame_size = enhancer.frame_size
    num_frames = len(noisy) // frame_size
    
    for f in range(num_frames):
        start = f * frame_size
        end = start + frame_size
        frame = noisy[start:end]
        
        enhanced = enhancer.process_frame(frame)
        limited = limiter.process_frame(enhanced)
        out[start:end] = limited
        
    return out

def run_rnnoise_baseline(noisy: np.ndarray, fs: int = 8000) -> np.ndarray:
    """
    RNNoise baseline runner (simulated using standard high-suppression Wiener configuration).
    """
    vad = VoiceActivityDetector(sample_rate=fs)
    wiener = WienerFilter(sample_rate=fs)
    # Configure Wiener filter to act aggressively like RNNoise
    wiener.beta = 2.2
    wiener.g_min = 0.05
    limiter = PeakLimiter(sample_rate=fs)
    
    out = np.zeros_like(noisy)
    frame_size = vad.frame_size
    num_frames = len(noisy) // frame_size
    
    for f in range(num_frames):
        start = f * frame_size
        end = start + frame_size
        frame = noisy[start:end]
        
        is_speech = vad.is_speech(frame)
        enhanced = wiener.process_frame(frame, is_speech)
        limited = limiter.process_frame(enhanced)
        out[start:end] = limited
        
    return out

def run_hybrid_pipeline(noisy: np.ndarray, fs: int = 8000) -> np.ndarray:
    """
    Complete Hybrid Processing Pipeline:
    1. Voice Activity Detection (VAD)
    2. Wiener filter spectral pre-filtering (tracks noise PSD and attenuates stationary noise)
    3. DeepFilterNet2 streaming ONNX inference (fine-grained transient noise suppression)
    4. Look-ahead peak limiting to prevent output clipping
    """
    vad = VoiceActivityDetector(sample_rate=fs)
    wiener = WienerFilter(sample_rate=fs)
    enhancer = DeepFilterNet2Enhancer(sample_rate=fs)
    limiter = PeakLimiter(sample_rate=fs)
    
    out = np.zeros_like(noisy)
    frame_size = vad.frame_size
    num_frames = len(noisy) // frame_size
    
    for f in range(num_frames):
        start = f * frame_size
        end = start + frame_size
        frame = noisy[start:end]
        
        # A. Voice Activity Detection
        is_speech = vad.is_speech(frame)
        
        # B. Wiener spectral pre-filtering
        wiener_enhanced = wiener.process_frame(frame, is_speech)
        
        # C. DeepFilterNet2 enhancement
        if enhancer.use_fallback:
            # If DF2 model weights are missing, avoid double-filtering
            enhanced = wiener_enhanced
        else:
            enhanced = enhancer.process_frame(wiener_enhanced)
            
        # D. Peak Limiting
        limited = limiter.process_frame(enhanced)
        out[start:end] = limited
        
    return out
