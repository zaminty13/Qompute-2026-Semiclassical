import hashlib
import json
from pathlib import Path

REPORT_PATH = Path('results/research/optimization_report.json')
SUMMARY_PATH = Path('results/option_b/research_summary.json')
MANIFEST_PATH = Path('docs/reviewed_results.json')


def waveform_id(report):
    payload = {
        'schema': 1,
        'config': report['config'],
        'winner': report['winner'],
        'controls': sorted(
            [{'name': row['name'], 'segments': row['segments']}
             for row in report['candidates']], key=lambda row: row['name']),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                         allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def load_report(root):
    report = json.loads((Path(root) / REPORT_PATH).read_text(encoding='utf-8'))
    actual = waveform_id(report)
    if report.get('waveform_id', actual) != actual:
        raise ValueError('Optimizer report waveform/configuration identifier is invalid.')
    return report


def verify_results(root, report, path=SUMMARY_PATH):
    root, path = Path(root), Path(path)
    raw = (root / path).read_bytes()
    results = json.loads(raw)
    expected = waveform_id(report)
    if 'waveform_id' in results:
        if results['waveform_id'] != expected:
            raise ValueError('Saved results belong to a different waveform/configuration. Generate matching results before displaying them.')
    else:
        manifest = json.loads((root / MANIFEST_PATH).read_text(encoding='utf-8'))
        if (manifest['waveform_id'] != expected or
                manifest['files'].get(path.as_posix()) != hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()):
            raise ValueError('Legacy results do not match the reviewed waveform/configuration or file hash. Generate matching results before displaying them.')
    if path == SUMMARY_PATH and results['config'] != report['config']:
        raise ValueError('Saved results have an incompatible simulation configuration.')
    return results


def optimizer_reporting(report):
    return report.get('solver_reports', {
        'status': 'unavailable',
        'reason': 'Historical report does not record solver termination or constraint residuals.'})
