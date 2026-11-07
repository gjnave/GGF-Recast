"""GGF installer support: explicit, pinned model downloads with hash verification."""
import argparse,hashlib,json,os,shutil,sys,urllib.request
from pathlib import Path
APP=Path(__file__).resolve().parent

def download_plan():
    vg='21665fa7a1e038e0a5312fb15f37b18d0f06f117'
    h3='54472221d27c695fca9621b0c3ed52f06c4af707'
    return [
      ('Viggle/Viggle-Remake',vg,'int8/viggle_remake_swap_pruned_int8_convrot.safetensors','video/Viggle'),
      ('Comfy-Org/MiniMax-H3',h3,'text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors','video/Comfy-Org'),
      ('Comfy-Org/MiniMax-H3',h3,'vae/minimax_h3_video_vae_fp16.safetensors','video/Comfy-Org'),
      ('Comfy-Org/MiniMax-H3',h3,'vae/minimax_h3_audio_vae_fp32.safetensors','video/Comfy-Org'),
      ('Comfy-Org/Qwen-Image-2.1','eee52e917df0f00d910bc1f04f8a4d825dcef255','diffusion_models/qwen_image_2.1_int8_convrot.safetensors','image'),
      ('Comfy-Org/Qwen3-VL','056c1bacea04322faeab9d7c9edb8c3f24460023','text_encoders/qwen3vl_8b_int8_convrot.safetensors','image'),
      ('Comfy-Org/Qwen-Image-2.1','eee52e917df0f00d910bc1f04f8a4d825dcef255','vae/qwen_image_2.1_vae_bf16.safetensors','image'),
      ('Viggle/Qwen-Image-2.1-viggle-turbo','bb26a0f38e5fe6c124aaccc9187a87eed5d9ed13','Qwen-Image-2.1-viggle-turbo-v0.2.1-6step-lora-r256.safetensors','loras'),
    ]

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
