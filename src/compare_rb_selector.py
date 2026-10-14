import argparse
import csv
from pathlib import Path
from rb import run_survival_study
from select_pulse import evaluate_pulses, select_pulse


def compare_study(study, min_fidelity=.99):
    config = study['config']
    conditions = {key: config[key] for key in ('amplitude_error', 'detuning_rad_per_ns',
                  'primitive_duration_ns', 't1_ns', 't2_ns')}
    for key in ('t1_ns', 't2_ns'):
        if conditions[key] == 'infinity':
            conditions[key] = float('inf')
    choice, direct = select_pulse(min_fidelity=min_fidelity, **conditions)
    direct = {row['sequence']: row for row in direct}
    rows = []
    for row in study['summary']:
        gate = direct[row['pulse_type']]
        rows.append({**row, 'direct_fidelity': gate['fidelity'],
                     'direct_infidelity': gate['infidelity'],
                     'minimum_fidelity': min_fidelity,
                     'selector_choice': choice['sequence'] if choice else 'none',
                     'amplitude_error': config['amplitude_error'],
                     'detuning_rad_per_ns': config['detuning_rad_per_ns'],
                     't1_ns': config['t1_ns'], 't2_ns': config['t2_ns']})
    return rows


def compare_fidelity_vs_rb(*, amplitude_error=.05, detuning_rad_per_ns=0.,
                           primitive_duration_ns=100., t1_ns=30000., t2_ns=20000.,
                           lengths=(2, 4, 8, 16, 32), num_trials=100,
                           seed=2026, min_fidelity=.99):
    study = run_survival_study(amplitude_error=amplitude_error,
        detuning_rad_per_ns=detuning_rad_per_ns, primitive_duration_ns=primitive_duration_ns,
        t1_ns=t1_ns, t2_ns=t2_ns, lengths=lengths, num_trials=num_trials, seed=seed)
    return compare_study(study, min_fidelity)


def main():
    parser = argparse.ArgumentParser(description='Direct fidelity and X/identity survival; not Clifford RB')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--trials', type=int, default=512)
    args = parser.parse_args()
    rows = compare_fidelity_vs_rb(seed=args.seed, num_trials=args.trials)
    with args.output.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print('Saved direct fidelity, threshold choice and state-specific survival:', args.output)


if __name__ == '__main__':
    main()
