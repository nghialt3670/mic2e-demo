import os

from dotenv import load_dotenv

load_dotenv()

# Server configuration
PORT = int(os.getenv("PORT", "8000"))

# LLM API keys (at least one required)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Inference service (required for image generation)
INFERENCE_API_URL = os.getenv("INFERENCE_API_URL")

if not INFERENCE_API_URL:
    raise ValueError("INFERENCE_API_URL must be set (e.g., http://localhost:8001)")
