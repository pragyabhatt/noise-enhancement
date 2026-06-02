import numpy as np
import pytest
from app.core.radio_chain import g711_compress, g711_expand

def test_g711_mu_roundtrip():
    # Generate a random float32 signal in [-1, 1]
    rng = np.random.default_rng(0)
    signal = rng.uniform(-1.0, 1.0, size=1024).astype(np.float32)
    compressed = g711_compress(signal, mode='mu')
    recovered = g711_expand(compressed, mode='mu')
    # After round‑trip the error should be very small (within 1e-3)
    diff = np.mean((signal - recovered) ** 2)
    assert diff < 1e-3, f"Mu‑law round‑trip MSE too high: {diff}"
