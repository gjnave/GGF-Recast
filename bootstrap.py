"""GGF installer support: explicit, pinned model downloads with hash verification."""
import argparse,hashlib,json,os,shutil,sys,urllib.request
from pathlib import Path
APP=Path(__file__).resolve().parent

def download_plan():
    entries=json.loads((APP/'model-manifest.json').read_text(encoding='utf8'))
    return [(e['repo'],e['revision'],e['name'],e['sub']) for e in entries]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--models-root',default=str(APP/'models'))
    parser.add_argument('--check',action='store_true');args=parser.parse_args()
    root=Path(args.models_root).resolve();root.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('HF_HOME',str(root/'.hf-cache'))
    from huggingface_hub import HfApi,hf_hub_download
    api=HfApi(); metadata={}; plan=[]
    for repo,revision,name,sub in download_plan():
        if (repo,revision) not in metadata:metadata[repo,revision]=api.model_info(repo,revision=revision,files_metadata=True)
        entry=next(x for x in metadata[repo,revision].siblings if x.rfilename==name)
        plan.append((repo,revision,name,sub,entry.size,entry.lfs.sha256 if entry.lfs else None))
    required=sum(size for _,_,name,sub,size,_ in plan if not (root/sub/name).is_file())
    if shutil.disk_usage(root).free < required+5*1024**3:raise RuntimeError(f'Need {required/1024**3+5:.1f} GiB free on {root.anchor}. Choose a drive with enough space.')
    if args.check:
        print('Pinned download manifest checked. Model bytes needed:',required);return 0
    verified=[]
    for i,(repo,revision,name,sub,size,sha) in enumerate(plan,1):
        target=root/sub/name
        print(f'[{i}/{len(plan)}] {name}',flush=True)
        if not target.exists():
            hf_hub_download(repo,filename=name,revision=revision,local_dir=root/sub)
        if target.stat().st_size!=size:raise RuntimeError(f'File size mismatch; existing file preserved: {target}')
        digest=hashlib.sha256()
        with target.open('rb') as stream:
            for chunk in iter(lambda:stream.read(16*1024*1024),b''):digest.update(chunk)
        if sha and digest.hexdigest()!=sha:raise RuntimeError(f'Hash mismatch; existing file preserved: {target}')
        verified.append({'file':str(target),'repo':repo,'revision':revision,'sha256':digest.hexdigest()})
        print('Verified.',flush=True)
    # The explicit image accelerator matches the six-step smoke-tested path.
    cfg={'python':sys.executable,'core':str(APP/'vendor/comfy_core'),'image_models':str(root/'image'),
         'image_loras':str(root/'loras'),'video_models':str(root/'video'),'projects':str(APP/'projects'),'reserve_vram':4}
    config=APP/'settings.local.json'
    if config.exists():
        import time
        shutil.copy2(config,APP/f'settings.backup-{time.time_ns()}.json')
    config.write_text(json.dumps(cfg,indent=2),encoding='utf-8')
    (APP/'model-verification.json').write_text(json.dumps(verified,indent=2),encoding='utf-8')
    print('Models verified. GGF Recast is ready.');return 0

if __name__=='__main__':raise SystemExit(main())
