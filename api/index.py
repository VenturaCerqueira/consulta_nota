"""
API de Extração de Dados de Notas Fiscais em PDF - Vercel API Route

Esta API permite extrair dados de notas fiscais em formato PDF.
Utiliza autenticação JWT para proteger os endpoints.
"""

import json
import base64
import hashlib
from datetime import datetime, timedelta
from typing import Optional

# Third-party imports - these need to be in requirements.txt
try:
    from jose import jwt, JWTError
    from passlib.context import CryptContext
    import pdfplumber
    import io
    import re
except ImportError as e:
    # Handle missing imports gracefully
    pass

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
        raise ValueError("O PDF não contém páginas")
    
    full_text = ""
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"
    
    if not full_text.strip():
        raise ValueError(
            "Não foi possível extrair texto do PDF. "
            "O documento pode ser uma imagem ou estar protegido."
        )
    
    pdf.close()
    data = parse_nota_fiscal_text(full_text)
    return data


def parse_nota_fiscal_text(text: str) -> dict:
    """Parseia o texto extraído para extrair campos específicos da nota fiscal"""
    text = text.strip()
    
    data = {
        "numero": None,
        "serie": None,
        "data_emissao": None,
        "emitente": {
            "cnpj_cpf": None,
            "nome": None,
            "endereco": None,
            "municipio": None,
            "uf": None
        },
        "destinatario": {
            "cnpj_cpf": None,
            "nome": None,
            "endereco": None,
            "municipio": None,
            "uf": None
        },
        "valor_total": None,
        "itens": [],
        "tributos": {},
        "raw_text": text[:1000]
    }
    
    # Extrair número da NF
    numero_match = re.search(r'(?:N[Fe]\s*[Nn]º?|NF-e)\s*[:\-]?\s*(\d{1,9})', text, re.IGNORECASE)
    if numero_match:
        data["numero"] = numero_match.group(1)
    
    # Extrair série
    serie_match = re.search(r'[Ss]é[rr]ie\s*[:\-]?\s*(\d{1,3})', text)
    if serie_match:
        data["serie"] = serie_match.group(1)
    
    # Extrair data de emissão
    data_emissao_match = re.search(
        r'(?:[Dd]ata\s*de\s*[Ee]missão|[Dd]ata\s*[Ee]missão)\s*[:\-]?\s*(\d{2}[\/\-]\d{2}[\/\-]\d{4})',
        text
    )
    if data_emissao_match:
        data["data_emissao"] = data_emissao_match.group(1)
    
    if not data["data_emissao"]:
        data_emissao_match = re.search(r'(\d{4}[\/\-]\d{2}[\/\-]\d{2})', text)
        if data_emissao_match:
            data["data_emissao"] = data_emissao_match.group(1)
    
    # Extrair CNPJ/CPF do emitente
    cnpj_emitente_match = re.search(
        r'(?:CNPJ|CPF)[^\d]*(\d{2}\.?\d{3}\.?\d{3}\.?\d{4}\.?\d{2}|\d{3}\.?\d{3}\.?\d{3}\-?\d{2})',
        text, re.IGNORECASE
    )
    if cnpj_emitente_match:
        data["emitente"]["cnpj_cpf"] = cnpj_emitente_match.group(1)
    
    # Extrair nome do emitente
    emitente_match = re.search(
        r'(?:Emitente|Fornecedor|Vendedor)[\s:]*([^\n]{3,60})',
        text, re.IGNORECASE
    )
    if emitente_match:
        nome_emitente = emitente_match.group(1).strip()
        nome_emitente = re.sub(r'^(CNPJ|CPF)', '', nome_emitente, flags=re.IGNORECASE).strip()
        data["emitente"]["nome"] = nome_emitente
    
    # Extrair CNPJ/CPF do destinatário
    cnpj_dest_match = re.search(
        r'(?:Destinatário|Comprador|Cliente)[^\d]*(\d{2}\.?\d{3}\.?\d{3}\.?\d{4}\.?\d{2}|\d{3}\.?\d{3}\.?\d{3}\-?\d{2})',
        text, re.IGNORECASE
    )
    if cnpj_dest_match:
        data["destinatario"]["cnpj_cpf"] = cnpj_dest_match.group(1)
    
    # Extrair nome do destinatário
    destinatario_match = re.search(
        r'(?:Destinatário|Comprador|Cliente)[\s:]*([^\n]{3,60})',
        text, re.IGNORECASE
    )
    if destinatario_match:
        nome_dest = destinatario_match.group(1).strip()
        nome_dest = re.sub(r'^(CNPJ|CPF)', '', nome_dest, flags=re.IGNORECASE).strip()
        data["destinatario"]["nome"] = nome_dest
    
    # Extrair valor total
    valor_total_match = re.search(
        r'(?:Valor\s*Total|Valor\s*a\s*Pagar|Total\s*a\s*Pagar|Valor\s*Liquido)[^\d]*R\$\s*([\d.,]+)',
        text, re.IGNORECASE
    )
    if valor_total_match:
        valor = valor_total_match.group(1).replace('.', '').replace(',', '.')
        data["valor_total"] = float(valor)
    
    if not data["valor_total"]:
        valor_total_match = re.search(r'TOTAL\s*[:\-]?\s*R\$\s*([\d.,]+)', text, re.IGNORECASE)
        if valor_total_match:
            valor = valor_total_match.group(1).replace('.', '').replace(',', '.')
            data["valor_total"] = float(valor)
    
    # Extrair itens
    data["itens"] = extract_itens(text)
    
    # Extrair tributos
    data["tributos"] = extract_tributos(text)
    
    return data


def extract_itens(text: str) -> list:
    """Extrai os itens/produtos da nota fiscal"""
    itens = []
    linhas = text.split('\n')
    
    for linha in linhas:
        item_match = re.search(
            r'(\d+)\s*\|?\s*([^\|]{5,50})\s*\|?\s*([\d.,]+)\s*\|?\s*([\d.,]+)\s*\|?\s*([\d.,]+)',
            linha
        )
        
        if item_match:
            item = {
                "codigo": item_match.group(1),
                "descricao": item_match.group(2).strip(),
                "quantidade": float(item_match.group(3).replace('.', '').replace(',', '.')),
                "valor_unitario": float(item_match.group(4).replace('.', '').replace(',', '.')),
                "valor_total": float(item_match.group(5).replace('.', '').replace(',', '.'))
            }
            itens.append(item)
    
    if not itens:
        for linha in linhas:
            alt_match = re.search(
                r'([A-Za-z\s]{5,40})\s+(\d+[\.,]?\d*)\s+(?:un|kg|l|ml|g|pc|p|und)\s+[R\$\s]*([\d.,]+)',
                linha, re.IGNORECASE
            )
            if alt_match:
                item = {
                    "codigo": None,
                    "descricao": alt_match.group(1).strip(),
                    "quantidade": float(alt_match.group(2).replace(',', '.')),
                    "valor_unitario": None,
                    "valor_total": float(alt_match.group(3).replace('.', '').replace(',', '.'))
                }
                itens.append(item)
    
    return itens


def extract_tributos(text: str) -> dict:
    """Extrai informações de tributos da nota fiscal"""
    tributos = {}
    
    icms_match = re.search(r'ICMS[^\d]*R\$\s*([\d.,]+)', text, re.IGNORECASE)
    if icms_match:
        valor = icms_match.group(1).replace('.', '').replace(',', '.')
        tributos["icms"] = float(valor)
    
    ipi_match = re.search(r'IPI[^\d]*R\$\s*([\d.,]+)', text, re.IGNORECASE)
    if ipi_match:
        valor = ipi_match.group(1).replace('.', '').replace(',', '.')
        tributos["ipi"] = float(valor)
    
    pis_match = re.search(r'PIS[^\d]*R\$\s*([\d.,]+)', text, re.IGNORECASE)
    if pis_match:
        valor = pis_match.group(1).replace('.', '').replace(',', '.')
        tributos["pis"] = float(valor)
    
    cofins_match = re.search(r'COFINS[^\d]*R\$\s*([\d.,]+)', text, re.IGNORECASE)
    if cofins_match:
        valor = cofins_match.group(1).replace('.', '').replace(',', '.')
        tributos["cofins"] = float(valor)
    
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
    """Helper to create a Vercel response"""
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
    """Extract and validate user from Authorization header"""
    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    payload = decode_token(token)
    
    if payload is None:
        return None
    
    username = payload.get("sub")
    if username is None:
        return None
    
    return fake_users_db.get(username)


# ============== API ROUTE HANDLERS ==============
def handler(request):
    """Main handler for Vercel serverless function"""
    
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return get_response(200, {"message": "OK"})
    
    path = request.url.path
    method = request.method
    
    # Get headers
    headers = dict(request.headers)
    
    # Route: /api/token - POST (login)
    if path == "/api/token" and method == "POST":
        return handle_login(request)
    
    # Route: /api/extract - POST (extract PDF)
    if path == "/api/extract" and method == "POST":
        return handle_extract(request, headers)
    
    # Route: /api/health - GET
    if path == "/api/health" and method == "GET":
        return get_response(200, {"message": "API está funcionando corretamente"})
    
    # Route: /api/ - GET (root)
    if (path == "/api/" or path == "/api") and method == "GET":
        return get_response(200, {"message": "API de Extração de Notas Fiscais"})
    
    # 404 Not Found
    return get_response(404, {"detail": "Endpoint não encontrado"})


def handle_login(request):
    """Handle POST /api/token"""
    try:
        # Parse form data from body
        body = request.body
        if isinstance(body, bytes):
            body = body.decode('utf-8')
        
        # Parse as form data (username=xxx&password=xxx)
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
        
        return get_response(200, {
            "access_token": access_token,
            "token_type": "bearer"
        })
    
    except Exception as e:
        return get_response(500, {"detail": str(e)})


def handle_extract(request, headers):
    """Handle POST /api/extract"""
    # Check authentication
    user = get_auth_user(headers)
    if not user:
        return get_response(401, {"detail": "Não autenticado"}, {"WWW-Authenticate": "Bearer"})
    
    try:
        # Get content type
        content_type = headers.get("content-type", "")
        
        if "multipart/form-data" not in content_type:
            return get_response(400, {"detail": "O arquivo deve ser enviado como multipart/form-data"})
        
        # Parse the multipart body
        body = request.body
        if isinstance(body, bytes):
            body = body
        
        # Extract file from multipart
        # Simple approach: find the PDF data between boundaries
        try:
            # Look for PDF file in body
            # This is a simplified parser - in production use a proper multipart parser
            boundary = content_type.split("boundary=")[-1].encode() if "boundary=" in content_type else b""
            
            if boundary:
                parts = body.split(b"--" + boundary)
                for part in parts:
                    if b"Content-Type: application/pdf" in part or b"Content-Type: application/octet-stream" in part:
                        # Extract PDF content (after headers)
                        header_end = part.find(b"\r\n\r\n")
                        if header_end > 0:
                            pdf_bytes = part[header_end + 4:]
                            # Remove trailing boundary markers
                            pdf_bytes = pdf_bytes.split(b"\r\n--")[0]
                            
                            # Extract data
                            data = extract_data_from_pdf(pdf_bytes)
                            
                            return get_response(200, {
                                "success": True,
                                "message": "Dados extraídos com sucesso",
                                "data": data
                            })
            
            # If no PDF found in multipart, try base64 encoding
            # For Vercel, files might be sent as base64 in JSON
            try:
                body_json = json.loads(body.decode('utf-8'))
                if "file" in body_json:
                    pdf_bytes = base64.b64decode(body_json["file"])
                    data = extract_data_from_pdf(pdf_bytes)
                    return get_response(200, {
                        "success": True,
                        "message": "Dados extraídos com sucesso",
                        "data": data
                    })
            except:
                pass
            
            return get_response(400, {"detail": "Nenhum arquivo PDF encontrado no request"})
            
        except ValueError as e:
            return get_response(400, {"detail": str(e)})
        except Exception as e:
            return get_response(500, {"detail": f"Erro ao processar o PDF: {str(e)}"})
    
    except Exception as e:
        return get_response(500, {"detail": str(e)})

