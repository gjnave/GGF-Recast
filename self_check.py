from settings import readiness,settings
import sys
def main():
    checks=readiness()
    for name,ok in checks.items():print(('OK  ' if ok else 'MISS'),name)
    import torch,gradio,av
    print('PyTorch',torch.__version__,'Gradio',gradio.__version__,'PyAV',av.__version__)
    print('CUDA',torch.cuda.is_available())
    # Exercise the same imports as preparation, so incomplete bundles fail here.
    from worker import initialise
    initialise(); print('Inference worker imports successfully.')
    from app import build
    build();print('Interface builds successfully.')
    from media import ffmpeg_path
    print('FFmpeg',ffmpeg_path())
    return 0 if all(checks.values()) and torch.cuda.is_available() else 1
if __name__=='__main__':raise SystemExit(main())
