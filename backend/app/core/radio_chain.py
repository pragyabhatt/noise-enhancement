import numpy as np
from scipy import signal
import logging

logger = logging.getLogger("radio_chain")

def resample_audio(data: np.ndarray, orig_fs: int, target_fs: int) -> np.ndarray:
    """
    Resample audio using scipy's polyphase filtering.
    """
    if orig_fs == target_fs:
        return data
    
    gcd = np.gcd(orig_fs, target_fs)
    up = target_fs // gcd
    down = orig_fs // gcd
    
    # Check if ratio is too large, fallback to simple interpolation
    if up > 1000 or down > 1000:
        duration = len(data) / orig_fs
        num_samples = int(duration * target_fs)
        x_old = np.linspace(0, duration, len(data))
        x_new = np.linspace(0, duration, num_samples)
        return np.interp(x_new, x_old, data)
        
    try:
        return signal.resample_poly(data, up, down)
    except Exception as e:
        logger.warning(f"resample_poly failed: {e}. Falling back to standard resample.")
        num_samples = int(len(data) * target_fs / orig_fs)
        return signal.resample(data, num_samples)

def g711_compress(x: np.ndarray, mode: str = "mu") -> np.ndarray:
    """
    Compress 16-bit linear PCM signal to 8-bit G.711 A-law or mu-law.
    Input signal x should be scaled between -1.0 and 1.0.
    Returns uint8 array of encoded values [0, 255].
    """
    x = np.clip(x, -1.0, 1.0)
    if mode.lower() == "mu":
        mu = 255.0
        encoded = np.sign(x) * np.log(1.0 + mu * np.abs(x)) / np.log(1.0 + mu)
        # Map [-1.0, 1.0] to [0, 255]
        encoded_uint8 = np.round((encoded + 1.0) * 127.5)
        return np.clip(encoded_uint8, 0, 255).astype(np.uint8)
    elif mode.lower() == "a":
        A = 87.6
        abs_x = np.abs(x)
        mask1 = abs_x < (1.0 / A)
        mask2 = ~mask1
        
        encoded = np.zeros_like(x)
        encoded[mask1] = (A * abs_x[mask1]) / (1.0 + np.log(A))
        encoded[mask2] = (1.0 + np.log(A * abs_x[mask2])) / (1.0 + np.log(A))
        
        encoded = np.sign(x) * encoded
        # Map [-1.0, 1.0] to [0, 255]
        encoded_uint8 = np.round((encoded + 1.0) * 127.5)
        return np.clip(encoded_uint8, 0, 255).astype(np.uint8)
    else:
        raise ValueError("Invalid G.711 mode. Use 'mu' or 'a'.")

def g711_expand(encoded: np.ndarray, mode: str = "mu") -> np.ndarray:
    """
    Expand 8-bit G.711 A-law or mu-law back to linear PCM signal in [-1.0, 1.0].
    Input encoded should be a uint8 array.
    """
    encoded_f = (encoded.astype(np.float32) / 127.5) - 1.0
    encoded_f = np.clip(encoded_f, -1.0, 1.0)
    
    if mode.lower() == "mu":
        mu = 255.0
        decoded = np.sign(encoded_f) * ((1.0 + mu) ** np.abs(encoded_f) - 1.0) / mu
        return decoded
    elif mode.lower() == "a":
        A = 87.6
        abs_e = np.abs(encoded_f)
        limit = 1.0 / (1.0 + np.log(A))
        mask1 = abs_e < limit
        mask2 = ~mask1
        
        decoded = np.zeros_like(encoded_f)
        decoded[mask1] = (abs_e[mask1] * (1.0 + np.log(A))) / A
        decoded[mask2] = np.exp(abs_e[mask2] * (1.0 + np.log(A)) - 1.0) / A
        return np.sign(encoded_f) * decoded
    else:
        raise ValueError("Invalid G.711 mode. Use 'mu' or 'a'.")

def levinson_durbin(r: np.ndarray, p: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Solve Yule-Walker equations using Levinson-Durbin recursion.
    r: Autocorrelation coefficients (length p + 1)
    p: Prediction order
    Returns (a, k) where:
        a: Predictor coefficients of length p
        k: Reflection coefficients of length p
    """
    a = np.zeros(p + 1)
    a[0] = 1.0
    k = np.zeros(p)
    
    # Regularization: add a tiny noise floor to autocorrelation to prevent division by zero
    r_reg = r.copy()
    r_reg[0] = r_reg[0] * 1.0001 + 1e-9
    
    E = r_reg[0]
    
    for i in range(1, p + 1):
        s = 0.0
        for j in range(i):
            s += a[j] * r_reg[i - j]
        
        if np.abs(E) < 1e-9:
            break
            
        ki = -s / E
        
        # Clip reflection coefficients to maintain filter stability
        if np.abs(ki) >= 0.999:
            ki = np.sign(ki) * 0.999
            
        k[i - 1] = ki
        
        a_new = np.zeros(p + 1)
        a_new[0] = 1.0
        for j in range(1, i):
            a_new[j] = a[j] + ki * a[i - j]
        a_new[i] = ki
        a = a_new
        
        E = E * (1.0 - ki**2)
        if E <= 1e-9:
            break
            
    return a[1:], k

def k_to_a(k: np.ndarray) -> np.ndarray:
    """
    Reconstruct predictor coefficients 'a' from reflection coefficients 'k'.
    """
    p = len(k)
    a = np.zeros(p + 1)
    a[0] = 1.0
    for i in range(1, p + 1):
        ki = k[i - 1]
        a_new = np.zeros(p + 1)
        a_new[0] = 1.0
        for j in range(1, i):
            a_new[j] = a[j] + ki * a[i - j]
        a_new[i] = ki
        a = a_new
    return a[1:]

def amr_simulate(x: np.ndarray, p: int = 10, frame_size: int = 160) -> np.ndarray:
    """
    Simulate AMR-NB speech codec channel effects:
    1. Bandpass filter (300Hz - 3.4kHz) representing telephone-grade audio.
    2. LPC analysis to model vocal tract envelope.
    3. Reflection coefficient quantization to ensure stable restoration.
    4. Residual excitation quantization (representing ACELP codebook approximation).
    5. Synthesis filtering.
    """
    # 1. Bandpass Filter
    nyq = 8000 / 2.0
    b, a_filter = signal.butter(4, [300.0 / nyq, 3400.0 / nyq], btype="band")
    x_filtered = signal.lfilter(b, a_filter, x)
    
    # Prepare output array
    out = np.zeros_like(x_filtered)
    
    # Filter state variables (so they carry over between frames, avoiding clicks)
    zi_analysis = np.zeros(p)
    zi_synthesis = np.zeros(p)
    
    # Process frame-by-frame
    num_frames = len(x_filtered) // frame_size
    for f in range(num_frames):
        start = f * frame_size
        end = start + frame_size
        frame = x_filtered[start:end]
        
        # Apply Hamming window for autocorrelation estimation
        windowed = frame * np.hamming(frame_size)
        
        # Compute autocorrelation
        r = np.zeros(p + 1)
        for lag in range(p + 1):
            r[lag] = np.sum(windowed[lag:] * windowed[:frame_size - lag])
            
        # Avoid zero division
        if r[0] < 1e-8:
            out[start:end] = frame * 0.1
            continue
            
        # LPC Analysis
        a_lpc, k = levinson_durbin(r, p)
        
        # Quantize reflection coefficients (guaranteed stable if -1 < k < 1)
        # Quantize to 4 bits (16 levels between -0.95 and 0.95)
        k_q = np.clip(k, -0.95, 0.95)
        k_q = np.round(k_q * 8.0) / 8.0
        
        # Reconstruct predictor coefficients
        a_q = k_to_a(k_q)
        
        # Calculate inverse filter excitation residual (FIR filter)
        b_fir = np.concatenate(([1.0], -a_q))
        e, zi_analysis = signal.lfilter(b_fir, [1.0], frame, zi=zi_analysis)
        
        # Quantize residual to simulate bitrate reduction
        e_std = np.std(e) + 1e-12
        e_norm = e / e_std
        e_q = np.zeros_like(e_norm)
        e_q[e_norm > 0.5] = 1.0
        e_q[e_norm < -0.5] = -1.0
        e_q = e_q * (e_std * 0.8) # scale back down
        
        # Synthesis filter (IIR filter: 1 / A(z))
        a_iir = np.concatenate(([1.0], -a_q))
        frame_hat, zi_synthesis = signal.lfilter([1.0], a_iir, e_q, zi=zi_synthesis)
        
        out[start:end] = frame_hat
        
    # Scale output to match input energy roughly
    std_in = np.std(x_filtered) + 1e-12
    std_out = np.std(out) + 1e-12
    if np.isnan(std_out) or std_out < 1e-8:
        return x_filtered
        
    out = out * (std_in / std_out)
    
    # Fail-safe check for any nan or inf propagation
    if np.isnan(out).any() or np.isinf(out).any():
        return x_filtered
        
    return np.clip(out, -1.0, 1.0)

def clip_simulate(x: np.ndarray, threshold: float = 0.9) -> np.ndarray:
    """
    Simulate signal saturation / clipping.
    Outputs are clipped to [-threshold, threshold] and then rescaled to [-1.0, 1.0].
    """
    clipped = np.clip(x, -threshold, threshold)
    return clipped / threshold

def encode_decode_chain(x: np.ndarray, fs: int, mode: str = "amr", clip_threshold: float = 0.95) -> np.ndarray:
    """
    Complete Radio Codec & Channel Simulation:
    1. Resample input to 8 kHz.
    2. Apply codec simulation (G.711 mu-law, A-law, or AMR).
    3. Apply clipping distortion.
    4. Return the processed 8 kHz signal.
    """
    # Step 1: Resample to 8 kHz
    x_8k = resample_audio(x, fs, 8000)
    
    # Step 2: Codec roundtrip
    m = mode.lower()
    if m == "amr":
        processed = amr_simulate(x_8k)
    elif m in ["g711_mu", "mu-law", "mulaw"]:
        compressed = g711_compress(x_8k, mode="mu")
        processed = g711_expand(compressed, mode="mu")
    elif m in ["g711_a", "a-law", "alaw"]:
        compressed = g711_compress(x_8k, mode="a")
        processed = g711_expand(compressed, mode="a")
    elif m == "passthrough":
        processed = x_8k
    else:
        logger.warning(f"Unknown mode {mode}, falling back to AMR simulation.")
        processed = amr_simulate(x_8k)
        
    # Step 3: Clipping simulation
    output = clip_simulate(processed, threshold=clip_threshold)
    
    return output
