import os
import numpy as np
import logging
from app.core.vad import VoiceActivityDetector
from app.core.wiener import WienerFilter

logger = logging.getLogger("enhancer_df2")

try:
    import onnxruntime as ort
    ORT_AVAILABLE = True
except ImportError:
    ORT_AVAILABLE = False
    logger.info("onnxruntime not available. Running in DSP fallback mode.")

class DeepFilterNet2Enhancer:
    def __init__(self, models_dir: str = None, sample_rate: int = 8000):
        """
        DeepFilterNet2 ONNX Streaming Enhancer.
        models_dir: Directory containing DeepFilterNet2 ONNX model files.
        sample_rate: Core sample rate (default 8000 Hz for DEAL).
        """
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * 0.02) # 20 ms frame (160 samples @ 8kHz)
        
        if models_dir is None:
            # Default models location
            self.models_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "models"
            )
        else:
            self.models_dir = models_dir
            
        self.use_fallback = True
        self.sessions = {}
        self.gru_state = None
        
        # 1. Attempt to load ONNX models
        if ORT_AVAILABLE:
            model_files = {
                "enc": "enc_conv_streaming.onnx",
                "gru": "enc_gru_streaming.onnx",
                "erb_dec": "erb_dec_streaming.onnx",
                "df_dec": "df_dec_streaming.onnx"
            }
            
            paths_exist = True
            for key, filename in model_files.items():
                path = os.path.join(self.models_dir, filename)
                if not os.path.exists(path):
                    paths_exist = False
                    break
                    
            if paths_exist:
                try:
                    logger.info("Loading DeepFilterNet2 ONNX streaming models...")
                    # Load each stage
                    opts = ort.SessionOptions()
                    opts.intra_op_num_threads = 1
                    opts.inter_op_num_threads = 1
                    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                    
                    for key, filename in model_files.items():
                        path = os.path.join(self.models_dir, filename)
                        self.sessions[key] = ort.InferenceSession(path, sess_options=opts, providers=["CPUExecutionProvider"])
                        
                    # Initialize GRU hidden state (typically [1, 1, 128] or similar depending on the exported model)
                    self.gru_state = np.zeros((1, 1, 128), dtype=np.float32)
                    self.use_fallback = False
                    logger.info("[SUCCESS] DeepFilterNet2 ONNX models loaded successfully.")
                except Exception as e:
                    logger.warning(f"Failed to load ONNX models: {e}. Falling back to DSP pipeline.")
            else:
                logger.info(f"ONNX weights not found in '{self.models_dir}'. Initializing high-quality DSP Wiener Filter fallback.")
        
        # 2. Setup DSP fallback
        if self.use_fallback:
            self.vad = VoiceActivityDetector(sample_rate=self.sample_rate)
            self.wiener = WienerFilter(sample_rate=self.sample_rate)
            
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Process a single 20ms frame of audio.
        """
        if self.use_fallback:
            # Fallback pipeline: VAD -> Wiener Filter
            is_speech = self.vad.is_speech(frame)
            return self.wiener.process_frame(frame, is_speech)
            
        # Standard ONNX path (DeepFilterNet2 streaming implementation)
        try:
            # Reshape frame to expected model inputs: usually (1, 160) or similar
            # DeepFilterNet typically expects 48 kHz but we can run standard 8 kHz if model supports it.
            # Here is the general streaming forward pass:
            frame_input = frame.astype(np.float32).reshape(1, -1)
            
            # Step A: Encoder Conv
            enc_outputs = self.sessions["enc"].run(None, {"input": frame_input})
            enc_feat = enc_outputs[0]
            
            # Step B: GRU State Update
            gru_outputs = self.sessions["gru"].run(None, {
                "input": enc_feat, 
                "state": self.gru_state
            })
            gru_out = gru_outputs[0]
            self.gru_state = gru_outputs[1] # update persistent state
            
            # Step C: ERB Decoder
            erb_outputs = self.sessions["erb_dec"].run(None, {"input": gru_out})
            erb_mask = erb_outputs[0]
            
            # Step D: Deep Filtering Decoder (Complex gain)
            df_outputs = self.sessions["df_dec"].run(None, {
                "input": gru_out,
                "erb_mask": erb_mask
            })
            enhanced_frame = df_outputs[0].flatten()
            
            return enhanced_frame
            
        except Exception as e:
            # Fallback dynamically if ONNX execution crashes at runtime
            logger.error(f"ONNX inference failure: {e}. Switching dynamically to DSP fallback.")
            self.use_fallback = True
            self.vad = VoiceActivityDetector(sample_rate=self.sample_rate)
            self.wiener = WienerFilter(sample_rate=self.sample_rate)
            
            # Run fallback
            is_speech = self.vad.is_speech(frame)
            return self.wiener.process_frame(frame, is_speech)
            
    def reset(self):
        """
        Reset states for both ONNX and fallback modes.
        """
        if self.use_fallback:
            self.vad.reset()
            self.wiener.reset()
        else:
            self.gru_state = np.zeros((1, 1, 128), dtype=np.float32)
