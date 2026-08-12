from fastapi import FastAPI

app = FastAPI(
    title="Monetra API",
    version="1.0.0"
)

@app.get("/")
def home():
    return {
        "message": "🚀 Bem-vindo à API da Monetra!"
    }