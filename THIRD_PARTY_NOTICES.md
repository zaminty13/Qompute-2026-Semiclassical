# Third-party software notices and licenses

PulseWise is built using externally maintained Python libraries. This page identifies **declared project dependencies** and their upstream licenses. They are typically installed with `pip` and are **not vendored into this repository**. This list covers top-level requirements, not the entire transitive dependency tree or every binary component of a downloaded wheel.

**Important:** A dependency's license does **not** automatically license PulseWise's original source code. As of this documentation update, the repository has **no top-level `LICENSE` file**. The team should agree on a license before adding one; until then do not describe PulseWise as MIT, Apache-2.0, or CC0 licensed.

## Declared dependencies

| Library | Role in PulseWise | Upstream license / authoritative source |
|---|---|---|
| [Qiskit](https://github.com/Qiskit/qiskit) | Quantum operators, `SuperOp`, `average_gate_fidelity` and circuits | [Apache-2.0](https://github.com/Qiskit/qiskit/blob/main/LICENSE.txt) |
| [Qiskit Aer](https://github.com/Qiskit/qiskit-aer) | Finite-shot circuit simulation | [Apache-2.0](https://github.com/Qiskit/qiskit-aer/blob/main/LICENSE.txt) |
| [Qiskit Experiments](https://github.com/qiskit-community/qiskit-experiments) | Declared optional experimentation package | [Apache-2.0](https://github.com/qiskit-community/qiskit-experiments/blob/main/LICENSE.txt) |
| [NumPy](https://github.com/numpy/numpy) | Arrays and linear algebra | [BSD-3-Clause core license and bundled license details](https://github.com/numpy/numpy/blob/main/LICENSE.txt); packaged wheels can contain components under additional terms |
| [SciPy](https://github.com/scipy/scipy) | Matrix exponentials, DE and SLSQP | [BSD-3-Clause, plus bundled components](https://github.com/scipy/scipy/blob/main/LICENSE.txt) |
| [Matplotlib](https://matplotlib.org/stable/project/license.html) | Research figures | [Matplotlib license agreement](https://matplotlib.org/stable/project/license.html), PSF-derived/BSD-compatible; **not simply Apache-2.0** |
| [Pandas](https://github.com/pandas-dev/pandas) | Tables/CSV exports | [BSD-3-Clause](https://github.com/pandas-dev/pandas/blob/main/LICENSE) |
| [Plotly for Python](https://github.com/plotly/plotly.py) | Interactive charts | [MIT](https://github.com/plotly/plotly.py/blob/master/LICENSE.txt) |
| [Streamlit](https://github.com/streamlit/streamlit) | Browser-based application | [Apache-2.0](https://github.com/streamlit/streamlit/blob/develop/LICENSE) |

The top-level requirement files are [`requirements.txt`](requirements.txt), [`requirements-demo.txt`](requirements-demo.txt), and [`requirements-research.txt`](requirements-research.txt). Some entries have no pinned version, and licensing/bundled notices can vary by installed release or platform. When distributing a packaged application or wheels, collect **exact installed package versions and license files** (including transitive dependencies) rather than relying solely on this summary.

## Research and published works

The public [qnl/gridium](https://github.com/qnl/gridium) research repository is published under **CC0-1.0**, but **it is not a Python dependency of PulseWise and its code is not imported here**. Its work and [Hyunseong Kim's thesis](https://escholarship.org/uc/item/8dj2b0kj) are acknowledged as research inspiration in [`REFERENCES.md`](REFERENCES.md). Their license must not be interpreted as the license for PulseWise.

The BB1, CORPSE, Lindblad, Differential Evolution and SLSQP publications are cited in [`REFERENCES.md`](REFERENCES.md), not listed as Python-package dependencies. An academic citation is not a software reuse license.

## Responsible reuse

- Retain each upstream package's notices and conditions when redistributing its source or binaries.
- Do not treat an upstream package name, university affiliation, or IBM branding as project sponsorship or endorsement.
- If the team adds copied external code, images, manuscript text, figures or datasets, document the exact source, attribution and reuse conditions before publishing them.
- This file is a practical notice summary, **not a complete legal audit or license grant**. Use the upstream license texts for legally controlling terms.
