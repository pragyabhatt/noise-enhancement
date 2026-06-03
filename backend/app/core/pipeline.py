import numpy as np
from app.metrics.baselines import run_hybrid_pipeline

def enhance_audio(noisy: np.ndarray, fs: int = 8000) -> np.ndarray:
    """
    Expose the core hybrid speech‑enhancement pipeline:
    1. VAD (Voice Activity Detection)
    2. Wiener filter spectral pre-filtering
    3. DeepFilterNet2 streaming ONNX inference
    4. Peak limiting
    
    Parameters
    ----------
    noisy : np.ndarray
        1D array containing noisy audio data as float32 in [-1.0, 1.0].
    fs : int
        Sample rate of the audio (default is 8000 Hz).
        
    Returns
    -------
    np.ndarray
        Enhanced speech audio.
    """
    return run_hybrid_pipeline(noisy, fs)
