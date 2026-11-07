"""GGF Recast -- local multi-character video replacement."""
import os,sys
os.environ.setdefault('GRADIO_ANALYTICS_ENABLED','False')
from pathlib import Path
import gradio as gr
import projects
from settings import settings,readiness

CSS='''
body {background:#0b1019;} .gradio-container{max-width:1240px!important;margin:auto!important;}
#brand{padding:20px 24px;border:1px solid #344052;border-radius:16px;background:linear-gradient(110deg,#172333,#132b2b);margin-bottom:16px;}
#brand h1{font-size:32px;margin-bottom:4px;color:#f3fbff!important;} #brand p{color:#b6d4cf;}
'''

def describe(doc):
    states=' · '.join(f'{s["id"]}: {s["state"]}' for s in doc['shots'])
    return f'Project: {Path(doc["folder"]).name}\n{doc["width"]} × {doc["height"]} · {doc["frames"]/24:.2f}s · {len(doc["shots"])} shots\n{states}'

def create(video,start,duration,quality,window,request,*cast_values):
    try:
        cast=[]
        for i in range(0,len(cast_values),3):
            photo,source,description=cast_values[i:i+3]
            cast.append({'image':photo,'source':source,'description':description})
        doc=projects.new_project(video,cast,request,start,duration,int(quality),int(window))
        return doc['folder'],projects.gallery(doc),describe(doc),gr.update(choices=[s['id'] for s in doc['shots']],value=1),doc['shots'][0]['source_frame']
    except Exception as exc:raise gr.Error(str(exc))

def paint(folder,seed,progress=gr.Progress()):
    try:
        doc=projects.paint_all(folder,seed,lambda e:progress(0,desc=e['message']))
        return projects.gallery(doc),describe(doc)+'\nReview every edited frame before rendering.'
    except Exception as exc:raise gr.Error(str(exc))

def render(folder,seed,progress=gr.Progress()):
    try:
        doc,path=projects.render_all(folder,seed,lambda e:progress((e.get('step',0),e.get('total',1)),desc=e['message']))
        return path,path,describe(doc)+'\nExport verified: frame count matches the selected range.',projects.gallery(doc)
    except Exception as exc:raise gr.Error(str(exc))

def open_project(path):
    try:
        doc=projects.load(path)
        output=doc['exports'][-1] if doc['exports'] else None
        return path,projects.gallery(doc),describe(doc),gr.update(choices=[s['id'] for s in doc['shots']],value=1),doc['shots'][0]['source_frame'],output,output
    except Exception as exc:raise gr.Error(str(exc))

def import_frame(folder,index,path):
    try:
        if projects.GPU_LOCK.locked():raise ValueError('Wait for the current job or cancel it before changing frames.')
        doc=projects.adopt_frame(folder,index,path);return projects.gallery(doc),describe(doc)
    except Exception as exc:raise gr.Error(str(exc))

def show_frame(folder,index):
    if not folder or not index:return None
    return projects.load(folder)['shots'][int(index)-1]['source_frame']

def cancel():projects.CANCEL.set();return 'Cancellation requested. Completed takes will remain in the project.'

def build():
    with gr.Blocks(title='GGF Recast') as demo:
        gr.HTML('<div id="brand"><h1>GGF Recast</h1><p>New characters. Original performance. Local video editing.</p></div>')
        gr.Markdown('**1. Add a video and cast → 2. Prepare and review frames → 3. Render and export**\n\nPowered by Viggle Remake / MiniMax H3. Experimental preview; inspect results before using them.')
        with gr.Accordion('Runtime status',open=False):
            gr.Markdown('\n'.join(f'- {"Ready" if ok else "Missing"}: {name}' for name,ok in readiness().items()))
            gr.Markdown('Inference runs locally after installation. Model terms and third-party notices are included with the app.')
        folder=gr.Textbox(label='Current project folder',interactive=False)
        with gr.Tabs():
            with gr.Tab('1 · Source & cast'):
                with gr.Row():
                    video=gr.Video(label='Source video',sources=['upload'])
                    with gr.Column():
                        start=gr.Number(label='Start time (seconds)',value=0,minimum=0)
                        duration=gr.Number(label='Duration (seconds, up to 120)',value=5.167,minimum=.25,maximum=120)
                        quality=gr.Radio([('Normal · 736p higher detail (experimental)','736'),('Turbo Mode · 480p faster','480')],value='736',label='Generation mode')
                        window=gr.Dropdown([90],value=90,label='Frames per render window')
                request=gr.Textbox(label='Scene instructions',placeholder='Keep the setting and choreography. Replace the two dancers with the selected cast.',lines=2)
                fields=[]
                with gr.Row():
                    for n in (1,2):
                        with gr.Column():
                            photo=gr.Image(type='filepath',label=f'Replacement character {n}',height=210)
                            who=gr.Textbox(label='Original person to replace',placeholder='The person on the left')
                            desc=gr.Textbox(label='Replacement appearance',placeholder='A silver robot wearing a blue jacket',lines=2)
                            fields.extend([photo,who,desc])
                with gr.Accordion('Characters 3 and 4',open=False):
                    with gr.Row():
                        for n in (3,4):
                            with gr.Column():
                                photo=gr.Image(type='filepath',label=f'Replacement character {n}',height=160)
                                who=gr.Textbox(label='Original person to replace')
                                desc=gr.Textbox(label='Replacement appearance',lines=2)
                                fields.extend([photo,who,desc])
                gr.Markdown('For a manual workflow, leave cast photos empty and import your own edited source frame in the Review tab. Cast assignments are saved when you create the project.')
                create_button=gr.Button('Create project & extract frames',variant='primary')
            with gr.Tab('2 · Review frames'):
                seed=gr.Number(label='Seed',value=42,precision=0,minimum=0,maximum=2147483647)
                paint_button=gr.Button('Prepare all missing replacement frames',variant='primary')
                gallery=gr.Gallery(label='Shot references · review each replacement',columns=2,height='auto',object_fit='contain')
                with gr.Row():
                    index=gr.Dropdown([],label='Shot',value=None)
                    original=gr.Image(label='Exact source frame to edit',type='filepath',interactive=False)
                    manual=gr.Image(label='Import your edited version of this source frame',type='filepath')
                import_button=gr.Button('Use imported frame for selected shot')
                gr.Markdown('Imported frames replace the active reference; earlier takes remain saved. The first version uses one reference per render window. Inspect faces, pose, framing and every person before rendering.')
            with gr.Tab('3 · Render & export'):
                gr.Markdown('Rendering uses the reviewed frames. Completed shots are reused when a job resumes. Short shots are padded for inference and trimmed back to their exact length. Long continuous shots are independent windows in this preview and can show seams.')
                render_button=gr.Button('Generate video',variant='primary')
                result=gr.Video(label='Finished video',interactive=False)
                download=gr.File(label='Download MP4',interactive=False)
            with gr.Tab('Saved projects'):
                saved=gr.Dropdown(projects.list_projects(),label='Project folder',allow_custom_value=True)
                refresh=gr.Button('Refresh list');open_button=gr.Button('Open project')
        status=gr.Textbox(label='Status',lines=4,interactive=False)
        stop=gr.Button('Cancel current job',variant='stop')
        outputs=[folder,gallery,status,index,original]
        create_button.click(create,[video,start,duration,quality,window,request,*fields],outputs)
        quality.change(lambda q:gr.update(choices=[90] if str(q)=='736' else [90,124,175,226,294],value=90 if str(q)=='736' else 124),quality,window)
        paint_button.click(paint,[folder,seed],[gallery,status],concurrency_id='gpu',concurrency_limit=1)
        render_button.click(render,[folder,seed],[result,download,status,gallery],concurrency_id='gpu',concurrency_limit=1)
        import_button.click(import_frame,[folder,index,manual],[gallery,status])
        index.change(show_frame,[folder,index],[original])
        stop.click(cancel,outputs=status,queue=False)
        refresh.click(lambda:gr.update(choices=projects.list_projects()),outputs=saved)
        open_button.click(open_project,saved,[*outputs,result,download])
    return demo

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=7877);parser.add_argument('--no-browser',action='store_true');parser.add_argument('--self-check',action='store_true')
    args=parser.parse_args()
    if args.self_check:
        from self_check import main
        raise SystemExit(main())
    import urllib.request,json,webbrowser
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/config',timeout=2) as response:running=json.load(response)
        if running.get('title')=='GGF Recast':
            print(f'GGF Recast is already running at http://127.0.0.1:{args.port}')
            if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{args.port}')
            raise SystemExit(0)
    except (OSError,ValueError):pass
    build().queue(max_size=8).launch(server_name='127.0.0.1',server_port=args.port,inbrowser=not args.no_browser,
        css=CSS,theme=gr.themes.Soft(primary_hue='teal'),allowed_paths=[settings()['projects']],show_error=True)
