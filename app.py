"""PulseWise: interactive, Qiskit-backed pulse selection lab.

Run from the Semiclassical repository root:
    python -m pip install streamlit plotly
    python -m streamlit run app.py
"""
from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
import sys

import numpy as np
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from pulses import SEQUENCE_NAMES, sequence_segments
from select_pulse import select_pulse, robust_select_pulse

COLORS = {"primitive": "#5D9DEF", "BB1": "#1AC1A3", "CORPSE": "#B78AFF"}
DISPLAY = {"primitive": "Primitive X", "BB1": "BB1", "CORPSE": "CORPSE"}
BACKGROUND = "#101820"

PRESETS = {
    "Decoherence-limited · Primitive X": {
        "amp": 5.0, "det": 0.0, "t1": 30.0, "t2": 20.0,
        "duration": 100.0, "threshold": 99.0,
    },
    "Amplitude error · BB1": {
        "amp": 5.0, "det": 0.0, "t1": 200.0, "t2": 150.0,
        "duration": 100.0, "threshold": 99.7,
    },
    "Detuning error · CORPSE": {
        "amp": 0.0, "det": 0.10, "t1": 200.0, "t2": 150.0,
        "duration": 100.0, "threshold": 99.7,
    },
}

st.set_page_config(page_title="PulseWise | Quantum Control Lab", page_icon="⚛️",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.block-container {padding-top: 1.2rem; max-width: 1440px}
h1 {letter-spacing: -.04em}
div[data-testid="stMetric"] {background:rgba(90,130,160,.08);
    border:1px solid rgba(135,170,200,.18); padding:15px;
    border-radius:12px}
div[data-testid="stMetricLabel"] {font-weight:600}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("⚛️ Control Lab")
    st.caption("Configure a modeled single-qubit X operation")
    preset_name = st.selectbox("Guided experiment", list(PRESETS))
    defaults = PRESETS[preset_name]
    st.subheader("Noise & accuracy")
    amplitude_percent = st.slider("Amplitude calibration error (%)", -15.0, 15.0,
                                  float(defaults["amp"]), step=0.5, key=f"amplitude_{preset_name}")
    detuning_over_omega = st.slider("Normalized detuning (Δ/Ω)", -0.20, 0.20,
                                    float(defaults["det"]), step=0.005, format="%.3f", key=f"detuning_{preset_name}")
    primitive_ns = st.slider("Primitive X duration (ns)", 20, 500,
                             int(defaults["duration"]), step=5, key=f"duration_{preset_name}")
    required_pct = st.slider("Minimum fidelity (%)", 90.0, 100.0,
                             float(defaults["threshold"]), step=0.1, key=f"threshold_{preset_name}")
    st.subheader("Coherence")
    t1_us = st.number_input("T₁ relaxation time (µs)", 1.0, 1000.0,
                            float(defaults["t1"]), step=5.0, key=f"t1_{preset_name}")
    t2_us = st.number_input("T₂ dephasing time (µs)", 1.0, 1000.0,
                            float(defaults["t2"]), step=5.0, key=f"t2_{preset_name}")
    st.caption("Physical model requires T₂ ≤ 2T₁")
    with st.expander("Advanced: sampled robustness", expanded=False):
        use_robust = st.toggle("Evaluate parameter uncertainty", value=False)
        amplitude_uncertainty = st.slider("Amplitude uncertainty (percentage points)",
                                          0.0, 5.0, 2.0, step=0.5)
        detuning_uncertainty = st.slider("Detuning uncertainty (Δ/Ω)",
                                         0.0, 0.10, 0.02, step=0.005, format="%.3f")
        sample_points = st.select_slider("Grid points per axis", options=[3, 5, 7], value=5)

st.markdown("# PulseWise  <span style='color:#1AC1A3'>/</span>  Quantum Control Lab",
            unsafe_allow_html=True)
st.caption("TEAM SEMICLASSICAL · QOMPUTE 2026 · TRACK 3: CAN WE TRUST A NOISY QUANTUM COMPUTER?")
st.markdown("**Which pulse is the fastest one that still meets our accuracy requirement?**")

if t2_us > 2*t1_us:
    st.error("These T₁ and T₂ values are incompatible with the physical noise model. Lower T₂ or increase T₁.")
    st.stop()

omega = np.pi / primitive_ns
kwargs = {
    "amplitude_error": amplitude_percent / 100,
    "detuning_rad_per_ns": detuning_over_omega * omega,
    "primitive_duration_ns": float(primitive_ns),
    "t1_ns": t1_us * 1000,
    "t2_ns": t2_us * 1000,
}
try:
    winner, rows = select_pulse(min_fidelity=required_pct/100, **kwargs)
except (ValueError, TypeError) as exc:
    st.error(f"Cannot evaluate this experiment: {exc}")
    st.stop()

winner_name = DISPLAY[winner["sequence"]] if winner else "No feasible pulse"
best_available = max(rows, key=lambda r: r["fidelity"])
cols = st.columns(4)
cols[0].metric("Recommended pulse", winner_name)
cols[1].metric("Selected fidelity", f"{winner['fidelity']*100:.4f}%" if winner else "—")
cols[2].metric("Total pulse duration", f"{winner['duration_ns']:.1f} ns" if winner else "—")
cols[3].metric("Accuracy requirement", f"{required_pct:.1f}%")

if winner is None:
    st.warning(f"No candidate reaches {required_pct:.1f}% average gate fidelity. "
               f"Best available is {DISPLAY[best_available['sequence']]} "
               f"at {best_available['fidelity']*100:.4f}%. "
               "Do not present a failing candidate as a safe recommendation.")
elif winner["sequence"] == "primitive":
    st.success("**Why this wins:** Primitive X satisfies the requirement with the shortest "
               "duration. A more complicated pulse is unnecessary under these modeled conditions.")
else:
    mechanism = ("BB1 is designed to suppress amplitude-calibration errors" if winner["sequence"]=="BB1"
                 else "CORPSE is designed to suppress frequency-detuning errors")
    st.success(f"**Why this wins:** {mechanism}. It is the shortest of the three "
               "modeled candidates meeting your fidelity threshold at these settings.")

first, second, third = st.tabs(["📊 Live decision", "〰️ Pulse anatomy", "🧪 Qiskit Aer experiment"])

with first:
    left, right = st.columns([1.55, 1])
    with left:
        st.subheader("Fidelity versus total pulse duration")
        fig = go.Figure()
        for r in rows:
            selected = winner is not None and r["sequence"] == winner["sequence"]
            fig.add_trace(go.Scatter(
                x=[r["duration_ns"]], y=[r["fidelity"]*100],
                mode="markers+text", text=[DISPLAY[r["sequence"]]],
                textposition="top center", textfont=dict(color=COLORS[r["sequence"]]),
                marker=dict(size=21 if selected else 15,
                            symbol="star" if selected else "circle",
                            color=COLORS[r["sequence"]],
                            line=dict(color="white", width=1)),
                name=DISPLAY[r["sequence"]],
                hovertemplate="%{text}<br>Duration %{x:.1f} ns<br>Fidelity %{y:.5f}%<extra></extra>",
                showlegend=False,
            ))
        fig.add_hline(y=required_pct, line_dash="dash", line_color="#F4A563",
                      annotation_text=f"Required {required_pct:.1f}%")
        fvals = [r["fidelity"]*100 for r in rows] + [required_pct]
        margin = max(0.15, (max(fvals)-min(fvals))*.25)
        fig.update_layout(height=420, margin=dict(t=25,l=20,r=25,b=25),
                          xaxis_title="Total modeled pulse duration (ns)",
                          yaxis_title="Average gate fidelity (%)",
                          yaxis_range=[min(fvals)-margin, min(100.1,max(fvals)+margin)],
                          hovermode="closest")
        st.plotly_chart(fig, width="stretch")
    with right:
        st.subheader("All candidates")
        st.dataframe([
            {"Pulse": DISPLAY[r["sequence"]],
             "Fidelity (%)": round(r["fidelity"]*100, 5),
             "Duration (ns)": round(r["duration_ns"], 2),
             "Meets threshold": "YES" if r["fidelity"] >= required_pct/100-1e-12 else "NO"}
            for r in rows], hide_index=True, width="stretch")
        st.caption("The criterion uses Qiskit average gate fidelity to the ideal X gate. "
                   "All durations include the complete composite sequence.")
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=["sequence", "fidelity", "duration_ns"])
        writer.writeheader()
        writer.writerows({k:r[k] for k in ["sequence","fidelity","duration_ns"]} for r in rows)
        st.download_button("Download current comparison CSV", output.getvalue(),
                           "pulsewise_current_comparison.csv", mime="text/csv")
    if use_robust:
        st.subheader("Robustness under sampled control uncertainty")
        try:
            robust_winner, robust_rows = robust_select_pulse(
                min_fidelity=required_pct/100,
                amplitude_center=amplitude_percent/100,
                amplitude_uncertainty=amplitude_uncertainty/100,
                detuning_center_over_omega=detuning_over_omega,
                detuning_uncertainty_over_omega=detuning_uncertainty,
                primitive_duration_ns=primitive_ns,
                t1_ns=t1_us*1000, t2_ns=t2_us*1000,
                points_per_axis=sample_points,
            )
            st.info("Shortest candidate satisfying the **sampled worst-case** threshold: "
                    + (DISPLAY[robust_winner["sequence"]] if robust_winner else "none"))
            rob_fig = go.Figure()
            for r in robust_rows:
                rob_fig.add_trace(go.Scatter(
                    x=[r["nominal_fidelity"]*100, r["sampled_worst_fidelity"]*100],
                    y=[DISPLAY[r["sequence"]]]*2, mode="lines+markers",
                    name=DISPLAY[r["sequence"]], line=dict(color=COLORS[r["sequence"]],width=5),
                    marker=dict(size=12)))
            rob_fig.add_vline(x=required_pct,line_dash="dash",line_color="#F4A563")
            rob_fig.update_layout(xaxis_title="Average gate fidelity (%)", height=280,
                                  margin=dict(t=20,l=20,r=20,b=20), showlegend=False)
            st.plotly_chart(rob_fig,width="stretch")
            st.caption("Worst case here means the minimum over a finite grid, not a guarantee "
                       "for every real-valued error inside the uncertainty region.")
        except (ValueError, TypeError) as exc:
            st.error(f"Robustness scan could not run: {exc}")

with second:
    st.subheader("What are we actually comparing?")
    st.write("Each bar below represents a sequence of rectangular rotating-drive "
             "segments. Length corresponds to time; annotations show the nominal "
             "rotation angle and microwave phase of each segment.")
    fig2 = go.Figure()
    for yi, name in enumerate(SEQUENCE_NAMES):
        t = 0.
        for angle, phase in sequence_segments(name):
            duration = angle / omega
            label = f"{angle/np.pi:.2g}π"
            fig2.add_shape(type="rect", x0=t, x1=t+duration,
                           y0=yi-.27,y1=yi+.27,
                           fillcolor=COLORS[name], opacity=.8,
                           line=dict(color="#15202C",width=1))
            fig2.add_trace(go.Scatter(x=[t+duration/2],y=[yi], mode="markers",
                                      marker=dict(size=6,opacity=0),
                                      text=[f"{DISPLAY[name]} | rotation {label} | phase {phase:.3f} rad | "
                                            f"duration {duration:.1f} ns"],
                                      hovertemplate="%{text}<extra></extra>",showlegend=False))
            if duration >= 50:
                fig2.add_annotation(x=t+duration/2,y=yi,text=label,
                                    showarrow=False,font=dict(size=11,color="#111923"))
            t += duration
    fig2.update_layout(height=315, yaxis=dict(tickvals=list(range(3)),
                       ticktext=[DISPLAY[s] for s in SEQUENCE_NAMES],autorange="reversed",
                       range=[2.7,-.7]),xaxis_title="Modeled duration (ns)",
                       margin=dict(t=20,l=20,r=20,b=30))
    st.plotly_chart(fig2,width="stretch")
    st.caption("These are piecewise drive segments, not physical IBM pulse schedules. "
               "They do not model bandwidth limits or leakage to higher levels.")
    st.subheader("The experiment's fixed reference figures")
    st.caption("Figures below were generated for specific documented noise settings. "
               "They do NOT automatically update when sidebar inputs change.")
    fig_dir = ROOT / "results" / "selector"
    for label, filename in [
        ("Selection map — fixed 99.7% threshold", "pulse_selection_map.png"),
        ("Fidelity-duration Pareto sweep — fixed scenario", "fidelity_duration.png"),
        ("Decoherence crossover — fixed amplitude error", "coherence_crossover.png"),
        ("Robustness — fixed uncertainty box", "gridium_inspired_robustness.png"),
    ]:
        path = fig_dir / filename
        if path.is_file():
            with st.expander(label):
                st.image(str(path), width="stretch")

with third:
    st.subheader("Qiskit Aer: a shot-based experiment")
    st.write("We build six one-qubit circuits, each with a different input state, "
             "apply the selected pulse's modeled quantum channel, undo the ideal "
             "X operation, and measure the probability of the expected result. "
             "Their mean estimates average gate fidelity.")
    st.info("This checks circuit execution and shot statistics against the **same modeled "
            "noise channel**. It is not independent hardware benchmarking, and it does "
            "not replace Taylor's randomized benchmarking.")
    pulse_to_measure = st.selectbox("Choose a pulse to verify",
                                    list(SEQUENCE_NAMES),
                                    index=list(SEQUENCE_NAMES).index(winner["sequence"]) if winner else 0,
                                    format_func=lambda s: DISPLAY[s])
    shots = st.select_slider("Shots per input state", options=[128,256,512,1024,2048],value=512)
    if st.button("▶ Run Qiskit Aer experiment", type="primary"):
        try:
            from aer_validation import estimate_gate_fidelity
            with st.spinner("Simulating six measurement circuits..."):
                outcome = estimate_gate_fidelity(
                    pulse_to_measure, shots_per_state=shots, **kwargs)
            st.session_state["aer_outcome"] = outcome
            st.session_state["aer_signature"] = (pulse_to_measure, shots,
                        tuple(kwargs.values()))
        except Exception as exc:
            st.error(f"Aer experiment failed: {exc}")
    signature = (pulse_to_measure, shots, tuple(kwargs.values()))
    if st.session_state.get("aer_signature") == signature:
        result = st.session_state["aer_outcome"]
        m1,m2,m3 = st.columns(3)
        m1.metric("Predicted channel fidelity", f"{result['predicted_fidelity']*100:.3f}%")
        m2.metric("Shot-based estimate", f"{result['shot_estimated_fidelity']*100:.3f}%")
        m3.metric("Approx. 1σ shot uncertainty", f"±{result['shot_standard_error']*100:.3f} pp")
        st.dataframe([{ "Input state": r["state"],
                        "Observed success": f"{r['p_ideal_output']*100:.2f}%",
                        "Counts": f"{r['successes']}/{shots}"}
                      for r in result["per_state"]],hide_index=True,width="stretch")
        with st.expander("View an actual Qiskit circuit diagram"):
            st.code(str(result["circuits"][0].draw(output="text")),language="text")
    else:
        st.caption("Press the button to run the current experiment. Results refresh only "
                   "when you run it; changing controls invalidates the previous result.")

st.divider()
st.caption("**Scientific scope:** Idealized two-level rectangular-pulse model. "
           "Modeled T₁/T₂ decoherence, amplitude error, and detuning only. "
           "No leakage, waveform calibration, real-device pulse access, or hardware measurements. "
           "We use Qiskit quantum channels and Qiskit Aer circuit simulation; "
           "the physics model remains an assumption to test, not a hardware guarantee. "
           "Responsible quantum computing means reporting both accuracy and operating cost.")
