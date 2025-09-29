from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from database import engine, Base
from app.api import router as api_router
from app.auth import router as auth_router

app = FastAPI(title="Система управления проектами")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешить все домены (для разработки)
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все HTTP методы
    allow_headers=["*"],  # Разрешить все заголовки
)

# Роутеры
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(api_router, prefix="/api", tags=["api"])

@app.get("/")
def root():
    return {"message": "Добро пожаловать в систему управления проектами"}