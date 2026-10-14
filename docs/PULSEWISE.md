# PulseWise: noise-aware pulse selection (Track 3)

The selector compares three implementations of a nominal single-qubit X gate:
Primitive X, BB1 (amplitude-error suppression), and CORPSE (detuning-error
suppression). It uses the existing `src/pulses.py` / `src/decoherence.py` models,
Qiskit `SuperOp`, and `qiskit.quantum_info.average_gate_fidelity`.

## Quick start

From the **repository root** on the validated `main` branch:

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
- This selector is **not** randomized benchmarking. For our completed known-answer
  X^32 and parity tests with Qiskit Aer, see [the architecture guide](ARCHITECTURE.md)
  and [numerical findings](../results/option_b/NUMERICAL_FINDINGS.md). These tests
  use modeled channels, not hardware data.

## External research inspiration

Our robustness and leakage analyses were informed by broader ideas in quantum
control and Gridium-related protected-qubit research. PulseWise does **not**
import the Gridium Hamiltonian, code, or measured gate data. See the public
sources and explicit attribution boundaries in [REFERENCES.md](../REFERENCES.md).


## Randomized X/Identity Survival Analysis

The corrected [survival study](../results/rb/survival_study/) builds on Taylor SQ's
[7e31e44 contribution](https://github.com/zaminty13/Qompute-2026-Semiclassical/commit/7e31e441174e3e0c44bfcd2776bfd765d6607eed).
It retains the restricted X/identity experiment because the validated composite
sequences implement X gates. It is not standard Clifford RB, interleaved RB, XEB,
or a general circuit benchmark. The primary observable is return probability to
|0>, not an error-per-gate estimate. A separate |1> control diagnoses state dependence.

Each position independently chooses X or identity from the implementation's two
equally weighted choices, so q=1/2. Identity takes zero time and has no noise.
Every X, including recovery, uses the full validated pulse-specific channel with
T1/T2 acting throughout its segments. Amplitude and detuning offsets are fixed
across gates and trials in each case. No extra ideal X is applied.

For k sampled X choices, ideal recovery adds k mod 2 further noisy X gates, so
N=k+(k mod 2). The final channel is S^N, where S is one complete physical X channel.
Order is immaterial under these assumptions: randomization samples repetition
counts, not general gate-order effects. For m positions, the exact mean is
sum over k=0..m of Binomial(m,k)*q^k*(1-q)^(m-k)*P0(S^(k+k mod 2)).
P0 means return to the initial |0> state; the diagnostic uses return to |1>.
Explicit enumeration of short sequences independently checks this reduction.
It would not apply unchanged to gate-varying errors or a noisy, finite-time idle.

The corrected workflow uses a local seeded generator and reuses identical sampled
sequences across pulse families, coherent/noisy cases, and the state diagnostic.
Legacy functions retain global-random behavior for compatibility; use
`run_survival_study` for controlled, replayable comparisons. CSVs retain every
sample's X/identity string, sampled X count, recovery count, total executed X count,
physical segment count, duration and survival. A composite X is one executed X
operation but contains several physical pulse segments.

Default settings: seed 2026; 512 independent sequences per length; lengths
2,4,8,16,32; nominal primitive X 100 ns; Omega=pi/100 rad/ns; amplitude error 0.05.
Mixed cases use detuning 0.003 rad/ns, with either infinite T1/T2 or 30000/20000 ns.
The selector comparison uses detuning zero and the finite coherence times.
The |1> diagnostic uses the same finite-coherence mixed-error configuration.
These are illustrative simulations, not measured hardware parameters.

Uncertainty bars are one standard error of the sampled sequence mean:
sample standard deviation (ddof=1) divided by sqrt(number of sequences). There are
no measurement shots. Exact binomial means, variances and standard errors are
exported separately, allowing sampling errors to be checked without an exponential
fit. Shared samples correlate pulse comparisons; uncertainties are not independent
across families. Rankings below are also confirmed by exact ensemble means.

### Duration and state interpretation

One X takes 100 ns (primitive), 500 ns (BB1), or 433.333333 ns (CORPSE). Each sample
lasts N times that duration. The duration figure plots the sampled ensemble mean,
not the identical duration of every sample; CSVs provide individual durations and
ensemble minimum/maximum. At m=32, the exact expected N is 16.5, giving expected
durations 1.65, 8.25, and 7.15 us. Families are not compared at equal elapsed time.
Connecting plotted points does not establish an equal-time ranking.

Survival is specific to initial state and protocol. Relaxation toward |0> can
increase its return probability without improving a gate. A diagnostic with drive
disabled (amplitude error -1), zero detuning, T1=1000 ns and T2=2000 ns gives
P0=1 but P1=exp(-0.2)=0.818731 after two 100 ns slots executing the nominal X
operation with ideal-parity recovery. This extreme diagnostic is not a main-study
parameter choice and is not a valid implementation of the intended X gate.
In the mixed default study at m=32, the exact |0>/|1> returns are
0.116003/0.115299 (primitive), 0.854396/0.854650 (BB1), and 0.214203/0.214284 (CORPSE).
The small differences do not certify state-independent gate quality.

### Supported comparison and withdrawn claims

At amplitude +5%, detuning zero, T1/T2=30/20 us and m=32:

| Pulse | Single-gate average fidelity | Sampled ground-state return +/- one SE | Exact mean return | Sampled mean duration (us) |
| --- | ---: | ---: | ---: | ---: |
| Primitive | 0.99369593 | 0.140028 +/- 0.005139 | 0.142011 | 1.655469 |
| BB1 | 0.98901180 | 0.855723 +/- 0.000951 | 0.856111 | 8.277344 |
| CORPSE | 0.98643279 | 0.217286 +/- 0.003871 | 0.218373 | 7.173698 |

The direct single-gate ranking is primitive, BB1, CORPSE. The selector chooses
primitive at threshold 0.99 because it is the shortest qualifying candidate.
Direct survival instead ranks BB1, CORPSE, primitive at this specified length.
The ranking difference survives removal of the fitted proxy, but compares distinct
observables and objectives; it does not make the selector wrong. No universal
ranking, equal-time advantage, or improvement across all noise regimes is claimed.

The original files directly under results/rb are historical and superseded for
scientific interpretation. Their labels and fitted proxies must not be presented
as current validated Clifford-RB errors. The old CSV ratio is
0.02722365523693393 / 0.00011478392083347222 = 237.173 for coherent MIXED errors,
and 0.027175640446069405 / 0.004673655661798559 = 5.81464 with decoherence.
Neither is a validated RB error reduction. The amplitude-only, finite-coherence
200x improvement claim is withdrawn. It is not replaced by a claim of 5.8x.

The previous fit audit found large primitive/CORPSE residuals (about 0.10 RMSE in
coherent survival), boundary fits, and a poorly identified BB1 denominator.
Twenty seeds did not establish a valid error-rate interpretation. The active
workflow does not fit exponentials or export error-per-gate proxies. `fit_decay`
remains solely for legacy compatibility and its original synthetic-fit test.

### Outputs and reproduction

Use [survival_by_length.png](../results/rb/survival_study/survival_by_length.png),
[survival_by_mean_duration.png](../results/rb/survival_study/survival_by_mean_duration.png),
and [selector_vs_survival.png](../results/rb/survival_study/selector_vs_survival.png).
Underlying files are summary.csv, samples.csv, selector_comparison.csv and
metadata.json in the same directory. Metadata records all case configurations,
package versions, source hashes, source commit and output checksums. Python and
CSV checksums normalize CRLF to LF so Git checkout line endings do not invalidate
provenance; image checksums use exact bytes.

From the review checkout, using an environment with requirements-research.txt:

```powershell
python -B -m unittest discover -s tests -p 'test_*.py' -v
$studyOutput = Join-Path $env:TEMP ('pulsewise-survival-' + [guid]::NewGuid())
python -B src/plot_rb.py --seed 2026 --trials 512 --output $studyOutput
$comparisonOutput = Join-Path $env:TEMP ('pulsewise-comparison-' + [guid]::NewGuid() + '.csv')
python -B src/compare_rb_selector.py --seed 2026 --trials 512 --output $comparisonOutput
```

Without --output, plot_rb.py targets results/rb/survival_study. It refuses to
replace an existing directory. The comparison script also refuses to overwrite
an existing file. `compare_fidelity_vs_rb` retains its import name but now returns
one dictionary per pulse and length with direct fidelity, threshold choice, and
survival statistics; the unsupported rb_error_per_gate field is intentionally
removed. Core pulse, selector, and legacy survival interfaces remain intact.

The earlier optional Qiskit InterleavedRB attempt is not evidence for a ranking.
Attaching a full physical X channel after an ideal X double-applies its rotation.
A bounded reproduction demonstrated this composition error and a bad fit, but
not the teammate's undocumented exact 50% number. This is not evidence that
Qiskit is broken. No new InterleavedRB implementation is included.

The official [Track 3 goals](https://github.com/sandraalhames/Qompute-2026#your-challenge-make-a-quantum-result-more-trustworthy)
require a known-answer experiment, ideal/noisy baselines, an error-handling
strategy and cost/impact comparison; they do not specifically require RB or XEB.
This study supplements the existing validated X^N/parity and pulse-suppression
evidence. A correct survival study alone does not complete the submission:
the required video, repository delivery and submission form still need team review.
