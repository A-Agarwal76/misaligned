from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .api.routes import router
from .config import get_settings

settings = get_settings()

app = FastAPI(
    title="ASEF: AI Safety Evaluation Framework",
    description="Framework for evaluating alignment faking and scheming in LLMs",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

# Mount dashboard if it exists
dashboard_path = Path(__file__).parent.parent / "dashboard"
if dashboard_path.exists():
    app.mount("/", StaticFiles(directory=str(dashboard_path), html=True), name="dashboard")

@app.on_event("startup")
async def startup_event():
    print("ASEF started. Warning: Mock environment.")
