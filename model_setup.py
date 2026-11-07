"""Pinned model inventory and local, resumable setup for Recast Settings."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from filelock import FileLock, Timeout
from settings import APP, settings

MANIFEST = json.loads((APP / 'model-manifest.json').read_text(encoding='utf8'))
REPORT = APP / 'model-checks.local.json'
GIB = 1024 ** 3

def locations():
    cfg = settings()
    for entry in MANIFEST:
        group, _, sub = entry['sub'].partition('/')
        folder = Path(cfg[{'image':'image_models', 'loras':'image_loras', 'video':'video_models'}[group]]) / sub
        yield entry, folder, folder / entry['name']

def records():
    try:
        return json.loads(REPORT.read_text(encoding='utf8'))
    except (OSError, ValueError):
        return {}

def inventory():
    checked = records()
    rows = []
    for entry, _, path in locations():
        try:
            st = path.stat()
            if not path.is_file() or st.st_size != entry['size']:
                state = 'Wrong size'
            else:
                old = checked.get(str(path), {})
                if old.get('mtime_ns') == st.st_mtime_ns and old.get('expected') == entry['sha256']:
                    state = 'Verified' if old['valid'] else 'Hash mismatch'
                else:
                    state = 'Present'
        except FileNotFoundError:
            state = 'Missing'
        rows.append((path.name, state))
    return rows

def ready(rows=None):
    return all(state in ('Verified','Present') for _, state in (inventory() if rows is None else rows))

def require_models():
    if not ready():
        raise ValueError('Model setup is incomplete. Open Settings on the PC to install or verify the Recast models.')

def fetch(entry, folder, report):
    from huggingface_hub import hf_hub_download
    from tqdm.auto import tqdm
    class ProgressBar(tqdm):
        def __init__(self, *args, **kwargs):
            self.primary = 'downloading bytes' not in kwargs.get('desc','')
            super().__init__(*args, **kwargs)
        def display(self, *args, **kwargs):
            if self.primary:
                report(min(self.n,entry['size']))
    hf_hub_download(entry['repo'], filename=entry['name'], revision=entry['revision'],
                    local_dir=folder, tqdm_class=ProgressBar)

def run(install, update, fetch_file=None):
    """update receives per-file fraction and real byte counts. Verify never uses the network."""
    try:
        with FileLock(str(REPORT.with_suffix('.lock')), timeout=0):
            return _run(install, update, fetch_file or fetch)
    except Timeout:
        raise RuntimeError('Another Recast model setup is running. Wait for it, then refresh status.') from None

def _run(install, update, fetch_file):
    items = list(locations())
    checked = records()
    if install:
        volumes = {}
        for entry, folder, path in items:
            if not path.exists():
                folder.mkdir(parents=True, exist_ok=True)
                free_root, amount = volumes.get(folder.stat().st_dev, (folder, 0))
                volumes[folder.stat().st_dev] = (free_root, amount + entry['size'])
        for folder, amount in volumes.values():
            if shutil.disk_usage(folder).free < amount + GIB:
                raise RuntimeError(f'Need at least {amount/GIB+1:.1f} GiB free on {folder.anchor} to finish the download.')
    missing = []
    for i,(entry, folder, path) in enumerate(items,1):
        size = entry['size']
        def counter(stage):
            last = 0
            def report(n):
                nonlocal last
                now = time.monotonic()
                if n not in (0,size) and now-last < 0.3:
                    return
                last = now
                update(n/size, f'{i}/{len(items)} · {stage} {path.name} · {n/GIB:.2f} / {size/GIB:.2f} GiB')
            return report
        if not path.exists():
            if not install:
                missing.append(path.name)
                continue
            downloaded = counter('Downloading')
            downloaded(0)
            fetch_file(entry, folder, downloaded)
        stat = path.stat()
        if stat.st_size != size:
            raise RuntimeError(f'Wrong size: {path}. File preserved. Move it aside and click Install / resume.')
        old = checked.get(str(path), {})
        if install and old.get('valid') and old.get('expected') == entry['sha256'] and old.get('mtime_ns') == stat.st_mtime_ns:
            update(1.0, f'{i}/{len(items)} - Already verified: {path.name}')
            continue
        digest = hashlib.sha256()
        verified = counter('Verifying')
        verified(0)
        n = 0
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(16*1024*1024), b''):
                digest.update(chunk)
                n += len(chunk)
                verified(n)
        if path.stat().st_mtime_ns != stat.st_mtime_ns:
            raise RuntimeError(f'{path.name} changed during verification. Retry when the download is finished.')
        valid = digest.hexdigest() == entry['sha256']
        checked[str(path)] = dict(mtime_ns=stat.st_mtime_ns, expected=entry['sha256'], valid=valid)
        tmp = REPORT.with_suffix('.tmp')
        tmp.write_text(json.dumps(checked, indent=2), encoding='utf8')
        os.replace(tmp, REPORT)
        if not valid:
            raise RuntimeError(f'SHA-256 mismatch: {path}. File preserved. Move it aside and click Install / resume.')
    if missing:
        return f'{len(missing)} file(s) missing. Click Install / resume to download them.'
    return 'Installed. All model files passed SHA-256 verification. Open Create to make a video.'
