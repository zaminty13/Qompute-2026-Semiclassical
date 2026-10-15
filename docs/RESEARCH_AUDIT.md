# Research Lab scientific audit — 2026-10-14

This note accompanies PR #7. Findings come from three user-exported live
Research Lab JSON reports, examined at full floating-point precision.
The reports and pre-existing frozen benchmark artifacts were NOT rewritten.

## Main physical interpretation

The matched SLSQP runs use identical five-segment parameterizations, bounds,
training samples, drive amplitude and target. Under these three tested settings,
the BB1- and primitive-initialized solutions become almost purely x-axis
rotations, with total pulse area approximately 0.963–0.979 pi. They therefore
behave like slightly underrotated primitive X gates split into five pieces.
This explains the extremely similar durations and fidelities. It does NOT
demonstrate retained BB1 composite-pulse error cancellation or global optimality.

The short duration is allowed because the fidelity *threshold* is below 100%.
The optimizer trades some fidelity for time. A fixed-Rabi-rate perfect X(pi)
gate still needs 100 ns under this model; a 96 ns near-X gate is not a
faster exact X(pi) implementation.

| Run | Amp ± | Detuning ± | Required fidelity | T1/T2 (us) | Fastest sampled passing | Time (ns) | Reduction versus passing primitive (100 ns) |
|---|---:|---:|---:|---|---|---:|---:|
| A | 5% | 0.040 | 98.7% | 200/150 | BB1-initialized SLSQP | 96.341194 | 3.66% |
| B | 3% | 0.060 | 99.1% | 130/150 | Primitive-initialized SLSQP | 96.610331 | 3.39% |
| C | 9% | 0.015 | 98.0% | 130/150 | BB1-initialized SLSQP | 97.863860 | 2.14% |

In every case the BB1/Primitive local-refinement times differ by less than
0.003 ns. Treat the identity of the reported fastest candidate as a numerical
near-tie, not a substantive algorithmic advantage.

The standard, unoptimized BB1 duration is 500 ns. A ~80% reduction *versus
BB1* is mathematically correct but by itself misleading because an unoptimized
100 ns primitive pulse also passes in all three of these cases. Compare against
the fastest **passing** conventional reference as well.

## Optimization caveats

- The SLSQP objective minimizes total pulse angle at fixed Rabi rate, with
  nine sampled train-fidelity constraints and a fixed internal 0.003
  percentage-point safety margin. A reported PASS checks the advertised
  threshold on nine training and 96 selection points; it does not imply a
  numerically successful SLSQP termination.
- In A, BB1-initialized SLSQP hit its 65-iteration limit, and its minimum
  internal safety-constraint residual was -1.84e-5 in fractional fidelity.
  It nevertheless passed the *advertised* 98.7% threshold. The
  Primitive-initialized alternative terminated successfully and was only
  0.000664 ns slower. It is not scientifically sensible to call BB1 superior.
- All three Differential Evolution runs exhausted their configured iteration
  budgets and failed the fidelity threshold. They are unsuccessful exploratory
  candidates, not validation of the global search strategy.
- The 96-point dataset is used for candidate selection. It must NOT be
  described as a final untouched test set.
- "Full" vs "Quick" currently changes the differential-evolution budget,
  while the three SLSQP refinements retain the same 65-iteration setting.

## Independent post-selection sampling in the same model

The separate diagnostic routine generates a 19 x 19 grid plus 128 seeded
random locations, removes all exact training and selection locations and
evaluates the displayed winner, duration near-ties, and fastest passing
reference without changing the winner. On the uploaded reports, each yielded
480 new evaluated locations, and no tested candidate fell below its configured
threshold on those points. This is an *in-model* post-selection stress test;
it is not a continuous minimization, error-model independence, or real
hardware validation.

## Appropriate demo claims

PulseWise implements and cross-checks a model-based, sampled-constrained
classical pulse optimization and fair multi-seed comparison. It reveals how
a relaxed fidelity threshold permits faster approximate gates and why nominal
pulse speed, single-gate fidelity, and circuit-level reliability must be
examined together. Do not describe this as a calibrated superconducting
hardware schedule, experimentally verified gate, globally fastest pulse,
or a validated Gridium physical Hamiltonian.
