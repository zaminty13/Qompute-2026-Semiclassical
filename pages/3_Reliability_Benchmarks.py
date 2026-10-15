"""Judges' view: match circuit, multilevel, and stress-testing evidence."""
from __future__ import annotations

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
    qiskit_aer_circuit_checks)
from result_provenance import load_report, verify_results, waveform_id

st.set_page_config(page_title='PulseWise | Reliability Benchmarks',page_icon='🔬',layout='wide')

COLORS={'primitive':'#65b5ed','BB1':'#1AC1A3','CORPSE':'#c495fa','synthesized':'#ff9f54'}
CASES=('zero systematic bias','amplitude +5%','detuning +0.04 Ω','combined corner')

st.title('PulseWise / Reliability Benchmarks')
st.caption('Team Semiclassical · Qompute 2026 · Model-based quantum reliability, not hardware calibration')
st.markdown('### Does a high single-gate fidelity actually make a quantum computation trustworthy?')

try:
    report=st.session_state.get('research_report')
    if report is None:
        report=load_report(ROOT)
    results=verify_results(ROOT,report)
except (OSError, ValueError, KeyError, TypeError) as exc:
    st.error(f'Reliability results unavailable or incompatible: {exc}')
    st.info('Saved results are hidden. Use the matching saved research report, or explicitly generate results for the new waveform before presenting them.')
    st.stop()
active_id=waveform_id(report)
st.caption('Verified waveform/configuration SHA-256: '+active_id)

st.warning('**Key discovery:** A pulse can satisfy the optimizer’s single-gate fidelity constraint yet perform poorly after repeated coherent errors. One model’s winner is not automatically another model’s winner.')

st.header('1. Known-answer circuit: 32 X gates should implement identity')
st.caption('Every gate uses the identical noise-affected control channel. The calibration offset is held fixed across the whole circuit; T₁/T₂ decoherence is included at full pulse duration.')
case=st.selectbox('Choose the simulated control-error regime',CASES,index=3)
data=[r for r in results['depth_results'] if r['case']==case]
selected=[r for r in data if r['depth']==32]
st.caption(f"This circuit case: amplitude error {100*selected[0]['amplitude_error']:+.1f}%, "
           f"detuning Delta/Omega = {selected[0]['detuning_over_omega']:+.3f}, "
           f"T1 = {report['config']['t1_ns']/1000:g} us, T2 = {report['config']['t2_ns']/1000:g} us; "
           f"shared Omega = pi/({report['config']['primitive_ns']:g} ns). All values are illustrative simulations.")
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
        'Sampled peak leakage (%)':round(100*r['peak_leakage'],3),
        'Duration (ns)':round(r['duration_ns'],2)} for r in ml]),
        use_container_width=True,hide_index=True)
    graph=go.Figure()
    for r in ml:
        graph.add_trace(go.Bar(name=r['label'],x=['Logical fidelity','Final leakage','Sampled peak leakage'],
            y=[100*r['fidelity_unconditional'],100*r['final_leakage'],100*r['peak_leakage']],
            marker_color=COLORS[r['candidate']]))
    graph.update_layout(barmode='group',height=340,yaxis_title='Percent (%)',
                        margin=dict(l=5,r=5,t=10,b=15),
                        legend=dict(orientation='h',y=-.25))
    st.plotly_chart(graph,use_container_width=True)
st.caption('Leakage maxima use 18 samples per segment, including segment endpoints; they are not continuous-time bounds.')
st.info('The model is useful precisely because it can **falsify** an apparently excellent two-level recommendation. It does not establish actual device performance.')

st.divider()
st.header('3. Did the synthesized pulse generalize?')
st.caption('The frozen waveform was evaluated without retraining on a subsequent dense grid (which includes training nodes), new random in-domain points, and deliberately shifted out-of-domain calibration points. These are separate from the 96 validation samples used during selection; table counts describe this saved run.')
scenarios={'dense_in_domain':'Dense in-domain grid',
           'new_random_in_domain':'Independent in-domain random points',
           'shifted_calibration_out_of_domain':'Shifted calibration (out-of-domain)'}
stress=pd.DataFrame([{'Regime':scenarios[r['scenario']],
                      'Pulse':LABELS[r['candidate']],
                      'Samples':r['n_points'],
                      'Worst fidelity (%)':round(100*r['min_fidelity'],4),
                      f"Below {100*report['config']['min_fidelity']:.2f}% (%)":round(100*r['fraction_below_threshold'],2),
                      'Pass all sampled':'YES' if r['passes_all_sampled'] else 'NO'}
                      for r in results['optimizer_stress']])
st.dataframe(stress,hide_index=True,use_container_width=True)
st.caption('A finite sample can reveal failures but cannot certify every point in a continuous uncertainty region. The out-of-domain box intentionally shifts the calibration beyond training.')

st.divider()
st.header('4. Qiskit Aer circuit demonstration')
st.write('Verify the **same 32-X-gate identity experiment** highlighted above, alongside a separate three-bit parity task, using explicit noisy Qiskit Aer circuits.')
st.caption('Frozen combined-error case: +5% amplitude error, Δ/Ω = +0.04, 2,048 shots per circuit. The 45 circuits are 5 pulse choices × (1 identity + 8 parity inputs). Aer samples the SAME modeled channels: this checks circuit implementation and shot statistics, not independent physics or hardware performance.')
if st.button('▶ Run 45 Aer circuits (including X^32)',type='primary'):
    try:
        with st.spinner('Running 45 circuits at 2,048 shots each, X depth = 32...'):
            st.session_state['option_b_aer_checks']=qiskit_aer_circuit_checks(report,depth=32)
    except Exception as error:
        st.error(f'Aer execution failed: {error}')

q=st.session_state.get('option_b_aer_checks')
if q is not None and q.get('waveform_id') != active_id:
    st.warning('Previous Aer results are incompatible with this waveform/configuration and are hidden. Rerun the Aer check.')
    q=None
if q is not None:
    checks=sum(bool(r['within_5_sigma_plus_sampling_floor']) for r in q['cases'])
    if q['all_consistent']:
        st.success('All Aer shot estimates satisfy the implemented model-consistency tolerance.')
    else:
        st.error('One or more Aer estimates exceed the model-consistency tolerance. Investigate before presenting.')
    metric_cols=st.columns(3)
    metric_cols[0].metric('Aer circuits executed',q['num_circuits'])
    metric_cols[1].metric('Shots per circuit',q['shots_per_circuit'])
    metric_cols[2].metric('Checks within tolerance',f"{checks}/{len(q['cases'])}")
    st.markdown(f"**Known-answer identity comparison: X^{q.get('identity_depth',32)}**")
    identity_rows=[{
        'Pulse':('Ideal' if row['candidate']=='ideal' else LABELS[row['candidate']]),
        'Model correct (%)':round(100*row['predicted_probability'],2),
        'Aer correct (%)':round(100*row['aer_shot_probability'],2),
        'Shot uncertainty (± pp, ~1σ)':round(100*row['estimated_shot_standard_error'],2),
        'Within tolerance':'YES' if row['within_5_sigma_plus_sampling_floor'] else 'NO'}
        for row in q['cases'] if row['task']=='identity']
    st.dataframe(pd.DataFrame(identity_rows),use_container_width=True,hide_index=True)
    with st.expander('View all 45 Aer circuit results (identity and parity)',expanded=False):
        st.dataframe(pd.DataFrame(q['cases']),use_container_width=True,hide_index=True)
        st.download_button('Download Aer results (CSV)',
            pd.DataFrame(q['cases']).to_csv(index=False).encode('utf-8'),
            file_name='pulsewise_aer_results.csv',mime='text/csv')


st.divider()
with st.expander('Optional Quantum Rings simulator comparison',expanded=False):
    st.write('Qiskit Aer vs an optional Quantum Rings simulator on the same '
             'coherent repeated-Rx circuits. This is separate from the '
             'T1/T2-and-detuning pulse experiment above.')
    error=st.slider('Coherent Rx amplitude error (%)',0.,10.,5.,step=.5,key='optional_qr_error')
    from quantum_rings_optional import DEPTHS, expected_probability, compare
    if st.button('Run Aer comparison',key='run_optional_aer'):
        try:
            st.session_state['optional_qr_comparison']={'error':error,
                'rows':compare(error/100)}
        except Exception as exc:
            st.error(f'Aer comparison failed: {exc}')
    if st.button('Run Quantum Rings + Aer',key='run_optional_qr'):
        try:
            st.session_state['optional_qr_comparison']={'error':error,
                'rows':compare(error/100,run_rings=True)}
        except Exception as exc:
            st.error(f'Optional Quantum Rings check unavailable: {exc}')
    saved=st.session_state.get('optional_qr_comparison')
    if saved and saved['error']==error:
        rows=[]
        for item in saved['rows']:
            row={'Depth':item['depth'],'Theory P(0) (%)':round(100*item['theory'],2),
                 'Aer P(0) (%)':round(100*item['aer'],2)}
            if item['quantum_rings'] is not None:
                row['Quantum Rings P(0) (%)']=round(100*item['quantum_rings'],2)
            rows.append(row)
        st.dataframe(pd.DataFrame(rows),hide_index=True)
        st.line_chart(pd.DataFrame(rows).set_index('Depth'))
        if 'Quantum Rings P(0) (%)' not in rows[0]:
            st.info('Quantum Rings was not executed; only Aer and theory are shown.')
        else:
            st.success('Quantum Rings simulator returned measurement counts.')
    else:
        st.dataframe(pd.DataFrame([{'Depth':n,
            'Theory P(0) (%)':round(100*expected_probability(n,error/100),2)}
            for n in DEPTHS]),hide_index=True)
    st.caption('Coherent amplitude error only. Not hardware validation. '
               'See docs/QUANTUM_RINGS_OPTIONAL.md.')

st.divider()
st.subheader('Scientific scope and reproducibility')
st.markdown('The optimizer was trained for average **single-gate** fidelity, not long-circuit success. The four-level model is a surrogate, not the physical Gridium Hamiltonian. The circuit benchmark neglects errors in CNOT/readout, and its calibration biases remain fixed during each circuit. None of these results are hardware measurements.')
st.code('python src/build_option_b.py\npython -m unittest discover -s tests -p "test_*.py" -v\npython src/build_option_b.py --qiskit',language='bash')
