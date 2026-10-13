"""Reproduce research-grade PulseWise synthesis and leakage figures.

At the repo root:
  python src/plot_research.py --quick
  python src/plot_research.py

This writes *new* files under results/research without altering existing team
science or changing the old dashboard's 41-test selector behavior.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0,str(Path(__file__).resolve().parent))
from research_synthesis import Experiment, synthesize, evaluate, uncertainty_points, save_report
from research_leakage import propagate

OUT=Path(__file__).resolve().parents[1]/'results'/'research'
COLORS={'primitive':'#356ca9','BB1':'#0c9277','CORPSE':'#9256ae',
        'BB1_constrained_synthesis':'#da8330'}


def _color(n):
    return COLORS.get(n,'#657e8d')


def build(ex:Experiment,*,quick=False):
    OUT.mkdir(parents=True,exist_ok=True)
    print("stage: optimize",flush=True)
    report=synthesize(ex,maxiter=4 if quick else 16,
                      popsize=3 if quick else 5)
    # On the actual Qiskit installation, validate our fast SciPy Liouvillian
    # with the team's independently implemented Qiskit SuperOp route.
    try:
        import qiskit
        from research_synthesis import qiskit_reference_check
        probes={}
        for candidate in report['candidates']:
            if candidate['name'] not in ('primitive','BB1','CORPSE',
                                        'BB1_constrained_synthesis'):
                continue
            check=qiskit_reference_check(candidate['segments'],ex,
                ex.amplitude_center,ex.detuning_center_over_omega)
            probes[candidate['name']]=check
            if check['channel_max_abs_error'] > 1e-9 or check['fidelity_difference'] > 1e-10:
                raise RuntimeError('Qiskit/reference physics mismatch: '+candidate['name'])
        report['qiskit_cross_checks']={'status':'passed','probes':probes}
    except ImportError:
        report['qiskit_cross_checks']={'status':'not run: Qiskit/decoherence unavailable'}
    save_report(report, OUT/'optimization_report.json')
    rows=report['candidates']
    winner=next((r for r in rows if r['name']==report['winner']),None)
    columns=['name','label','duration_ns','nominal_fidelity','train_worst',
             'heldout_worst','heldout_mean','train_pass','heldout_pass']
    with (OUT/'candidate_comparison.csv').open('w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=columns)
        w.writeheader()
        w.writerows({k:r[k] for k in columns} for r in rows)

    baseline=[r for r in rows if r['name'] in ('primitive','BB1','CORPSE')]
    comparisons=baseline+([winner] if winner and winner['label']=='synthesized' else [])
    print("stage: plot1",flush=True)
    # Panel 1: sampled performance vs runtime, explicit pass/fail.
    fig,ax=plt.subplots(figsize=(10,5.8),layout='constrained')
    for r in comparisons:
        c=_color(r['name'])
        marker='*' if r['label']=='synthesized' else 'o'
        ax.scatter(r['duration_ns'],100*r['heldout_worst'],s=270 if marker=='*' else 120,
                   marker=marker,c=c,edgecolors='#1b2635',linewidths=1,zorder=3)
        is_right = r['name']=='BB1'
        ax.annotate(r['name'].replace('_constrained_synthesis',' (synthesized)'),
                    (r['duration_ns'],100*r['heldout_worst']),
                    xytext=(-8,9) if is_right else (7,9),
                    ha='right' if is_right else 'left',
                    textcoords='offset points',fontsize=10,color=c)
    ax.axhline(100*ex.min_fidelity,c='#b74f42',ls='--',label=f'Sampled threshold: {100*ex.min_fidelity:.2f}%')
    ax.set(xlabel='Total drive duration (ns)',ylabel='Held-out worst sampled fidelity (%)',
           title='A pulse the algorithm designs vs. standard sequences')
    ax.legend(loc='upper left')
    ax.grid(alpha=.2)
    ax.text(.01,.07,'96 held-out points · sampled, not a continuous guarantee',
            transform=ax.transAxes,fontsize=9,color='#4b5661')
    fig.savefig(OUT/'synthesis_speed_robustness.png',dpi=220,facecolor='white')
    plt.close(fig)

    print("stage: plot2",flush=True)
    # Panel 2: compare the BB1 and trained pulse fidelity landscapes under the
    # same exact T1/T2 Markovian model, not independent hardware calibrations.
    ref=next(r for r in rows if r['name']=='BB1')
    adaptive=next((r for r in rows if r['name']=='BB1_constrained_synthesis'),ref)
    nx=25
    amps=np.linspace(ex.amplitude_center-ex.amplitude_width,
                     ex.amplitude_center+ex.amplitude_width,nx)
    dets=np.linspace(ex.detuning_center_over_omega-ex.detuning_width_over_omega,
                     ex.detuning_center_over_omega+ex.detuning_width_over_omega,nx)
    grid=np.array([(a,d) for d in dets for a in amps])
    fref=evaluate(ref['segments'],ex,grid).reshape(nx,nx)
    fnew=evaluate(adaptive['segments'],ex,grid).reshape(nx,nx)
    fig,axes=plt.subplots(1,3,figsize=(14.5,4.6),layout='constrained')
    bounds=(100*amps[0],100*amps[-1],dets[0],dets[-1])
    zmin=min(np.min(fref),np.min(fnew))*100
    for ax,z,label in zip(axes[:2],[fref,fnew],['BB1 reference','Synthesized candidate']):
        im=ax.imshow(100*z,extent=bounds,origin='lower',aspect='auto',
                     cmap='viridis',vmin=zmin,vmax=100.)
        ax.set(xlabel='Amplitude error (%)',ylabel='Detuning Δ/Ω',title=label)
        ax.contour(100*z,levels=[100*ex.min_fidelity],extent=bounds,
                    colors=['white'],linewidths=1.3) if 100*z.min()<100*ex.min_fidelity<100*z.max() else None
        fig.colorbar(im,ax=ax,label='Average gate fidelity (%)')
    z=100*(fnew-fref)
    im=axes[2].imshow(z,extent=bounds,origin='lower',aspect='auto',cmap='coolwarm',
                     vmin=-max(.1,np.max(np.abs(z))),vmax=max(.1,np.max(np.abs(z))))
    axes[2].set(xlabel='Amplitude error (%)',ylabel='Detuning Δ/Ω',
                title='Synthesized − BB1 (percentage points)')
    fig.colorbar(im,ax=axes[2],label='Δ fidelity (pp)')
    fig.suptitle('Robustness is a landscape, not one headline fidelity',fontsize=15)
    fig.savefig(OUT/'synthesis_fidelity_landscape.png',dpi=220,facecolor='white')
    plt.close(fig)

    print("stage: plot3",flush=True)
    # Panel 3: show the multilevel caveat under a separate coherent surrogate.
    picks=baseline+([adaptive] if adaptive['name']=='BB1_constrained_synthesis' else [])
    alpha=np.linspace(-8.,-1.,25)
    fig,axs=plt.subplots(1,2,figsize=(12.5,4.8),layout='constrained')
    leakage_rows=[]
    for row in picks:
        outcomes=[propagate(row['segments'],anharmonicity_over_omega=float(a),
                            steps_per_segment=8) for a in alpha]
        f=np.array([r['fidelity_unconditional'] for r in outcomes])
        leak=np.array([r['peak_leakage'] for r in outcomes])
        axs[0].plot(alpha,100*f,lw=2.3,label=row['name'],color=_color(row['name']))
        axs[1].plot(alpha,100*leak,lw=2.3,label=row['name'],color=_color(row['name']))
        leakage_rows.extend({'candidate':row['name'],'alpha_over_omega':float(a),
                    'unconditional_fidelity':float(v), 'peak_leakage':float(l)}
                   for a,v,l in zip(alpha,f,leak))
    for ax in axs:
        ax.set_xlabel('Anharmonicity α/Ω (toy-model setting)')
        ax.axvline(-3.,c='#8795a1',ls='--',lw=1)
        ax.grid(alpha=.2)
    axs[0].set(ylabel='Coherent unconditional logical fidelity (%)',
               title='Logical errors, counting leakage as failure')
    axs[1].set(ylabel='Peak population outside logical subspace (%)',
               title='Transient leakage can be substantial')
    axs[0].legend(fontsize=8,loc='lower left')
    fig.suptitle('Multilevel reality check — illustrative 4D surrogate, no decoherence',fontsize=14)
    fig.savefig(OUT/'multilevel_leakage_stress_test.png',dpi=220,facecolor='white')
    plt.close(fig)
    with (OUT/'leakage_sweep.csv').open('w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=list(leakage_rows[0]))
        w.writeheader();w.writerows(leakage_rows)

    print("stage: waveform",flush=True)
    if winner:
        wave=winner['segments']
        fig,ax=plt.subplots(figsize=(10,3.8),layout='constrained')
        t=0.
        for i,(ang,phase) in enumerate(wave):
            dt=float(ang)/ex.omega
            ax.hlines(np.cos(phase),t,t+dt,color='#138d78',lw=5)
            ax.hlines(np.sin(phase),t,t+dt,color='#a454cc',lw=5)
            ax.axvline(t,color='#71808c',alpha=.35,lw=.8)
            t+=dt
        ax.set(xlabel='Total pulse time (ns)',ylabel='Normalized drive quadratures',
            ylim=(-1.25,1.25),title='Synthesized piecewise rectangular drive')
        from matplotlib.lines import Line2D
        ax.legend(handles=[Line2D([0],[0],c='#138d78',lw=4,label='Ωx/Ω'),
                           Line2D([0],[0],c='#a454cc',lw=4,label='Ωy/Ω')],loc='lower right')
        ax.grid(alpha=.15)
        fig.savefig(OUT/'synthesized_waveform.png',dpi=220,facecolor='white')
        plt.close(fig)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--quick',action='store_true',help='Smaller optimization budget')
    args=parser.parse_args()
    # Center zero: control bias unknown, symmetric uncertainty. This is a new
    # test case, not the legacy +5% nominal demo; avoids trivial recentering.
    ex=Experiment(amplitude_center=0.,amplitude_width=.05,
                  detuning_width_over_omega=.04,min_fidelity=.997)
    report=build(ex,quick=args.quick)
    print('Winner:',report['winner'])
    for row in report['candidates']:
        print(f"{row['name']:29s} T={row['duration_ns']:7.2f} ns  "
              f"train={row['train_worst']:.6%}  held={row['heldout_worst']:.6%} "
              f"passes={row['train_pass'] and row['heldout_pass']}")
    print('Generated science and figures:',OUT.resolve())
