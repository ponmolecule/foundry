"""Build the main-based delivery consumed by deploy_foundry_dynamic.ps1.

The deployment fetches `main`, so never publish a feature-only bundle.
The optional rollback uses a forward commit restoring the exact baseline tree.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *map(str, args)], cwd=cwd, text=True).strip()

def zip_delivery(path, bundle, stamp, manifest, nested=None):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(bundle, 'delivery/foundry-full.bundle')
        archive.writestr('delivery/BUILD_STAMP', stamp)
        archive.writestr('delivery/RELEASE.json', json.dumps(manifest, indent=2)+'\n')
        if nested:
            archive.write(nested, 'rollback/'+nested.name)
            archive.writestr('rollback/README.txt',
                'Only if reverting: extract the rollback ZIP in this folder to Downloads, '
                'then run deploy_foundry_dynamic.ps1. It advertises a NEW main commit '
                'restoring r198, so the same fast-forward deployment script can apply it. '
                'Do not extract it to Downloads until you want to roll back. '
                'Saved engagement data is not rolled back.\n')

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--rollback', help='Baseline tag to restore through a forward rollback commit')
    args=parser.parse_args()
    head=git('rev-parse','HEAD')
    if git('rev-parse','refs/heads/main') != head:
        raise SystemExit('Refusing delivery: main does not point to HEAD; deploy script imports main.')
    if git('diff','HEAD','--'):
        raise SystemExit('Refusing delivery: tracked files differ from committed HEAD.')
    args.out.mkdir(parents=True,exist_ok=True)
    date=dt.datetime.now(dt.timezone.utc).strftime('%m%d%Y_%H%M')
    filename=lambda sha:f'foundry-v2-delivery_GPT_{sha[:7]}_{date}.zip'
    with tempfile.TemporaryDirectory(prefix='foundry-delivery-') as folder:
        temp=Path(folder)
        nested=None
        baseline=None
        rollback_sha=None
        if args.rollback:
            baseline=git('rev-parse',args.rollback)
            tree=git('rev-parse',baseline+'^{tree}')
            rollback_sha=git('commit-tree',tree,'-p',head,'-m',f'Restore {args.rollback} through a fast-forward deployment rollback')
            git('update-ref',f'refs/tags/{head[:7]}-rollback-to-r198',rollback_sha)
            bare=temp/'rollback.git'
            git('init','--bare',bare)
            git('--git-dir',bare,'fetch','--quiet',ROOT,rollback_sha)
            git('--git-dir',bare,'update-ref','refs/heads/main',rollback_sha)
            rollback_bundle=temp/'rollback.bundle'
            git('--git-dir',bare,'bundle','create',rollback_bundle,'main')
            nested=temp/filename(rollback_sha)
            zip_delivery(nested,rollback_bundle,git('show',baseline+':BUILD_STAMP')+'\n',
                         {'branch':'main','commit':rollback_sha,'restores_commit':baseline,'kind':'rollback'})
        bundle=temp/'foundry-full.bundle'
        git('bundle','create',bundle,'--all')
        refs=git('bundle','list-heads',bundle).splitlines()
        assert f'{head} refs/heads/main' in refs, 'main missing or points to wrong release'
        output=args.out/filename(head)
        zip_delivery(output,bundle,(ROOT/'BUILD_STAMP').read_text(),
                     {'branch':'main','commit':head,'build_stamp':(ROOT/'BUILD_STAMP').read_text().strip(),
                      'kind':'release','rollback_commit':rollback_sha,'rollback_baseline':baseline},nested)
        print(output)
