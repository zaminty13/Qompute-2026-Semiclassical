"""Optional coherent-only Quantum Rings simulator check. No pulse or hardware claims."""
import math
import os

DEPTHS=(2,4,8,16,32)

def expected_probability(depth,error):
    if isinstance(depth,bool) or not isinstance(depth,int) or depth<1:
        raise ValueError("depth must be positive integer")
    if not isinstance(error,(int,float)) or not math.isfinite(error) or not -.5<=error<=.5:
        raise ValueError("amplitude error must be in [-.5,.5]")
    return math.cos(depth*math.pi*(1+error)/2)**2

def circuits(error=.05):
    from qiskit import QuantumCircuit
    output=[]
    for depth in DEPTHS:
        expected_probability(depth,error)
        circuit=QuantumCircuit(1,1)
        for _ in range(depth):
            circuit.rx(math.pi*(1+error),0)
        circuit.measure(0,0)
        output.append(circuit)
    return output

def run_aer(error=.05,shots=2048):
    from qiskit_aer import AerSimulator
    if not isinstance(shots,int) or isinstance(shots,bool) or shots<64:
        raise ValueError("shots must be integer >=64")
    result=AerSimulator(method="density_matrix").run(circuits(error),shots=shots,seed_simulator=2026).result()
    return [result.get_counts(i).get("0",0)/shots for i in range(len(DEPTHS))]

def run_quantum_rings(error=.05,shots=2048):
    """Only invoked on explicit opt-in; requires optional SDK and credentials."""
    if not isinstance(shots,int) or isinstance(shots,bool) or shots<64:
        raise ValueError("shots must be integer >=64")
    try:
        from quantumrings.toolkit.qiskit import QrBackendV2
    except ImportError as exc:
        raise RuntimeError("Quantum Rings SDK unavailable; see docs/QUANTUM_RINGS_OPTIONAL.md") from exc
    from qiskit import transpile
    token,account=os.environ.get("QR_TOKEN"),os.environ.get("QR_ACCOUNT")
    if bool(token)!=bool(account):
        raise RuntimeError("Set both QR_TOKEN and QR_ACCOUNT or use saved SDK credentials")
    settings={"backend":"scarlet_quantum_rings","num_qubits":1}
    if token:
        settings.update({"token":token,"name":account})
    backend=QrBackendV2(**settings)
    output=[]
    for circuit in circuits(error):
        compiled=transpile(circuit,backend,optimization_level=0)
        output.append(backend.run(compiled,shots=shots).result().get_counts().get("0",0)/shots)
    return output

def compare(error=.05,shots=2048,run_rings=False):
    theory=[expected_probability(n,error) for n in DEPTHS]
    aer=run_aer(error,shots)
    rings=run_quantum_rings(error,shots) if run_rings else None
    return [{"depth":n,"theory":theory[i],"aer":aer[i],
             "quantum_rings":rings[i] if rings is not None else None}
            for i,n in enumerate(DEPTHS)]
