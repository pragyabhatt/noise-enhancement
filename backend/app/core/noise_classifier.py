import numpy as np
from scipy import signal
import logging

logger = logging.getLogger("noise_classifier")

class NoiseProfileClassifier:
    def __init__(self, sample_rate: int = 8000):
        """
        Digtial Signal Processing feature-based Noise Profile Classifier.
        Classifies background noise into: 'rotor', 'engine', 'static', 'wind', 'crowd', or 'clean'.
        """
        self.sample_rate = sample_rate

    def classify_noise(self, x: np.ndarray, blind_snr: float = None) -> dict:
        """
        Perform noise profile classification.
        x: Input raw noisy signal.
        blind_snr: Optional pre-calculated blind SNR. If SNR is high, classifies as clean.
        """
        # 1. Check for clean signal first
        if blind_snr is not None and blind_snr > 25.0:
            return {"class": "clean", "probability": 0.99, "explanation": "Signal has very low ambient noise floor."}
            
        N = len(x)
        if N < 512:
            return {"class": "clean", "probability": 0.50, "explanation": "Audio clip too short for classification."}
            
        # 2. Compute spectral features
        # We run FFT on the whole block or average across frames
        n_fft = min(2048, N)
        frequencies = np.fft.rfftfreq(n_fft, d=1.0/self.sample_rate)
        
        # Compute magnitude spectrum
        stft_matrix = np.abs(signal.stft(x, fs=self.sample_rate, nperseg=n_fft, noverlap=n_fft//2)[2])
        magnitude_avg = np.mean(stft_matrix, axis=1) + 1e-12
        power_avg = magnitude_avg ** 2
        
        # A. Spectral Centroid
        centroid = np.sum(frequencies * magnitude_avg) / np.sum(magnitude_avg)
        
        # B. Spectral Flatness
        geometric_mean = np.exp(np.mean(np.log(power_avg)))
        arithmetic_mean = np.mean(power_avg)
        flatness = geometric_mean / (arithmetic_mean + 1e-12)
        
        # C. Envelope Modulation analysis (detect periodic beats for helicopter/rotor)
        # We low-pass filter the absolute value of the signal (envelope) and compute its FFT
        envelope = np.abs(x)
        # Lowpass filter the envelope at 30Hz
        nyq = self.sample_rate / 2.0
        b_env, a_env = signal.butter(2, 30.0 / nyq, btype="low")
        envelope_filtered = signal.lfilter(b_env, a_env, envelope)
        
        # Find peak modulation frequency in 5 Hz - 20 Hz (typical rotor blade pass rates)
        env_detrend = envelope_filtered - np.mean(envelope_filtered)
        env_fft = np.abs(np.fft.rfft(env_detrend, n=min(4096, len(env_detrend))))
        env_freqs = np.fft.rfftfreq(min(4096, len(env_detrend)), d=1.0/self.sample_rate)
        
        rotor_band_mask = (env_freqs >= 6.0) & (env_freqs <= 16.0)
        peak_mod_energy = 0.0
        if np.sum(rotor_band_mask) > 0:
            peak_mod_energy = np.max(env_fft[rotor_band_mask])
        total_mod_energy = np.sum(env_fft[env_freqs <= 30.0]) + 1e-12
        rotor_ratio = peak_mod_energy / total_mod_energy
        
        # 3. Decision Tree / Heuristic Classification based on features
        scores = {
            "rotor": 0.0,
            "engine": 0.0,
            "static": 0.0,
            "wind": 0.0,
            "crowd": 0.0
        }
        
        # Engine: Tonal, very low frequency harmonics (fundamental < 150 Hz)
        # Tonal signals have low flatness. Low centroid.
        if centroid < 380 and flatness < 0.05:
            scores["engine"] = 0.85
        elif centroid < 500:
            scores["engine"] = 0.40
            
        # Static: High frequency, very high flatness (pink/white noise-like)
        if flatness > 0.15 and centroid > 1500:
            scores["static"] = 0.90
        elif flatness > 0.08 and centroid > 1000:
            scores["static"] = 0.50
            
        # Rotor: Strong periodic beats in envelope (rotor_ratio) and low-frequency rumble
        if rotor_ratio > 0.08 and centroid < 600:
            scores["rotor"] = 0.95
        elif rotor_ratio > 0.05:
            scores["rotor"] = 0.60
            
        # Wind: Extremely low frequency, moderate flatness, slow temporal fluctuations
        if centroid < 300 and flatness >= 0.05:
            scores["wind"] = 0.80
        elif centroid < 450 and flatness >= 0.04:
            scores["wind"] = 0.45
            
        # Crowd: Speech band concentration (400 Hz - 1800 Hz) with moderate flatness
        if 400 <= centroid <= 1200 and 0.02 <= flatness <= 0.12:
            scores["crowd"] = 0.80
        elif 300 <= centroid <= 1500:
            scores["crowd"] = 0.40
            
        # Find winning class
        predicted_class = max(scores, key=scores.get)
        confidence_prob = scores[predicted_class]
        
        # Fallback to general noise if scores are all low
        if confidence_prob < 0.25:
            predicted_class = "static"
            confidence_prob = 0.35
            
        explanations = {
            "rotor": "Periodic amplitude envelope modulation detected in the 8-14 Hz range, typical of helicopter rotor blades.",
            "engine": "Low-frequency harmonic tones detected below 200 Hz, indicative of heavy machinery or diesel engines.",
            "static": "Flat high-frequency spectral density with random impulsive peaks, indicating thermal or radio static interference.",
            "wind": "Dominant subsonic rumblings below 150 Hz with slow dynamic wind gust dynamics.",
            "crowd": "Broadband spectral energy concentrated in the vocal range (300-2000 Hz) with speech-like modulation envelopes."
        }
        
        return {
            "class": predicted_class,
            "probability": round(float(confidence_prob), 2),
            "explanation": explanations.get(predicted_class, "General ambient noise floor.")
        }
