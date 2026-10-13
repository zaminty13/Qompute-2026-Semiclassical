# PulseWise: noise-aware pulse selection (Track 3)

The selector compares three implementations of a nominal single-qubit X gate:
Primitive X, BB1 (amplitude-error suppression), and CORPSE (detuning-error
suppression). It uses the existing `src/pulses.py` / `src/decoherence.py` models,
Qiskit `SuperOp`, and `qiskit.quantum_info.average_gate_fidelity`.

## Quick start

From the **repository root** on the `feature/decoherence`-based branch:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_selector.py' -v
python src/plot_selector.py --quick
python src/plot_selector.py
```

The results are generated under `results/selector/`:

- `fidelity_duration.png` (+ CSV): the sampled fidelity/duration Pareto frontier.
- `pulse_selection_map.png` (+ CSV): fastest passing sequence versus amplitude
  calibration error and normalized detuning, including a no-feasible region.
- `gridium_inspired_robustness.png` (+ CSV): nominal fidelity versus worst
  fidelity across a **finite grid** of uncertain control errors.
- `coherence_crossover.png` (+ CSV): how the preferable control method changes
  as qubit coherence times vary.

## Selection rules

- `select_pulse(min_fidelity=..., **conditions)` evaluates all three candidates
  with the same nominal drive amplitude, taking account of the **full duration**
  of each sequence; it picks the fastest candidate meeting the threshold.
- `robust_select_pulse(...)` uses the minimum fidelity on a finite rectangular
  amplitude-error/detuning grid. A sampled minimum is **not** a guarantee over
  the continuous domain or on actual hardware.
- If no candidate passes the threshold, the selector returns `None`.
- The duration sweep allows drive strength to change as Omega=pi/T_primitive.
  It is a hypothetical comparison, not a calibrated device-specific control
  optimization with drive-strength constraints.

## Known demonstration scenarios

All are simulated with a 100 ns primitive X and the Qiskit fidelity metric.

| Scenario | Parameters | Threshold | Expected recommendation |
|---|---|---|---|
| Decoherence limited | amplitude=5%; detuning=0; T1=30 µs; T2=20 µs | 99% | Primitive X |
| Amplitude error | amplitude=5%; detuning=0; T1=200 µs; T2=150 µs | 99.7% | BB1 |
| Detuning error | amplitude=0; detuning/Omega=0.1; T1=200 µs; T2=150 µs | 99.7% | CORPSE |

## Scientific limitations

- Simulated two-level driven system with ideal rectangular pulse segments.
- Physical pulse schedule execution on IBM hardware is **not** demonstrated.
- Bandwidth, signal distortions, leakage to higher levels, drift, calibrator
  uncertainty beyond modeled bounds, and compilation constraints are excluded.
- Average gate fidelity is not the same as single-input state fidelity.
- An Aer simulation using an inserted Kraus channel validates channel handling,
  not an independently measured implementation of the underlying analog drive.
- Qiskit Experiments randomized benchmarking should be added by the benchmarking
  team member with **matched pulse-specific channels** for a meaningful comparison.

## Reuse from Gridium

The method borrows Gridium's preference for constrained candidate selection,
Pareto comparison, robustness sweeps, and reproducible analysis. It does **not**
import the Gridium Hamiltonian or use its simulated gate fidelities as evidence
for this distinct two-level model.
