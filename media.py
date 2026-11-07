"""GGF media preparation with exact 24 fps project timing and original audio."""
from fractions import Fraction
from pathlib import Path
import math, subprocess, shutil
import av
import numpy as np
from PIL import Image

FPS=24

def probe(path):
    with av.open(str(path)) as c:
        if not c.streams.video: raise ValueError('This file has no video track.')
        v=c.streams.video[0]
        duration=float(v.duration*v.time_base) if v.duration else float(c.duration or 0)/av.time_base
        return {'width':v.width,'height':v.height,'fps':float(v.average_rate or 24),
                'duration':duration,'audio':bool(c.streams.audio)}

def canvas(width,height,short_edge):
    if width<=0 or height<=0: raise ValueError('Invalid source dimensions.')
    ratio=short_edge/min(width,height)
    return max(32,round(width*ratio/32)*32),max(32,round(height*ratio/32)*32)

def read_frames(path,start,seconds,width,height):
    """Sample by presentation timestamps; duplicate/drop frames to a 24 fps clock."""
    count=max(1,round(seconds*FPS))
    result=[]
    with av.open(str(path)) as c:
        stream=c.streams.video[0]
        stream.thread_type='AUTO'
        origin=float(stream.start_time*stream.time_base) if stream.start_time else 0.0
        c.seek(max(0,int((start+origin)*av.time_base)),backward=True)
        last=None
        for frame in c.decode(stream):
            if frame.time is None: continue
            t=float(frame.time)-origin
            if t+1/FPS < start: continue
            arr=frame.reformat(width=width,height=height,format='rgb24').to_ndarray()
            if last is None: last=arr
            while len(result)<count and start+len(result)/FPS < t-0.5/FPS:
                result.append(last)
            if len(result)<count and t >= start+len(result)/FPS-0.5/FPS:
                result.append(arr)
            last=arr
            if len(result)>=count: break
        if last is None: raise ValueError('No frames could be decoded in the selected range.')
        while len(result)<count: result.append(last)
    return np.stack(result)

def write_video(frames,path,fps=FPS):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): raise FileExistsError(f'Refusing to overwrite existing video: {path}')
    with av.open(str(path),'w') as c:
        stream=c.add_stream('libx264',rate=fps)
        stream.width=frames.shape[2]; stream.height=frames.shape[1]
        stream.pix_fmt='yuv420p'; stream.options={'crf':'18','preset':'fast'}
        for i,rgb in enumerate(frames):
            frame=av.VideoFrame.from_ndarray(np.asarray(rgb,dtype=np.uint8),format='rgb24')
            frame.pts=i; frame.time_base=Fraction(1,fps)
            for packet in stream.encode(frame): c.mux(packet)
        for packet in stream.encode(): c.mux(packet)
    return str(path)

def audio_samples(path,start,seconds,rate=32000):
    output=np.zeros((2,round(seconds*rate)),dtype=np.float32)
    with av.open(str(path)) as c:
        if not c.streams.audio: return output
        stream=c.streams.audio[0]
        resampler=av.AudioResampler(format='fltp',layout='stereo',rate=rate)
        c.seek(max(0,int(start*av.time_base)),backward=True)
        cursor=None
        for frame in c.decode(stream):
            for converted in resampler.resample(frame):
                t=float(converted.pts*converted.time_base) if converted.pts is not None else (cursor or start)
                arr=converted.to_ndarray(); pos=round((t-start)*rate)
                a=max(0,pos); b=min(output.shape[1],pos+arr.shape[1])
                if b>a: output[:,a:b]=arr[:,a-pos:b-pos]
                cursor=t+arr.shape[1]/rate
                if pos>=output.shape[1]: return output
    return output

def ffmpeg_path():
    found=shutil.which('ffmpeg')
    if found: return found
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def mux_audio(silent,source,start,seconds,destination):
    if Path(destination).exists(): raise FileExistsError(destination)
    command=[ffmpeg_path(),'-nostdin','-v','error','-n','-i',str(silent),'-ss',str(start),
             '-i',str(source),'-map','0:v:0','-map','1:a:0?','-c:v','copy','-c:a','aac',
             '-b:a','192k','-t',str(seconds),'-movflags','+faststart',str(destination)]
    subprocess.run(command,check=True,capture_output=True,timeout=180)
    return str(destination)

def frame_count(path):
    with av.open(str(path)) as c: return sum(1 for _ in c.decode(video=0))

def plan_windows(total_frames,limit=124):
    """Independent fixed budget planner; short tails pad at render and trim at export."""
    if not 90<=limit<=294 or (limit-5)%17: raise ValueError('Invalid window length.')
    return [{'start':s,'count':min(limit,total_frames-s),
             'render_frames':max(90,5+17*math.ceil((min(limit,total_frames-s)-5)/17))}
            for s in range(0,total_frames,limit)]


def parse_timestamp(value):
    """Seconds, MM:SS or HH:MM:SS; reject ambiguous or non-finite input."""
    parts=str(value).strip().split(':')
    if not 1<=len(parts)<=3:raise ValueError('Use seconds, MM:SS, or HH:MM:SS.')
    try:values=[float(p) for p in parts]
    except ValueError:raise ValueError('Use seconds, MM:SS, or HH:MM:SS.') from None
    if any(not math.isfinite(v) or v<0 for v in values):raise ValueError('Timestamps must be finite and non-negative.')
    if len(values)>1 and any(v>=60 for v in values[1:]):raise ValueError('Minutes and seconds after a colon must be below 60.')
    if any(v!=int(v) for v in values[:-1]):raise ValueError('Only the seconds field can contain decimals.')
    return sum(v*60**i for i,v in enumerate(reversed(values)))


def selection_bounds(start,end,duration,maximum=120):
    start=parse_timestamp(start);end=parse_timestamp(end)
    if not math.isfinite(duration) or duration<=0:raise ValueError('Could not determine the source video duration.')
    if start>=duration or end>duration+1/FPS:raise ValueError(f'Timestamps must be within this {duration:.2f}-second video.')
    end=min(end,duration)
    if end-start<.25:raise ValueError('End must be at least 0.25 seconds after start.')
    if end-start>maximum+1e-6:raise ValueError(f'Select up to {maximum} seconds per project; the uploaded video can be longer.')
    return start,end


def prepare_clip(source,start,end,short_edge,destination):
    """Seek into the upload and transcode only the selected range; never overwrite."""
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    info=probe(source);start,end=selection_bounds(start,end,info['duration'])
    if short_edge not in (480,736):raise ValueError('Choose 480p or 736p.')
    width,height=canvas(info['width'],info['height'],short_edge)
    if max(width,height)>1600:raise ValueError('Use a video aspect ratio no wider than about 2:1.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Input seeking avoids decoding the entire beginning of a long upload.
    command=[ffmpeg_path(),'-nostdin','-v','error','-n','-ss',str(start),'-i',str(source),
        '-t',str(end-start),'-map','0:v:0','-map','0:a:0?',
        '-vf',f'scale={width}:{height}:flags=lanczos,setsar=1,fps=24,setpts=PTS-STARTPTS',
        '-c:v','libx264','-threads','4','-preset','fast','-crf','17','-pix_fmt','yuv420p',
        '-c:a','aac','-b:a','192k','-ac','2','-ar','48000',
        '-af','aresample=async=1:first_pts=0','-movflags','+faststart',str(destination)]
    subprocess.run(command,check=True,capture_output=True,timeout=900)
    result=probe(destination)
    if abs(result['duration']-(end-start))>2/FPS:raise RuntimeError('Prepared clip duration does not match the selected range.')
    return str(destination),{'start':start,'end':end,'original':info,'prepared':result}
