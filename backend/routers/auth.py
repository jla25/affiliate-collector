from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from auth import create_access_token, hash_password, verify_password
from database import get_session
from models import User
from schemas import InitAdminRequest, LoginRequest, Token

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/init", summary="Crear administrador inicial")
def init_admin(body: InitAdminRequest, session: Session = Depends(get_session)):
    """Crea el primer usuario administrador. Solo funciona si no existe ningún usuario."""
    existing = session.exec(select(User)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un administrador. Usa /auth/login.",
        )
    user = User(username=body.username, hashed_password=hash_password(body.password))
    session.add(user)
    session.commit()
    return {"message": f"Administrador '{body.username}' creado correctamente."}


@router.post("/login", response_model=Token, summary="Iniciar sesión")
def login(body: LoginRequest, session: Session = Depends(get_session)):
    """Devuelve un token JWT válido por 8 horas."""
    user = session.exec(select(User).where(User.username == body.username)).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )
    return Token(access_token=create_access_token(user.username))
