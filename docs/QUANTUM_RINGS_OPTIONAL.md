# Optional Quantum Rings comparison

PulseWise's Reliability Benchmarks page includes a coherent amplitude-overrotation experiment using Qiskit Aer and an optional Quantum Rings simulator.

The experiment applies Rx(pi*(1+error)) N times from |0>, for N=2,4,8,16,32, and measures P(0). Analytical reference: cos^2(N*pi*(1+error)/2).

Quantum Rings is not required for the normal app. It is used only after pressing its separate button. Install the official Quantum Rings SDK and Qiskit toolkit in a separate Python 3.11+ environment; the existing Python 3.10 environment need not change. See https://www.quantumrings.com/doc/ for setup. Configure QR_TOKEN and QR_ACCOUNT locally or use the SDK's saved credentials. Never commit or share tokens.

Scope: coherent amplitude error only, simple Qiskit circuits. No T1/T2 noise, detuning, actual synthesized pulses, Gridium Hamiltonian, calibrated pulse schedules, or hardware execution. Quantum Rings and Aer agreement does not independently validate PulseWise's physics model. If the provider cannot run, no Quantum Rings measurements are displayed.
