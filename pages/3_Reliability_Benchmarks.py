"""Judges' view: match circuit, multilevel, and stress-testing evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from option_b_benchmarks import (
    CANDIDATES, LABELS, shared_multilevel_comparison,
    circuit_depth_benchmark, qiskit_aer_circuit_checks)

st.set_page_config(page_title='PulseWise | Reliability Benchmarks',page_icon='🔬',layout='wide')

COLORS={'primitive':'#65b5ed','BB1':'#1AC1A3','CORPSE':'#c495fa','synthesized':'#ff9f54'}
CASES=('zero systematic bias','amplitude +5%','detuning +0.04 Ω','combined corner')

@st.cache_data(show_spinner=False)
def load_research():
    paths=[ROOT/'results'/'option_b'/'research_summary.json']
    for path in paths:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    return None

@st.cache_data(show_spinner=False)
def frozen_report():
    for path in (ROOT/'results'/'research'/'optimization_report.json',
                 ROOT/'results'/'option_b'/'baseline_optimizer_report.json'):
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    return None

st.title('PulseWise / Reliability Benchmarks')
st.caption('Team Semiclassical · Qompute 2026 · Model-based quantum reliability, not hardware calibration')
st.markdown('### Does a high single-gate fidelity actually make a quantum computation trustworthy?')

results=load_research()
report=frozen_report()
if results is None or report is None:
    st.error('The frozen benchmark results have not been generated. From repository root, run `python src/build_option_b.py`.')
    st.stop()

st.warning('**Key discovery:** A pulse can satisfy the optimizer’s single-gate fidelity constraint yet perform poorly after repeated coherent errors. One model’s winner is not automatically another model’s winner.')

st.header('1. Known-answer circuit: 32 X gates should implement identity')
st.caption('Every gate uses the identical noise-affected control channel. The calibration offset is held fixed across the whole circuit; T₁/T₂ decoherence is included at full pulse duration.')
case=st.selectbox('Choose the simulated control-error regime',CASES,index=3)
data=[r for r in results['depth_results'] if r['case']==case]
selected=[r for r in data if r['depth']==32]
columns=st.columns(4)
for col,name in zip(columns,CANDIDATES):
    row=next(r for r in selected if r['candidate']==name)
    col.metric(LABELS[name],f"{100*row['success_probability']:.2f}%",
               help='Probability of the correct |0> measurement after X^32')
fig=go.Figure()
for name in CANDIDATES:
    seq=[r for r in data if r['candidate']==name]
    fig.add_trace(go.Scatter(x=[r['depth'] for r in seq],
                             y=[100*r['success_probability'] for r in seq],
                             name=LABELS[name],mode='lines+markers',
                             line=dict(color=COLORS[name],width=3),marker=dict(size=9)))
fig.add_hline(y=100,line_dash='dot',line_color='#64748b')
fig.update_layout(height=400,xaxis_title='Number of successive noisy X gates',
                  yaxis_title='Correct output probability (%)',
                  yaxis_range=[0,101],xaxis_type='log',
                  legend=dict(orientation='h',y=-.24),
                  margin=dict(l=10,r=15,t=15,b=10))
st.plotly_chart(fig,use_container_width=True)

st.subheader('Accuracy is only one axis; duration and control complexity also matter')
df=pd.DataFrame([{'Pulse':LABELS[r['candidate']],
   'Circuit correct (%)':round(100*r['success_probability'],3),
   'Total duration (µs)':round(r['total_duration_ns']/1000,3),
   'Control segments':r['total_segments'],
   '3-bit parity correct (%)':round(100*r['parity_3bit_mean_success'],3)}
   for r in selected])
st.dataframe(df,use_container_width=True,hide_index=True)
st.caption('The parity task is separate from X^32. Parity estimates are averaged over all eight 3-bit inputs, and assume ideal CNOT gates, initialization, and readout. Only X preparations are noisy.')

st.divider()
st.header('2. Multilevel reality check — same 4D surrogate for all four pulses')
st.caption('This section uses coherent dynamics **without T₁/T₂**. It is deliberately a separate physical approximation from the noisy two-level circuit above. This is not the calibrated Gridium Hamiltonian.')
ml1,ml2=st.columns([1,3])
with ml1:
    alpha=st.slider('Anharmonicity α/Ω',-8.,-1.,-3.,step=.25)
    eta=st.slider('Leakage coupling η',0.,2.,float(np.sqrt(2)),step=.05)
    amp=st.slider('Actual amplitude bias (%)',-10.,10.,0.,step=.5)
    det=st.slider('Actual detuning Δ/Ω',-.1,.1,0.,step=.005)
with ml2:
    with st.spinner('Propagating the four controls through identical surrogate physics...'):
        ml=shared_multilevel_comparison(report,
            anharmonicity_over_omega=alpha,coupling_ratio=eta,
            amplitude_error=amp/100,detuning_over_omega=det)
    st.dataframe(pd.DataFrame([{
        'Pulse':r['label'],'Logical fidelity (%)':round(100*r['fidelity_unconditional'],3),
        'Final leakage (%)':round(100*r['final_leakage'],3),
        'Peak leakage (%)':round(100*r['peak_leakage'],3),
        'Duration (ns)':round(r['duration_ns'],2)} for r in ml]),
        use_container_width=True,hide_index=True)
    graph=go.Figure()
    for r in ml:
        graph.add_trace(go.Bar(name=r['label'],x=['Logical fidelity','Final leakage','Peak leakage'],
            y=[100*r['fidelity_unconditional'],100*r['final_leakage'],100*r['peak_leakage']],
            marker_color=COLORS[r['candidate']]))
    graph.update_layout(barmode='group',height=340,yaxis_title='Percent (%)',
                        margin=dict(l=5,r=5,t=10,b=15),
                        legend=dict(orientation='h',y=-.25))
    st.plotly_chart(graph,use_container_width=True)
st.info('The model is useful precisely because it can **falsify** an apparently excellent two-level recommendation. It does not establish actual device performance.')

st.divider()
st.header('3. Did the synthesized pulse generalize?')
st.caption('The frozen waveform was evaluated without retraining on 31 × 31 independent dense points, 512 new random in-domain points, and 512 deliberately shifted out-of-domain calibration points.')
scenarios={'dense_in_domain':'Dense in-domain grid',
           'new_random_in_domain':'Independent in-domain random points',
           'shifted_calibration_out_of_domain':'Shifted calibration (out-of-domain)'}
stress=pd.DataFrame([{'Regime':scenarios[r['scenario']],
                      'Pulse':LABELS[r['candidate']],
                      'Worst fidelity (%)':round(100*r['min_fidelity'],4),
                      'Below 99.7% (%)':round(100*r['fraction_below_threshold'],2),
                      'Pass all sampled':'YES' if r['passes_all_sampled'] else 'NO'}
                      for r in results['optimizer_stress']])
st.dataframe(stress,hide_index=True,use_container_width=True)
st.caption('A finite sample can reveal failures but cannot certify every point in a continuous uncertainty region. The out-of-domain box intentionally shifts the calibration beyond training.')

st.divider()
st.header('4. Qiskit Aer circuit demonstration')
st.write('The numerical comparisons above are exact model-based predictions. Aer is used to execute explicit noisy quantum circuits and independently check **sampling** against those predicted probabilities.')
st.caption('The Aer circuits are constructed from the same mathematical noisy channels; consistency does not validate a calibrated hardware pulse schedule or independent physical model.')
if st.button('▶ Run 45 ideal/noisy/suppressed Aer circuits',type='primary'):
    try:
        with st.spinner('Running 45 circuits at 2,048 shots each...'):
            q=qiskit_aer_circuit_checks(report)
        st.success('Aer shot results consistent with mathematical predictions.' if q['all_consistent']
                   else 'An Aer discrepancy was detected. Investigate before presenting.')
        st.metric('Aer circuits',q['num_circuits'])
        st.metric('Shots per circuit',q['shots_per_circuit'])
        st.dataframe(pd.DataFrame(q['cases']),hide_index=True,use_container_width=True)
    except Exception as error:
        st.error(f'Aer not available or validation failed: {error}')

st.divider()
st.subheader('Scientific scope and reproducibility')
st.markdown('The optimizer was trained for average **single-gate** fidelity, not long-circuit success. The four-level model is a surrogate, not the physical Gridium Hamiltonian. The circuit benchmark neglects errors in CNOT/readout, and its calibration biases remain fixed during each circuit. None of these results are hardware measurements.')
st.code('python src/build_option_b.py\npython -m unittest discover -s tests -p "test_*.py" -v\npython src/build_option_b.py --qiskit',language='bash')
