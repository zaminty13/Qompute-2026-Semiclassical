import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MultipleLocator
from qiskit.circuit.library import XGate
from qiskit.quantum_info import Operator, average_gate_fidelity

from pulses import (
    PAULI_X,
    analytic_x_fidelity,
    average_infidelity,
    require_close,
    basic_x_pulse,
    small_error_infidelity,
    x_pulse_unitary,
)

DURATION_NS = 100.0
MAX_ERROR = 0.20
NUM_POINTS = 401
NUM_QISKIT_CHECKS = 9

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
AXIS_LINE = "#c3c2b7"
SERIES_COLORS = (
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#6250d6",
    "#e34948",
)


def simulated_infidelities(duration_ns, amplitude_errors):
    unitaries = x_pulse_unitary(duration_ns, amplitude_errors)
    return average_infidelity(unitaries, PAULI_X)


def qiskit_infidelities(duration_ns, amplitude_errors):
    ideal_x = Operator(XGate())
    return np.array([
        1.0 - average_gate_fidelity(
            basic_x_pulse(duration_ns, error),
            target=ideal_x,
        )
        for error in amplitude_errors
    ])


def plot_infidelity_curves(amplitude_errors, curves, title, *,
                           xlabel="Drive amplitude error (%)", xscale=100, tick_step=5):
    if len(curves) > len(SERIES_COLORS):
        raise ValueError(f"At most {len(SERIES_COLORS)} curves are supported.")

    fig, ax = plt.subplots(figsize=(8, 5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    for (label, values, linestyle), color in zip(curves, SERIES_COLORS):
        ax.plot(
            amplitude_errors * xscale,
            values,
            label=label,
            color=color,
            linestyle=linestyle,
            linewidth=2,
            solid_capstyle="round",
            dash_capstyle="round",
        )

    ax.set(
        xlabel=xlabel,
        ylabel="Average gate infidelity (1 − F)",
        xlim=(amplitude_errors[0] * xscale, amplitude_errors[-1] * xscale),
        ylim=(0, None),
    )
    ax.set_title(title, color=INK, loc="left", pad=12)
    ax.xaxis.set_major_locator(MultipleLocator(tick_step))

    ax.set_axisbelow(True)
    ax.grid(True, color=GRIDLINE, linewidth=1, linestyle="-")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS_LINE)
    ax.tick_params(colors=INK_MUTED, labelcolor=INK_SECONDARY, length=0)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)

    legend = ax.legend(loc="upper center", frameon=False)
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)

    fig.tight_layout()
    return fig


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-show", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    amplitude_errors = np.linspace(-MAX_ERROR, MAX_ERROR, NUM_POINTS)

    simulated = simulated_infidelities(DURATION_NS, amplitude_errors)
    require_close(
        "the analytic result",
        simulated,
        1.0 - analytic_x_fidelity(amplitude_errors),
    )

    spot_checks = np.linspace(0, NUM_POINTS - 1, NUM_QISKIT_CHECKS).astype(int)
    require_close(
        "Qiskit",
        simulated[spot_checks],
        qiskit_infidelities(DURATION_NS, amplitude_errors[spot_checks]),
    )

    approximate = small_error_infidelity(amplitude_errors)
    overshoot = approximate[-1] / simulated[-1] - 1.0

    fig = plot_infidelity_curves(
        amplitude_errors,
        curves=[
            ("Basic rectangular pulse", simulated, "-"),
            ("Small-error approximation", approximate, "--"),
        ],
        title=f"Amplitude error sensitivity of an X gate ({DURATION_NS:g} ns)",
    )

    output_dir = Path(__file__).resolve().parent.parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "amplitude_error_baseline.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())

    print(f"Plot saved to: {output_path}")
    print(
        f"At ±{MAX_ERROR:.0%} error the approximation overestimates "
        f"infidelity by {overshoot:.1%}."
    )

    if args.no_show:
        plt.close(fig)
    else:
        plt.show()


if __name__ == "__main__":
    main()
