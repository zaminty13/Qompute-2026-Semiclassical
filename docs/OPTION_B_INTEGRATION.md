# Option B — Reliability Benchmarks: reproducibility and scientific handoff

This is a **component already integrated into the PulseWise main application**. No separate ZIP install, feature branch, or pull request is needed to run it.

## Local integration checkout

The current reviewed assembly is `d698222` on `feature/integration-review`,
including integration commit `e160387` and the main documentation through
`85785c1`. This reference identifies the inspected state; it is not a reset
instruction. The branch is already present on origin. The original checkout
remains on `feature/decoherence`. Preserve later commits and uncommitted work.
`docs/decoherence.md` is explicitly excluded from publication by the owner and
is not copied into this review worktree. This isolated correction uses branch
`feature/rb-survival-review`; the completed integration checkout is untouched.

Use your own checkout path. This prepared checkout already has its own `.venv`:

```powershell
Set-Location (Read-Host 'Enter the full path to your integration checkout')
code .
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_*.py' -v
.\.venv\Scripts\python.exe -B -m streamlit run app.py --server.address=127.0.0.1 --server.port=8502 --server.headless=true --browser.gatherUsageStats=false
```

For a new environment only, run `py -m venv .venv`, then
`.\.venv\Scripts\python.exe -m pip install -r requirements-research.txt`.
Do not install into the original checkout's environment. Stop an existing local
server on port 8502 before starting another, or select another local port.

## Which saved waveform is displayed?

The default is **only** `results/research/optimization_report.json`, the source
of the reviewed 345.678608 ns waveform and 4.3164% repeated-X result.
`results/option_b/baseline_optimizer_report.json` is preserved as historical
material; its slightly different 345.677183 ns waveform gives 4.3073%, and is
not a fallback for the current presentation or tests.

`src/result_provenance.py` hashes a canonical JSON payload containing schema 1,
the full experiment configuration, winner name, and all candidate names and
ordered segment angles/phases (candidates sorted by name). Metrics and solver
metadata are excluded. All fields use the report's JSON numeric representation.
The current SHA-256 is:

`7ab267d72c5971d2306f82011be7f5c4c7cfe78eb561474ec0056608787a2801`

Both research and reliability pages show this identifier. New optimizer reports,
reliability summaries and Aer results record it. The unchanged historical JSON
results have no embedded identifier: `docs/reviewed_results.json` binds their
exact file hashes to this reviewed waveform/configuration bundle. This is
reproducibility metadata, not a hardware certificate.

Missing, changed or incompatible saved results are hidden with an explanation.
A new in-session research report also invalidates incompatible reliability/Aer
results; changing sidebar inputs alone leaves the saved report visible with a
warning. Reloading the browser clears an unsaved research session. Future results
must be generated explicitly for the intended saved report. No automatic fallback
or optimizer run is performed by the reliability page.

The existing builders overwrite their output directories when called directly.
To verify the saved waveform without changing those directories or optimizing:

```powershell
@'
import sys, tempfile
from pathlib import Path
sys.path.insert(0, 'src')
import build_option_b
build_option_b.OUT = Path(tempfile.mkdtemp(prefix='qompute-validation-'))
build_option_b.build(run_qiskit=True)
'@ | .\.venv\Scripts\python.exe -B -
```

This writes fresh figures, CSVs and JSON to the printed temporary location. Keep
historical reports/results intact. Do not update the legacy manifest merely to
bypass a mismatch: first verify the new waveform and regenerate matching results.

## Local crossover contribution

The copied `src/analyze_crossovers.py`, `tests/test_crossovers.py`, and 26 files
are preserved; the 26 exploration files now live under
`results/decoherence/exploration/crossover_baseline/`. Only the integration copy
was renamed from `day2`, with all file contents verified identical. Historical
metadata retains its original run name and command. The CLI default remains
`day2` for compatibility; use `--run-name crossover_baseline` explicitly. All 29 files checked during the original local integration initially matched their source SHA-256 hashes. The unpublished decoherence notes are not included in this branch.

For the original model, see [src/decoherence.py](../src/decoherence.py). For the crossover analysis, see [analysis_notes.md](../results/decoherence/exploration/crossover_baseline/analysis_notes.md). The crossover analysis uses T1 = 30 us and T2 = 20 us, while the optimizer uses T1 = 200 us and T2 = 150 us. Both are illustrative simulation parameters.
## Selection and solver reporting

Nine training points enter optimization. The additional 96 points are
**validation used during candidate selection**, including eligibility and tie
breaking. Existing API/JSON keys such as `heldout_worst`, `n_heldout` and
`held_out=True` remain for compatibility, but mean this validation set.
The subsequent dense grid includes some training nodes; new random stress points
are separate from optimization/selection. None certifies a continuous region.

The advertised fidelity requirement is **0.997**. The internal SLSQP safety target
is **0.99703**. The selected saved candidate's minimum is **0.9970266918518526**:
it passes the advertised requirement but misses the safety target by about
0.00000331. Historical solver termination metadata is unavailable, not inferred.
For future optimization runs, `solver_reports` records each solver's success,
status/message, iteration/evaluation counts when available, per-point fidelity
residuals against both thresholds, angle-budget slack and bound residuals.
Positive residuals mean satisfied constraints. The DE safety residual is a
comparison diagnostic, not an added DE constraint. Objectives, constraints and
candidate selection have not been changed. No new optimization was run here.

## Leakage sampling

The displayed peak is the **maximum over sampled times**, not a proven
continuous-time maximum. Dashboard/comparison: 18 steps per segment; Option B
anharmonicity sweep: 12; research leakage figure: 8. Segment endpoints are included.
New output metadata records the resolution. Historical PNG/CSV/JSON files remain
unchanged and may retain older wording; use these qualifications when presenting
them. This is a separate coherent surrogate with **no T1/T2 noise**.

## Experiments and separate physical models

| Study | Primary output | Scientific scope |
| --- | --- | --- |
| Single-gate constrained synthesis | Minimum sampled average gate fidelity and modeled duration | No global optimality certificate |
| X^32 known-answer identity | Correct final-bit probability, segment count and modeled total control time | Two-level noisy Lindblad channels; fixed calibration error per circuit |
| Three-bit parity | Mean correct parity over all eight inputs | Noisy input X preparations; ideal CNOT and readout |
| Four-level comparison | Unconditional logical fidelity, final/sampled-peak leakage | Coherent surrogate; **no T₁/T₂** and not the physical Gridium Hamiltonian |
| Optimizer stress | In-domain and shifted-calibration sampled failure rates | Finite samples; no continuous-region guarantee |
| Qiskit Aer | 45 circuits, 2,048 shots each; X^32 and parity | Circuit/sampling consistency using **same modeled channels** |

The selected candidate is approximately 30.9% shorter than BB1 at the sampled
single-gate threshold, not universally better. At +5% amplitude error and
Delta/Omega = +0.04 with T1/T2 = 200/150 us, X^32 correct-output probability is
about **4.32% synthesized versus 95.57% BB1**. This metric is distinct from
average gate fidelity. Repeated-X and parity are not randomized benchmarking.
Taylor SQ's later contribution `7e31e44` is on `origin/feature/decoherence`.
Its source and historical outputs are imported into the isolated survival-review
worktree with narrow corrections. It is accepted only as the state-specific
X/identity survival study described in [PULSEWISE.md](PULSEWISE.md#randomized-xidentity-survival-analysis),
not as standard randomized benchmarking.

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
- `src/result_provenance.py`: report identity and saved-result compatibility checks.
- `src/build_option_b.py`: deterministic figures and CSV/JSON provenance; explicitly verifies identity depth 32 with Aer when requested.
- `pages/3_Reliability_Benchmarks.py`: interactive visualization and a collapsible detailed Aer evidence table.
- `tests/test_option_b_benchmarks.py`: mathematical sanity checks and optional Aer regression tests.

## Judge-facing demonstration

Open **Control Lab** to explain the fidelity/duration tradeoff; show the **Research Lab** candidate optimized for one modeled goal; then open **Reliability Benchmarks** to show its X^32 failure case, the coherent four-level surrogate, and the Aer consistency summary. State each model's caveats explicitly and close on transparent reliability reporting.

## Integration validation

The combined pre-fix baseline was **69 tests across 10 files**. After adding
`test_result_provenance.py` (7 tests) and `test_dashboard.py` (6 tests), the suite
passes **82 tests across 12 files**. The existing reliability tests now use the
same selected research report as the dashboard and builder. No test is skipped
in the prepared research environment. An initial attempt during dependency
installation had import errors; the completed environment passed the baseline.

Streamlit AppTest covers default pages, valid control/noise changes, detuning
and time conversions, no qualifying pulse, saved-report warnings, missing files,
new-session waveform mismatches and stale Aer results. It never runs optimization.
The local browser also loaded the selector, research and reliability pages and
confirmed the no-feasible selector state and matching provenance identifiers.
A separate temporary result build regenerated all five figures and ran all 45
Aer circuits; results matched the saved scientific calculations. An encoding
issue caught by that build was corrected before final validation.

The prepared environment uses Python 3.14.7, Qiskit 2.5.2, Aer 0.17.2, NumPy 2.5.4,
SciPy 1.18.1 and Streamlit 1.65.0. Requirements remain unchanged and unpinned.
Streamlit reports existing `use_container_width` deprecation warnings; current
page checks pass. Matplotlib may substitute available font weights. Historical
solver metadata remains unavailable. Nothing here
establishes a hardware performance guarantee or a continuous leakage maximum.


## Corrected restricted X/identity study

The isolated review preserves Taylor SQ's contribution from `7e31e44`, its eight
original tests and all historical result bytes. The original fit-based claims are
superseded, not silently deleted. Active methodology, corrected results and
reproduction commands are in [PULSEWISE.md](PULSEWISE.md#randomized-xidentity-survival-analysis).
The working dashboard does not load the historical results/rb files, so no page
change is required. Its existing waveform/configuration checks remain intact.

The corrected workflow uses matched seeded sequences, counts noisy recovery and
physical duration, exports raw samples and sequence standard errors, and checks
means/variances using exact binomial averaging. It makes no standard-RB error-rate
claim and does not introduce idle noise or an InterleavedRB implementation.
The eight original tests plus thirteen focused survival tests supplement the
existing 82-test suite. See the final review report for the actual execution result.

Qiskit Experiments remains a declared dependency but is not needed by the corrected
survival workflow. No dependency or environment changes were made. The bounded
optional Qiskit reproduction from the earlier review is not used as scientific
evidence for pulse rankings; the original exact failure remains unreproduced.

The corrected study originates on `feature/rb-survival-review`, based on `d698222`.
Final local assembly uses `feature/final-assembly-review`; the protected original
and integration checkouts remain untouched. Inspect the final Git history for the
reviewed correction and original teammate contribution before publication.
