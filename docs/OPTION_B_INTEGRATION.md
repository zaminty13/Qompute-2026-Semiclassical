# Option B — Reliability Benchmarks: reproducibility and scientific handoff

This is a **component already integrated into the PulseWise main application**. No separate ZIP install, feature branch, or pull request is needed to run it.

## Run from the repository root

```bash
python -m pip install -r requirements-research.txt
python -m unittest discover -s tests -p "test_*.py" -v
python src/build_option_b.py                 # numerical figures, CSV, JSON
python src/build_option_b.py --qiskit        # adds 45 Qiskit Aer checks
python -m streamlit run app.py               # select Reliability Benchmarks
```

All numerical results are regenerated from the frozen optimizer candidate at `results/research/optimization_report.json`, falling back to the committed `results/option_b/baseline_optimizer_report.json` when necessary. The builder does **not** optimize a new waveform.

## Experiments and separate physical models

| Study | Primary output | Scientific scope |
| --- | --- | --- |
| Single-gate constrained synthesis | Minimum sampled average gate fidelity and modeled duration | No global optimality certificate |
| X^32 known-answer identity | Correct final-bit probability, segment count and modeled total control time | Two-level noisy Lindblad channels; fixed calibration error per circuit |
| Three-bit parity | Mean correct parity over all eight inputs | Noisy input X preparations; ideal CNOT and readout |
| Four-level comparison | Unconditional logical fidelity, final/peak leakage | Coherent surrogate; **no T₁/T₂** and not the physical Gridium Hamiltonian |
| Optimizer stress | In-domain and shifted-calibration sampled failure rates | Finite samples; no continuous-region guarantee |
| Qiskit Aer | 45 circuits, 2,048 shots each; X^32 and parity | Circuit/sampling consistency using **same modeled channels** |

For the exact frozen findings see [`../results/option_b/NUMERICAL_FINDINGS.md`](../results/option_b/NUMERICAL_FINDINGS.md).

## Interpretation notes

- A high average fidelity for an **individual gate** can conceal coherent error accumulation across longer circuits. The probability of a correct result need not decrease monotonically with depth.
- The synthesized 345.68 ns waveform was chosen for short duration subject to sampled **single-gate** constraints, *not* circuit depth or multilevel performance.
- All four waveforms use identical drive limits within each comparison, but **different physical models must never be equated**.
- The sample-boundary and shifted-box results indicate model fragility; they do not prove global optimality or device-level reliability.
- Aer shot agreement is not an independent hardware or physical-model validation.
- Real deployment would require calibrated parameters, pulse hardware support, gate/readout errors, and cross-device testing.

## Implementation map

- `src/option_b_benchmarks.py`: reference controls, mathematical channel repetition, parity prediction, four-level comparison, stress tests, optional Aer.
- `src/build_option_b.py`: deterministic figures and CSV/JSON provenance; explicitly verifies identity depth 32 with Aer when requested.
- `pages/3_Reliability_Benchmarks.py`: interactive visualization and a collapsible detailed Aer evidence table.
- `tests/test_option_b_benchmarks.py`: mathematical sanity checks and optional Aer regression tests.

## Judge-facing demonstration

Open **Control Lab** to explain the fidelity/duration tradeoff; show the **Research Lab** candidate optimized for one modeled goal; then open **Reliability Benchmarks** to show its X^32 failure case, the coherent four-level surrogate, and the Aer consistency summary. State each model's caveats explicitly and close on transparent reliability reporting.
