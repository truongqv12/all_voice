import os
import sys

# Set env before importing app
os.environ["PREVIEW_WARM_ON_STARTUP"] = "false"

from app import main as _app
from app.backends.registry import registry
from app.previews import ensure_preview, prune_orphans

def main():
    if len(sys.argv) > 1:
        model = sys.argv[1]
        voices = [v for v in registry.all_voices() if v.model == model]
        print(f"Building {len(voices)} voices for {model}...")
        for v in voices:
            try:
                print(f" - {v.id}")
                ensure_preview(v.model, v.id, force=True)
            except Exception as e:
                print(f"Error building {v.model}/{v.id}: {e}")
    else:
        # parent process: call this script for each model
        import subprocess
        models = registry.models()
        print(f"Models to build: {models}")
        for model in models:
            print(f"\n--- Launching builder for {model} ---")
            subprocess.run(["uv", "run", "python", "scripts/build_by_model.py", model], check=False)
        
        print("\n--- Pruning orphans ---")
        prune_orphans()
        print("Done.")

if __name__ == "__main__":
    main()
