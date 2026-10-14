"""Build judge-facing Option B research artifacts reproducibly.

At the repository root:
  python src/build_option_b.py                 # numerical suite + PNGs
  python src/build_option_b.py --quick         # smoke-test visualization
  python src/build_option_b.py --qiskit        # also run 45 explicit Aer circuits

Runs only the *frozen* optimizer waveform from optimization_report.json.
Nothing is reoptimized or silently substituted. Never implies hardware data.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from option_b_benchmarks import (CANDIDATES, LABELS, shared_multilevel_comparison,
    multilevel_sweep, circuit_depth_benchmark, stress_test_report,
    qiskit_aer_circuit_checks)

from result_provenance import REPORT_PATH, load_report, waveform_id

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results'/'option_b'
COLOR={'primitive':'#26729C', 'BB1':'#128A73',
       'CORPSE':'#9556A5', 'synthesized':'#DD7925'}
CASES=('zero systematic bias','amplitude +5%','detuning +0.04 Ω','combined corner')


def _load_report():
    report = load_report(ROOT)
    if report.get('winner') is None:
        raise RuntimeError('The optimizer report has no winning candidate')
    return report, REPORT_PATH.as_posix()


def _csv(name,rows):
    if not rows: raise ValueError('Empty table: '+name)
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader();writer.writerows(rows)


def _plot_depth(rows):
    fig,axes=plt.subplots(2,2,figsize=(13.7,9),layout='constrained',sharex=True,sharey=True)
    for ax,case in zip(axes.ravel(),CASES):
        for name in CANDIDATES:
            subset=[r for r in rows if r['case']==case and r['candidate']==name]
            ax.plot([r['depth'] for r in subset],
                    [100*r['success_probability'] for r in subset],
                    lw=2.7,marker='o',ms=6,label=LABELS[name],color=COLOR[name])
        ax.axhline(100,color='#999999',ls=':',lw=1.4)
        ax.set_title(case,fontsize=14,weight='semibold')
        ax.grid(alpha=.22)
        ax.set_xscale('log',base=2)
        ax.set_xticks([1,2,4,8,16,32],labels=['1','2','4','8','16','32'])
        ax.set_ylim(0,101)
    for ax in axes[1]: ax.set_xlabel('Number of successive noisy X gates',fontsize=12)
    for ax in axes[:,0]:ax.set_ylabel('Probability of correct final bit (%)',fontsize=12)
    axes[1,0].legend(loc='lower left',fontsize=11,framealpha=.88)
    fig.suptitle('Gate-level fidelity is not a guarantee of circuit-level reliability',
                 fontsize=16,weight='bold')
    fig.savefig(OUT/'01_known_answer_depth.png',dpi=190,facecolor='white')
    plt.close(fig)


def _plot_multilevel(rows):
    fig,axs=plt.subplots(1,3,figsize=(14,5.6),layout='constrained')
    names=[LABELS[r['candidate']] for r in rows]
    colors=[COLOR[r['candidate']] for r in rows]
    fields=[('fidelity_unconditional','Unconditional logical fidelity',100),
            ('final_leakage','Final leaked population',100),
            ('peak_leakage','Sampled peak leakage\n(18 steps/segment)',100)]
    for ax,(key,title,scale) in zip(axs,fields):
        values=[scale*r[key] for r in rows]
        bars=ax.bar(range(4),values,color=colors,width=.7)
        ax.set_title(title,fontsize=13,weight='semibold')
        ax.set_ylabel('Percent (%)',fontsize=11)
        ax.set_xticks(range(4),names,rotation=26,ha='right',fontsize=10)
        ax.set_ylim(0, min(100.,max(values)*1.22+1) if key=='fidelity_unconditional'
                    else max(values)*1.22+1)
        ax.grid(axis='y',alpha=.17)
        for bar,v in zip(bars,values):
            ax.text(bar.get_x()+bar.get_width()/2,v+max(values)*.035,
                    f'{v:.1f}%',ha='center',fontsize=10,weight='medium')
    fig.suptitle('Four-pulse comparison under identical four-level surrogate physics',
                 fontsize=16,weight='bold')
    fig.savefig(OUT/'02_matched_multilevel.png',dpi=190,facecolor='white')
    plt.close(fig)


def _plot_stress(rows):
    suites=('dense_in_domain','new_random_in_domain','shifted_calibration_out_of_domain')
    readable=('Dense in-domain','New random in-domain','Shifted outside training box')
    x=np.arange(len(suites));width=.19
    fig,ax=plt.subplots(figsize=(11.5,5.7),layout='constrained')
    for j,name in enumerate(CANDIDATES):
        vals=[100*next(r for r in rows if r['candidate']==name and r['scenario']==s)['fraction_below_threshold']
              for s in suites]
        ax.bar(x+(j-1.5)*width, vals,width,label=LABELS[name],color=COLOR[name])
    ax.set_xticks(x,readable)
    ax.set_ylabel('Samples failing the 99.7% single-gate threshold (%)')
    ax.set_ylim(0,60)
    ax.grid(axis='y',alpha=.2)
    ax.legend(ncol=4,loc='upper center')
    ax.set_title('Frozen optimizer: in-domain resilience vs calibration drift',fontsize=15,weight='bold')
    fig.savefig(OUT/'03_stress_failure_rate.png',dpi=190,facecolor='white')
    plt.close(fig)


def _plot_cost(rows):
    subset=[r for r in rows if r['case']=='combined corner' and r['depth']==32]
    names=[LABELS[r['candidate']] for r in subset]
    colors=[COLOR[r['candidate']] for r in subset]
    fig,axs=plt.subplots(1,2,figsize=(11.8,5.3),layout='constrained')
    for ax,key,title,unit in zip(axs,
            ['total_duration_ns','total_segments'],
            ['Total drive duration','Control segments executed'],
            ['µs','segments']):
        values=[r[key]/1000 if key=='total_duration_ns' else r[key] for r in subset]
        bars=ax.bar(range(4),values,color=colors)
        ax.set_xticks(range(4),names,rotation=22,ha='right')
        ax.set_ylabel(unit)
        ax.set_title(title,fontsize=13,weight='semibold')
        ax.set_ylim(0,max(values)*1.17)
        ax.grid(axis='y',alpha=.2)
        for b,v in zip(bars,values):
            ax.text(b.get_x()+b.get_width()/2,v+max(values)*.025,
                    f'{v:.1f}' if key=='total_duration_ns' else str(int(v)),
                    ha='center',fontsize=10)
    fig.suptitle('Real costs of pulse-based suppression: the 32-X-gate circuit',
                 fontsize=15,weight='bold')
    fig.savefig(OUT/'04_circuit_resource_cost.png',dpi=190,facecolor='white')
    plt.close(fig)


def _plot_parity(rows):
    fig,ax=plt.subplots(figsize=(10.4,5.5),layout='constrained')
    cases=('amplitude +5%','detuning +0.04 Ω','combined corner')
    labels=[LABELS[c] for c in CANDIDATES]
    mat=np.array([[100*next(r for r in rows if r['candidate']==name and r['case']==case)['parity_3bit_mean_success']
                   for case in cases] for name in CANDIDATES])
    im=ax.imshow(mat,aspect='auto',cmap='viridis',vmin=97,vmax=100)
    ax.set_xticks(range(3),cases)
    ax.set_yticks(range(4),labels)
    for (i,j),value in np.ndenumerate(mat):
        ax.text(j,i,f'{value:.3f}%',ha='center',va='center',
                color='black' if value>99.25 else 'white',fontsize=12,weight='semibold')
    ax.set_title('Qiskit-ready known-answer algorithm: 3-bit parity',fontsize=15,weight='bold')
    ax.set_xlabel('Shared simulated control-bias regime')
    fig.colorbar(im,ax=ax,label='Average probability of correct parity (%)')
    fig.savefig(OUT/'05_parity_algorithm.png',dpi=190,facecolor='white')
    plt.close(fig)


def _write_readme(report,ml,depth,stress):
    by={r['candidate']:r for r in ml}
    corner={r['candidate']:r for r in depth if r['case']=='combined corner' and r['depth']==32}
    dense={r['candidate']:r for r in stress if r['scenario']=='dense_in_domain'}
    ood={r['candidate']:r for r in stress if r['scenario']=='shifted_calibration_out_of_domain'}
    lines=['# PulseWise Option B — Validated Numerical Report','',
        '## Core discovery: gate scores can hide circuit failure','',
        'Single-gate average fidelity was used to *select* the synthesized waveform. Its',
        'circuit-level correctness was NOT included in the optimization objective.',
        'Repeating the same slightly imperfect channel 32 times exposes coherent',
        'error accumulation (within the specified Lindblad model).','',
        '| Pulse | P(correct) after X^32, combined corner | Duration | Segments |',
        '|---|---:|---:|---:|']
    for name in CANDIDATES:
        r=corner[name]
        lines.append(f"| {LABELS[name]} | {100*r['success_probability']:.3f}% | {r['total_duration_ns']/1000:.3f} µs | {r['total_segments']} |")
    lines.extend(['','Combined corner: amplitude error +0.05, detuning +0.04 Ω, T1/T2 fixed',
                  'by the saved optimizer report. Circuit is an X^32 identity test.',
                  'This is a precise known-answer circuit but NOT a hardware demonstration.','',
                  '## Matched coherent four-level surrogate comparison','',
                  '| Pulse | Unconditional logical fidelity | Final leakage | Sampled peak leakage (18 steps/segment) |',
                  '|---|---:|---:|---:|'])
    for name in CANDIDATES:
        r=by[name]
        lines.append(f"| {LABELS[name]} | {100*r['fidelity_unconditional']:.3f}% | {100*r['final_leakage']:.3f}% | {100*r['peak_leakage']:.3f}% |")
    lines.extend(['','Shared parameters: α/Ω=-3, η=√2, amp/detuning bias=0, Ω=π/(100 ns).',
                  '**Coherent surrogate, no T1/T2.** Do not compare absolute four-level',
                  'fidelities to decohering two-level fidelities as though they share a model.','',
                  '## Subsequent stress test of the frozen optimized waveform','',
                  '| Pulse | Dense grid worst in box | Shifted-box fraction below 99.7% |',
                  '|---|---:|---:|'])
    for name in CANDIDATES:
        lines.append(f"| {LABELS[name]} | {100*dense[name]['min_fidelity']:.4f}% | {100*ood[name]['fraction_below_threshold']:.1f}% |")
    lines.extend(['','The out-of-domain box deliberately shifts by +0.025 amplitude and',
                  '+0.02 normalized detuning. No guarantee was made outside training.',
                  '', '## Interpreting these results','',
                  '- Strong single-gate average fidelity is **not sufficient** to certify a',
                  '  long sequence, especially under coherent, quasi-static calibration errors.',
                  '- Standard BB1 can outperform this synthesized candidate at the circuit level',
                  '  even where the synthesized waveform passes its sampled gate threshold.',
                  '- A shorter primitive can have better logical fidelity than composite pulses',
                  '  in the surrogate multilevel model. This does not generalize to hardware.',
                  '- The parity algorithm assumes *perfect CNOTs and readout*, and only tests',
                  '  noise in single-qubit X preparations. This is a model-specific scope.',
                  '- All optimizer/dynamics findings are simulation outputs, not experimental',
                  '  performance claims or an independently calibrated Gridium model.',
                  '', '## Reproduce','',
                  '```bash','python src/build_option_b.py',
                  'python -m unittest discover -s tests -p "test_*.py" -v',
                  'python src/build_option_b.py --qiskit  # if Qiskit Aer installed',
                  'python -m streamlit run app.py','```','',
                  'Figures and CSV/JSON results appear in `results/option_b/`.',
                  'Generated by deterministic algorithms without changing saved optimizer settings.',
                  'Waveform/configuration SHA-256: '+waveform_id(report),
                  'Leakage peaks are sampled maxima, not continuous-time bounds.',
                  ''])
    (OUT/'NUMERICAL_FINDINGS.md').write_text('\n'.join(lines),encoding='utf-8')


def build(*,quick=False,run_qiskit=False):
    OUT.mkdir(parents=True,exist_ok=True)
    report,source=_load_report()
    print('Option B optimizer source:',source,flush=True)
    ml=shared_multilevel_comparison(report)
    sweep=multilevel_sweep(report,alphas=np.linspace(-8.,-1.,29))
    depth=circuit_depth_benchmark(report)
    stress=stress_test_report(report,grid_size=11 if quick else 31,
                              n_random=64 if quick else 512)
    _csv('multilevel_comparison.csv',ml)
    _csv('multilevel_sweep.csv',sweep)
    _csv('known_answer_circuit.csv',depth)
    _csv('optimizer_stress_test.csv',stress)
    print('Option B plotting 1/5 ...',flush=True)
    _plot_depth(depth)
    print('Option B plotting 2/5 ...',flush=True)
    _plot_multilevel(ml)
    print('Option B plotting 3/5 ...',flush=True)
    _plot_stress(stress)
    print('Option B plotting 4/5 ...',flush=True)
    _plot_cost(depth)
    print('Option B plotting 5/5 ...',flush=True)
    _plot_parity(depth)
    _write_readme(report,ml,depth,stress)
    summary={'source_report':source,'config':report['config'],
             'waveform_id':waveform_id(report),
             'leakage_sampling':{'comparison_steps_per_segment':18,
                                 'sweep_steps_per_segment':12},
             'candidate_names':list(CANDIDATES),
             'models':{'circuit':'two-level Lindblad; static control bias across each circuit',
                       'multilevel':'4D coherent surrogate without T1/T2',
                       'parity':'3 noisy X preparations and 3 ideal CNOTs; ideal measurement'},
             'multilevel_comparison':ml,'depth_results':depth,'optimizer_stress':stress,
             'qiskit_aer_status':'not run (use --qiskit)'}
    if run_qiskit:
        print('Option B running 45 Qiskit Aer circuits ...',flush=True)
        qr=qiskit_aer_circuit_checks(report,depth=32)
        (OUT/'qiskit_aer_validation.json').write_text(json.dumps(qr,indent=2)+'\n',encoding='utf-8')
        summary['qiskit_aer_status']='passed' if qr['all_consistent'] else 'disagreement detected'
    (OUT/'research_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print('Option B complete:',OUT.resolve(),flush=True)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--quick',action='store_true')
    parser.add_argument('--qiskit',action='store_true')
    args=parser.parse_args()
    build(quick=args.quick,run_qiskit=args.qiskit)
