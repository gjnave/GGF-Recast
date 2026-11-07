GGF RECAST — LOCAL DEVELOPMENT PREVIEW
Build: 2026-11-06 preview v3 (see CHANGES-V2.txt and CHANGES-V3.txt)

FIRST RUN
Run the root RUN.bat. The app opens at http://127.0.0.1:7877.
If models are missing, Settings shows the L/iZ video and Install / resume.
Downloads and SHA-256 verification run on the PC. Verify model files works offline.
With all models present, Recast opens Create and the helper is hidden.

QUICK START
1. Upload a video. Choose a short, clear shot and select its timestamps.
   Turbo defaults to 480p; Normal uses native 736p with the same INT8 model.
2. Add replacement images and describe which original person each replaces.
3. Click Generate video to prepare missing frames and render automatically.
   To inspect or import a frame first, click Prepare replacement frames.
   Generate uses the prepared frames and leaves the preview visible.
4. Download the MP4 when complete.
Saved projects can be reopened. Completed shots are reused; older takes remain.
The included samples show the exact synthetic two-character smoke-test fixture.

WHAT IS IMPLEMENTED
Local Gradio UI; up to four cast entries; source range selection; cut detection;
per-shot reference creation; manual reference import; private JSON GPU workers;
serialized GPU jobs; cancellation; saved project history; resumed rendering;
short-shot padding and trimming; multi-window assembly; original audio export.
The tester accepts videos up to 2 GB with no source-duration cap, and selections
up to 120 seconds. FFmpeg trims/resizes the selection before AI preparation.
The video engine is Viggle Remake Swap on MiniMax H3. Qwen Image 2.1 prepares
the references. Image and video workers unload between stages.

GGF app orchestration and prompts were written for this app. No WanGP,
Showrunner or MMGP code is included or required. Embedded official upstream
ComfyUI and Viggle components are included with provenance and licenses.

TESTED RESULT
On this RTX 4090 / 128 GB RAM computer: two characters replaced in a 3.75-second
832 x 480 clip, 90 frames at 24 fps, with source audio retained. Image preparation
took 21.46 seconds and the video stage 105.6 seconds. Peak PyTorch allocation
was 22.109 GiB (22.930 GiB reserved). See SMOKE-TEST.txt for scope and evidence.

LIMITS OF THIS PREVIEW
24 GB GPU verified; lower VRAM has not been validated. Normal 736p passed a
six-second, two-section GPU test; video generation took about 15.5 minutes.
Three/four-character casts, realistic footage, crossing people, complex occlusion
and long clips have not been validated with generation tests. Independent windows
can show seams. Background details and framing can drift. Review outputs.
The cut detector is a basic heuristic, not semantic scene understanding.
The model's territory/commercial terms still apply; see MODEL-TERMS.txt.
This is a local development build, not a published commercial release.

FRESH INSTALL
Extract the complete ZIP onto a drive with at least 85 GB free. Keep this layout:
  Install-GGF-Recast.bat, RUN.bat, disclaimer.md, about.nfo, thumbnail.png
  GGF-Recast/app.py, GGF-Recast/RUN.bat and other app files
Run Install-GGF-Recast.bat to install the private runtime, NVIDIA PyTorch and GUI.
Run RUN.bat. In Settings, click Install / resume to download missing model files.
Existing configured paths are preserved. Default projects live in GGF-Recast/projects.
