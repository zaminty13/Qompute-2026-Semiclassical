import numpy as np
from select_pulse import evaluate_pulses
from rb import rb_decay_curve_with_decoherence
from plot_rb import fit_decay
from pulses import SEQUENCE_NAMES
import csv
from pathlib import Path

def compare_fidelity_vs_rb(*, amplitude_error=0.05, detuning_rad_per_ns=0.0,
                           primitive_duration_ns=100.0, t1_ns=30000, t2_ns=20000,
                           lengths=(2,4,8,16,32), num_trials=100):
    omega_rad_per_ns = np.pi / primitive_duration_ns
    
    direct_records = {r['sequence']: r for r in evaluate_pulses(
        amplitude_error=amplitude_error, detuning_rad_per_ns=detuning_rad_per_ns,
        primitive_duration_ns=primitive_duration_ns, t1_ns=t1_ns, t2_ns=t2_ns)}
    rows = []
    for pulse_type in SEQUENCE_NAMES:
        decay_curve_data = rb_decay_curve_with_decoherence(
            list(lengths), num_trials, pulse_type, omega_rad_per_ns,
            amplitude_error, detuning_rad_per_ns, t1_ns, t2_ns)
        A, p, B, rb_error_per_gate = fit_decay(decay_curve_data)
        
        direct_row = direct_records[pulse_type]
        rows.append({
            'pulse_type': pulse_type,
            'duration_ns': direct_row['duration_ns'],
            'direct_infidelity': direct_row['infidelity'],
            'rb_error_per_gate': rb_error_per_gate,
            'amplitude_error': amplitude_error,
            'detuning_rad_per_ns': detuning_rad_per_ns,
            't1_ns': t1_ns,
            't2_ns': t2_ns,
        })
    return rows

def main():
    rows = compare_fidelity_vs_rb()
    
    output_dir = Path(__file__).resolve().parents[1] / 'results' / 'rb'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    fieldnames = ['pulse_type', 'duration_ns', 'direct_infidelity', 'rb_error_per_gate',
                  'amplitude_error', 'detuning_rad_per_ns', 't1_ns', 't2_ns']
    with open(output_dir / 'rb_vs_direct_fidelity.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{'pulse_type':10s} {'duration_ns':>12s} {'direct_infidelity':>18s} {'rb_error_per_gate':>18s}")
    for row in rows:
        print(f"{row['pulse_type']:10s} {row['duration_ns']:12.2f} "
            f"{row['direct_infidelity']:18.6f} {row['rb_error_per_gate']:18.6f}")
    print(f"\nSaved comparison to {output_dir / 'rb_vs_direct_fidelity.csv'}")
    
if __name__ == '__main__':
    main()