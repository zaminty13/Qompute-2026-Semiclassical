"""PulseWise: choose simulated X-gate pulse sequences using Qiskit fidelity.

This uses the existing ``pulses.py`` / ``decoherence.py`` from Team Semiclassical.
It does not model real IBM pulse hardware, finite bandwidth, or leakage.
"""

from __future__ import annotations

import numpy as np
from qiskit.quantum_info import Operator, average_gate_fidelity

from pulses import PAULI_X, SEQUENCE_NAMES, sequence_duration_ns
from decoherence import sequence_superop

TARGET = Operator(PAULI_X)
THRESHOLD_TOLERANCE = 1e-12


def _threshold(value: float) -> float:
    value = float(value)
    if not np.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Minimum fidelity must be finite and between 0 and 1.')
    return value


def evaluate_pulses(*, amplitude_error: float = .05,
                    detuning_rad_per_ns: float = 0.,
                    primitive_duration_ns: float = 100.,
                    t1_ns: float = 30000., t2_ns: float = 20000.) -> list[dict]:
    """Return fidelity and full physical duration for all three pulse sequences."""
    duration = float(primitive_duration_ns)
    if not np.isfinite(duration) or duration <= 0:
        raise ValueError('primitive_duration_ns must be positive and finite.')
    omega = np.pi / duration
    records = []
    for name in SEQUENCE_NAMES:
        channel = sequence_superop(
            name, omega, amplitude_error=amplitude_error,
            detuning_rad_per_ns=detuning_rad_per_ns,
            t1_ns=t1_ns, t2_ns=t2_ns,
        )
        fidelity = float(average_gate_fidelity(channel, target=TARGET))
        records.append({
            'sequence': name,
            'fidelity': fidelity,
            'infidelity': 1. - fidelity,
            'duration_ns': float(sequence_duration_ns(name, omega)),
            'primitive_duration_ns': duration,
            'amplitude_error': float(amplitude_error),
            'detuning_rad_per_ns': float(detuning_rad_per_ns),
            't1_ns': float(t1_ns), 't2_ns': float(t2_ns),
        })
    return records


def select_pulse(*, min_fidelity: float = .99, **conditions) -> tuple[dict | None, list[dict]]:
    """Choose shortest qualifying pulse, or None if no pulse qualifies."""
    limit = _threshold(min_fidelity)
    records = evaluate_pulses(**conditions)
    eligible = [r for r in records if r['fidelity'] >= limit - THRESHOLD_TOLERANCE]
    choice = min(eligible, key=lambda r: (r['duration_ns'], -r['fidelity'])) if eligible else None
    return choice, records


def robust_select_pulse(*, min_fidelity: float = .997,
                        amplitude_center: float = .05, amplitude_uncertainty: float = .02,
                        detuning_center_over_omega: float = 0.,
                        detuning_uncertainty_over_omega: float = .02,
                        primitive_duration_ns: float = 100.,
                        t1_ns: float = 200000., t2_ns: float = 150000.,
                        points_per_axis: int = 5) -> tuple[dict | None, list[dict]]:
    """Choose shortest pulse meeting a sampled worst-case fidelity constraint.

    This finite-grid check is NOT a guarantee over the full continuous uncertainty
    box, nor a physical-hardware performance guarantee. The drive strength is
    held fixed across the three candidate sequences.
    """
    limit = _threshold(min_fidelity)
    if isinstance(points_per_axis, (bool, np.bool_)) or not isinstance(points_per_axis, (int, np.integer)) or points_per_axis < 3:
        raise ValueError('points_per_axis must be an integer >= 3.')
    for name, val in (
        ('amplitude_center', amplitude_center),
        ('amplitude_uncertainty', amplitude_uncertainty),
        ('detuning_center_over_omega', detuning_center_over_omega),
        ('detuning_uncertainty_over_omega', detuning_uncertainty_over_omega),
    ):
        if not np.isscalar(val) or not np.isfinite(val):
            raise ValueError(f'{name} must be a finite real scalar.')
    if amplitude_uncertainty < 0 or detuning_uncertainty_over_omega < 0:
        raise ValueError('Uncertainty widths cannot be negative.')
    duration = float(primitive_duration_ns)
    if not np.isfinite(duration) or duration <= 0:
        raise ValueError('primitive_duration_ns must be positive and finite.')
    omega = np.pi / duration
    base = dict(primitive_duration_ns=duration, t1_ns=t1_ns, t2_ns=t2_ns)
    nominal = evaluate_pulses(
        amplitude_error=amplitude_center,
        detuning_rad_per_ns=detuning_center_over_omega * omega,
        **base)
    nominal_by_name = {r['sequence']: r for r in nominal}
    worst = {s: float('inf') for s in SEQUENCE_NAMES}
    amps = np.linspace(amplitude_center - amplitude_uncertainty,
                       amplitude_center + amplitude_uncertainty, points_per_axis)
    dets = np.linspace(detuning_center_over_omega - detuning_uncertainty_over_omega,
                       detuning_center_over_omega + detuning_uncertainty_over_omega, points_per_axis)
    for amp in amps:
        for det in dets:
            for r in evaluate_pulses(amplitude_error=float(amp),
                                     detuning_rad_per_ns=float(det * omega), **base):
                worst[r['sequence']] = min(worst[r['sequence']], r['fidelity'])
    records = [
        {'sequence': s,
         'duration_ns': nominal_by_name[s]['duration_ns'],
         'nominal_fidelity': nominal_by_name[s]['fidelity'],
         'sampled_worst_fidelity': worst[s],
         'robust_pass': worst[s] >= limit - THRESHOLD_TOLERANCE}
        for s in SEQUENCE_NAMES
    ]
    eligible = [r for r in records if r['robust_pass']]
    choice = min(eligible, key=lambda r: (r['duration_ns'], -r['sampled_worst_fidelity'])) if eligible else None
    return choice, records
