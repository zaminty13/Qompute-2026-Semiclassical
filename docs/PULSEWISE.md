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
- Randomized benchmarking has been added, (see 'Randomized Benchmarking' below) using matched pulse-specific channels.

## Reuse from Gridium

The method borrows Gridium's preference for constrained candidate selection,
Pareto comparison, robustness sweeps, and reproducible analysis. It does **not**
import the Gridium Hamiltonian or use its simulated gate fidelities as evidence
for this distinct two-level model.


## Randomized Benchmarking
`src/rb.py` adds randomized benchmarking for the same three pulse implementations and answers the team's original question: is a composite pulse's improved accuracy worth its extra time?

### Approach
- Randomizes over a restricted two-element group (apply X, or do nothing), instead of the full 24-element single-qubit Clifford group. BB1 and CORPSE are derived for a fixed pi rotation, so generalizing them to arbitrary Clifford rotations was out of scope, which resulted in a deliberate simplification.
- Builds each random sequence (plus its inverting gate) as either a 2x2 unitary (coherent errors only) or a 4x4 SuperOp via `decoherence.sequence_superop` (the same matched and pulse-specific channel `select_pulse.py` uses) then fits an exponential decay across sequence lengths to extract an error-per-gate estimate.
- `src/plot_rb.py` runs this for primitive/BB1/CORPSE, coherent-only and with T1/T2 decoherence, saving plots and a CSV to `results/rb/`.
- `src/compare_rb_selector.py` runs `select_pulse.evaluate_pulses()` and the randomized benchmarking under the same noise conditions, confirming both use the same physics and reporting where the two measurements agree or disagree.
- `tests/test_rb.py` covers the core logic (8 tests)

### Qiskit Experiments' `InterleavedRB`
We also explored using Qiskit Experiments' own `InterleaveRB` directly, with a custom gate whose noise came from `decoherence.sequence_superop(...)`. However, we unfortunately ran into a subtlety: Aer applies a gate's ideal unitary before attaching noise, so attaching our full physical channel (which already includes the intended rotation) double-applies the rotation, and produces a non-physical ~50% error-per-Clifford. The fix (isolating just the residual error channel) is solvable but needed more verification than time accounted for. We're reporting this exploration honestly rather than publishing the broken ~50% error-per-Clifford number it produced. All results in this document come from the RB implementation above, which is independently verified against known cases and covered by a passing test suite.

### Result
Whether the extra time is worth it depends entirely on which error dominates. We observed that BB1 cuts amplitude-error-only infidelity by ~200x over primitive, even after paying its 5x duration cost under realistic T1/T2. With no coherent error at all, BB1/CORPSE's longer duration makes them strictly worse than primitive. In a mixed scenario, direct fidelity and RB-measured error-per-gate disagree on which pulse is best, which showcases how one-shot theoretical fidelity can miss what repeated real use reveals.