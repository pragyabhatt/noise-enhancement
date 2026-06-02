import json
import asyncio
import logging
from typing import Dict, Any

from fastapi import WebSocket, WebSocketDisconnect
from fastapi import APIRouter

from app.core.radio_chain import resample_audio
from app.core.vad import VoiceActivityDetector
from app.core.wiener import WienerFilter
from app.core.enhancer_df2 import DeepFilterNet2Enhancer
from app.core.limiter import PeakLimiter
from app.core.confidence import calculate_confidence
from app.core.speaker_sim import SpeakerSimilarityChecker
from app.core.noise_classifier import NoiseProfileClassifier
from app.metrics.deploy_metrics import estimate_single_channel_snr, compute_dnsmos

logger = logging.getLogger(__name__)

router = APIRouter()

# Helper to send JSON diagnostics per frame
async def send_json(ws: WebSocket, payload: Dict[str, Any]):
    await ws.send_text(json.dumps(payload))

@router.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    """WebSocket endpoint for real‑time audio streaming.

    The client sends raw 8 kHz PCM frames (float32, little‑endian) of size
    `frame_size` bytes. The server processes each frame through the
    enhancement pipeline and returns a JSON packet containing diagnostics
    and the enhanced PCM frame (base64‑encoded). The connection closes
    gracefully on client disconnect.
    """
    await ws.accept()

    # Initialise pipeline components once per connection
    vad = VoiceActivityDetector(sample_rate=8000)
    wiener = WienerFilter(sample_rate=8000)
    enhancer = DeepFilterNet2Enhancer()
    limiter = PeakLimiter()
    speaker_sim = SpeakerSimilarityChecker()
    noise_classifier = NoiseProfileClassifier()

    try:
        while True:
            # Expect a binary message containing raw PCM float32 samples
            data = await ws.receive_bytes()
            if not data:
                continue
            # Convert bytes to numpy array
            import numpy as np
            frame = np.frombuffer(data, dtype=np.float32)

            # VAD decision
            is_speech = vad.is_speech(frame)

            # Wiener noise reduction (only on non‑speech frames)
            if not is_speech:
                frame = wiener.process(frame)

            # DeepFilterNet2 enhancement (always applied)
            enhanced = enhancer.enhance(frame)

            # Limiter to avoid clipping
            enhanced = limiter.limit(enhanced)

            # Compute per‑frame diagnostics (lightweight)
            pre_snr = estimate_single_channel_snr(frame)
            post_snr = estimate_single_channel_snr(enhanced)
            pre_sig, pre_bak, pre_ovr = compute_dnsmos(frame, 8000)
            post_sig, post_bak, post_ovr = compute_dnsmos(enhanced, 8000)
            dnsmos_delta = post_ovr - pre_ovr
            confidence_val, confidence_status = calculate_confidence(
                blind_snr=post_snr,
                gain_db=20 * np.log10(np.std(enhanced) / (np.std(frame) + 1e-12) + 1e-12),
                dnsmos_delta=dnsmos_delta,
                vad_ratio=1.0 if is_speech else 0.0,
            )
            speaker_similarity = speaker_sim.calculate_similarity(frame, enhanced, fs=8000)
            noise_info = noise_classifier.classify_noise(frame, blind_snr=pre_snr)

            # Prepare JSON payload
            payload = {
                "confidence": confidence_val,
                "confidence_status": confidence_status,
                "speaker_similarity": speaker_similarity,
                "noise_class": noise_info["class"],
                "noise_probability": noise_info["probability"],
                "noise_explanation": noise_info["explanation"],
                "pre_snr_db": round(pre_snr, 2),
                "post_snr_db": round(post_snr, 2),
                "snr_improvement_db": round(post_snr - pre_snr, 2),
                "pre_dnsmos": {"sig": pre_sig, "bak": pre_bak, "ovr": pre_ovr},
                "post_dnsmos": {"sig": post_sig, "bak": post_bak, "ovr": post_ovr},
                "dnsmos_improvement_ovr": round(post_ovr - pre_ovr, 2),
                "is_speech": is_speech,
                "audio_frame": (data).hex(),  # raw PCM hex string (client can decode)
                "enhanced_frame": enhanced.tobytes().hex(),
            }
            await send_json(ws, payload)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception(f"WebSocket stream error: {e}")
        await ws.close()
