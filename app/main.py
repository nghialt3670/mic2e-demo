from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.lifespan import lifespan
from app.routes.chat2edit_routes import router as chat2edit_router
from app.routes.health_routes import router as health_router

app = FastAPI(
    title="MIC2E Demo",
    description="Simple demo for MIC2E image editing chatbot",
    lifespan=lifespan,
    root_path="/chat2edit"  # Support basepath for reverse proxy
)

# CORS middleware for API calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for demo
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Include API routers first
app.include_router(health_router)
app.include_router(chat2edit_router)

# Mount static files last (catch-all)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
