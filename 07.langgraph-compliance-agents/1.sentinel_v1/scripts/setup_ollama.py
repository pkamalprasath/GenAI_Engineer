"""
Configure Ollama on D drive and pull required models.
Run once after installing Ollama: python scripts/setup_ollama.py
"""
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODELS = os.getenv("OLLAMA_MODELS", r"D:\ollama\models")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Models required for SENTINEL — total ~2.5GB RAM when loaded
REQUIRED_MODELS = [
    ("llama3.2:3b", "Classification agent — fast, 2.2GB"),
    ("nomic-embed-text", "Embeddings — local, 300MB"),
]

def check_ollama_running() -> bool:
    """Check if Ollama process is running and accepting connections."""
    import httpx
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def pull_model(model_name: str) -> bool:
    """Pull an Ollama model. Returns True on success."""
    print(f"  Pulling {model_name}...", end=" ", flush=True)
    env = {**os.environ, "OLLAMA_MODELS": OLLAMA_MODELS}
    result = subprocess.run(
        ["ollama", "pull", model_name],
        capture_output=True, text=True, env=env,
    )
    if result.returncode == 0:
        print("✓")
        return True
    else:
        print(f"✗ ({result.stderr[:100]})")
        return False


def main():
    print("\n🛡️  SENTINEL — Ollama Setup")
    print(f"   Models directory: {OLLAMA_MODELS}")
    print(f"   Ollama URL:       {OLLAMA_BASE_URL}\n")

    # Ensure model directory exists on D drive
    Path(OLLAMA_MODELS).mkdir(parents=True, exist_ok=True)

    if not check_ollama_running():
        print("❌ Ollama is not running. Start Ollama first, then re-run this script.")
        print("   Download: https://ollama.com")
        sys.exit(1)

    print("✓ Ollama is running\n")
    print("Pulling required models:")

    success_count = 0
    for model, description in REQUIRED_MODELS:
        if pull_model(model):
            success_count += 1
        print(f"    ({description})")

    print(f"\n✓ {success_count}/{len(REQUIRED_MODELS)} models ready")
    print(f"  Estimated RAM usage: ~2.5GB\n")

    if success_count == len(REQUIRED_MODELS):
        print("✅ Ollama setup complete. You can now run SENTINEL.")
    else:
        print("⚠️  Some models failed. SENTINEL will use API fallback where possible.")


if __name__ == "__main__":
    main()
