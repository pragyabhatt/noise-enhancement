import numpy as np
from scipy import signal
import logging

logger = logging.getLogger("wiener")

class WienerFilter:
    def __init__(self, sample_rate: int = 8000, n_fft: int = 256, hop_length: int = 160):
        """
        Stateful Wiener Filter for stationary noise reduction.
        Operates on 20ms frames (160 samples at 8 kHz).
        """
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.alpha_noise = 0.95    # Smoothing factor for noise PSD update
        self.beta = 1.8           # Over-subtraction factor to reduce musical noise
        self.g_min = 0.15          # Spectral floor (approx -16 dB attenuation limit)
        
        # State variables
        self.P_noise = np.ones(n_fft // 2 + 1) * 1e-5
        self.input_buffer = np.zeros(n_fft - hop_length)      # Overlap input history
        self.output_buffer = np.zeros(n_fft - hop_length)     # OLA output buffer
        self.win_sum_buffer = np.zeros(n_fft - hop_length)    # OLA window sum buffer
        self.window = np.hamming(n_fft)

    def process_frame(self, frame: np.ndarray, is_speech: bool) -> np.ndarray:
        """
        Process a single frame of audio (160 samples).
        Updates noise PSD during non-speech frames and filters during speech.
        """
        # Ensure frame length matches hop_length
        if len(frame) != self.hop_length:
            if len(frame) < self.hop_length:
                frame = np.pad(frame, (0, self.hop_length - len(frame)))
            else:
                frame = frame[:self.hop_length]
                
        full_frame = np.concatenate((self.input_buffer, frame))
        self.input_buffer = frame[-(self.n_fft - self.hop_length):].copy() # update input overlap buffer
        
        # 2. Apply analysis window
        windowed = full_frame * self.window
        
        # 3. FFT
        X = np.fft.rfft(windowed)
        P_frame = np.abs(X) ** 2
        
        # 4. Update noise PSD or estimate gain
        if not is_speech:
            # Update noise estimate recursively during silence/non-speech
            self.P_noise = self.alpha_noise * self.P_noise + (1.0 - self.alpha_noise) * P_frame
            gain = np.ones_like(P_frame) * self.g_min
        else:
            # Calculate Wiener gain: (P_frame - beta * P_noise) / P_frame
            # We scale the noise floor to perform over-subtraction
            gain = (P_frame - self.beta * self.P_noise) / (P_frame + 1e-12)
            gain = np.clip(gain, self.g_min, 1.0)
            
        # 5. Apply gain
        Y = X * gain
        
        # 6. IFFT
        y_windowed = np.fft.irfft(Y, n=self.n_fft)
        
        # 7. Overlap-add for signal reconstruction
        reconstructed = np.zeros(self.n_fft)
        reconstructed[:self.n_fft - self.hop_length] = self.output_buffer + y_windowed[:self.n_fft - self.hop_length]
        reconstructed[self.n_fft - self.hop_length:] = y_windowed[self.n_fft - self.hop_length:]
        self.output_buffer = reconstructed[self.hop_length:]
        
        # 8. Overlap-add window sum tracker for normalization
        reconstructed_win_sum = np.zeros(self.n_fft)
        reconstructed_win_sum[:self.n_fft - self.hop_length] = self.win_sum_buffer + self.window[:self.n_fft - self.hop_length]
        reconstructed_win_sum[self.n_fft - self.hop_length:] = self.window[self.n_fft - self.hop_length:]
        self.win_sum_buffer = reconstructed_win_sum[self.hop_length:]
        
        # Get current frame output and normalize by the window sum to prevent amplitude modulation
        out_chunk = reconstructed[:self.hop_length]
        win_sum_chunk = reconstructed_win_sum[:self.hop_length]
        
        normalized_chunk = out_chunk / (win_sum_chunk + 1e-12)
        return normalized_chunk

    def filter_signal(self, noisy_signal: np.ndarray, speech_mask: np.ndarray) -> np.ndarray:
        """
        Offline/block processing method for Wiener filtering on a full 1D array.
        noisy_signal: 1D float array.
        speech_mask: Boolean array of same length indicating voice activity per sample.
        """
        self.reset()
        
        # Process in hops
        out = np.zeros_like(noisy_signal)
        num_frames = len(noisy_signal) // self.hop_length
        
        for f in range(num_frames):
            start = f * self.hop_length
            end = start + self.hop_length
            chunk = noisy_signal[start:end]
            
            # Frame speech decision (majority vote in the frame)
            mask_chunk = speech_mask[start:end]
            is_speech = np.mean(mask_chunk.astype(float)) > 0.3
            
            out_chunk = self.process_frame(chunk, is_speech)
            out[start:end] = out_chunk
            
        return out

    def reset(self):
        """
        Reset internal filters and OLA state.
        """
        self.P_noise = np.ones(self.n_fft // 2 + 1) * 1e-5
        self.input_buffer = np.zeros(self.n_fft - self.hop_length)
        self.output_buffer = np.zeros(self.n_fft - self.hop_length)
        self.win_sum_buffer = np.zeros(self.n_fft - self.hop_length)
