# apps/api/src/nq_api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nq_api.routes import stocks, screener, analyst, query

app = FastAPI(title="NeuralQuant API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://neuralquant.vercel.app"],
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
app.include_router(screener.router, prefix="/screener", tags=["screener"])
app.include_router(analyst.router, prefix="/analyst", tags=["analyst"])
app.include_router(query.router, prefix="/query", tags=["query"])


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}
