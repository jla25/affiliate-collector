from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import create_db
from routers.auth import router as auth_router
from routers.collect import router as collect_router
from routers.operators import router as operators_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db()
    yield


app = FastAPI(
    title="Affiliate Collector API",
    version="1.0.0",
    description="Panel de gestión de operadores de afiliados. Soporta MyAffiliates, Cellxpert y Superpartners.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(operators_router)
app.include_router(collect_router)


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}
