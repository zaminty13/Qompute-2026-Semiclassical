# PulseWise Option B — safe integration and scientific handoff

## What this adds

- `src/option_b_benchmarks.py`: matched four-pulse coherent 4D surrogate; exact noisy X^depth circuit model; 3-bit parity known-answer algorithm; frozen optimizer stress suite; optional Qiskit Aer shot checks.
- `src/build_option_b.py`: reproducible CSV, JSON, and 5 presentation-grade figures.
- `pages/3_Reliability_Benchmarks.py`: independent Streamlit page, avoids modifying earlier app or scientific code.
- `tests/test_option_b_benchmarks.py`: adversarial regression tests and an Aer sampling check.
- `results/option_b/*`: precomputed deterministic mathematical model outputs, **not hardware measurements**.

**No existing team science files, tests, dashboard pages, or branches are overwritten by this overlay.**

## Safe install on the Mac (from repository root)

1. Keep PR #2 intact. Create a branch **from** `feature/interactive-demo`:

   ```bash
   git switch feature/interactive-demo
   git pull --ff-only origin feature/interactive-demo
   git switch -c feature/reliability-benchmarks
   ```

2. Extract `PulseWise_Option_B_Upgrade.zip` in Finder, then from the repo root:

   ```bash
   UPGRADE="$HOME/Downloads/PulseWise_Option_B_Upgrade"
   cp "$UPGRADE/src/option_b_benchmarks.py" src/
   cp "$UPGRADE/src/build_option_b.py" src/
   cp "$UPGRADE/tests/test_option_b_benchmarks.py" tests/
   cp "$UPGRADE/pages/3_Reliability_Benchmarks.py" pages/
   mkdir -p results/option_b docs
   cp "$UPGRADE"/results/option_b/* results/option_b/
   cp "$UPGRADE/docs/OPTION_B_INTEGRATION.md" docs/
   ```

   If Finder chooses another extraction name, adjust only `UPGRADE`.

3. Validate **in this order**, using the same environment that ran your 53 passing tests:

   ```bash
   python -m unittest discover -s tests -p 'test_option_b_benchmarks.py' -v
   python src/build_option_b.py
   python src/build_option_b.py --qiskit
   python -m unittest discover -s tests -p 'test_*.py' -v
   python -m streamlit run app.py
   ```

4. In the Streamlit sidebar, open `Reliability Benchmarks`. Inspect all three regimes and the Aer button. Avoid merging until local Aer and the full regression suite pass.

5. After review:

   ```bash
   git status --short
   git add src/option_b_benchmarks.py src/build_option_b.py
   git add tests/test_option_b_benchmarks.py pages/3_Reliability_Benchmarks.py
   git add docs/OPTION_B_INTEGRATION.md results/option_b/
   git diff --cached --check
   git commit -m 'Benchmark pulse reliability across circuits and multilevel leakage'
   git push -u origin feature/reliability-benchmarks
   ```

   Open a PR targeting `feature/interactive-demo`. Do NOT push directly to `main` or overwrite PR #2. Coordinate final integration with teammates.

## Experimental matrix

| Experiment | Model | Primary metric | Limitation |
| --- | --- | --- | --- |
| Single gate threshold | Lindblad 2-level model | Average gate fidelity | Objective does not include repeated circuits |
| X^depth known answer | Repeated 2-level Lindblad channel at fixed calibration bias | Correct terminal-bit probability | Does not model gates beyond X or hardware drift |
| 3-bit parity algorithm | Noisy X preparations + ideal CX | Mean correct parity over 8 inputs | Ideal entangling gates and readout |
| Multilevel comparison | Coherent 4D ladder with spectator | Logical fidelity, final/peak leakage | No T1/T2 and not physical Gridium Hamiltonian |
| Optimizer stress | Exact 2-level Lindblad evaluations on unseen grids | Worst sampled fidelity; fraction failing | No continuous-region certificate |

The frozen waveform's single-gate sampled fidelity was measured on the training/heldout sets. It was not chosen for circuit depth or multilevel robustness, so the new experiments are **genuinely out-of-objective**, but they still reuse the same mathematical dynamical models and are not hardware-independent validation.

## Important caveats

- Same Rabi rate and fixed maximum drive magnitude are used for each sequence.
- A longer composite pulse incurs longer T1/T2 exposure; a short pulse can still have a worse circuit result because coherent systematic errors accumulate.
- The X^depth reliability curve can be nonmonotonic due to coherent phase accumulation and revivals; do not claim monotonic decay or universality.
- The simulated winner depends on the specific calibration error, detuning, depth, and error model.
- The four-dimensional surrogate is **inspired by multilevel reasoning used in Gridium**, not Gridium's validated hardware Hamiltonian.
- Aer uses the same derived noisy channels, making it a circuit/sampling consistency check, **not** an independent physics experiment.
- Only results explicitly labeled 'Qiskit Aer checks passed' from a completed successful Mac test can be described as Qiskit-validated.
- No device characterization, native Qiskit Pulse waveform execution, or hardware benchmark is included.

## Suggested ten-minute talk placement

1. Show original PulseWise pulse choice and 30.9% reduced duration **for single-gate optimization only**.
2. Ask whether the faster pulse produces correct answers in an actual circuit.
3. Show Figure `01_known_answer_depth.png`: the short optimized pulse can fail under repeated coherent errors; BB1 may preserve correctness.
4. Show Figure `02_matched_multilevel.png`: the same controls can rank differently in the coherent four-level model.
5. Reveal limits, resource costs, and failure under shifted out-of-domain calibration.
6. Demonstrate the Qiskit 3-bit parity algorithm and Aer shot check (only after running it successfully).
7. Close with societal relevance: transparent reliability, error/resource costs, and avoiding false confidence in NISQ results.
