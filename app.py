"""GGF Recast -- local multi-character video replacement."""
import os,sys
from functools import partial
os.environ.setdefault('GRADIO_ANALYTICS_ENABLED','False')
from pathlib import Path
import gradio as gr
import projects
import branding
from settings import settings
import model_setup
from model_ui import setup_tab

CSS=branding.CSS+'''
body {background:#0b1019;} .gradio-container{width:100%!important;min-width:0!important;max-width:1240px!important;margin:auto!important;box-sizing:border-box;}
.gradio-container .main{padding-inline:clamp(8px,3vw,32px)!important;min-width:0;}
#model-inventory code{white-space:normal;overflow-wrap:anywhere;}
#prepared-preview{max-width:760px;margin:auto;}
#prepared-preview img{object-fit:contain!important;}
#recast-setup-guide{background:#111c2f;border-radius:12px;padding:16px;}
#recast-setup-guide :is(h3,p,strong){color:#e8eef9!important;}
#recast-setup-video{width:100%;max-width:420px;}
#recast-model-install{background:#f5b942!important;color:#091425!important;}
'''

def describe(doc):
    states=' · '.join(f'{s["id"]}: {s["state"]}' for s in doc['shots'])
    return f'Project: {Path(doc["folder"]).name}\n{doc["width"]} × {doc["height"]} · {doc["frames"]/24:.2f}s · {len(doc["shots"])} shots\n{states}'

def create(video,start,duration,quality,window,request,*cast_values, project_root=None):
    try:
        cast=[]
        for i in range(0,len(cast_values),3):
            photo,source,description=cast_values[i:i+3]
            cast.append({'image':photo,'source':source,'description':description})
        doc=projects.new_project(video,cast,request,start,duration,int(quality),int(window),project_root=project_root)
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
        exports = doc.get('exports', [])
        output = next((file for file in reversed(exports) if Path(file).is_file()), None)
        status = describe(doc)
        if exports and output != exports[-1]:
            status += ('\nLatest export is missing. Showing the previous available video.' if output else
                       '\nSaved export missing. Click Generate video to make a new export.')
        return path,projects.gallery(doc),status,gr.update(choices=[s['id'] for s in doc['shots']],value=1),doc['shots'][0]['source_frame'],output,output
    except Exception as exc:raise gr.Error(str(exc))

def import_frame(folder,index,path):
    try:
        if projects.GPU_LOCK.locked():raise ValueError('Wait for the current job or cancel it before changing frames.')
        doc=projects.adopt_frame(folder,index,path);return projects.gallery(doc),describe(doc)
    except Exception as exc:return gr.skip(), error_status(exc)

def show_frame(folder,index):
    if not folder or not index:return None
    return projects.load(folder)['shots'][int(index)-1]['source_frame']

def cancel():projects.CANCEL.set();return 'Cancellation requested. Completed takes will remain in the project.'

def error_status(exc):
    message = exc.message if isinstance(exc, gr.Error) else str(exc)
    return f'Error: {message or type(exc).__name__}'

def prepare_current(folder, previous_form, seed, progress=gr.Progress(), *form, project_root=None):
    try:
        model_setup.require_models()
        seed = projects.job_seed(seed)
        if not folder or previous_form != list(form):
            progress(0, desc='Reading the selected video')
            folder = create(*form,project_root=project_root)[0]
        doc = projects.load(folder)
        if doc['cast']:
            doc = projects.paint_all(folder,seed,lambda e:progress(0,desc=e['message']),replace=True)
            message = f'Prepared frame ready for all sections. Seed {seed}.'
        else:
            message = 'Import one edited frame under Manual frame editing.'
        return (folder, projects.gallery(doc), message,
                gr.update(choices=[s['id'] for s in doc['shots']],value=1),
                doc['shots'][0]['source_frame'], list(form), None, None)
    except Exception as exc:
        skip = gr.skip()
        return skip, [], error_status(exc), skip, skip, None, None, None


def open_current(path, *form):
    try:
        return (*open_project(path), list(form))
    except Exception as exc:
        skip = gr.skip()
        return skip, skip, error_status(exc), skip, skip, skip, skip, skip


def generate(folder, previous_form, seed, progress=gr.Progress(), *form, project_root=None):
    # The preview belongs to these source, cast and trim settings. An opened
    # project is also reusable until the operator changes one of those inputs.
    skip = gr.skip()
    try:
        model_setup.require_models()
        seed = projects.job_seed(seed)
        if not folder or previous_form != list(form):
            progress(0, desc='Preparing frames automatically before video generation')
            folder, gallery, status, index, original = create(*form,project_root=project_root)
            yield folder, gallery, status, index, original, None, None, list(form)

        doc = projects.load(folder)
        if not projects.prepared_frame(doc):
            if not doc['cast']:
                raise ValueError('Add a replacement character or import one edited frame for the clip under Manual frame editing.')
            def report(event):
                progress(0, desc='Auto-preparing frames: ' + event['message'])
            doc = projects.paint_all(folder, seed, report)
            yield skip, projects.gallery(doc), 'Frames ready. Generating video.', skip, skip, skip, skip, skip
            if projects.CANCEL.is_set():
                raise InterruptedError('Cancelled. Prepared frames were saved.')

        else:
            yield skip, skip, f'Using prepared frames. Generating video with seed {int(seed)}.', skip, skip, skip, skip, skip

        def render_progress(event):
            progress((event.get('step', 0), event.get('total', 1)), desc=event['message'])
        doc, path = projects.render_all(folder, seed, render_progress)
        yield skip, skip, describe(doc) + f'\nVideo ready to download. Seed {seed}.', skip, skip, path, path, skip
    except Exception as exc:
        yield skip, skip, error_status(exc), skip, skip, skip, skip, skip


def create_tab(phone_root):
    gr.Markdown('Add a video and cast, then click **Generate video**. To review the replacement first, click **Prepare replacement frames**.\n\nPowered by Viggle Remake / MiniMax H3. Experimental preview; inspect results before using them.')
    folder=gr.State(None) if phone_root else gr.Textbox(label='Current project folder',interactive=False)
    with gr.Row():
        video=gr.Video(label='Source video',sources=['upload'])
        with gr.Column():
            start=gr.Number(label='Start time (seconds)',value=0,minimum=0)
            duration=gr.Number(label='Duration (seconds, up to 120)',value=5.167,minimum=.25,maximum=120)
            quality=gr.Radio([('Normal · 736p higher detail (experimental)','736'),('Turbo Mode · 480p faster','480')],value='480',label='Generation mode')
            window=gr.Dropdown([90,124,175,226,294],value=124,label='Frames per render window')
    request=gr.Textbox(label='Scene instructions',value=projects.DEFAULT_SCENE,lines=2)
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
    gr.Markdown('For a manual workflow, leave cast photos empty and import your own edited source frame under Manual frame editing below. Cast assignments are saved when you create the project.')
    create_button=gr.Button('Extract source frames only (for manual editing)',visible=False)
    seed=gr.Number(label='Seed',value=-1,precision=0,minimum=-1,maximum=2147483647,
                   info='-1 picks a new seed each time. Enter a fixed seed to repeat a result.')
    paint_button=gr.Button('Prepare replacement frame',variant='primary')
    prep_status=gr.Textbox(label='Preparation status',interactive=False,lines=1)
    gallery=gr.Gallery(label='Prepared cast frame',columns=1,height=420,object_fit='contain',elem_id='prepared-preview')
    render_button=gr.Button('Generate video',variant='primary')
    status=gr.Textbox(label='Generation status',lines=2,interactive=False)
    with gr.Accordion('Manual frame editing',open=False):
        index=gr.Dropdown([],label='Shot',value=None)
        original=gr.Image(label='Exact source frame to edit',type='filepath',interactive=False)
        manual=gr.Image(label='Import your edited version of this source frame',type='filepath')
        import_button=gr.Button('Use imported frame for selected shot')
        gr.Markdown('Import one edited frame to use as the cast reference for the whole clip.')
    result=gr.Video(label='Finished video',interactive=False)
    download=gr.File(label='Download MP4',interactive=False)
    if not phone_root:
        with gr.Accordion('Saved projects',open=False):
            saved=gr.Dropdown(projects.list_projects(),label='Project folder',allow_custom_value=True)
            refresh=gr.Button('Refresh list');open_button=gr.Button('Open project')
    stop=gr.Button('Cancel current job',variant='stop')
    outputs=[folder,gallery,status,index,original]
    create_button.click(partial(create,project_root=phone_root),[video,start,duration,quality,window,request,*fields],outputs,api_name="create")
    quality.change(lambda q:gr.update(choices=[90] if str(q)=='736' else [90,124,175,226,294],value=90 if str(q)=='736' else 124),quality,window)
    form = [video,start,duration,quality,window,request,*fields]
    previous_form = gr.State(None)
    job = dict(concurrency_id='gpu', concurrency_limit=1)
    paint_button.click(lambda: ([], 'Preparing replacement frame…'), outputs=[gallery,prep_status],
                       queue=False, show_progress='hidden', api_name=False).then(
        partial(prepare_current,project_root=phone_root),[folder,previous_form,seed,*form],
        [folder,gallery,prep_status,index,original,previous_form,result,download],
        api_name="prepare_current",show_progress_on=[prep_status],**job)
    render_button.click(partial(generate,project_root=phone_root),[folder,previous_form,seed,*form],[*outputs,result,download,previous_form],api_name="generate",show_progress_on=[status],**job)
    import_button.click(import_frame,[folder,index,manual],[gallery,prep_status])
    index.change(show_frame,[folder,index],[original])
    stop.click(cancel,outputs=status,queue=False)
    if not phone_root:
        refresh.click(lambda:gr.update(choices=projects.list_projects()),outputs=saved)
        open_button.click(open_current,[saved,*form],[*outputs,result,download,previous_form],show_progress_on=[status])

def build(phone_root=None, remote=False):
    with gr.Blocks(title='Viggle Recast · Get Going Fast') as demo:
        gr.HTML(branding.HEADER)
        with gr.Tabs(selected='create' if model_setup.ready() else 'settings') as tabs:
            with gr.Tab('Create',id='create'):
                create_tab(phone_root)
            start_view, outputs = setup_tab(tabs, remote=remote or bool(phone_root))
        demo.load(start_view, outputs=outputs, queue=False)
    return demo

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=7877);parser.add_argument('--no-browser',action='store_true');parser.add_argument('--self-check',action='store_true')
    parser.add_argument('--phone-address', help='PC LAN IPv4 address for same-Wi-Fi phone access')
    parser.add_argument('--phone-port', type=int, default=8877)
    parser.add_argument('--phone-link', action='store_true', help='Start a temporary HTTPS phone link')
    args=parser.parse_args()
    if args.self_check:
        from self_check import main
        raise SystemExit(main())
    import urllib.request,json,webbrowser
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/config',timeout=2) as response:running=json.load(response)
        if running.get('title') in {'GGF Recast', 'Viggle Recast · Get Going Fast'}:
            print(f'Viggle Recast is already running at http://127.0.0.1:{args.port}')
            if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{args.port}')
            raise SystemExit(0)
    except (OSError,ValueError):pass
    if args.phone_address or args.phone_link:
        password = os.environ.get('GGF_RECAST_PHONE_PASSWORD')
        phone_root = Path(settings()['projects']).resolve().parent / 'phone-projects' if not password else None
        phone_ui = build(phone_root, remote=True).queue(max_size=8)
        phone_ui.launch(server_name=args.phone_address or '127.0.0.1', server_port=args.phone_port,
                        auth=('recast', password) if password else None,
                        share=args.phone_link, prevent_thread_lock=True, css=CSS,
                        theme=gr.themes.Soft(primary_hue='teal'),
                        allowed_paths=[str(phone_root or settings()['projects'])],
                        blocked_paths=[settings()['projects'], str(Path(__file__).resolve().parent)] if phone_root else [], show_error=True)
    build().queue(max_size=8).launch(server_name='127.0.0.1',server_port=args.port,inbrowser=not args.no_browser,
        css=CSS,theme=gr.themes.Soft(primary_hue='teal'),allowed_paths=[settings()['projects']],show_error=True)
