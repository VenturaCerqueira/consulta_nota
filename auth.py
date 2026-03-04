"""
Módulo de autenticação da API

Responsável por:
- Criar tokens JWT
- Verificar senhas
- Hash de senhas
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

# Configurações - Em produção, use variáveis de ambiente
SECRET_KEY = "sua_chave_secreta_aqui_mude_em_producao"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Contexto para hashing de senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a senhaplain corresponde à senha hasheada
    
    Args:
        plain_password: Senha em texto plano
        hashed_password: Senha hasheada
        
    Returns:
        True se as senhas corresponderem, False caso contrário
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Gera hash de uma senha
    
    Args:
        password: Senha em texto plano
        
    Returns:
        Senha hasheada
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Cria um token JWT de acesso
    
    Args:
        data: Dados a serem codificados no token
        expires_delta: Tempo até a expiração do token
        
    Returns:
        Token JWT codificado
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decodifica um token JWT
    
    Args:
        token: Token JWT a ser decodificado
        
    Returns:
        Dados do token ou None se inválido
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

