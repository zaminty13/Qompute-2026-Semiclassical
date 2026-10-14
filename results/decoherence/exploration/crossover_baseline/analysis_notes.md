# Crossover analysis

Illustrative two-level X-gate simulations; not hardware measurements.

Delta F = F_composite - F_primitive. A difference within 1e-10 is a numerical tie. Root tolerance is 1e-12 in the coordinate units (fraction or rad/ns), with rtol 1e-12. Significant opposite signs bracket roots; exact ties and touches are not counted as order changes.

crossovers.csv includes both fidelities, durations, refined coordinates, and fresh simulator evaluations at the bracket endpoints on either side. intervals.csv uses refined +/-1e-10 boundaries: endpoints at these thresholds belong to the tie band. Domain endpoints are included. Intervals are inferred from samples and fresh midpoint checks, not proven analytically. The finer-grid check is numerical evidence, not a guarantee against unobserved narrow features.

Coherent-only uses the existing unitary simulator and Qiskit fidelity. Every noisy result uses the complete Lindblad SuperOp. Positive and negative detuning are evaluated independently. T1/T2 scale together; the coherent limit is separate. Shared drive means actual durations 100 ns (primitive), 500 ns (BB1), and 433.333333 ns (CORPSE).

Each sweep CSV contains paired fidelities, parameters, units, sequence names and durations. Coarse and fine files retain both independently evaluated grids. Metadata records versions, source hashes, spacing checks and tolerances. Existing output directories are never overwritten; a repeated run gets a timestamp suffix.

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe src\analyze_crossovers.py --points 1001 --run-name day2 --no-show
```
