"""Settings controls for local model setup."""
from functools import partial
from queue import Queue
from threading import Thread
import gradio as gr
import model_setup as models
from branding import FLOYD_PROMO
from settings import APP

def snapshot():
    rows = models.inventory()
    ok = models.ready(rows)
    verified = all(state == 'Verified' for _,state in rows)
    title = ('🟢 Installed · SHA-256 verified' if verified else
             '🟢 Installed · files present' if ok else 'Model setup needed')
    return ok, '### '+title+'\n\n'+'\n'.join(f'- {state}: `{name}`' for name,state in rows)

def task(install, progress=gr.Progress()):
    events = Queue()
    def work():
        try:
            result = models.run(install, lambda n,m: events.put(('progress', (n,m))))
        except Exception as exc:
            result = f'Setup stopped: {exc}'
        events.put(('done',result))
    Thread(target=work, daemon=True).start()
    while True:
        kind,payload = events.get()
        if kind == 'done':
            ok, listing = snapshot()
            return payload, listing, gr.update(visible=not ok)
        n,message = payload
        progress(n, desc=message)

def setup_tab(tabs, remote=False):
    ok, listing = snapshot()
    with gr.Tab('Settings', id='settings'):
        if remote:
            gr.Markdown('Model setup is managed on the PC. Open Recast on the PC to install or verify model files.')
        with gr.Column(visible=not ok and not remote, elem_id='recast-setup-guide') as guide:
            if not remote:
                gr.Markdown('### First run with L/iZ')
                gr.Video(str(APP/'assets/liz-recast-setup.mp4'), label='L/iZ · model setup',
                         interactive=False, autoplay=False, height=225, buttons=[], elem_id='recast-setup-video')
                gr.Markdown('Click **Install / resume** below. Recast downloads any missing files and checks them. '
                            'When you see **Installed**, open **Create**. Next time, Recast opens there automatically.')
        gr.Markdown('### Recast model set\nQwen Image 2.1 prepares the cast frame. Viggle Remake / MiniMax H3 renders the video. '
                    f'Turbo and Normal share the same eight files ({sum(e["size"] for e in models.MANIFEST)/1e9:.1f} GB total).')
        status = gr.Markdown(listing,elem_id='model-inventory')
        if not remote:
            with gr.Accordion('Publisher model terms', open=False):
                gr.Markdown((APP/'MODEL-TERMS.txt').read_text(encoding='utf8'))
            with gr.Row():
                install = gr.Button('Install / resume', variant='primary', elem_id='recast-model-install')
                verify = gr.Button('Verify model files')
            log = gr.Textbox(label='Model setup progress', interactive=False)
            for button, action in ((install,True),(verify,False)):
                button.click(partial(task, action), outputs=[log,status,guide], show_progress_on=[log],
                             concurrency_id='model-setup', concurrency_limit=1, trigger_mode='once',
                             api_name='install_models' if action else 'verify_models')
        refresh = gr.Button('Refresh model status')
        gr.HTML(FLOYD_PROMO)
    def refresh_view():
        ok, listing = snapshot()
        return listing, gr.update(visible=not ok and not remote)
    refresh.click(refresh_view, outputs=[status,guide], queue=False)
    def start_view():
        listing, guide_update = refresh_view()
        return gr.update(selected='create' if models.ready() else 'settings'), listing, guide_update
    return start_view, [tabs,status,guide]
