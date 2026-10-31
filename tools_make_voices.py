import subprocess, os, json, sys
sys.path.insert(0, "."); import coka_data as D
P = "/workspace/an_dl/piper/piper/piper"; M = "/workspace/piper_voices/en_GB-vctk-medium.onnx"
SPK = {"KIM": 4, "ANA": 1}         # VCTK p259 (male), p236 (female)
for mid, *_, br in D.MISSIONS:
    for k, (who, line) in enumerate(br):
        out = os.path.abspath("assets/voice/%s_%d.wav" % (mid, k))
        subprocess.run([P, "-m", M, "-s", str(SPK[who]), "-f", out, "-q", "--length_scale", "1.0" if who == "ANA" else "1.08"], input=line.encode(), check=True,
                       cwd=os.path.dirname(P), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
extra = {"rankup": ("ANA", "Rank up!"), "wave": ("KIM", "Next wave incoming!"), "checkpoint": ("KIM", "Checkpoint reached."), "fail": ("KIM", "Drill failed. Back to the last checkpoint."),
         "done": ("KIM", "Outstanding work, soldier. Mission complete.")}
for k, (who, line) in extra.items():
    subprocess.run([P, "-m", M, "-s", str(SPK[who]), "-f", os.path.abspath("assets/voice/%s.wav" % k), "-q"], input=line.encode(), check=True, cwd=os.path.dirname(P), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(len(os.listdir("assets/voice")))
