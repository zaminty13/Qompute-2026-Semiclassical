# Scientific references and research attribution

PulseWise is an original hackathon integration of published **methods**, established **pulse families**, open-source **software**, and the team's own simulations. This file credits the intellectual sources; package licensing is tracked separately in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Composite-pulse design

1. **S. Wimperis** (1994), “Broadband, Narrowband, and Passband Composite Pulses for Use in Advanced NMR Experiments,” *Journal of Magnetic Resonance, Series A* **109**, 221–231. [DOI: 10.1006/jmra.1994.1159](https://doi.org/10.1006/jmra.1994.1159). Background for the **BB1** composite-pulse family.
2. **H. K. Cummins, G. Llewellyn, and J. A. Jones** (2003), “Tackling systematic errors in quantum logic gates with composite rotations,” *Physical Review A* **67**, 042308. [DOI: 10.1103/PhysRevA.67.042308](https://doi.org/10.1103/PhysRevA.67.042308). Background for off-resonance composite rotations including **CORPSE**.

Our pulse definitions are coded directly in [`src/pulses.py`](src/pulses.py); these citations credit the underlying established methods rather than claiming to invent them.

## Open-system dynamics and classical optimization

3. **G. Lindblad** (1976), “On the generators of quantum dynamical semigroups,” *Communications in Mathematical Physics* **48**, 119–130. [DOI: 10.1007/BF01608499](https://doi.org/10.1007/BF01608499). The mathematical foundation for the Markovian noise model.
4. **R. Storn and K. Price** (1997), “Differential Evolution – A Simple and Efficient Heuristic for Global Optimization over Continuous Spaces,” *Journal of Global Optimization* **11**, 341–359. [DOI: 10.1023/A:1008202821328](https://doi.org/10.1023/A:1008202821328). Background for Differential Evolution.
5. **D. Kraft** (1988), “A Software Package for Sequential Quadratic Programming,” *DFVLR-FB 88-28*, DLR. [SciPy's SLSQP documentation and references](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html). Background for constrained SLSQP optimization.
6. **P. Virtanen et al.** (2020), “SciPy 1.0: Fundamental Algorithms for Scientific Computing in Python,” *Nature Methods* **17**, 261–272. [DOI: 10.1038/s41592-019-0686-2](https://doi.org/10.1038/s41592-019-0686-2). Software/methods reference for SciPy.

## Gridium: external research inspiration, not an implementation dependency

7. **Long B. Nguyen, Hyunseong Kim, Dat T. Le, Thomas Ersevim, et al.** (2025), “The superconducting grid-states qubit.” [arXiv:2509.14656](https://arxiv.org/abs/2509.14656). The public research preprint describing the gridium superconducting qubit; credited as conceptual background, not a component of our simulator.
8. **Hyunseong Kim** (2026), *The Superconducting Grid States Qubit*, University of California, Berkeley (doctoral thesis; advisor Irfan Siddiqi). [UC eScholarship record](https://escholarship.org/uc/item/8dj2b0kj).
9. **Quantum Nanoelectronics Laboratory (qnl)**, [`qnl/gridium` public research repository](https://github.com/qnl/gridium), “Numerical Code and Processed Data for *Intrinsically Protected Grid States in a Superconducting Qubit*.” The repository identifies its code/data and shows a **CC0-1.0** license at the repository level. Use the upstream repository for its own source attribution and license terms.

**Relationship to PulseWise:** The Gridium work concerns protected superconducting grid-state qubits and motivated us to consider robustness and physics beyond an ideal two-level description. PulseWise does **not** import the Gridium simulator, reproduce its full circuit Hamiltonian, validate its gate results, or model an experimental Gridium device. Our four-level pedagogical surrogate is an independent **illustration of leakage sensitivity**, not a faithful device model. Citing a research source is different from reusing its code.

## Qiskit, tools, and challenge

10. **Qiskit**: [Qiskit SDK](https://github.com/Qiskit/qiskit), [Qiskit Aer](https://github.com/Qiskit/qiskit-aer), and [Qiskit documentation](https://quantum.cloud.ibm.com/docs). These supply quantum-information operators, noisy channels, circuits and finite-shot simulations used in this project.
11. **Qompute 2026 organizers**: [Official challenge brief](https://github.com/sandraalhames/Qompute-2026), Track 3, “Can We Trust a Noisy Quantum Computer?” Used to frame the known-answer, noisy-baseline and resource-cost comparison.

## What is and is not attributable to others

- **Established ideas:** X, BB1, CORPSE, Lindblad channels, DE and SLSQP are not inventions of PulseWise.
- **Software:** We use upstream open-source Python dependencies under their respective licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).
- **Our work in this repository:** The application, chosen model conditions, numerical experiments, pulse selector, constrained five-segment synthesis, circuit-depth stress tests, supplementary surrogate, generated figures and analysis. See commit and PR history for individual contribution provenance.
- **Not claimed:** Hardware data, an experimental Gridium implementation, an independent calibration of physical noise, universally optimal control, or a proof of robustness over a continuous parameter box.

If direct excerpts, images, code or datasets from an external research work are added in the future, separately document each asset's origin, permission and license here and in the relevant file.
