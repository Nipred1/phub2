from fastapi import FastAPI
# from database import engine, Base
from app.api import router as api_router
from app.auth import router as auth_router

app = FastAPI(title="Система управления проектами")

# Роутеры
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(api_router, prefix="/api", tags=["api"])

# Пример корневого эндпоинта
@app.get("/")
def root():
    return {"message": "Добро пожаловать в систему управления проектами"}
