from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app import models
from app.routes import router
from app.whatsapp.webhook import router as whatsapp_router


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Monetra API",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "message": "🚀 Bem-vindo à API da Monetra!"
    }


# Rotas principais da API
app.include_router(router)

# Webhook do WhatsApp
app.include_router(whatsapp_router)