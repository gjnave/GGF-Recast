"""GGF app-local image/video worker. JSON events on stdout, diagnostics on stderr."""
import sys, json, time, traceback, importlib.util
from pathlib import Path
from settings import APP, settings, IMAGE_FILES, VIDEO_FILES

PROTOCOL=sys.stdout
sys.stdout=sys.stderr

def event(kind,**data):
    PROTOCOL.write(json.dumps({'event':kind,**data})+'\n'); PROTOCOL.flush()

def progress(message,**data): event('progress',message=message,**data)

def initialise():
    cfg=settings(); core=Path(cfg['core'])
    sys.path.insert(0,str(core))
    sys.argv=[sys.argv[0],'--disable-auto-launch','--reserve-vram',str(cfg['reserve_vram'])]
    import torch, nodes, folder_paths
    if not torch.cuda.is_available(): raise RuntimeError('This build requires an NVIDIA CUDA GPU.')
    return cfg,torch,nodes,folder_paths

def load_rgb(path,torch):
    import numpy as np
    from PIL import Image,ImageOps
    with Image.open(path) as im:
        im=ImageOps.exif_transpose(im).convert('RGB')
        return torch.from_numpy(np.asarray(im,dtype=np.float32).copy()/255).unsqueeze(0)

class ImageEngine:
    def __init__(self,env): self.cfg,self.torch,self.nodes,self.paths=env; self.loaded=False
    def load(self):
        if self.loaded:return
        from comfy_extras.nodes_qwen import TextEncodeQwenImage21
        self.encoder=TextEncodeQwenImage21
        root=Path(self.cfg['image_models'])
        for kind in ['diffusion_models','text_encoders','vae']:
            self.paths.add_model_folder_path(kind,str(root/kind),is_default=True)
        self.paths.add_model_folder_path('loras',self.cfg['image_loras'],is_default=True)
        progress('Loading GGF image editor')
        self.model=self.nodes.UNETLoader().load_unet(Path(IMAGE_FILES['model']).name,'default')[0]
        self.clip=self.nodes.CLIPLoader().load_clip(Path(IMAGE_FILES['text']).name,'qwen_image','default')[0]
        self.vae=self.nodes.VAELoader().load_vae(Path(IMAGE_FILES['vae']).name)[0]
        turbo='Qwen-Image-2.1-viggle-turbo-v0.2.1-6step-lora-r256.safetensors'
        self.turbo=(Path(self.cfg['image_loras'])/turbo).is_file()
        if self.turbo:self.model=self.nodes.LoraLoader().load_lora(self.model,None,turbo,1.0,0.0)[0]
        self.loaded=True
    def plan(self,paths,cast):
        import comfy.utils
        plans=[]
        for index,entry in enumerate(cast,1):
            images=[]
            for path in (paths[0],paths[index]):
                rgb=load_rgb(path,self.torch)
                height,width=rgb.shape[1:3];scale=512/max(height,width)
                images.append(comfy.utils.common_upscale(rgb.movedim(-1,1),max(32,round(width*scale/32)*32),
                    max(32,round(height*scale/32)*32),'bilinear','disabled').movedim(1,-1))
            question=('Analyze these two images to plan a character replacement. Image 1 is the source scene. '
                f'The source subject to replace is: {entry["source"]}. If there is only one character, that is the source subject. '
                f'Image 2 is the identity reference. Select this character from it: {entry["description"]}. '
                'Return only a JSON object with four short string values: '
                '"source_identity": visual description identifying the original subject; '
                '"source_pose": its actual arm and leg positions, expression and orientation in IMAGE 1 (never image 2); '
                '"framing": the actual source camera crop, e.g. face close-up with no body visible, waist-up, or full body head-to-toe; '
                '"target_identity": selected reference character face, hair and clothing, with no reference pose or background. '
                'For a close-up, explicitly say the replacement face must fill the frame and no full body should appear. '
                'Ignore all printed captions. Keep each value under 45 words.')
            tokens=self.clip.tokenize(question,images=images)
            raw=self.clip.decode(self.clip.generate(tokens,do_sample=False,max_length=300,seed=42))
            try:
                plan=json.loads(raw[raw.index('{'):raw.rindex('}')+1])
                if any(not isinstance(plan.get(k),str) for k in ('source_identity','source_pose','framing','target_identity')):raise ValueError('Incomplete visual plan')
            except (ValueError,KeyError):
                raise RuntimeError('Could not identify the source and reference character. Use a clear reference or describe the selected person more specifically.')
            plans.append(plan)
        return plans
    def run(self,req):
        import numpy as np
        from PIL import Image
        self.load(); t=self.torch
        paths=[req['source_frame'],*req.get('references',[])]
        if not 1<=len(paths)<=9: raise ValueError('Use one source frame and up to eight cast references.')
        progress('Encoding source frame and cast references')
        with t.no_grad():
            plans=[];prompt=req['prompt']
            if req.get('cast'):
                from prompts import image_prompt
                progress('Inspecting source pose, camera crop and replacement identity')
                plans=self.plan(paths,req['cast'])
                prompt=image_prompt(req['cast'],plans)+' '+req.get('instructions','')
            pos,neg,latent=self.encoder.execute(self.clip,prompt,'',vae=self.vae,
                resolution=int(req.get('resolution',640)),images={f'image_{i+1}':load_rgb(p,t) for i,p in enumerate(paths)})
            progress('Painting replacement characters')
            if self.turbo:
                # Publisher's distilled flow schedule: six raw nodes, exponential
                # resolution shift, deterministic Euler and no CFG/negative branch.
                import comfy.samplers,comfy.sample,math
                samples=latent['samples']
                tokens=samples.shape[-2]*samples.shape[-1]
                shift=math.exp(.5+.4*(tokens-256)/(8192-256))
                raw=t.tensor([1,.9375,.875,.75,.5,.25],dtype=t.float64)
                sigmas=t.cat([shift*raw/(1+(shift-1)*raw),t.zeros(1,dtype=t.float64)]).float()
                guider=comfy.samplers.CFGGuider(self.model)
                guider.inner_set_conds({'positive':pos});guider.set_cfg(1.0)
                seed=int(req.get('seed',42))
                noise=comfy.sample.prepare_noise(samples,seed)
                latent={'samples':guider.sample(noise,samples,comfy.samplers.sampler_object('euler'),sigmas,seed=seed)}
            else:
                latent=self.nodes.KSampler().sample(self.model,int(req.get('seed',42)),30,
                    1.0,'euler','simple',pos,neg,latent,denoise=1.0)[0]
            pixels=self.nodes.VAEDecode().decode(self.vae,latent)[0][0].cpu().numpy()
        out=Path(req['output']); out.parent.mkdir(parents=True,exist_ok=True)
        if out.exists(): raise FileExistsError(out)
        with Image.open(paths[0]) as original: size=original.size
        im=Image.fromarray(np.rint(pixels.clip(0,1)*255).astype(np.uint8)).resize(size,Image.Resampling.LANCZOS)
        im.save(out)
        return {'output':str(out),'size':list(size),'references':len(paths)-1,'visual_plan':plans,'prompt':prompt,'editor_revision':2}

class VideoEngine:
    def __init__(self,env): self.cfg,self.torch,self.nodes,self.paths=env; self.loaded=False
    def load(self):
        if self.loaded:return
        root=Path(self.cfg['video_models'])
        mapping={'diffusion_models':root/'Viggle'/'int8','text_encoders':root/'Comfy-Org'/'text_encoders','vae':root/'Comfy-Org'/'vae'}
        for kind,path in mapping.items():self.paths.add_model_folder_path(kind,str(path),is_default=True)
        adapter=APP/'vendor'/'viggle_remake'/'nodes.py'
        spec=importlib.util.spec_from_file_location('publisher_viggle_remake',adapter)
        self.remake=importlib.util.module_from_spec(spec); spec.loader.exec_module(self.remake)
        progress('Loading quantized video model')
        model=self.nodes.UNETLoader().load_unet(Path(VIDEO_FILES['model']).name,'default')[0]
        # Publisher's INT8 file already includes Swap: do not apply its LoRA again.
        self.model=self.remake.RemakeKeyframeUntil().run(model,.9)[0]
        self.clip=self.nodes.CLIPLoader().load_clip(Path(VIDEO_FILES['text']).name,'minimax','default')[0]
        self.vae=self.nodes.VAELoader().load_vae(Path(VIDEO_FILES['vae']).name)[0]
        # MiniMax VAE attention uses a registered normalization buffer directly.
        # Partial offload can strand that buffer on CPU during high-res decoding.
        # Keep this ~5 GB VAE resident when it runs; the larger models still offload.
        self.vae.disable_offload=True
        self.audio_vae=self.nodes.VAELoader().load_vae(Path(VIDEO_FILES['audio_vae']).name)[0]
        self.loaded=True
    def run(self,req):
        import numpy as np
        import comfy.samplers, comfy.model_management
        from media import read_frames,audio_samples,write_video
        nf=int(req['frames']); se=int(req.get('short_edge',480)); seed=int(req.get('seed',42))
        if nf<90 or nf>294 or (nf-5)%17: raise ValueError('Video length must be 17n+5 frames, from 90 to 294.')
        refs=req['references']; pins=req.get('pins',[])
        if not 1<=len(refs)<=4:raise ValueError('Provide one to four edited frames.')
        if len(pins)!=len(refs) or any(int(p)<0 or int(p)>=nf for p in pins):raise ValueError('Each edited frame needs a valid zero-based position.')
        self.load(); t=self.torch
        t.cuda.reset_peak_memory_stats()
        progress('Reading source motion and original audio')
        own=int(req.get('trim_frames',nf))
        frames=read_frames(req['source'],float(req.get('start',0)),own/24,int(req['width']),int(req['height']))
        if own<nf:frames=np.concatenate([frames,np.repeat(frames[-1:],nf-own,axis=0)])
        audio=audio_samples(req['source'],float(req.get('start',0)),own/24)
        kw={f'ref_{i+1}':load_rgb(p,t) for i,p in enumerate(refs)}
        with t.no_grad():
            progress('Encoding video, edited frames and soundtrack')
            positive,latent=self.remake.RemakeConditioning().run(self.clip,self.vae,self.audio_vae,
                t.from_numpy(frames.astype(np.float32)/255),req['prompt'],pins=','.join(map(str,pins)),
                frames=nf,short_edge=se,audio={'waveform':t.from_numpy(audio).unsqueeze(0),'sample_rate':32000},**kw)
            del frames,audio
            noise=self.remake.RemakeNoise().run(positive,seed)[0].generate_noise(latent)
            guider=comfy.samplers.CFGGuider(self.model)
            guider.inner_set_conds({'positive':positive}); guider.set_cfg(1.0)
            sampler=comfy.samplers.sampler_object('euler')
            sigmas=t.tensor([1.0,.990476,.965243,.923077,.8,.631579,0.0])
            def callback(step,x0,x,total):progress(f'Rendering step {step+1} of {total}',step=step+1,total=total)
            progress('Starting six-step video render')
            samples=guider.sample(noise,latent['samples'],sampler,sigmas,denoise_mask=latent['noise_mask'],callback=callback,seed=seed)
            progress('Decoding video')
            samples=samples.to('cpu')
            del noise,positive,latent,guider,kw
            comfy.model_management.unload_all_models()
            comfy.model_management.soft_empty_cache()
            pixels=self.nodes.VAEDecode().decode(self.vae,{'samples':samples})[0]
            result=np.rint(pixels[:int(req.get('trim_frames',nf))].cpu().numpy().clip(0,1)*255).astype(np.uint8)
        path=write_video(result,req['output'])
        t.cuda.synchronize()
        return {'output':path,'frames':len(result),'width':result.shape[2],'height':result.shape[1],
                'peak_allocated_gib':round(t.cuda.max_memory_allocated()/1024**3,3),
                'peak_reserved_gib':round(t.cuda.max_memory_reserved()/1024**3,3)}

def main():
    kind=sys.argv[1]
    try: env=initialise(); engine=ImageEngine(env) if kind=='image' else VideoEngine(env)
    except Exception as exc: traceback.print_exc(); event('error',message=str(exc)); return 1
    event('ready',worker_kind=kind)
    for line in sys.stdin:
        try:
            req=json.loads(line)
            if req.get('command')=='stop':return 0
            started=time.perf_counter(); answer=engine.run(req)
            event('result',seconds=round(time.perf_counter()-started,2),**answer)
        except Exception as exc: traceback.print_exc(); event('error',message=f'{type(exc).__name__}: {exc}')
    return 0

if __name__=='__main__':raise SystemExit(main())
