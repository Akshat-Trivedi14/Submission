from fastapi import FastAPI

from src.api.routes import router

app = FastAPI(title="E-Commerce Backend")
app.include_router(router)
