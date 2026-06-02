import os
import sys
import csv
import json
import numpy as np
from scipy.io import wavfile

# Add backend to path so we can import modules
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.metrics.eval_metrics import compute_seg_snr, compute_stoi, compute_si_sdr
from app.metrics.baselines import (
    run_passthrough,
    run_wiener,
    run_df2_only,
    run_rnnoise_baseline,
    run_hybrid_pipeline
)

def main():
    print("==================================================")
    print("DEAL Labs: Running Gate 0 CLI Benchmark Harness...")
    print("==================================================")
    
    base_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "catr_radio_v0.1"
    )
    
    manifest_path = os.path.join(base_dir, "manifest.csv")
    
    if not os.path.exists(manifest_path):
        print(f"[ERROR] Manifest file not found at: {manifest_path}")
        print("Please run scripts/generate_dataset.py first to synthesize the dataset.")
        sys.exit(1)
        
    # Read manifest and filter for test split
    test_clips = []
    with open(manifest_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["noisy_path"].startswith("test/"):
                test_clips.append(row)
                
    num_test = len(test_clips)
    print(f"Loaded {num_test} test clips from manifest.")
    if num_test == 0:
        print("[ERROR] No test clips found in the manifest! Ensure test split was generated.")
        sys.exit(1)
        
    baselines = {
        "Passthrough": run_passthrough,
        "Wiener-Only": run_wiener,
        "RNNoise-Sim": run_rnnoise_baseline,
        "DF2-Only": run_df2_only,
        "Hybrid-Pipeline": run_hybrid_pipeline
    }
    
    # Initialize metric accumulation
    metrics_summary = {
        name: {"seg_snr": [], "stoi": [], "si_sdr": []} for name in baselines.keys()
    }
    
    detailed_rows = []
    
    print("\nEvaluating test set (this may take a few seconds)...")
    for idx, clip in enumerate(test_clips):
        noisy_abs = os.path.join(base_dir, clip["noisy_path"])
        ref_abs = os.path.join(base_dir, clip["ref_path"])
        
        fs_n, noisy_data = wavfile.read(noisy_abs)
        fs_r, ref_data = wavfile.read(ref_abs)
        
        # Ensure scale is in [-1.0, 1.0] for calculations
        if noisy_data.dtype == np.int16:
            noisy_data = noisy_data.astype(np.float32) / 32768.0
        if ref_data.dtype == np.int16:
            ref_data = ref_data.astype(np.float32) / 32768.0
            
        row_detail = {
            "id": clip["id"],
            "snr_in": float(clip["snr"]),
            "noise_primary": clip["noise_primary"]
        }
        
        for name, runner in baselines.items():
            # Run enhancement
            enhanced = runner(noisy_data, fs=fs_n)
            
            # Compute metrics
            seg_snr = compute_seg_snr(ref_data, enhanced, fs=fs_n)
            stoi = compute_stoi(ref_data, enhanced, fs=fs_n)
            si_sdr = compute_si_sdr(ref_data, enhanced)
            
            # Accumulate
            metrics_summary[name]["seg_snr"].append(seg_snr)
            metrics_summary[name]["stoi"].append(stoi)
            metrics_summary[name]["si_sdr"].append(si_sdr)
            
            # Detailed csv logging
            row_detail[f"{name}_SegSNR"] = round(seg_snr, 3)
            row_detail[f"{name}_STOI"] = round(stoi, 4)
            row_detail[f"{name}_SISDR"] = round(si_sdr, 3)
            
        detailed_rows.append(row_detail)
        
        # Progress indicator
        if (idx + 1) % 10 == 0 or (idx + 1) == num_test:
            print(f"Processed {idx + 1}/{num_test} clips...")
            
    # Calculate average metrics
    average_metrics = {}
    for name in baselines.keys():
        average_metrics[name] = {
            "SegSNR": float(np.mean(metrics_summary[name]["seg_snr"])),
            "STOI": float(np.mean(metrics_summary[name]["stoi"])),
            "SISDR": float(np.mean(metrics_summary[name]["si_sdr"]))
        }
        
    # Write detailed CSV
    detailed_csv_path = os.path.join(base_dir, "benchmark_detailed.csv")
    with open(detailed_csv_path, "w", newline="") as f:
        if detailed_rows:
            fieldnames = list(detailed_rows[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in detailed_rows:
                writer.writerow(row)
                
    # Write summary JSON
    summary_json_path = os.path.join(base_dir, "benchmark_summary.json")
    with open(summary_json_path, "w") as f:
        json.dump(average_metrics, f, indent=4)
        
    # Print Markdown Table to console
    print("\n" + "=" * 60)
    print("               GATE 0 BENCHMARK SUMMARY RESULTS")
    print("=" * 60)
    print(f"Dataset: catr_radio_v0.1 | Test split: {num_test} clips")
    print(f"Metrics: Averaged over all test files")
    print("-" * 60)
    print(f"| {'Baseline / Model':<18} | {'SegSNR (dB)':<12} | {'STOI (0-1)':<10} | {'SI-SDR (dB)':<11} |")
    print(f"|{'-' * 20}|{'-' * 14}|{'-' * 12}|{'-' * 13}|")
    for name, m in average_metrics.items():
        print(f"| {name:<18} | {m['SegSNR']:>12.3f} | {m['STOI']:>10.4f} | {m['SISDR']:>11.3f} |")
    print("=" * 60)
    
    # Check Gate 0 Exit condition: Hybrid beats or matches DF2-only
    hybrid_stoi = average_metrics["Hybrid-Pipeline"]["STOI"]
    df2_stoi = average_metrics["DF2-Only"]["STOI"]
    
    print("\nGate 0 Exit Evaluation:")
    print(f"  Hybrid Pipeline STOI: {hybrid_stoi:.4f}")
    print(f"  DF2-Only Baseline STOI: {df2_stoi:.4f}")
    if hybrid_stoi >= df2_stoi - 1e-4:
        print("[EXIT SUCCESS] Hybrid pipeline meets or exceeds DF2-only baseline!")
    else:
        print("[WARNING] Hybrid pipeline STOI is slightly below DF2-only. Tune Wiener filter parameter beta.")
        
    print(f"\nDetailed CSV exported to: {detailed_csv_path}")
    print(f"Summary JSON exported to: {summary_json_path}")
    print("==================================================")

if __name__ == "__main__":
    main()
