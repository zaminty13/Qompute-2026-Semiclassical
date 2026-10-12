import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from qiskit.quantum_info import Operator, average_gate_fidelity

from plot_amplitude_error import plot_infidelity_curves
from pulses import (PAULI_X, SEQUENCE_NAMES, average_infidelity, require_close,
                    sequence_duration_ns, sequence_unitary)


def main():
    parser = argparse.ArgumentParser(description='Compare coherent detuning errors at equal nominal Omega; write plots and CSV.')
    parser.add_argument('--no-show', action='store_true')
    args = parser.parse_args()
    omega = np.pi / 100
    normalized = np.linspace(-1, 1, 801)
    delta = normalized * omega
    output = Path(__file__).resolve().parent.parent / 'results'
    output.mkdir(exist_ok=True)
    curves = []
    columns = [normalized, delta]
    header = ['delta_over_omega', 'delta_rad_per_ns']
    for name in SEQUENCE_NAMES:
        unitaries = sequence_unitary(name, omega, detuning_rad_per_ns=delta)
        infidelity = average_infidelity(unitaries, PAULI_X)
        checks = np.linspace(0, len(delta) - 1, 17).astype(int)
        qiskit_values = np.array([1 - average_gate_fidelity(Operator(unitaries[i]),
                                    target=Operator(PAULI_X)) for i in checks])
        require_close(f'{name} Qiskit', infidelity[checks], qiskit_values)
        duration = sequence_duration_ns(name, omega)
        print(f'{name}: Omega={omega:.10f} rad/ns; total duration={duration:.6f} ns')
        curves.append((f'{name} ({duration:g} ns)', infidelity, '-'))
        columns.extend([1 - infidelity, infidelity])
        header.extend([f'{name}_fidelity', f'{name}_infidelity'])
    fig = plot_infidelity_curves(normalized, curves,
        'Detuning sensitivity of an X gate (amplitude error = 0)',
        xlabel='Normalized detuning Δ/Ω (Δ = ωqubit − ωdrive)', xscale=1, tick_step=.25)
    fig.savefig(output / 'detuning_error_comparison.png', dpi=300,
                bbox_inches='tight', facecolor=fig.get_facecolor())
    zoom = np.abs(normalized) <= .2 + 1e-12
    zoom_curves = [(name, values[zoom], style) for name, values, style in curves]
    zoom_fig = plot_infidelity_curves(normalized[zoom], zoom_curves,
        'Small-detuning sensitivity (amplitude error = 0)',
        xlabel='Normalized detuning Δ/Ω', xscale=1, tick_step=.05)
    zoom_fig.savefig(output / 'detuning_error_small.png', dpi=300,
                     bbox_inches='tight', facecolor=zoom_fig.get_facecolor())
    with (output / 'detuning_error_comparison.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(zip(*columns))
    print('\nInfidelity at selected errors (all pulses use the same Omega):')
    for mode in ['amplitude', 'detuning']:
        for error in [-1.0, -.5, -.2, -.1, -.01, 0.0, .01, .05, .1, .2, .5, 1.0]:
            kwargs = {'amplitude_error': error} if mode == 'amplitude' else {'detuning_rad_per_ns': error * omega}
            values = [float(average_infidelity(sequence_unitary(name, omega, **kwargs), PAULI_X))
                      for name in SEQUENCE_NAMES]
            print(f'{mode:9s} {error:5.2f}: ' + ' '.join(f'{name}={value:.8g}' for name, value in zip(SEQUENCE_NAMES, values)))
    if args.no_show:
        plt.close(fig)
        plt.close(zoom_fig)
    else:
        plt.show()


if __name__ == '__main__':
    main()
