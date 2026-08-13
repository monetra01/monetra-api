from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse

app = FastAPI(
    title="Monetra API",
    version="1.0.0"
)

VERIFY_TOKEN = "monetra_webhook_2026"

@app.get("/")
def home():
    return {
        "message": "🚀 Bem-vindo à API da Monetra!"
    }

@app.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)

    return PlainTextResponse("Token inválido", status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()
    print("Webhook recebido:", data)

    return {"status": "ok"}
