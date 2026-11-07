"""Restricted, temporary tester interface. No filesystem/project browsing endpoints."""
import os
from pathlib import Path
ROOT=Path(os.environ.get('GGF_RECAST_TEST_ROOT','D:/ggf-apps/ggf-recast-runtime/public-test'))
ROOT.mkdir(parents=True,exist_ok=True)
CACHE=ROOT/'cache';CACHE.mkdir(exist_ok=True)
EXPORTS=ROOT/'exports';EXPORTS.mkdir(exist_ok=True)
os.environ['GRADIO_TEMP_DIR']=str(CACHE)
os.environ['GRADIO_ANALYTICS_ENABLED']='False'
import json,shutil,uuid,logging,hashlib,threading
import gradio as gr
import projects
import branding
from settings import settings,APP
from media import probe,selection_bounds,prepare_clip,plan_windows,parse_timestamp

base=settings()
projects.settings=lambda:{**base,'projects':str(ROOT/'projects')}
logging.basicConfig(filename=str(ROOT/'server.log'),level=logging.INFO)
PREP_LOCK=threading.Lock()
CSS=branding.CSS+'''
.gradio-container {max-width:1100px!important;margin:auto!important;}
#frame-preview {width:min(760px,100%)!important;max-width:100%!important;margin:0 auto!important;height:auto!important;}
#frame-preview .image-container {height:auto!important;min-height:160px!important;}
#frame-preview img {max-height:560px!important;width:auto!important;max-width:100%!important;object-fit:contain!important;margin:auto!important;}
#clip-preview video, #finished-video video {max-height:480px!important;object-fit:contain!important;}
'''

def upload(path,extensions,limit_mb=80):
    if not path:raise ValueError('Upload the required video and replacement images.')
    p=Path(path).resolve()
    if not p.is_relative_to(CACHE.resolve()) or not p.is_file():raise ValueError('Use the upload controls to provide files.')
    if p.suffix.lower() not in extensions:raise ValueError('Unsupported file type.')
    if p.stat().st_size>limit_mb*1024*1024:raise ValueError(f'File exceeds the {limit_mb} MB upload limit.')
    return str(p)

def source_details(video):
    if not video:return '', '0:00', '0:05', None
    try:
        p=upload(video,{'.mp4','.mov','.webm','.mkv','.avi','.m4v'},2048)
        info=probe(p)
        return f'Source: {info["duration"]:.2f} seconds · {info["width"]} × {info["height"]} · {Path(p).stat().st_size/1024**2:.1f} MB. Choose the part to process below.','0',str(min(5,round(info['duration'],3))),None
    except Exception as exc:return 'Error: '+failure(exc).message, gr.skip(), gr.skip(), gr.skip()

def selected_clip(video,start,end,quality):
    if shutil.disk_usage(ROOT).free<20*1024**3:raise ValueError('The test server is full. Please try later.')
    video=upload(video,{'.mp4','.mov','.webm','.mkv','.avi','.m4v'},2048)
    info=probe(video);start,end=selection_bounds(start,end,info['duration'])
    edge=int(quality)
    if edge not in (480,736):raise ValueError('Choose 480p or 736p.')
    p=Path(video);key=hashlib.sha256(f'{p.resolve()}|{p.stat().st_mtime_ns}|{p.stat().st_size}|{start}|{end}|{edge}'.encode()).hexdigest()
    folder=CACHE/'selected';folder.mkdir(exist_ok=True)
    record=folder/(key+'.json')
    with PREP_LOCK:
        if record.is_file():
            saved=json.loads(record.read_text())
            if Path(saved['path']).is_file():return saved['path'],saved['selection']
        path,selection=prepare_clip(video,start,end,edge,folder/(uuid.uuid4().hex+'.mp4'))
        record.write_text(json.dumps({'path':path,'selection':selection}))
    return path,selection

def selection_summary(selection,quality):
    length=selection['end']-selection['start'];info=selection['prepared']
    count=len(plan_windows(round(length*24),90 if int(quality)==736 else 124))
    return f'Selected {selection["start"]:.2f}s–{selection["end"]:.2f}s ({length:.2f}s). Prepared {info["width"]} × {info["height"]} at 24 fps; {count} render section(s), before additional scene cuts.'

def preview_selection(video,start,end,quality,progress=gr.Progress()):
    try:
        progress(0,desc='FFmpeg: trimming and resizing the selected range')
        path,selection=selected_clip(video,start,end,quality)
        return path,selection_summary(selection,quality)
    except Exception as exc:return gr.skip(), 'Error: '+failure(exc).message

def current(folder):
    if not folder:raise ValueError('Prepare your replacement frames first.')
    p=Path(folder).resolve()
    if p.parent!=(ROOT/'projects').resolve():raise ValueError('Invalid session project.')
    return str(p)

def publish(path):
    p=Path(path)
    if p.suffix.lower() not in {'.png','.mp4'}:raise ValueError('Unsupported export.')
    target=EXPORTS/(uuid.uuid4().hex+p.suffix.lower())
    shutil.copy2(p,target)
    return str(target)

def failure(exc):
    tag=uuid.uuid4().hex[:8]
    logging.exception('Tester error %s',tag)
    if isinstance(exc,ValueError):return gr.Error(str(exc))
    return gr.Error(f'This job could not finish (reference {tag}). Try a shorter, simpler clip or report this reference.')

def prepare(video,first,left,first_identity,second,right,second_identity,instructions,start,end,quality,progress=gr.Progress()):
    try:
        if shutil.disk_usage(ROOT).free<20*1024**3:raise ValueError('The test server is full. Please try later.')
        if any(len(str(x or ''))>1000 for x in (left,right,first_identity,second_identity,instructions)):raise ValueError('Keep descriptions under 1,000 characters.')
        cast=[]
        for photo,who,identity in ((first,left,first_identity),(second,right,second_identity)):
            if photo:
                cast.append({'image':upload(photo,{'.png','.jpg','.jpeg','.webp'}),'source':who or 'The person on the left',
                             'description':identity.strip() if identity and identity.strip() else 'The main character in the replacement reference image'})
        if not cast:raise ValueError('Add at least one replacement character image.')
        progress(0,desc='FFmpeg: trimming and resizing only the selected range')
        video,selection=selected_clip(video,start,end,quality)
        doc=projects.new_project(video,cast,instructions,0,selection['prepared']['duration'],int(quality),90 if int(quality)==736 else 124,prepared=True)
        doc['input_selection']=selection;projects.save(doc)
        progress(0,desc='Preparing your replacement frames. Jobs use one shared GPU.')
        seed=projects.job_seed()
        doc=projects.paint_all(doc['folder'],seed,lambda e:progress(0,desc=e['message']))
        gallery=[(publish(projects.prepared_frame(doc)), 'Cast frame for the whole clip')]
        return doc['folder'],gallery,gallery[0][0],selection_summary(selection,quality)+f'\nFrame ready. Seed {seed}. Check the cast, pose and framing before generating.',None,video
    except Exception as exc:return None, [], None, 'Error: '+failure(exc).message, None, gr.skip()

def render(folder,quality,start,end,progress=gr.Progress()):
    try:
        folder=current(folder)
        prepared=projects.load(folder)
        selection=prepared.get('input_selection',{})
        if int(quality)!=prepared['short_edge'] or abs(parse_timestamp(start)-selection.get('start',0))>1/24 or abs(parse_timestamp(end)-selection.get('end',prepared['frames']/24))>1/24:
            raise ValueError('The mode or timestamps changed. Prepare replacement frames for the new selection before generating.')
        seed=projects.job_seed()
        doc,path=projects.render_all(folder,seed,lambda e:progress((e.get('step',0),e.get('total',1)),desc=e['message']))
        return publish(path),f'Finished. Seed {seed}. Download your result from the video player.'
    except Exception as exc:return gr.skip(), 'Error: '+failure(exc).message

def select_frame(folder,evt:gr.SelectData):
    try:
        doc=projects.load(current(folder));index=int(evt.index)
        if index<0 or index>=len(doc['shots']):raise ValueError('Choose an existing reference frame.')
        shot=doc['shots'][index]
        return publish(shot['edited_frames'][0])
    except Exception as exc:raise failure(exc)

def build(preview_fixture=None):
    with gr.Blocks(title='GGF Recast · Test Preview') as demo:
        gr.HTML(branding.HEADER)
        gr.Markdown('**Test preview v3 · Normal / Turbo · select up to 2 minutes**\n\nUpload a video, select your timestamps and add replacement characters. Preview the selected clip, prepare and review its frames, then generate. Longer selections take multiple render sections and can show seams between sections. Keep this page open while processing.')
        gr.Markdown('Uploads are processed and retained on the host computer for this test. Use non-sensitive material you have permission to share. Powered by Viggle Remake / MiniMax H3.')
        state=gr.State(None)
        video=gr.File(label='Source video · any length, up to 2 GB',type='filepath',file_types=['.mp4','.mov','.webm','.mkv','.avi','.m4v'])
        source_info=gr.Textbox(label='Source details',interactive=False)
        with gr.Row():
            start=gr.Textbox(label='Start timestamp',value='0:00',placeholder='Seconds, MM:SS or HH:MM:SS')
            end=gr.Textbox(label='End timestamp',value='0:05',placeholder='Seconds, MM:SS or HH:MM:SS')
        quality=gr.Radio([('Normal · 736p higher detail','736'),('Turbo Mode · 480p faster','480')],value='736',label='Generation mode')
        gr.Markdown('Only the selected range is processed. FFmpeg trims it, fits it to the working resolution and converts it to 24 fps before AI preparation. Choose up to 120 seconds; the source upload can be much longer. Normal generates at 736p; Turbo uses the existing 480p path. Both use the same INT8 model. Normal can take several minutes per section.')
        preview_button=gr.Button('Preview selected range')
        clip=gr.Video(label='Selected clip preview',interactive=False,elem_id='clip-preview')
        with gr.Accordion('Model precision and quality',open=False):
            gr.Markdown('**Current video model: Viggle Remake Swap, INT8 convrot. Text encoder: INT8.**\n\n736p increases native generation detail; it is not just an enlarged 480p export. Higher precision is not a guarantee of better character replacement. Upstream Q8 is similar to INT8, Q6/Q4 trade fidelity for memory, and BF16 needs substantially more resources. Those alternate weights are not installed or enabled in this tester.')
            gr.Markdown('Measured on this server: a six-second Normal test, split into two sections, took about 15½ minutes for video generation. Timing varies with the clip and available resources. Longer selections can show visible changes between sections.')
        with gr.Row():
            with gr.Column():
                first=gr.Image(label='Replacement character 1',type='filepath',sources=['upload'],height=220)
                left=gr.Textbox(label='Which character in the source video?',value='The person on the left',max_length=1000)
                first_identity=gr.Textbox(label='Which character in reference image 1?',placeholder='For a group photo: the short-haired woman in the gray jacket. For a portrait, leave blank.',max_length=1000)
            with gr.Column():
                second=gr.Image(label='Replacement character 2 (optional)',type='filepath',sources=['upload'],height=220)
                right=gr.Textbox(label='Which character in the source video?',value='The person on the right',max_length=1000)
                second_identity=gr.Textbox(label='Which character in reference image 2?',placeholder='Describe the replacement character if the reference contains several people.',max_length=1000)
        instructions=gr.Textbox(label='Scene instructions',value=projects.DEFAULT_SCENE,max_length=1000)
        prepare_button=gr.Button('1 · Prepare / regenerate replacement frames',variant='primary')
        reference=gr.Image(value=preview_fixture,label='Prepared frame · full image fitted to view',type='filepath',interactive=False,height=None,width=760,elem_id='frame-preview')
        gallery=gr.Gallery(label='Choose a section to review',columns=6,height=150,object_fit='contain',allow_preview=False)
        render_button=gr.Button('Generate video',variant='primary')
        result=gr.Video(label='Finished video',interactive=False,elem_id='finished-video')
        status=gr.Textbox(label='Status',interactive=False)
        video.change(source_details,video,[source_info,start,end,clip])
        preview_button.click(preview_selection,[video,start,end,quality],[clip,status])
        prepare_button.click(lambda:([],None,'Preparing replacement frame…'), outputs=[gallery,reference,status],
                             queue=False,show_progress='hidden',api_name=False).then(
            prepare,[video,first,left,first_identity,second,right,second_identity,instructions,start,end,quality],
            [state,gallery,reference,status,result,clip],concurrency_id='gpu',concurrency_limit=1,show_progress_on=[status])
        gallery.select(select_frame,state,reference)
        render_button.click(render,[state,quality,start,end],[result,status],concurrency_id='gpu',concurrency_limit=1,show_progress_on=[status])
        # A prepared frame belongs to exactly the input selection that made it.
        # Changing source/cast/mode cannot accidentally render the previous project.
        for component in [video,first,left,first_identity,second,right,second_identity,instructions,start,end,quality]:
            component.change(lambda:(None,[],None,None),outputs=[state,gallery,reference,result],queue=False)
    return demo

if __name__=='__main__':
    # A maintenance restart may reuse an already-running tunnel to keep the URL.
    reuse=os.environ.get('GGF_RECAST_REUSE_SHARE')
    demo=build().queue(max_size=4,default_concurrency_limit=1)
    demo.launch(server_name='127.0.0.1',server_port=7878,share=not bool(reuse),inbrowser=False,
                allowed_paths=[str(EXPORTS)],blocked_paths=[str(APP),str(ROOT/'projects'),str(ROOT/'server.log'),base['projects'],base['image_models'],base['video_models']],
                max_file_size='2gb',show_error=False,theme=gr.themes.Soft(primary_hue='teal'),css=CSS,prevent_thread_lock=True)
    (ROOT/'share.json').write_text(json.dumps({'url':reuse or demo.share_url,'port':7878,'pid':os.getpid()},indent=2))
    demo.block_thread()
