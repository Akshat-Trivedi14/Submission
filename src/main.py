from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.api.routes import router
from src.database import SessionLocal, engine
from src.models.models import Base, User
from src.core.security import get_password_hash


def init_db():
    """Create tables and default admin user if not exists."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "admin@example.com").first()
        if not admin:
            admin_user = User(
                email="admin@example.com",
                password=get_password_hash("admin123"),
                role="admin"
            )
            db.add(admin_user)
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown


app = FastAPI(title="E-Commerce Backend", lifespan=lifespan)
app.include_router(router)
