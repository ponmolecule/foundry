"""Exercise the same fetch-main and merge flow shown in the user's deployment log."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

with tempfile.TemporaryDirectory(prefix='foundry-deploy-test-') as folder:
    temp=Path(folder)
    with zipfile.ZipFile(sys.argv[1]) as archive:
        archive.extractall(temp/'release')
    delivery=temp/'release'/'delivery'
    manifest=json.loads((delivery/'RELEASE.json').read_text())
    bundle=delivery/'foundry-full.bundle'
    deploy=temp/'deploy';deploy.mkdir()
    def git(*args):
        return subprocess.check_output(['git',*map(str,args)],cwd=deploy,text=True,stderr=subprocess.DEVNULL).strip()
    git('init','--quiet')
    git('fetch',bundle,'refs/tags/r198-rollback')
    git('checkout','-b','main','FETCH_HEAD')
    baseline_tree=git('rev-parse','HEAD^{tree}')
    git('fetch',bundle,'main')
    git('merge','--ff-only','FETCH_HEAD')
    assert git('rev-parse','HEAD')==manifest['commit']
    assert (deploy/'BUILD_STAMP').read_text().strip()==manifest['build_stamp']
    print('PASS main import updates r198 to '+manifest['commit'][:7])
    nested=list((temp/'release'/'rollback').glob('*.zip'))
    assert len(nested)==1
    with zipfile.ZipFile(nested[0]) as archive:archive.extractall(temp/'rollback')
    git('fetch',temp/'rollback'/'delivery'/'foundry-full.bundle','main')
    git('merge','--ff-only','FETCH_HEAD')
    assert git('rev-parse','HEAD')==manifest['rollback_commit']
    assert git('rev-parse','HEAD^{tree}')==baseline_tree
    print('PASS same main import restores exact r198 tree with a forward rollback commit')
