"""Versioned, non-overwriting experiment entry point. Never substitutes for Harbor."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from .env import OpsDesk
from .reference import POLICIES
from .verify import report
from .world import PROFILE_FAMILIES

ROOT = Path(__file__).resolve().parent.parent
VERSION = 'opsdesk-v3.1.7'


def source_hashes():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'opsdesk').glob('*')) if p.suffix in ('.py','.md')}


def scripted(policy, seed, profile='all', nuisance=None):
    env = OpsDesk(seed, profile=profile)
    if nuisance == 'rename':
        for i,b in enumerate(env.bookings.values()):
            b.name = f'Traveler {i}'
    def call(name, args):
        result = env.tool(name, dict(reversed(list(args.items()))) if nuisance == 'key_order' else args)
        if nuisance == 'row_order':
            for key in ('flights', 'bookings'):
                if isinstance(result.get(key), list) and all(isinstance(x,dict) for x in result[key]):
                    result[key] = list(reversed(result[key]))
        if nuisance == 'rephrase':
            for key in ('alerts','new_alerts'):
                for row in result.get(key,[]):
                    row['text'] = 'Operations update. ' + row['text']
        return result
    POLICIES[policy](call)
    if not env.ended:
        env.finish(reason='harness')
    return report(env)


def harbor_outcome(stats: dict, infra: int, process_exit: int, expected: int) -> tuple[dict, int]:
    summary = {name: stats.get(key, 0) for name, key in (
        ('completed_trials', 'n_completed_trials'), ('errored_trials', 'n_errored_trials'),
        ('cancelled_trials', 'n_cancelled_trials'), ('running_trials', 'n_running_trials'),
        ('pending_trials', 'n_pending_trials'))}
    summary.update(expected_trials=expected, verifier_infrastructure_failures=infra, process_exit_code=process_exit)
    incomplete = summary['completed_trials'] != expected or any(summary[k] for k in (
        'errored_trials', 'cancelled_trials', 'running_trials', 'pending_trials'))
    return summary, process_exit or int(bool(incomplete or infra))


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('--suite', choices=['scripted','audit','harbor'], required=True)
    ap.add_argument('--name', default=None)
    ap.add_argument('--seeds', type=int, nargs='+', default=[1,2,3])
    ap.add_argument('--agent', choices=['oracle','nop','opencode'], default='oracle')
    ap.add_argument('--model')
    ap.add_argument('--runs', type=int, default=1)
    ap.add_argument('--concurrent', type=int, default=1)
    ap.add_argument('--opencode-config', type=Path)
    ap.add_argument('--api-key-name', default='GEMINI_API_KEY')
    a = ap.parse_args()
    name = a.name or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+a.suite
    if Path(name).name != name or name in ('.','..'):
        ap.error('--name must be a single directory name')
    out = ROOT/'results'/'experiments'/name
    out.mkdir(parents=True, exist_ok=False)
    manifest = {'experiment_version':VERSION,'suite':a.suite,'utc_started':datetime.now(timezone.utc).isoformat(),
                'python':platform.python_version(),'source_sha256':source_hashes(), 'seeds':a.seeds,
                'profile_seeds':{'development':[1,2,3],'final':[11,12,13]} if a.suite=='audit' else {'all':a.seeds},
                'runner':'Harbor' if a.suite == 'harbor' else 'in-process scripted, no model inference',
                'agent':a.agent if a.suite=='harbor' else None, 'model':a.model, 'runs_per_seed':a.runs,
                'opencode_config_sha256':hashlib.sha256(a.opencode_config.read_bytes()).hexdigest() if a.opencode_config else None,
                'family_split':{k:sorted(v) for k,v in PROFILE_FAMILIES.items()},
                'limitation':'Family audit was designed after builder exposure to the original all-family world. It is not an unseen-world frontier-model test.'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if a.suite == 'harbor':
        if a.agent == 'opencode' and not a.model:
            ap.error('--model is required for OpenCode')
        from .make_harbor import build
        tasks = out/'tasks'
        build(a.seeds,'standard',tasks,10800)
        env = dict(os.environ, OPSDESK_GRADER_TOKEN=secrets.token_hex(32))
        args = ['harbor','run','-y','--jobs-dir',str(out/'jobs'),'--job-name','run','-a',a.agent,'-k',str(a.runs),'-n',str(a.concurrent)]
        for task in sorted(tasks.iterdir()):
            args += ['-p',str(task)]
        if a.model:
            args += ['-m',a.model,'--api-key-name',a.api_key_name]
        if a.opencode_config:
            args += ['--ak','opencode_config='+json.dumps(json.loads(a.opencode_config.read_text()))]
        # Credentials stay in environment; Harbor scrubs run logs on completion.
        rc = subprocess.call(args,env=env)
        result_path = out/'jobs'/'run'/'result.json'
        stats = json.loads(result_path.read_text()).get('stats', {}) if result_path.exists() else {}
        infra = sum(bool(json.loads(p.read_text()).get('infra_error')) for p in (out/'jobs'/'run').glob('*/verifier/details.json'))
        # A zero Harbor process exit can still mean cancelled, missing, or infra-failed trials.
        manifest['harbor_summary'], manifest['exit_code'] = harbor_outcome(stats, infra, rc, len(a.seeds) * a.runs)

    else:
        rows, errors = [], []
        profiles = [('all',a.seeds)] if a.suite == 'scripted' else [('development',[1,2,3]),('final',[11,12,13])]
        for profile,seeds in profiles:
            for seed in seeds:
                for policy in ['reference','nothing','stop_early','naive']:
                    try:
                        baseline = scripted(policy,seed,profile)
                    except Exception as exc:
                        errors.append({'seed':seed,'profile':profile,'policy':policy,'error_type':type(exc).__name__,'error':str(exc)})
                        (out/'errors.json').write_text(json.dumps(errors,indent=2)+'\n')
                        continue
                    rows.append({'policy':policy,'nuisance':None, **baseline})
                    if a.suite == 'audit' and profile == 'development':
                        for nuisance in ['rename','key_order','row_order','rephrase']:
                            r = scripted(policy,seed,profile,nuisance)
                            rows.append({'policy':policy,'nuisance':nuisance,
                                         'same_score':r['score']==baseline['score'],
                                         'same_value':r['value']==baseline['value'], **r})
        (out/'reports.json').write_text(json.dumps(rows,indent=2)+'\n')
        manifest['failed_trials']=len(errors)
        if a.suite == 'scripted':
            from .exploits import ATTEMPTS
            attacks = []
            for name,policy in ATTEMPTS.items():
                for seed in a.seeds:
                    e=OpsDesk(seed);policy(e.tool)
                    if not e.ended:e.finish(reason='harness')
                    attacks.append({'attempt':name,**report(e)})
            (out/'exploits.json').write_text(json.dumps(attacks,indent=2)+'\n')
        manifest['exit_code']=0
    manifest['utc_finished']=datetime.now(timezone.utc).isoformat()
    manifest['source_unchanged']=manifest['source_sha256']==source_hashes()
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Evidence:',out)
    return manifest['exit_code']

if __name__=='__main__':
    raise SystemExit(main())
