"""
Módulo de extração de dados de PDF

Responsável por extrair dados de notas fiscais em PDF.
Utiliza pdfplumber para extração do conteúdo.
"""

import io
import re
from typing import Dict, Any, List, Optional
import pdfplumber


def extract_data_from_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Extrai dados de uma nota fiscal em PDF
    
    Args:
        pdf_bytes: Conteúdo do arquivo PDF em bytes
        
    Returns:
        Dicionário com os dados extraídos da nota fiscal
        
    Raises:
        ValueError: Se o PDF for inválido ou não contiver uma nota fiscal
    """
    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as e:
        raise ValueError(f"Erro ao abrir o PDF: {str(e)}")
    
    if len(pdf.pages) == 0:
        raise ValueError("O PDF não contém páginas")
    
    # Extrair texto de todas as páginas
    full_text = ""
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"
    
    # Se não conseguiu extrair texto, pode ser uma imagem
    if not full_text.strip():
        raise ValueError(
            "Não foi possível extrair texto do PDF. "
            "O documento pode ser uma imagem ou estar protegido."
        )
    
    pdf.close()
    
    # Processar o texto extraído
    data = parse_nota_fiscal_text(full_text)
    
    return data


def parse_nota_fiscal_text(text: str) -> Dict[str, Any]:
    """
    Parseia o texto extraído para extrair campos específicos da nota fiscal
    
    Args:
        text: Texto completo extraído do PDF
        
    Returns:
        Dicionário com campos da nota fiscal
    """
    # Normalizar texto
    text = text.strip()
    
    # Dicionário para armazenar os dados extraídos
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
        "raw_text": text[:1000]  # Primeiros 1000 caracteres para referência
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
    
    # Tentar formato alternativo de data (YYYY-MM-DD)
    if not data["data_emissao"]:
        data_emissao_match = re.search(
            r'(\d{4}[\/\-]\d{2}[\/\-]\d{2})',
            text
        )
        if data_emissao_match:
            data["data_emissao"] = data_emissao_match.group(1)
    
    # Extrair CNPJ/CPF do emitente
    cnpj_emitente_match = re.search(
        r'(?:CNPJ|CPF)[^\d]*(\d{2}\.?\d{3}\.?\d{3}\.?\d{4}\.?\d{2}|\d{3}\.?\d{3}\.?\d{3}\-?\d{2})',
        text,
        re.IGNORECASE
    )
    if cnpj_emitente_match:
        data["emitente"]["cnpj_cpf"] = cnpj_emitente_match.group(1)
    
    # Extrair nome do emitente (procura após "Emitente" ou "Fornecedor")
    emitente_match = re.search(
        r'(?:Emitente|Fornecedor|Vendedor)[\s:]*([^\n]{3,60})',
        text,
        re.IGNORECASE
    )
    if emitente_match:
        nome_emitente = emitente_match.group(1).strip()
        # Limpar o nome
        nome_emitente = re.sub(r'^(CNPJ|CPF)', '', nome_emitente, flags=re.IGNORECASE).strip()
        data["emitente"]["nome"] = nome_emitente
    
    # Extrair CNPJ/CPF do destinatário
    cnpj_dest_match = re.search(
        r'(?:Destinatário|Comprador|Cliente)[^\d]*(\d{2}\.?\d{3}\.?\d{3}\.?\d{4}\.?\d{2}|\d{3}\.?\d{3}\.?\d{3}\-?\d{2})',
        text,
        re.IGNORECASE
    )
    if cnpj_dest_match:
        data["destinatario"]["cnpj_cpf"] = cnpj_dest_match.group(1)
    
    # Extrair nome do destinatário
    destinatario_match = re.search(
        r'(?:Destinatário|Comprador|Cliente)[\s:]*([^\n]{3,60})',
        text,
        re.IGNORECASE
    )
    if destinatario_match:
        nome_dest = destinatario_match.group(1).strip()
        nome_dest = re.sub(r'^(CNPJ|CPF)', '', nome_dest, flags=re.IGNORECASE).strip()
        data["destinatario"]["nome"] = nome_dest
    
    # Extrair valor total
    valor_total_match = re.search(
        r'(?:Valor\s*Total|Valor\s*a\s*Pagar|Total\s*a\s*Pagar|Valor\s*Liquido)[^\d]*R\$\s*([\d.,]+)',
        text,
        re.IGNORECASE
    )
    if valor_total_match:
        valor = valor_total_match.group(1).replace('.', '').replace(',', '.')
        data["valor_total"] = float(valor)
    
    # Se não encontrou, tentar outro padrão
    if not data["valor_total"]:
        valor_total_match = re.search(
            r'TOTAL\s*[:\-]?\s*R\$\s*([\d.,]+)',
            text,
            re.IGNORECASE
        )
        if valor_total_match:
            valor = valor_total_match.group(1).replace('.', '').replace(',', '.')
            data["valor_total"] = float(valor)
    
    # Extrair itens da nota (produtos/serviços)
    itens = extract_itens(text)
    data["itens"] = itens
    
    # Extrair tributos
    tributos = extract_tributos(text)
    data["tributos"] = tributos
    
    return data


def extract_itens(text: str) -> List[Dict[str, Any]]:
    """
    Extrai os itens/produtos da nota fiscal
    
    Args:
        text: Texto completo da nota fiscal
        
    Returns:
        Lista de dicionários com os itens
    """
    itens = []
    
    # Padrão para itens de nota fiscal (formato comum)
    # Procura por linhas que contenham código, descrição e valores
    linhas = text.split('\n')
    
    for linha in linhas:
        # Verificar se a linha parece ser um item
        # Formato comum: código | descrição | quantidade | valor unitário | valor total
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
    
    # Se não encontrou nenhum item com o padrão acima, tentar outro formato
    if not itens:
        # Padrão alternativo: descrição seguida de valores
        for linha in linhas:
            # Procura por linhas com descrição e valor
            alt_match = re.search(
                r'([A-Za-z\s]{5,40})\s+(\d+[\.,]?\d*)\s+(?:un|kg|l|ml|g|pc|p|und)\s+[R\$\s]*([\d.,]+)',
                linha,
                re.IGNORECASE
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


def extract_tributos(text: str) -> Dict[str, Any]:
    """
    Extrai informações de tributos da nota fiscal
    
    Args:
        text: Texto completo da nota fiscal
        
    Returns:
        Dicionário com informações de tributos
    """
    tributos = {}
    
    # Extrair valor do ICMS
    icms_match = re.search(
        r'ICMS[^\d]*R\$\s*([\d.,]+)',
        text,
        re.IGNORECASE
    )
    if icms_match:
        valor = icms_match.group(1).replace('.', '').replace(',', '.')
        tributos["icms"] = float(valor)
    
    # Extrair valor do IPI
    ipi_match = re.search(
        r'IPI[^\d]*R\$\s*([\d.,]+)',
        text,
        re.IGNORECASE
    )
    if ipi_match:
        valor = ipi_match.group(1).replace('.', '').replace(',', '.')
        tributos["ipi"] = float(valor)
    
    # Extrair valor do PIS
    pis_match = re.search(
        r'PIS[^\d]*R\$\s*([\d.,]+)',
        text,
        re.IGNORECASE
    )
    if pis_match:
        valor = pis_match.group(1).replace('.', '').replace(',', '.')
        tributos["pis"] = float(valor)
    
    # Extrair valor do COFINS
    cofins_match = re.search(
        r'COFINS[^\d]*R\$\s*([\d.,]+)',
        text,
        re.IGNORECASE
    )
    if cofins_match:
        valor = cofins_match.group(1).replace('.', '').replace(',', '.')
        tributos["cofins"] = float(valor)
    
    return tributos

