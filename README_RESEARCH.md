# PulseWise Research Lab — bounded control synthesis and leakage stress testing

**Team Semiclassical · Qompute 2026 · Track 3**

This additive research module builds on the team's working PulseWise dashboard. It
introduces two concrete Gridium-*inspired* ideas: automatically synthesized
multi-segment drives and leakage-aware multilevel diagnosis. It **does not** run,
reproduce, or validate the Gridium four-mode Hamiltonian. It **does not** claim
an IBM hardware pulse implementation or an experimental gate fidelity.

## Setup (from the merged Team Semiclassical repository)

These research modules are already included in `main`; no ZIP overlay, old
feature branch, or special installation process is needed.

```bash
python -m pip install -r requirements-research.txt
python -m unittest discover -s tests -p "test_*.py" -v
python src/plot_research.py --quick
python -m streamlit run app.py
```

Open **Research Lab** in Streamlit. The higher-budget `python src/plot_research.py`
run explores further, but may find a different feasible candidate; avoid
mixing newly generated optimization results with the frozen Option B report
unless you explicitly document and retest the change.

## Scientifically meaningful main experiment

**Default frozen scenario:** original X drive rate Ω = π/(100 ns), T1 = 200 μs,
T2 = 150 μs, *unknown and symmetric* amplitude-calibration error ±5%, normalized
detuning ±0.04, and minimum gate fidelity 99.7%. The objective is the **shortest
candidate that passes** both sets of *sampled* conditions. No known bias is
available to trivially recenter the waveform.

1. **References:** primitive X (100 ns), BB1 (500 ns), CORPSE (433.33 ns), with
   full physical durations. Calibrated references are included for other
   parameter-center choices.
2. **Control family:** five ordered rectangular pieces, arbitrary phase and
   duration (each angle is constrained), identical maximum Rabi strength Ω,
   and total angle budget ≤5.25π. This is not gradient optimization of an IBM
   Pulse schedule; hardware slew/bandwidth/quantization/phase-control costs
   are omitted.
3. **Classical optimizer:** seeded differential evolution plus a bounded SLSQP
   local refinement initialized from an *exactly equivalent, split BB1* seed.
   The SLSQP constraint enforces ≥99.7% on the 3×3 training grid with a small
   numerical safety margin. This is a **local candidate search**, not proof of
   a globally optimal pulse. Failed candidates are reported, not discarded.
4. **Held-out evaluation:** 96 additional samples (72 unseen points on a 9×9
   boundary-inclusive grid plus 24 seeded interior random points). **No**
   held-out fidelities enter the optimizer objective or constraints.
5. **Physics:** each rectangular segment is evolved with the exact
   time-independent Markovian Lindblad propagator of the team's `decoherence.py`
   two-level model. A formula for qubit average gate fidelity to X is used in
   the fast inner loop. The CLI and unit tests cross-check the segment channel
   and gate fidelity against Qiskit `SuperOp` and the team's independently
   coded `pulse_superop` when Qiskit is installed.
6. **Qiskit circuit evidence:** a six-cardinal-state `AerSimulator` test embeds
   the resulting channel, prepares/undoes each state and the X target, and
   compares observed success probabilities with Qiskit `average_gate_fidelity`.
   These are finite-shot checks of the SAME assumed model, not independent
   calibration or actual hardware validation.

**Frozen quick-run observation (SciPy; subsequently checked on the team’s Mac):** the synthesized candidate
achieved about 345.68 ns, versus 500 ns for BB1, while its minimum fidelity was
about 99.7027% over the nine training samples and 99.7193% across 96 disjoint
held-out samples. A further 31×31 scan had minimum ~99.7027%. Thus the
candidate was about 30.9% shorter *under this specific modeled scenario*.
These remain model calculations; the Mac-based tests and Qiskit circuit checks
confirm implementation consistency, not hardware performance. Another noise box,
coherence ratio or optimization seed may yield no advantage.

## Multilevel reality check: deliberate, clearly labeled surrogate

`research_leakage.py` models a four-dimensional Hilbert space on **two Qiskit
qubits**: |00⟩ and |01⟩ are computational states; |10⟩ is one off-resonant
leakage state; |11⟩ is a spectator. The 0↔1 and 1↔2 transitions share a
phase-controlled drive, with coupling ratio η (default √2). A rotating-frame
anharmonicity α/Ω controls the leakage level. The model is a *pedagogical ladder*,
not a Gridium circuit model or a validated transmon spectrum.

We compute coherent 4×4 unitary evolution, unconditional logical-state averaged
fidelity to X (leakage counts as failure), final mean population outside the
computational subspace, and **peak** mean leakage during all pulse segments.
Because this study excludes T1/T2 decoherence, **do not compare its absolute
fidelities directly to the noisy two-level performance above**. It tests a
model-assumption failure: a seemingly excellent two-level pulse may drive
unwanted levels. The second Aer experiment embeds the 4×4 model as a two-qubit
`Operator`, measures leakage states, and verifies probabilities by shots.

Four generated figures in `results/research/`:

- `synthesis_speed_robustness.png` — held-out sampled fidelity vs full duration.
- `synthesis_fidelity_landscape.png` — BB1 and new pulse sensitivity surfaces.
- `multilevel_leakage_stress_test.png` — multilevel conditional caveat;
  *coherent* logical fidelity and transient leakage vs anharmonicity.
- `synthesized_waveform.png` — implementable-*in-model* piecewise control phase.

Source provenance: `optimization_report.json` (configuration, full segment
angles/phases, 9+96 samples, all candidates, winner, Qiskit consistency checks),
`candidate_comparison.csv`, `leakage_sweep.csv`.

## What we can and cannot claim

**Can:** Qiskit-backed controlled simulations of suppression-vs-duration;
reproducible sample-constrained pulse synthesis; an independently tested
uncertainty set; evidence for model sensitivity to leakage; circuit execution
checks in Qiskit Aer; transparent failure cases and modeling assumptions.

**Cannot:** Guaranteed fidelity over all continuous uncertainty parameters,
global time optimality, physical IBM pulse-schedule execution, a converged
Gridium four-mode gate, measured device-level speedup, or hardware-validated
error mitigation. Our approach primarily models **error suppression**, not
quantum error correction. Taylor's independently chosen benchmark should be
presented separately, with noise assumptions matched before comparison.

## Rubric and human impact

**Technical:** measurable ideal/noisy/suppressed outcomes with costs and Qiskit
checks. **Originality:** propose rather than simply choose controls, and test
multilevel failure modes. **Societal:** people using limited shared quantum
resources should see *when no available operation meets a reliability goal*,
not hide negative results. The runtime/fidelity tradeoff influences access,
resource consumption, and how honestly researchers communicate results.
**Presentation:** demonstrate a control designed by the app, its held-out
comparison, its temporary leakage trajectory, and why neither result should be
oversold.

Deadline: **Wednesday October 14, 2026**. The official README has two distinct
form links; the team should verify which submission form is authoritative.
