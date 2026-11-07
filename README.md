# GGF Viggle Recast

Local multi-character video replacement using the published Viggle Remake / MiniMax H3 models. Normal generates at 736p; Turbo Mode generates at 480p. Source selection, frame preparation, project management, and multi-section video assembly are implemented in this repository.

This is the **app source**, with no model weights or quick installer. For the GGF quick installer, see [getgoingfast.pro/tools/viggle-recast](https://getgoingfast.pro/tools/viggle-recast). The app's `RUN.bat` starts an existing installation; it does not install dependencies or models.

Read [MODEL-TERMS.txt](MODEL-TERMS.txt) before using the models. The included `vendor/` components are official upstream ComfyUI and Viggle components with their own license files. GGF orchestration code is original and does not include WanGP, Showrunner, or MMGP implementation code.

The preview was tested on an RTX 4090 with 24 GB VRAM and 128 GB RAM. A six-second 736p, two-section output with preserved audio completed in about 15.5 minutes. Longer and more complex selections can have visible seams or drift. See `README.txt` for the development notes.
