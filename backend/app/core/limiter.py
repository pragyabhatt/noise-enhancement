import numpy as np
import logging

logger = logging.getLogger("limiter")

class PeakLimiter:
    def __init__(self, threshold: float = 0.98, look_ahead_ms: float = 1.5, release_ms: float = 50.0, sample_rate: int = 8000):
        """
        Stateful look-ahead peak limiter to prevent digital clipping on output frames.
        threshold: maximum allowed output amplitude (e.g. 0.98).
        look_ahead_ms: look-ahead window size in milliseconds.
        release_ms: release smoothing filter time in milliseconds.
        sample_rate: sample rate of the signal (e.g., 8000 or 16000 Hz).
        """
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.look_ahead_samples = max(1, int(look_ahead_ms * 1e-3 * sample_rate))
        self.release_coef = np.exp(-1.0 / (release_ms * 1e-3 * sample_rate))
        
        # State variables
        self.delay_line = np.zeros(self.look_ahead_samples)
        self.g_smooth = 1.0

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Limit a single frame of audio.
        Input frame should be a float array.
        Returns limited frame of the same size.
        """
        N = len(frame)
        if N == 0:
            return frame
            
        # Combine previous look-ahead delay line and current frame
        signal_full = np.concatenate((self.delay_line, frame))
        
        out = np.zeros(N)
        for n in range(N):
            # Window looking ahead from current sample n
            window = signal_full[n : n + self.look_ahead_samples + 1]
            peak = np.max(np.abs(window))
            
            # Gain calculation
            if peak > self.threshold:
                g_target = self.threshold / (peak + 1e-12)
            else:
                g_target = 1.0
                
            # Apply attack/release smoothing
            # Attack is instantaneous look-ahead due to the window max.
            # Release is smoothed to avoid rapid gain pumping.
            if g_target > self.g_smooth:
                self.g_smooth = self.release_coef * self.g_smooth + (1.0 - self.release_coef) * g_target
            else:
                self.g_smooth = g_target
                
            out[n] = signal_full[n] * self.g_smooth
            
        # Update delay line for the next frame (last L samples)
        self.delay_line = signal_full[N:]
        
        return out

    def limit_signal(self, signal_data: np.ndarray) -> np.ndarray:
        """
        Limit a full 1D signal block.
        """
        self.reset()
        # Process in chunks of 160 samples
        chunk_size = 160
        out = np.zeros_like(signal_data)
        num_chunks = len(signal_data) // chunk_size
        
        for i in range(num_chunks):
            start = i * chunk_size
            end = start + chunk_size
            out[start:end] = self.process_frame(signal_data[start:end])
            
        # Process remaining samples
        if len(signal_data) % chunk_size > 0:
            start = num_chunks * chunk_size
            out[start:] = self.process_frame(signal_data[start:])
            
        return out

    def reset(self):
        """
        Reset limiter state variables.
        """
        self.delay_line = np.zeros(self.look_ahead_samples)
        self.g_smooth = 1.0
