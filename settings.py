"""GGF Recast local configuration. No network service is required for inference."""
from pathlib import Path
import json, sys

APP = Path(__file__).resolve().parent

def settings():
    cfg = {
        'python': sys.executable, 'core': str(APP/'vendor'/'comfy_core'),
        'image_models': str(APP/'models'/'image'),
        'image_loras': str(APP/'models'/'loras'),
        'video_models': str(APP/'models'/'video'),
        'projects': str(APP/'projects'), 'reserve_vram': 4,
    }
    path=APP/'settings.local.json'
    if path.is_file(): cfg.update(json.loads(path.read_text(encoding='utf-8')))
    return cfg

IMAGE_FILES = {
 'model': 'diffusion_models/qwen_image_2.1_int8_convrot.safetensors',
 'text': 'text_encoders/qwen3vl_8b_int8_convrot.safetensors',
 'vae': 'vae/qwen_image_2.1_vae_bf16.safetensors',
}
VIDEO_FILES = {
 'model': 'Viggle/int8/viggle_remake_swap_pruned_int8_convrot.safetensors',
 'text': 'Comfy-Org/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors',
 'vae': 'Comfy-Org/vae/minimax_h3_video_vae_fp16.safetensors',
 'audio_vae': 'Comfy-Org/vae/minimax_h3_audio_vae_fp32.safetensors',
}

def readiness():
    cfg=settings()
    checks={'Python':Path(cfg['python']).is_file(),
            'Inference core':(Path(cfg['core'])/'nodes.py').is_file()}
    for prefix,key,files in [('Image','image_models',IMAGE_FILES),('Video','video_models',VIDEO_FILES)]:
        for label,name in files.items(): checks[f'{prefix} {label}']=(Path(cfg[key])/name).is_file()
    return checks
