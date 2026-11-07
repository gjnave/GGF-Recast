"""Original GGF project and render orchestration. Every media take is preserved."""
import json, uuid, shutil, threading, time, subprocess
from datetime import datetime
from pathlib import Path
from PIL import Image,ImageOps
import numpy as np
from settings import settings
from media import probe,canvas,read_frames,plan_windows,write_video,mux_audio,ffmpeg_path,frame_count,prepare_clip
from prompts import image_prompt,video_prompt
from runtime import Worker

GPU_LOCK=threading.Lock()
CANCEL=threading.Event()

def save(doc):
    folder=Path(doc['folder'])
    text=json.dumps(doc,indent=2)
    # Keep a revision, then update the small current project document.
    revisions=folder/'history'; revisions.mkdir(exist_ok=True)
    (revisions/f'{time.time_ns()}.json').write_text(text,encoding='utf-8')
    (folder/'project.json').write_text(text,encoding='utf-8')

def load(folder):
    if not folder:raise ValueError('Create or open a project first.')
    p=Path(folder).resolve()
    if not (p/'project.json').is_file():raise ValueError('Choose a GGF Recast project folder.')
    doc=json.loads((p/'project.json').read_text(encoding='utf-8'))
    if doc.get('format')!='ggf-recast-1':raise ValueError('Unsupported project format.')
    return doc

def new_project(source,cast,request,start=0,duration=5.167,short_edge=480,window=124,prepared=False):
    if not source or not Path(source).is_file():raise ValueError('Upload a source video.')
    info=probe(source); start=float(start); duration=float(duration)
    if start<0 or start>=info['duration']:raise ValueError('Start time is outside the video.')
    if not 0<duration<=120:raise ValueError('Choose a duration from 0 to 120 seconds.')
    duration=min(duration,info['duration']-start)
    if duration<.25:raise ValueError('The selected range is too short.')
    if short_edge not in (480,736):raise ValueError('Choose 480p or 736p.')
    width,height=canvas(info['width'],info['height'],short_edge)
    if max(width,height)>1600:raise ValueError('Use a source aspect ratio no wider than about 2:1.')
    name=datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    folder=Path(settings()['projects'])/name; folder.mkdir(parents=True)
    source_copy=folder/('source'+Path(source).suffix.lower()) if prepared else folder/'source.mp4'
    selection=None
    if prepared:shutil.copy2(source,source_copy)
    else:
        _,selection=prepare_clip(source,start,start+duration,short_edge,source_copy)
        start=0
    checked=[]
    for i,item in enumerate(cast):
        if not item.get('image'):continue
        if not item.get('source','').strip() or not item.get('description','').strip():raise ValueError('Every cast photo needs an original-person label and a replacement description.')
        with Image.open(item['image']) as im:
            im=ImageOps.exif_transpose(im).convert('RGB'); im.thumbnail((1536,1536))
            target=folder/f'cast-{i+1}.png'; im.save(target)
        checked.append({**item,'image':str(target)})
    total=max(1,round(duration*24))
    shots=plan_windows(total,int(window))
    # Split on large full-frame changes, then apply our independent duration budget.
    thumbs=read_frames(source_copy,start,total/24,160,96)
    diffs=np.mean(np.abs(np.diff(thumbs.astype(np.float32),axis=0)),axis=(1,2,3))
    cuts=[]
    for i,value in enumerate(diffs,1):
        if value>45 and (not cuts or i-cuts[-1]>=12) and 6<i<total-6:cuts.append(i)
    if cuts:
        shots=[]
        for begin,end in zip([0,*cuts],[*cuts,total]):
            for piece in plan_windows(end-begin,int(window)):
                shots.append({**piece,'start':piece['start']+begin})
    del thumbs
    doc={'format':'ggf-recast-1','folder':str(folder),'source':str(source_copy),'source_info':info,
         'start_seconds':start,'frames':total,'width':width,'height':height,'short_edge':short_edge,
         'cast':checked,'request':request or 'Use the replacement appearances in the edited frames.',
         'detected_cuts':cuts,'shots':[],'exports':[]}
    if selection:doc['input_selection']=selection
    for i,shot in enumerate(shots):
        pin=min(shot['count']-1,max(0,shot['count']//2))
        pic=read_frames(source_copy,start+(shot['start']+pin)/24,1/24,width,height)[0]
        frame=folder/f'shot-{i+1:03d}-source.png'; Image.fromarray(pic).save(frame)
        doc['shots'].append({**shot,'id':i+1,'pin':pin,'source_frame':str(frame),
            'edited_frames':[],'image_takes':[],'video_takes':[],'state':'needs_frame'})
    save(doc);return doc

def gallery(doc):
    return [(s['edited_frames'][0] if s['edited_frames'] else s['source_frame'],
             f'Shot {s["id"]} · {s["count"]/24:.2f}s · {s["state"]}') for s in doc['shots']]

def adopt_frame(folder,index,path):
    doc=load(folder); shot=doc['shots'][int(index)-1]
    if not path:raise ValueError('Upload an edited reference frame.')
    target=Path(folder)/f'shot-{shot["id"]:03d}-manual-{uuid.uuid4().hex[:8]}.png'
    with Image.open(path) as im:
        ImageOps.exif_transpose(im).convert('RGB').resize((doc['width'],doc['height']),Image.Resampling.LANCZOS).save(target)
    shot['image_takes'].append(str(target));shot['edited_frames']=[str(target)];shot['state']='frame_ready'
    shot.pop('selected_video',None);save(doc);return doc

def paint_all(folder,seed,progress):
    if not GPU_LOCK.acquire(blocking=False):raise RuntimeError('Another GPU job is running.')
    CANCEL.clear(); worker=Worker('image')
    try:
        doc=load(folder)
        if not doc['cast']:raise ValueError('This project has no cast references. Import an edited frame for each shot instead.')
        for s in doc['shots']:
            if s['edited_frames']:continue
            output=Path(folder)/f'shot-{s["id"]:03d}-paint-{uuid.uuid4().hex[:8]}.png'
            progress({'message':f'Preparing shot {s["id"]} / {len(doc["shots"])}'})
            try:
                result=worker.request({'source_frame':s['source_frame'],'references':[x['image'] for x in doc['cast']],
                    'prompt':image_prompt(doc['cast'])+' '+doc['request'],'cast':doc['cast'],'instructions':doc['request'],'seed':int(seed)+s['id'],
                    'resolution':1024,'output':str(output)},folder,progress,CANCEL)
                s['image_takes'].append(result['output']);s['edited_frames']=[result['output']];s['state']='frame_ready';s['image_metrics']=result
            except Exception as exc:s['state']='paint_failed';s['error']=str(exc);save(doc);raise
            save(doc)
        return doc
    finally:worker.stop();GPU_LOCK.release()

def render_all(folder,seed,progress):
    if not GPU_LOCK.acquire(blocking=False):raise RuntimeError('Another GPU job is running.')
    CANCEL.clear(); worker=Worker('video')
    try:
        doc=load(folder)
        missing=[s['id'] for s in doc['shots'] if not s['edited_frames']]
        if missing:raise ValueError(f'Prepare or import edited frames for shots {missing} first.')
        for s in doc['shots']:
            if s.get('selected_video') and Path(s['selected_video']).is_file():continue
            output=Path(folder)/f'shot-{s["id"]:03d}-render-{uuid.uuid4().hex[:8]}.mp4'
            progress({'message':f'Rendering shot {s["id"]} / {len(doc["shots"])}'})
            s['state']='rendering';save(doc)
            def section_progress(event):
                progress({**event,'message':f'Section {s["id"]} / {len(doc["shots"])} · {event["message"]}'})
            try:
                result=worker.request({'source':doc['source'],'start':doc['start_seconds']+s['start']/24,
                    'frames':s['render_frames'],'trim_frames':s['count'],'width':doc['width'],'height':doc['height'],
                    'short_edge':doc['short_edge'],'references':s['edited_frames'],'pins':[s['pin']],
                    'prompt':video_prompt(doc['cast'],doc['request']),'seed':int(seed)+s['id'],'output':str(output)},folder,section_progress,CANCEL)
                actual=frame_count(output)
                if actual!=s['count']:raise RuntimeError(f'Render returned {actual} frames; expected {s["count"]}.')
                s['video_takes'].append(result);s['selected_video']=str(output);s['state']='rendered';s.pop('error',None)
            except Exception as exc:s['state']='render_failed';s['error']=str(exc);save(doc);raise
            save(doc)
        worker.stop();progress({'message':'Assembling shots and restoring source audio'})
        token=uuid.uuid4().hex[:8];concat=Path(folder)/f'concat-{token}.txt'
        lines=[]
        for s in doc['shots']:
            path=Path(s['selected_video']).as_posix().replace("'","'\\''")
            lines.append("file '"+path+"'")
        concat.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        silent=Path(folder)/f'assembled-{token}-silent.mp4'
        subprocess.run([ffmpeg_path(),'-nostdin','-v','error','-n','-f','concat','-safe','0','-i',str(concat),
            '-c','copy',str(silent)],check=True,capture_output=True,timeout=180)
        final=Path(folder)/f'GGF-Recast-{token}.mp4'
        mux_audio(silent,doc['source'],doc['start_seconds'],doc['frames']/24,final)
        if frame_count(final)!=doc['frames']:raise RuntimeError('Export frame-count check failed.')
        doc['exports'].append(str(final));save(doc)
        return doc,str(final)
    finally:worker.stop();GPU_LOCK.release()

def list_projects():
    root=Path(settings()['projects'])
    return sorted([str(p.parent) for p in root.glob('*/project.json')],reverse=True) if root.is_dir() else []
