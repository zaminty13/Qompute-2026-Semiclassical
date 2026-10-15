"""PulseWise Research Lab -- additional Streamlit multipage view.

Existing app.py / selector unaffected. Select Research Lab in the sidebar.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from research_synthesis import Experiment, synthesize
from research_leakage import propagate
from research_diagnostics import summarize_selection, independent_sample_stress
from result_provenance import load_report, waveform_id, optimizer_reporting

st.set_page_config(page_title='PulseWise | Research Lab',page_icon='🧬',layout='wide')
st.title('🧬 PulseWise / Research Lab')
st.caption('TEAM SEMICLASSICAL · QOMPUTE 2026 · GRIDIUM-INSPIRED CONTROL SYNTHESIS')
st.write('**Can an automatically designed gate pass a robustness threshold faster than BB1—and what happens when leakage becomes possible?**')
st.info('The optimizer searches a two-level Lindblad simulation. The separate multilevel demonstration is an illustrative four-state surrogate, **not a validated Gridium device**. Qiskit Aer checks the same modeled channels, not actual hardware.')

with st.sidebar:
    st.header('Research configuration')
    st.caption('Independent of settings on the classic selector page.')
    amin=st.slider('Amplitude uncertainty ± (%)',1.,10.,5.,step=.5)
    dmin=st.slider('Normalized detuning uncertainty ±',.005,.10,.04,step=.005,format='%.3f')
    threshold=st.slider('Required worst sampled fidelity (%)',98.0,99.9,99.7,step=.1)
    t1us=st.slider('T₁ (µs)',30,500,200,step=10)
    t2us=st.slider('T₂ (µs)',20,500,150,step=10)
    effort=st.select_slider('Optimization budget',options=['Quick (~15–40 sec)','Full (~30–90 sec)'])
    st.caption('Unlike the classic page, this research case assumes zero-centered calibration uncertainty (no known 5% bias to recenter).')

if t2us>2*t1us:
    st.error('Choose a physical combination with T₂ ≤ 2T₁.'); st.stop()
ex=Experiment(amplitude_center=0.,amplitude_width=amin/100,
              detuning_width_over_omega=dmin,min_fidelity=threshold/100,
              t1_ns=1000*t1us,t2_ns=1000*t2us)

if st.button('🧪 Synthesize and stress-test new controls',type='primary'):
    with st.spinner('Optimizing phased segments, then evaluating validation conditions used for selection...'):
        try:
            report=synthesize(ex,maxiter=4 if effort.startswith('Quick') else 16,
                              popsize=3 if effort.startswith('Quick') else 5)
            st.session_state['research_report']=report
        except Exception as exc:
            st.error(f'Synthesis failed: {exc}')

report=st.session_state.get('research_report')
if report is None:
    try:
        report=load_report(ROOT)
        st.caption('Showing the saved research report. Synthesis uses the current sidebar settings.')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.warning(f'Saved research report unavailable: {exc}')
if report is None:
    st.markdown('### Ready to synthesize')
    st.write('Press the button above. The algorithm explores five-piece rectangular control waveforms, limited to the same maximum drive strength as X/BB1/CORPSE, and compares them under matched decoherence and control errors.')
    st.write('The work is CPU-based and may take tens of seconds. For reproducibility, use `python src/plot_research.py --quick` to generate a frozen report and shareable figures.')
    st.stop()

st.caption('Waveform/configuration SHA-256: '+waveform_id(report))
with st.expander('Solver reporting and fidelity requirements'):
    st.write('The advertised requirement is '+str(report['config']['min_fidelity'])+
             '; the internal SLSQP safety target is '+str(min(1.,report['config']['min_fidelity']+3e-5))+'.')
    st.json(optimizer_reporting(report))
last=report['config']
if (last['amplitude_width'] != ex.amplitude_width or
    last['detuning_width_over_omega'] != ex.detuning_width_over_omega or
    last['min_fidelity'] != ex.min_fidelity or
    last['t1_ns'] != ex.t1_ns or last['t2_ns'] != ex.t2_ns):
    st.warning('The displayed results are from your previous experiment. Rerun synthesis to reflect sidebar changes.')
rex=Experiment(**last)
rows=report['candidates']
winner=next((r for r in rows if r['name']==report['winner']),None)
ref=next(r for r in rows if r['name']=='BB1')

m1,m2,m3,m4=st.columns(4)
m1.metric('Fastest passing candidate',winner['name'] if winner else 'None')
m2.metric('Fastest duration',f"{winner['duration_ns']:.1f} ns" if winner else '—')
m3.metric('BB1 reference duration','500.0 ns')
m4.metric('Validation points used for selection',str(report['n_heldout']))
if winner is None:
    st.error('No candidate passes both TRAIN and VALIDATION under the current configuration. Do not claim an optimized winner.')
elif winner['label']=='synthesized':
    savings=100*(1-winner['duration_ns']/ref['duration_ns'])
    st.success(f"Synthesized candidate passed the sampled fidelity threshold at {winner['duration_ns']:.1f} ns — {savings:.1f}% shorter than standard BB1 in this model. Both training and validation checks passed.")
else:
    st.info('A reference control or calibration adjustment is fastest in this scenario. The optimizer did not show a validated speed advantage.')

left,right=st.columns([1.45,1.])
with left:
    st.subheader('The speed–reliability frontier')
    fig=go.Figure()
    for r in rows:
        kind=r['label']
        marker_color=('#1AC1A3' if r['name']==report['winner'] else
                      '#7291ad' if kind=='reference' else '#db9548')
        fig.add_trace(go.Scatter(x=[r['duration_ns']],y=[100*r['heldout_worst']],
            mode='markers',marker=dict(color=marker_color,size=17 if r['name']==report['winner'] else 11,
                        symbol='star' if r['name']==report['winner'] else 'circle'),
            name=r['name'],hovertemplate='%{text}<br>%{x:.2f} ns<br>%{y:.5f}%<extra></extra>',
            text=[r['name']]))
    fig.add_hline(y=100*rex.min_fidelity,line_dash='dash',line_color='#ef8c64',
                  annotation_text=f'Threshold {100*rex.min_fidelity:.2f}%')
    fig.update_layout(xaxis_title='Full control duration (ns)',
                      yaxis_title='Validation worst sampled fidelity (%)',
                      height=430,legend=dict(orientation='h',y=-.25),margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig,use_container_width=True)
with right:
    st.subheader('What was actually tested?')
    view=[dict(Candidate=r['name'],Duration_ns=round(r['duration_ns'],2),
               Nominal_pct=round(100*r['nominal_fidelity'],4),
               TRAIN_worst_pct=round(100*r['train_worst'],4),
               VALIDATION_worst_pct=round(100*r['heldout_worst'],4),
               Pass='YES' if r['train_pass'] and r['heldout_pass'] else 'NO')
          for r in rows]
    st.dataframe(pd.DataFrame(view),hide_index=True,use_container_width=True)
    st.caption('Each *_constrained_synthesis candidate is a separate SLSQP local refinement from the named starting pulse. All use the same constraints and evaluation points. TRAIN: nine corner/center conditions. VALIDATION: 96 separate boundary/interior samples used to select candidates and break duration ties. Subsequent dense/random stress tests are separate. No continuous bound is certified.')
    st.download_button('Download complete research report (JSON)',
                       __import__('json').dumps(report,indent=2),
                       file_name='pulsewise_research_report.json',mime='application/json')

st.subheader('Scientific interpretation of this selection')
audit = summarize_selection(report)
if audit['fastest_passing_reference'] is not None:
    st.write(f"Fastest passing conventional reference: **{audit['fastest_passing_reference']}** "
             f"({audit['fastest_passing_reference_ns']:.2f} ns). "
             f"Time reduction relative to that reference: "
             f"**{audit['reduction_vs_fastest_passing_reference_pct']:.2f}%**. "
             "The BB1 500 ns comparison is shown separately above.")
if len(audit['near_tied_candidates']) > 1:
    st.info(f"Numerical near-tie within {audit['near_tie_ns']:.2f} ns: "
            + ', '.join(audit['near_tied_candidates'])
            + '. The named fastest candidate is not demonstrably superior at this precision.')
if audit['winner_solver_success'] is False:
    st.warning('Selected candidate passed the advertised sampled fidelity threshold, '
               'but its optimizer did NOT report successful convergence: '
               + str(audit['winner_solver_message'])
               + '. Inspect the solver residuals above before drawing conclusions.')
elif audit['winner_solver_success'] is True:
    st.caption('Selected optimizer reported successful termination. This is local, not global optimality.')
if audit['winner_near_single_axis']:
    st.info('The winner has nearly identical x-axis segment phases with total unsigned '
            f'pulse area {audit["winner_total_unsigned_angle_over_pi"]:.5f}π. '
            'It effectively resembles a slightly underrotated primitive X pulse, '
            'not a demonstrated BB1 composite-pulse advantage.')
if audit['differential_evolution_converged'] is False:
    st.caption('Differential Evolution did not report convergence within its budget. '
               'Quick/Full changes the DE budget; SLSQP uses up to 65 iterations in either mode.')

with st.expander('Extra post-selection stress test (separate from candidate selection)'):
    st.caption('Fresh deterministic grid and random locations from the same 2-level '
               'Lindblad model, excluding training and selection points. '
               'Does not alter the winner; is not hardware or continuous-bound certification.')
    if st.button('Run additional post-selection samples'):
        with st.spinner('Checking fresh uncertainty samples...'):
            st.session_state['post_selection_audit'] = {
                'waveform_id': waveform_id(report),
                'result': independent_sample_stress(report)}
    cached = st.session_state.get('post_selection_audit')
    if cached is not None and cached['waveform_id'] == waveform_id(report):
        extra = cached['result']
        st.write(f"Evaluated **{extra['total_points']} new uncertainty points**.")
        st.dataframe(pd.DataFrame([{
            'Candidate': c['candidate'], 'Worst_fidelity_pct': round(100*c['worst_fidelity'], 5),
            'Pass': 'YES' if c['pass_stress'] else 'NO',
            'Failures': c['below_threshold_count']
        } for c in extra['candidates']]), hide_index=True)
        st.caption(extra['disclaimer'])

st.divider()
st.header('1. Discover what the optimizer actually built')
choices=[r['name'] for r in rows]
default_index=choices.index(winner['name']) if winner else 0
chosen=st.selectbox('Inspect candidate',choices,index=default_index)
record=next(r for r in rows if r['name']==chosen)
segments=record['segments']
fig=go.Figure()
t=0.
for ang,phase in segments:
    dt=float(ang)/rex.omega
    for val,name,color in [(np.cos(phase),'Ωx/Ω','#1AC1A3'),
                           (np.sin(phase),'Ωy/Ω','#b78aff')]:
        fig.add_trace(go.Scatter(x=[t,t+dt],y=[val,val],mode='lines',
                                 line=dict(color=color,width=5),showlegend=False,
                                 hovertemplate=name+': %{y:.3f}<br>t=%{x:.1f} ns<extra></extra>'))
    t+=dt
fig.update_layout(height=260,xaxis_title='Time (ns)',yaxis_title='Normalized drive quadrature',
                  yaxis_range=[-1.15,1.15],margin=dict(l=10,r=10,t=10,b=10))
st.plotly_chart(fig,use_container_width=True)
st.caption('Piecewise phase-controlled drive at **fixed Ω = π/100 ns**, identical maximum drive magnitude to the standard sequences. This is not an executable IBM backend pulse schedule.')

st.header('2. The Gridium-inspired multilevel reality check')
st.write('The ordinary selector assumes only logical states |0⟩ and |1⟩. This additional experiment introduces an off-resonant leakage level |2⟩ and a decoupled spectator |3⟩ (a four-dimensional unitary suitable for two Qiskit qubits).')
a1,a2=st.columns([1,2])
with a1:
    alpha=st.slider('Toy-model anharmonicity α/Ω',-8.0,-1.0,-3.0,step=.25)
    eta=st.slider('Leakage coupling relative to logical drive',0.0,2.0,float(np.sqrt(2)),step=.05)
    amp=st.slider('Actual amplitude error for leakage run (%)',-10.,10.,0.,step=.5)
    det=st.slider('Actual detuning Δ/Ω for leakage run',-.10,.10,0.,step=.005)
ml=propagate(segments,primitive_ns=rex.primitive_ns,
             anharmonicity_over_omega=alpha,coupling_ratio=eta,
             amplitude_error=amp/100,detuning_over_omega=det)
with a2:
    r1,r2,r3=st.columns(3)
    r1.metric('Unconditional logical fidelity',f"{100*ml['fidelity_unconditional']:.2f}%")
    r2.metric('Final leakage',f"{100*ml['final_leakage']:.2f}%")
    r3.metric('Sampled peak leakage',f"{100*ml['peak_leakage']:.2f}%")
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=ml['times_ns'],y=np.array(ml['mean_leakage'])*100,
             name='Mean leakage',line=dict(color='#f5a764',width=3)))
    fig.add_trace(go.Scatter(x=ml['times_ns'],y=np.array(ml['leak_state_population_if_zero'])*100,
             name='Leakage |0⟩ input',line=dict(color='#5D9DEF',dash='dot')))
    fig.add_trace(go.Scatter(x=ml['times_ns'],y=np.array(ml['leak_state_population_if_one'])*100,
             name='Leakage |1⟩ input',line=dict(color='#b78aff',dash='dot')))
    fig.update_layout(height=350,xaxis_title='Time (ns)',yaxis_title='Leakage population (%)',
                      margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig,use_container_width=True)
st.caption(f"Leakage maximum over sampled times: {ml['steps_per_segment']} steps per segment. This is not a continuous-time maximum.")
st.warning('Important: This multilevel calculation is coherent (no T₁/T₂) and uses a **surrogate ladder**, not the physical Gridium Hamiltonian. Its absolute fidelities cannot be directly compared with the noisy two-level figures above. The lesson is that a two-level winner can fail when leakage is introduced.')

st.header('3. Qiskit: circuit checks of the model')
c1,c2=st.columns(2)
with c1:
    if st.button('▶ Verify synthesized single-qubit channel (six states)'):
        try:
            from research_qiskit import six_state_aer_check
            with st.spinner('Running six Qiskit Aer circuits...'):
                q=six_state_aer_check(segments,rex,shots=1024)
            st.write(f"Qiskit predicted {100*q['predicted_fidelity']:.4f}% vs shot estimate {100*q['shot_estimate']:.4f}% ± {100*q['shot_standard_error']:.3f} pp (approx. 1σ).")
            st.code(str(q['circuits'][0].draw(output='text')))
        except Exception as exc: st.error(str(exc))
with c2:
    if st.button('▶ Verify multilevel leakage using two-qubit Aer'):
        try:
            from research_leakage import qiskit_sample_leakage
            with st.spinner('Running two Qiskit Aer circuits...'):
                q=qiskit_sample_leakage(ml['unitary'],shots=4096)
            st.write(f"Exact final leakage {100*q['exact_mean_leakage']:.3f}% vs Aer shot estimate {100*q['estimated_mean_leakage']:.3f}%.")
            st.code(str(q['circuits'][0].draw(output='text')))
        except Exception as exc: st.error(str(exc))
st.caption('Neither Qiskit check validates a hardware pulse schedule. They independently execute circuits using the same mathematically modeled channels/unitaries. Real hardware and an experimentally calibrated Hamiltonian would be required for physical validation.')
