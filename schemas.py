"""
Schemas de validação da API

Define os modelos Pydantic para entrada e saída de dados.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Emitente(BaseModel):
    """Schema para informações do emitente"""
    cnpj_cpf: Optional[str] = Field(None, description="CNPJ ou CPF do emitente")
    nome: Optional[str] = Field(None, description="Nome ou razão social do emitente")
    endereco: Optional[str] = Field(None, description="Endereço do emitente")
    municipio: Optional[str] = Field(None, description="Município do emitente")
    uf: Optional[str] = Field(None, description="UF do emitente")


class Destinatario(BaseModel):
    """Schema para informações do destinatário"""
    cnpj_cpf: Optional[str] = Field(None, description="CNPJ ou CPF do destinatário")
    nome: Optional[str] = Field(None, description="Nome ou razão social do destinatário")
    endereco: Optional[str] = Field(None, description="Endereço do destinatário")
    municipio: Optional[str] = Field(None, description="Município do destinatário")
    uf: Optional[str] = Field(None, description="UF do destinatário")


class Item(BaseModel):
    """Schema para itens da nota fiscal"""
    codigo: Optional[str] = Field(None, description="Código do produto/serviço")
    descricao: Optional[str] = Field(None, description="Descrição do produto/serviço")
    quantidade: Optional[float] = Field(None, description="Quantidade")
    valor_unitario: Optional[float] = Field(None, description="Valor unitário")
    valor_total: Optional[float] = Field(None, description="Valor total do item")


class NotaFiscalData(BaseModel):
    """Schema para dados extraídos da nota fiscal"""
    numero: Optional[str] = Field(None, description="Número da nota fiscal")
    serie: Optional[str] = Field(None, description="Série da nota fiscal")
    data_emissao: Optional[str] = Field(None, description="Data de emissão")
    emitente: Emitente = Field(default_factory=Emitente, description="Informações do emitente")
    destinatario: Destinatario = Field(default_factory=Destinatario, description="Informações do destinatário")
    valor_total: Optional[float] = Field(None, description="Valor total da nota")
    itens: List[Item] = Field(default_factory=list, description="Itens da nota fiscal")
    tributos: Dict[str, Any] = Field(default_factory=dict, description="Tributos")
    raw_text: Optional[str] = Field(None, description="Texto raw extraído do PDF")


class NotaFiscalResponse(BaseModel):
    """Schema para resposta da extração de nota fiscal"""
    success: bool = Field(..., description="Indica se a extração foi bem sucedida")
    message: str = Field(..., description="Mensagem de retorno")
    data: Optional[NotaFiscalData] = Field(None, description="Dados extraídos da nota")


class Token(BaseModel):
    """Schema para resposta do token de acesso"""
    access_token: str = Field(..., description="Token de acesso JWT")
    token_type: str = Field(..., description="Tipo do token (bearer)")


class MessageResponse(BaseModel):
    """Schema para resposta simples de mensagem"""
    message: str = Field(..., description="Mensagem de retorno")


class ErrorResponse(BaseModel):
    """Schema para resposta de erro"""
    detail: str = Field(..., description="Detalhes do erro")

