"""
API de Extração de Dados de Notas Fiscais em PDF

Esta API permite extrair dados de notas fiscais em formato PDF.
Utiliza autenticação JWT para proteger os endpoints.
"""

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
import os
from datetime import datetime, timedelta

from auth import verify_password, create_access_token, get_password_hash
from extractor import extract_data_from_pdf
from schemas import Token, NotaFiscalResponse, MessageResponse

# Configurações da aplicação
app = FastAPI(
    title="API de Extração de Notas Fiscais",
    description="API REST para extração de dados de notas fiscais em PDF",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Usuário em memória (em produção, use um banco de dados)
fake_users_db = {
    "admin": {
        "username": "admin",
        "full_name": "Administrador",
        "hashed_password": get_password_hash("admin123"),
        "disabled": False,
    }
}

# Configurações de tempo de expiração do token
ACCESS_TOKEN_EXPIRE_MINUTES = 30


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency para obter o usuário atual autenticado"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = create_access_token(data={"sub": "admin"})
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        user = fake_users_db.get(username)
        if user is None:
            raise credentials_exception
        return user
    except Exception:
        raise credentials_exception


@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Endpoint para obter token de acesso
    """
    user = fake_users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/extract", response_model=NotaFiscalResponse)
async def extract_nota_fiscal(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Endpoint para extrair dados de nota fiscal PDF
    
    - **file**: Arquivo PDF da nota fiscal
    - Retorna dados extraídos em formato JSON
    """
    # Validar tipo do arquivo
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo deve ser um PDF"
        )
    
    # Validar extensão do arquivo
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo deve ter extensão .pdf"
        )
    
    try:
        # Ler o conteúdo do arquivo
        contents = await file.read()
        
        # Extrair dados do PDF
        data = extract_data_from_pdf(contents)
        
        return NotaFiscalResponse(
            success=True,
            message="Dados extraídos com sucesso",
            data=data
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar o PDF: {str(e)}"
        )


@app.get("/", response_model=MessageResponse)
async def root():
    """
    Endpoint raiz da API
    """
    return MessageResponse(
        message="API de Extração de Notas Fiscais - Use /docs para documentação"
    )


@app.get("/health", response_model=MessageResponse)
async def health_check():
    """
    Endpoint para verificar saúde da API
    """
    return MessageResponse(
        message="API está funcionando corretamente"
    )


# Personalizar OpenAPI schema para incluir segurança
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="API de Extração de Notas Fiscais",
        version="1.0.0",
        description="API REST para extração de dados de notas fiscais em PDF",
        routes=app.routes,
    )
    
    # Adicionar esquema de segurança
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "description": "JWT token de autenticação"
        }
    }
    
    # Adicionar segurança a todos os endpoints
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if method in ["get", "post", "put", "delete"]:
                if path != "/token":  # Token endpoint não precisa de auth
                    openapi_schema["paths"][path][method]["security"] = [{"Bearer": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

