# PulseWise interactive demo

This is an addition to `Qompute-2026-Semiclassical` and requires the team's
`src/pulses.py`, `src/decoherence.py`, and `src/select_pulse.py`.

## Setup (run from repository root)

```shell
python -m pip install streamlit plotly
python -m streamlit run app.py
```

Or install `requirements-demo.txt` for all needed project dependencies.

The main interactive prediction uses the team's existing Qiskit `SuperOp`
channel model and `average_gate_fidelity`. On the **Qiskit Aer check** tab,
pressing the button constructs six single-qubit measurement circuits, embeds
the pulse's same simulated Kraus channel, and estimates average gate fidelity
from finite-shot outcomes. This is a circuit/execution consistency check **not**
independent noise-model validation or real-hardware benchmarking.

## Validation

```shell
python -m unittest discover -s tests -p 'test_*.py' -v
```

This adds optional Aer tests to the existing test suite. The baseline selector
and the original team simulations are unchanged.

## Scope and limitations

- All modeled pulses are piecewise rectangular controls of a two-level qubit.
- Durations are physical modeled pulse times, not transpiled gate times.
- Predicted fidelities do not represent measured performance on IBM hardware.
- The archived selection-map PNG is a *fixed reference sweep*, not a live map
  of the current widget values.
- T2 must satisfy `T2 <= 2*T1` for the model.
