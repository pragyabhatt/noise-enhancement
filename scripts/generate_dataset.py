import os
import sys
import json
import csv
import numpy as np
from scipy import signal
from scipy.io import wavfile

# Add backend to path so we can import radio_chain
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
from app.core.radio_chain import encode_decode_chain

def generate_unique_speech(duration=3.0, fs=8000, seed=42):
    """
    Generates a unique, high-fidelity synthetic speech-like signal.
    Includes voiced vowel-like formants, syllables, and unvoiced fricatives.
    """
    np.random.seed(seed)
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    
    # 1. Fundamental frequency sweep (voice pitch)
    f0_base = np.random.uniform(110.0, 240.0)
    f0 = f0_base + 25.0 * np.sin(2 * np.pi * np.random.uniform(0.6, 1.8) * t)
    
    # 2. Formant frequencies (sweeping resonances)
    f1 = np.random.uniform(450, 750) + 120 * np.sin(2 * np.pi * np.random.uniform(0.5, 1.1) * t)
    f2 = np.random.uniform(1500, 2100) + 250 * np.cos(2 * np.pi * np.random.uniform(0.4, 0.8) * t)
    f3 = np.random.uniform(2400, 2900) + 150 * np.sin(2 * np.pi * np.random.uniform(0.9, 1.4) * t)
    
    # 3. Generate harmonics
    speech = np.sin(2 * np.pi * f0 * t)
    speech += 0.65 * np.sin(2 * np.pi * f1 * t)
    speech += 0.4 * np.sin(2 * np.pi * f2 * t)
    speech += 0.2 * np.sin(2 * np.pi * f3 * t)
    
    # 4. Syllable amplitude envelope (2-4 Hz amplitude modulation)
    syllable_rate = np.random.uniform(2.2, 3.8)
    envelope = 0.5 * (1.0 + np.sin(2 * np.pi * syllable_rate * t + np.random.uniform(0, 2*np.pi)))
    
    # Add random word pauses
    pause_freq = np.random.uniform(0.4, 0.7)
    pause_mask = (np.sin(2 * np.pi * pause_freq * t + np.random.uniform(0, 2*np.pi)) > -0.2).astype(float)
    envelope = envelope * pause_mask
    
    speech = speech * envelope
    
    # 5. Fricative unvoiced noise (consonants like 's' or 'f')
    noise = np.random.normal(0, 1.0, len(t))
    nyq = fs / 2.0
    b_fric, a_fric = signal.butter(2, [3000.0 / nyq, 3900.0 / nyq], btype="band")
    fricative_noise = signal.lfilter(b_fric, a_fric, noise)
    
    # Active during envelope transitions
    fricative_env = (envelope < 0.25) * (envelope > 0.03)
    speech += 0.18 * fricative_noise * fricative_env
    
    # Final smoothing bandpass filter
    b_band, a_band = signal.butter(4, [100.0 / nyq, 3800.0 / nyq], btype="band")
    speech = signal.lfilter(b_band, a_band, speech)
    
    # Normalize to -8 dBFS
    speech = speech / (np.max(np.abs(speech)) + 1e-12) * 0.4
    return speech

# ----------------- NOISE GENERATORS -----------------

def generate_rotor_noise(length, fs=8000):
    t = np.arange(length) / fs
    beats = 0.5 * (1.0 + np.sin(2 * np.pi * 12.0 * t)) ** 5
    noise = np.random.normal(0, 1.0, length)
    nyq = fs / 2.0
    b, a = signal.butter(2, 300.0 / nyq, btype="low")
    rumble = signal.lfilter(b, a, noise)
    rotor = rumble * (1.0 + 3.5 * beats)
    return rotor / (np.std(rotor) + 1e-12)

def generate_engine_noise(length, fs=8000):
    t = np.arange(length) / fs
    hum = 0.65 * np.sin(2 * np.pi * 55.0 * t) + 0.3 * np.sin(2 * np.pi * 110.0 * t) + 0.1 * np.sin(2 * np.pi * 165.0 * t)
    noise = np.random.normal(0, 1.0, length)
    nyq = fs / 2.0
    b, a = signal.butter(2, [50.0 / nyq, 200.0 / nyq], btype="band")
    vibration = signal.lfilter(b, a, noise)
    engine = hum + 0.4 * vibration
    return engine / (np.std(engine) + 1e-12)

def generate_static_noise(length, fs=8000):
    white = np.random.normal(0, 1.0, length)
    fft_vals = np.fft.rfft(white)
    frequencies = np.fft.rfftfreq(length)
    frequencies[0] = frequencies[1]
    scale = 1.0 / np.sqrt(frequencies)
    scale = scale / scale[1]
    pink = np.fft.irfft(fft_vals * scale, n=length)
    
    # Static pops
    pops = np.zeros(length)
    num_pops = int(length / fs * 8)
    for _ in range(num_pops):
        idx = np.random.randint(0, length)
        pops[idx] = np.random.uniform(-4.0, 4.0)
    nyq = fs / 2.0
    b, a = signal.butter(1, 1800.0 / nyq, btype="low")
    pops_filtered = signal.lfilter(b, a, pops)
    
    static = pink + pops_filtered
    return static / (np.std(static) + 1e-12)

def generate_wind_noise(length, fs=8000):
    t = np.arange(length) / fs
    noise = np.random.normal(0, 1.0, length)
    nyq = fs / 2.0
    b, a = signal.butter(2, 450.0 / nyq, btype="low")
    base_wind = signal.lfilter(b, a, noise)
    gusts = 0.5 * (1.0 + np.sin(2 * np.pi * 0.18 * t))
    wind = base_wind * (0.25 + 1.75 * gusts)
    return wind / (np.std(wind) + 1e-12)

def generate_crowd_noise(length, fs=8000):
    t = np.arange(length) / fs
    babble = np.zeros(length)
    for i in range(10):
        carrier_freq = 160.0 + i * 110.0 + np.random.uniform(-15, 15)
        mod_freq = 2.8 + np.random.uniform(-0.8, 0.8)
        envelope = 0.5 * (1.0 + np.sin(2 * np.pi * mod_freq * t + np.random.uniform(0, 2*np.pi)))
        carrier = np.sin(2 * np.pi * carrier_freq * t) + 0.25 * np.sin(4 * np.pi * carrier_freq * t)
        babble += envelope * carrier
    babble += 0.25 * np.random.normal(0, 1.0, length)
    return babble / (np.std(babble) + 1e-12)

def mix_noise_at_snr(clean: np.ndarray, noise: np.ndarray, target_snr: float) -> tuple[np.ndarray, np.ndarray]:
    rms_clean = np.sqrt(np.mean(clean ** 2)) + 1e-12
    rms_noise = np.sqrt(np.mean(noise ** 2)) + 1e-12
    rms_target = rms_clean / (10 ** (target_snr / 20.0))
    scale = rms_target / rms_noise
    
    scaled_noise = noise * scale
    noisy = clean + scaled_noise
    # Scale back to prevent clipping
    max_val = np.max(np.abs(noisy))
    if max_val > 0.98:
        noisy = noisy / max_val * 0.98
        scaled_noise = scaled_noise / max_val * 0.98
    return noisy, scaled_noise

# ----------------- MAIN PIPELINE -----------------

def main():
    print("==================================================")
    print("DEAL Labs: Synthesizing Dataset catr_radio_v0.1...")
    print("==================================================")
    
    fs = 8000
    duration = 3.0
    length = int(fs * duration)
    
    base_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "catr_radio_v0.1"
    )
    
    splits = ["train", "val", "test"]
    for split in splits:
        os.makedirs(os.path.join(base_dir, split), exist_ok=True)
        
    manifest_path = os.path.join(base_dir, "manifest.csv")
    
    noise_generators = {
        "rotor": generate_rotor_noise,
        "engine": generate_engine_noise,
        "static": generate_static_noise,
        "wind": generate_wind_noise,
        "crowd": generate_crowd_noise
    }
    noise_types = list(noise_generators.keys())
    codecs = ["amr", "g711_mu", "g711_a"]
    
    # Dataset definition
    # 500 train, 100 val, 100 test
    dataset_setup = [
        ("train", 500, 1000),
        ("val", 100, 2000),
        ("test", 100, 3000)
    ]
    
    csv_rows = []
    global_id = 0
    
    for split, count, seed_offset in dataset_setup:
        print(f"Generating {count} clips for '{split}' split...")
        for i in range(count):
            seed = seed_offset + i
            np.random.seed(seed)
            
            # 1. Generate clean speech
            clean_speech = generate_unique_speech(duration=duration, fs=fs, seed=seed)
            
            # 2. Process through radio chain (resampling, G.711/AMR, and clipping)
            codec = np.random.choice(codecs)
            ref_clean = encode_decode_chain(clean_speech, fs=fs, mode=codec, clip_threshold=0.95)
            
            # 3. Choose noise profile and target SNR
            noise_name = np.random.choice(noise_types)
            # Second noise name (none by default, can be added)
            noise_sec = "none"
            
            snr = np.random.uniform(-5.0, 15.0)
            
            # Generate noise
            noise_signal = noise_generators[noise_name](length, fs=fs)
            
            # Mix noise
            noisy, _ = mix_noise_at_snr(ref_clean, noise_signal, snr)
            
            # Save files
            noisy_filename = f"noisy_{global_id:04d}.wav"
            ref_filename = f"ref_{global_id:04d}.wav"
            
            noisy_path_rel = os.path.join(split, noisy_filename)
            ref_path_rel = os.path.join(split, ref_filename)
            
            noisy_path_abs = os.path.join(base_dir, noisy_path_rel)
            ref_path_abs = os.path.join(base_dir, ref_path_rel)
            
            # Convert to float32 to save disk and represent standard values
            wavfile.write(noisy_path_abs, fs, noisy.astype(np.float32))
            wavfile.write(ref_path_abs, fs, ref_clean.astype(np.float32))
            
            # Write individual metadata.json for this clip
            meta = {
                "id": global_id,
                "split": split,
                "noisy_path": noisy_path_rel,
                "ref_path": ref_path_rel,
                "snr": float(round(snr, 2)),
                "noise_primary": noise_name,
                "noise_secondary": noise_sec,
                "codec": codec,
                "seed": seed
            }
            meta_path = os.path.join(base_dir, split, f"meta_{global_id:04d}.json")
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=4)
                
            # Store row for CSV (relative paths to base_dir as per spec)
            csv_rows.append({
                "id": global_id,
                "noisy_path": noisy_path_rel.replace("\\", "/"),
                "ref_path": ref_path_rel.replace("\\", "/"),
                "snr": round(snr, 2),
                "noise_primary": noise_name,
                "noise_secondary": noise_sec,
                "seed": seed
            })
            
            global_id += 1
            
    # Write master manifest CSV
    with open(manifest_path, "w", newline="") as f:
        fieldnames = ["id", "noisy_path", "ref_path", "snr", "noise_primary", "noise_secondary", "seed"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)
            
    print("==================================================")
    print(f"[SUCCESS] Synthesized {global_id} clips in total.")
    print(f"Manifest written to: {manifest_path}")
    print("==================================================")

if __name__ == "__main__":
    main()
