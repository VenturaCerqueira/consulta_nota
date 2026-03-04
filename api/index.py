"""
API de Extracao de Dados de Notas Fiscais em PDF - Vercel API Route
"""

import json
import base64
import io
import re
from datetime import datetime, timedelta
from typing import Optional

# Third-party imports
from jose import jwt, JWTError
from passlib.context import CryptContext
import pdfplumber


# ============== AUTH MODULE ==============
SECRET_KEY = "sua_chave_secreta_aqui_mude_em_producao"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# ============== EXTRACTOR MODULE ==============
def extract_data_from_pdf(pdf_bytes: bytes) -> dict:
    """Extrai dados de uma nota fiscal em PDF"""
    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as e:
        raise ValueError(f"Erro ao abrir o PDF: {str(e)}")
    
    if len(pdf.pages) == 0:
        raise ValueError("O PDF nao contem paginas")
    
    full_text = ""
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"
    
    pdf.close()
    
    if not full_text.strip():
        raise ValueError("Nao foi possivel extrair texto do PDF")
    
    return parse_nota_fiscal_text(full_text)


def parse_nota_fiscal_text(text: str) -> dict:
    """Parseia o texto extraido para extrair campos especificos da nota fiscal"""
    text = text.strip()
    
    data = {
        "numero": None,
        "serie": None,
        "data_emissao": None,
        "emitente": {"cnpj_cpf": None, "nome": None, "endereco": None, "municipio": None, "uf": None},
        "destinatario": {"cnpj_cpf": None, "nome": None, "endereco": None, "municipio": None, "uf": None},
        "valor_total": None,
        "itens": [],
        "tributos": {},
        "raw_text": text[:1000]
    }
    
    # Numero da NF
    numero_match = re.search(r'(?:N[Fe]\s*[Nn]º?|NF-e)\s*[:\-]?\s*(\d{1,9})', text, re.IGNORECASE)
    if numero_match:
        data["numero"] = numero_match.group(1)
    
    # Serie
    serie_match = re.search(r'[Ss]é[rr]ie\s*[:\-]?\s*(\d{1,3})', text)
    if serie_match:
        data["serie"] = serie_match.group(1)
    
    # Data emissao
    data_emissao_match = re.search(r'(\d{2}[\/\-]\d{2}[\/\-]\d{4})', text)
    if data_emissao_match:
        data["data_emissao"] = data_emissao_match.group(1)
    
    # CNPJ/CPF emitente
    cnpj_emitente_match = re.search(
        r'(?:CNPJ|CPF)[^\d]*(\d{2}\.?\d{3}\.?\d{3}\.?\d{4}\.?\d{2}|\d{3}\.?\d{3}\.?\d{3}\-?\d{2})',
        text, re.IGNORECASE
    )
    if cnpj_emitente_match:
        data["emitente"]["cnpj_cpf"] = cnpj_emitente_match.group(1)
    
    # Nome emitente
    emitente_match = re.search(r'(?:Emitente|Fornecedor|Vendedor)[\s:]*([^\n]{3,60})', text, re.IGNORECASE)
    if emitente_match:
        nome_emitente = emitente_match.group(1).strip()
        nome_emitente = re.sub(r'^(CNPJ|CPF)', '', nome_emitente, flags=re.IGNORECASE).strip()
        data["emitente"]["nome"] = nome_emitente
    
    # CNPJ/CPF destinatario
    cnpj_dest_match = re.search(
        r'(?:Destinatário|Comprador|Cliente)[^\d]*(\d{2}\.?\d{3}\.?\d{3}\.?\d{4}\.?\d{2}|\d{3}\.?\d{3}\.?\d{3}\-?\d{2})',
        text, re.IGNORECASE
    )
    if cnpj_dest_match:
        data["destinatario"]["cnpj_cpf"] = cnpj_dest_match.group(1)
    
    # Nome destinatario
    destinatario_match = re.search(r'(?:Destinatário|Comprador|Cliente)[\s:]*([^\n]{3,60})', text, re.IGNORECASE)
    if destinatario_match:
        nome_dest = destinatario_match.group(1).strip()
        nome_dest = re.sub(r'^(CNPJ|CPF)', '', nome_dest, flags=re.IGNORECASE).strip()
        data["destinatario"]["nome"] = nome_dest
    
    # Valor total
    valor_total_match = re.search(r'(?:Valor\s*Total|Valor\s*a\s*Pagar|Total\s*a\s*Pagar)[^\d]*R\$\s*([\d.,]+)', text, re.IGNORECASE)
    if valor_total_match:
        valor = valor_total_match.group(1).replace('.', '').replace(',', '.')
        data["valor_total"] = float(valor)
    
    # Itens
    data["itens"] = extract_itens(text)
    
    # Tributos
    data["tributos"] = extract_tributos(text)
    
    return data


def extract_itens(text: str) -> list:
    itens = []
    linhas = text.split('\n')
    
    for linha in linhas:
        item_match = re.search(r'(\d+)\s*\|?\s*([^\|]{5,50})\s*\|?\s*([\d.,]+)\s*\|?\s*([\d.,]+)\s*\|?\s*([\d.,]+)', linha)
        if item_match:
            item = {
                "codigo": item_match.group(1),
                "descricao": item_match.group(2).strip(),
                "quantidade": float(item_match.group(3).replace('.', '').replace(',', '.')),
                "valor_unitario": float(item_match.group(4).replace('.', '').replace(',', '.')),
                "valor_total": float(item_match.group(5).replace('.', '').replace(',', '.'))
            }
            itens.append(item)
    
    return itens


def extract_tributos(text: str) -> dict:
    tributos = {}
    
    icms_match = re.search(r'ICMS[^\d]*R\$\s*([\d.,]+)', text, re.IGNORECASE)
    if icms_match:
        valor = icms_match.group(1).replace('.', '').replace(',', '.')
        tributos["icms"] = float(valor)
    
    ipi_match = re.search(r'IPI[^\d]*R\$\s*([\d.,]+)', text, re.IGNORECASE)
    if ipi_match:
        valor = ipi_match.group(1).replace('.', '').replace(',', '.')
        tributos["ipi"] = float(valor)
    
    return tributos


# ============== USER DATABASE ==============
fake_users_db = {
    "admin": {
        "username": "admin",
        "full_name": "Administrador",
        "hashed_password": get_password_hash("admin123"),
        "disabled": False,
    }
}


# ============== HELPER FUNCTIONS ==============
def get_response(status_code: int, body: dict, headers: dict = None):
    return {
        "statusCode": status_code,
        "body": json.dumps(body),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            **(headers or {})
        }
    }


def get_auth_user(headers: dict) -> Optional[dict]:
    auth_header = headers.get("authorization", "")
    if not auth_header:
        return None
    
    # Handle both "Bearer token" and just "token"
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = auth_header
    
    payload = decode_token(token)
    if payload is None:
        return None
    
    username = payload.get("sub")
    if username is None:
        return None
    
    return fake_users_db.get(username)


# ============== API HANDLERS ==============
def handle_login(body: str) -> dict:
    try:
        # Parse form data
        params = {}
        for pair in body.split('&'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                params[key] = value.replace('+', ' ')
        
        username = params.get('username', '')
        password = params.get('password', '')
        
        user = fake_users_db.get(username)
        if not user or not verify_password(password, user["hashed_password"]):
            return get_response(401, {"detail": "Incorrect username or password"})
        
        access_token = create_access_token(
            data={"sub": user["username"]},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return get_response(200, {"access_token": access_token, "token_type": "bearer"})
    
    except Exception as e:
        return get_response(500, {"detail": str(e)})


def handle_extract(body: bytes, content_type: str, headers: dict) -> dict:
    # Check authentication
    user = get_auth_user(headers)
    if not user:
        return get_response(401, {"detail": "Nao autenticado"}, {"WWW-Authenticate": "Bearer"})
    
    try:
        pdf_bytes = None
        
        # Try to parse as JSON with base64
        try:
            body_json = json.loads(body.decode('utf-8'))
            if "file" in body_json:
                pdf_bytes = base64.b64decode(body_json["file"])
        except:
            pass
        
        # Try multipart form data
        if pdf_bytes is None and "multipart/form-data" in content_type:
            try:
                boundary = content_type.split("boundary=")[-1] if "boundary=" in content_type else ""
                if boundary:
                    parts = body.split(b"--" + boundary.encode())
                    for part in parts:
                        if b"Content-Type: application/pdf" in part:
                            header_end = part.find(b"\r\n\r\n")
                            if header_end > 0:
                                pdf_bytes = part[header_end + 4:]
                                pdf_bytes = pdf_bytes.split(b"\r\n--")[0]
                                break
            except:
                pass
        
        if pdf_bytes is None:
            return get_response(400, {"detail": "Nenhum arquivo PDF encontrado"})
        
        data = extract_data_from_pdf(pdf_bytes)
        
        return get_response(200, {
            "success": True,
            "message": "Dados extraidos com sucesso",
            "data": data
        })
    
    except ValueError as e:
        return get_response(400, {"detail": str(e)})
    except Exception as e:
        return get_response(500, {"detail": f"Erro ao processar: {str(e)}"})


# ============== MAIN HANDLER ==============
def handler(event, context):
    """Vercel serverless function handler"""
    
    # Handle CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return get_response(200, {"message": "OK"})
    
    method = event.get("httpMethod")
    path = event.get("path", "/")
    headers = event.get("headers", {})
    body = event.get("body", "")
    
    # Normalize path - remove trailing slashes
    path = path.rstrip("/")
    if not path:
        path = "/"
    
    # Decode body if base64
    if event.get("isBase64Encoded", False):
        body = base64.b64decode(body)
    elif isinstance(body, str):
        body = body.encode('utf-8')
    
    content_type = headers.get("content-type", headers.get("Content-Type", ""))
    
    # Routes - handle both /api prefix and without
    if method == "POST" and ("/token" in path or path == "/api/token"):
        return handle_login(body.decode('utf-8') if body else "")
    
    if method == "POST" and ("/extract" in path or path == "/api/extract"):
        return handle_extract(body, content_type, headers)
    
    if method == "GET" and ("/health" in path or path == "/api/health"):
        return get_response(200, {"message": "API funcionando"})
    
    if method == "GET" and (path in ["/", "/api", "/api/"]):
        return get_response(200, {"message": "API de Extracao de Notas Fiscais"})
    
    # 404
    return get_response(404, {"detail": f"Endpoint nao encontrado: {path}"})


# Export for Vercel
app = handler

