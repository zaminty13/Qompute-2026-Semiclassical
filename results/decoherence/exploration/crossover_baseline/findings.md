# Day 2 findings

Illustrative two-level results at shared Omega = pi/100 rad/ns. Primitive X lasts 100 ns, BB1 500 ns, and CORPSE 433.333333 ns. These are pairwise comparisons, not a ranking of every pulse under every condition.

## Refined crossings

| Sweep | T1/T2 case | Coordinate | Percent or delta/Omega | Primitive F | Composite F | Left winner | Right winner |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| amplitude | stronger | 0.103485030643 fraction | 10.348503064333329% | 0.978259116344 | 0.978259116344 | primitive | composite |
| amplitude | baseline | 0.073339069481 fraction | 7.333906948100344% | 0.989010976177 | 0.989010976177 | primitive | composite |
| amplitude | weaker | 0.0519185028764 fraction | 5.191850287635004% | 0.994475191630 | 0.994475191630 | primitive | composite |
| detuning | stronger | -0.00467990517593 rad/ns | -0.14896600839012364 | 0.981040543069 | 0.981040543069 | composite | primitive |
| detuning | stronger | 0.00467990517593 rad/ns | 0.14896600839012422 | 0.981040543069 | 0.981040543069 | primitive | composite |
| detuning | baseline | -0.00330847430727 rad/ns | -0.10531200801879471 | 0.990454014655 | 0.990454014655 | composite | primitive |
| detuning | baseline | 0.00330847430727 rad/ns | 0.10531200801879419 | 0.990454014655 | 0.990454014655 | primitive | composite |
| detuning | weaker | -0.00234018074485 rad/ns | -0.07449026665426572 | 0.995207237439 | 0.995207237439 | composite | primitive |
| detuning | weaker | 0.00234018074485 rad/ns | 0.0744902666542658 | 0.995207237439 | 0.995207237439 | primitive | composite |

Stronger T1/T2 = 15,000/10,000 ns; baseline = 30,000/20,000 ns; weaker = 60,000/40,000 ns.

## Favorable intervals

For each noisy amplitude case, primitive is favored below its crossing and BB1 above it through 0.20 (20%). For each noisy detuning case, primitive is favored between the negative and positive crossings; CORPSE is favored outside them through the evaluated endpoints -0.01 and +0.01 rad/ns. Equality is a tie. Tiny bands with absolute Delta F <= 1e-10 are also treated as ties; intervals.csv retains their refined boundaries.

In the coherent-only limit, neither sweep has a preference-changing crossing. BB1 is favored for amplitude errors above approximately 7.79697e-6 through 0.20; smaller errors are numerical ties at this tolerance. CORPSE is favored for absolute detuning above approximately 3.84765e-7 rad/ns through 0.01 rad/ns, with a numerical tie band around zero. The zero-error equality is not an order-changing crossing.

Longer coherence times reduce the error level needed to justify the longer composite pulse. BB1 suppresses amplitude error and CORPSE suppresses detuning error, but their extra rotations accumulate noise. Thus shortest is not always most accurate. No claims extend beyond these ranges.

## Numerical evidence

Each of eight sweep/case combinations used 1,001 and 2,001 independently evaluated points. Amplitude spacings: 0.0002 and 0.0001 fraction. Detuning spacings: 0.00002 and 0.00001 rad/ns. Brent root refinement used absolute coordinate tolerance 1e-12 and relative tolerance 1e-12. Meaningful fidelity difference tolerance: 1e-10.

Both grids found the same nine roots; the largest coordinate shift was 1.215e-13. Maximum fresh root residual was 3.458e-13 in fidelity. Fresh bracket-endpoint checks and additional probes at root +/-1e-5 fraction or +/-1e-6 rad/ns all changed preference. The 18 noisy channels evaluated at roots were completely positive and trace preserving within 1e-12.

Positive and negative detuning were calculated separately; their fidelities agree within 6.662e-16 over these grids. No additional crossing was detected by the finer grid. This is numerical evidence, not a mathematical guarantee against narrow missed features. Plots were visually inspected for curve coverage, labels and clipping.

Baseline: 29 tests passed in 1.066 s. Added five numerical-analysis tests passed in 0.002 s. Final: 34 tests passed in 1.089 s. The original 29 tests remain unchanged. Analysis elapsed time: 27.14 s.

## Reproduction

Run in PowerShell from the repository root:

```powershell
.\.venv\Scripts\python.exe src\analyze_crossovers.py --points 1001 --run-name day2 --no-show
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_crossovers.py -v
```

An existing run directory is preserved; reruns create a timestamp-suffixed sibling. All analysis outputs stay under results/decoherence/exploration/. No existing source, tests, documentation or results were changed.

## Interpretation for a future selector

This analysis answers which candidate has higher fidelity at shared drive strength. The separate question of the shortest pulse meeting a required fidelity needs a fidelity requirement and permitted drive range. These rows provide candidate fidelities and actual durations at this one shared drive; they can screen candidates but cannot optimize over untested drives or errors. No selector was implemented.

Only fixed X-pi sequences are implemented. Segment functions support arbitrary equatorial phases and angles, but generalized BB1/CORPSE and benchmarking compilation are missing. README.md names randomized benchmarking; a cross-entropy benchmarking workflow is not established by the current repository. These workflows should not be treated as interchangeable.

The model omits leakage, drive limits, shaped pulses, finite-temperature excitation and drive-dependent noise. All parameters are examples, not calibrated hardware values. Highest simulated fidelity is not a claim of global or hardware optimality.
