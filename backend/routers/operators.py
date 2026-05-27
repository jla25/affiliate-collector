from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlmodel import Session, select

from auth import get_current_user
from database import get_session
from models import Operator
from schemas import OperatorCreate, OperatorRead, OperatorUpdate

router = APIRouter(
    prefix="/operators",
    tags=["Operadores"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/", response_model=list[OperatorRead], summary="Listar operadores")
def list_operators(session: Session = Depends(get_session)):
    return session.exec(select(Operator)).all()


_CREATE_EXAMPLES = {
    "myaffiliates_oauth2": {
        "summary": "MyAffiliates — OAuth2",
        "description": (
            "Método preferido. Usa client_id + client_secret obtenidos desde "
            "Account → Authorisation → OAuth2 Clients del portal de afiliados. "
            "No expone tu usuario/contraseña y el acceso se puede revocar en cualquier momento."
        ),
        "value": {
            "name": "Betify",
            "platform": "myaffiliates",
            "url": "https://affiliates.betify.partners/statistics.php",
            "credentials": {
                "client_id": "RgCnw93TVpdvJ8HjbovMxrq8u",
                "client_secret": "tXMFgZ494S1c...",
            },
        },
    },
    "myaffiliates_basic": {
        "summary": "MyAffiliates — Basic Auth",
        "description": (
            "Usar cuando el portal no tenga OAuth2 disponible (sección Authorisation ausente). "
            "Requiere usuario y contraseña directos de la cuenta de afiliado."
        ),
        "value": {
            "name": "Betsafe",
            "platform": "myaffiliates",
            "url": "https://affiliates.betssongroupaffiliates.com/statistics.php",
            "credentials": {"user": "mi_usuario", "pass": "mi_contraseña"},
        },
    },
    "cellxpert": {
        "summary": "Cellxpert (BlueWin…)",
        "description": (
            "Plataforma Cellxpert. "
            "El affiliate_id y api_key se obtienen desde el portal de afiliados → API Settings. "
            "Endpoints usados: mediareport (XML), registrations (JSON) y commissions (XML). "
            "La URL debe terminar en /api/ (p.ej. https://go.bluewinpartners.com/api/)."
        ),
        "value": {
            "name": "BlueWin",
            "platform": "cellxpert",
            "url": "https://go.bluewinpartners.com/api/",
            "credentials": {"affiliate_id": "35327", "api_key": "abc123..."},
        },
    },
    "superpartners": {
        "summary": "Superpartners (Betway…)",
        "description": (
            "Plataforma Superpartners. "
            "El username y api_key se obtienen desde el portal de afiliados → FEED. "
            "Endpoint usado: /api/trafficfeed con parámetros startdate/enddate. "
            "La URL base debe ser el dominio raíz sin path (p.ej. https://account.superpartners.com)."
        ),
        "value": {
            "name": "Betway",
            "platform": "superpartners",
            "url": "https://account.superpartners.com",
            "credentials": {"username": "OverOption_x", "api_key": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"},
        },
    },
    "affilka": {
        "summary": "Affilka by SOFTSWISS (BC.Game…)",
        "description": (
            "Plataforma Affilka de SOFTSWISS. "
            "El api_key se obtiene desde el portal de afiliados (partnerbc.com) "
            "y se envía en el header Authorization directamente (sin prefijo Bearer). "
            "Endpoints usados: /api/customer/v1/partner/campaigns y /api/customer/v1/partner/report."
        ),
        "value": {
            "name": "BCGame",
            "platform": "affilka",
            "url": "https://partnerbc.com",
            "credentials": {"api_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"},
        },
    },
}


@router.post("/", response_model=OperatorRead, status_code=status.HTTP_201_CREATED, summary="Crear operador")
def create_operator(
    body: OperatorCreate = Body(openapi_examples=_CREATE_EXAMPLES),
    session: Session = Depends(get_session),
):
    existing = session.exec(select(Operator).where(Operator.name == body.name)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe un operador con el nombre '{body.name}'")
    operator = Operator(**body.model_dump())
    session.add(operator)
    session.commit()
    session.refresh(operator)
    return operator


@router.get("/{operator_id}", response_model=OperatorRead, summary="Obtener operador")
def get_operator(operator_id: int, session: Session = Depends(get_session)):
    operator = session.get(Operator, operator_id)
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operador no encontrado")
    return operator


@router.patch("/{operator_id}", response_model=OperatorRead, summary="Actualizar operador")
def update_operator(operator_id: int, body: OperatorUpdate, session: Session = Depends(get_session)):
    operator = session.get(Operator, operator_id)
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operador no encontrado")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(operator, key, value)
    session.add(operator)
    session.commit()
    session.refresh(operator)
    return operator


@router.delete("/{operator_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar operador")
def delete_operator(operator_id: int, session: Session = Depends(get_session)):
    operator = session.get(Operator, operator_id)
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operador no encontrado")
    session.delete(operator)
    session.commit()
