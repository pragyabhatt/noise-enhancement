import numpy as np
import logging

logger = logging.getLogger("vad")

# Try to import webrtcvad
try:
    import webrtcvad
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    logger.info("webrtcvad not available. Using custom energy-based VAD.")

class VoiceActivityDetector:
    def __init__(self, sample_rate: int = 8000, frame_duration_ms: int = 20, mode: int = 1):
        """
        Voice Activity Detector.
        sample_rate: 8000, 16000, 32000, or 48000 Hz.
        frame_duration_ms: 10, 20, or 30 ms.
        mode: WebRTC VAD aggressiveness (0, 1, 2, or 3).
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * (frame_duration_ms / 1000.0))
        
        # WebRTC VAD initialization
        self.webrtc_vad = None
        if WEBRTC_AVAILABLE:
            try:
                self.webrtc_vad = webrtcvad.Vad(mode)
            except Exception as e:
                logger.warning(f"Failed to initialize webrtcvad: {e}. Falling back to energy-based VAD.")
                
        # Energy-based VAD state parameters
        self.noise_floor_est = None  # in dB
        self.alpha_noise = 0.98      # recursive tracking factor
        self.threshold_db = 12.0     # speech threshold above noise floor in dB
        self.hangover_max = 5        # frames (100 ms at 20ms frames)
        self.hangover_counter = 0

    def _energy_vad(self, frame: np.ndarray) -> bool:
        """
        Energy-based VAD fallback logic:
        1. Compute frame energy in dB.
        2. Track rolling noise floor energy estimate.
        3. Trigger speech if frame energy is sufficiently higher than noise floor.
        4. Apply hangover frames to bridge consonant/vowel boundaries.
        """
        energy = np.mean(frame ** 2) + 1e-12
        energy_db = 10 * np.log10(energy)
        
        if self.noise_floor_est is None:
            self.noise_floor_est = energy_db
            return False
            
        # Update noise floor during low energy frames (rolling estimate)
        if energy_db < self.noise_floor_est + 4.0:
            self.noise_floor_est = self.alpha_noise * self.noise_floor_est + (1 - self.alpha_noise) * energy_db
        else:
            # Let noise floor slowly drift upward if audio volume shifts
            self.noise_floor_est += 0.01 * (energy_db - self.noise_floor_est)
            
        # Speech detection decision
        is_speech_frame = energy_db > (self.noise_floor_est + self.threshold_db)
        
        if is_speech_frame:
            self.hangover_counter = self.hangover_max
            return True
        else:
            if self.hangover_counter > 0:
                self.hangover_counter -= 1
                return True
            else:
                return False

    def is_speech(self, frame: np.ndarray) -> bool:
        """
        Check if a frame contains speech.
        Input frame should be a float array scaled between -1.0 and 1.0.
        """
        # Ensure frame length is correct
        if len(frame) != self.frame_size:
            # If length is slightly off, interpolate or pad/truncate
            if len(frame) < self.frame_size:
                frame = np.pad(frame, (0, self.frame_size - len(frame)))
            else:
                frame = frame[:self.frame_size]
                
        # Try WebRTC VAD
        if self.webrtc_vad is not None:
            try:
                # Convert float32 [-1.0, 1.0] to int16 PCM [-32768, 32767]
                pcm_data = (np.clip(frame, -1.0, 1.0) * 32767.0).astype(np.int16)
                pcm_bytes = pcm_data.tobytes()
                return self.webrtc_vad.is_speech(pcm_bytes, self.sample_rate)
            except Exception as e:
                # Fallback to energy VAD on error
                return self._energy_vad(frame)
        else:
            return self._energy_vad(frame)
            
    def reset(self):
        """
        Reset VAD state variables.
        """
        self.noise_floor_est = None
        self.hangover_counter = 0
