"""GGF worker controller: progress events, cancellation, bounded jobs, clean exit."""
from pathlib import Path
import json, subprocess, threading, queue, time, os
from settings import APP, settings

class Worker:
    def __init__(self,kind):
        self.kind=kind; self.process=None; self.events=queue.Queue(); self.log=None
    def start(self,folder):
        cfg=settings(); folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
        self.log=(folder/f'{self.kind}-worker.log').open('a',encoding='utf-8')
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1')
        self.process=subprocess.Popen([cfg['python'],'-u',str(APP/'worker.py'),self.kind],cwd=APP,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,encoding='utf-8',
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),env=env)
        def reader():
            for line in self.process.stdout:
                try: self.events.put(json.loads(line))
                except ValueError: self.log.write(line); self.log.flush()
            self.events.put({'event':'closed'})
        threading.Thread(target=reader,daemon=True).start()
    def request(self,payload,folder,progress=lambda _:None,cancel=None,timeout=7200):
        if self.process is None:
            waiting=time.monotonic()
            while True:
                if cancel and cancel.is_set():raise InterruptedError('Cancelled while waiting for GPU.')
                try:
                    raw=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=10)
                    used,util=[int(x.strip()) for x in raw.splitlines()[0].split(',')]
                except (OSError,ValueError,subprocess.SubprocessError):break
                if used<6000 and util<70:break
                progress({'event':'progress','message':f'Waiting for the GPU: {used} MiB in use, {util}% utilization. Other applications are left running.'})
                if time.monotonic()-waiting>7200:raise TimeoutError('GPU remained busy for two hours. Retry when other GPU work finishes.')
                if cancel:cancel.wait(5)
                else:time.sleep(5)
            self.start(folder)
        self.process.stdin.write(json.dumps(payload)+'\n'); self.process.stdin.flush()
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if cancel and cancel.is_set(): self.stop(); raise InterruptedError('Cancelled. Completed files were preserved.')
            try: event=self.events.get(timeout=.25)
            except queue.Empty: continue
            if event.get('event')=='progress': progress(event); continue
            if event.get('event')=='ready': continue
            if event.get('event')=='result': return event
            if event.get('event')=='error': raise RuntimeError(event.get('message','Worker failed'))
            if event.get('event')=='closed': raise RuntimeError(f'{self.kind} worker exited; see its project log.')
        self.stop(); raise TimeoutError('Job exceeded its two-hour limit. Completed files were preserved.')
    def stop(self):
        p=self.process
        if p and p.poll() is None:
            try: p.stdin.write('{"command":"stop"}\n'); p.stdin.flush(); p.wait(timeout=3)
            except (OSError,subprocess.TimeoutExpired):
                p.terminate()
                try: p.wait(timeout=5)
                except subprocess.TimeoutExpired: p.kill(); p.wait(timeout=5)
        if self.log: self.log.close()
        self.process=None
