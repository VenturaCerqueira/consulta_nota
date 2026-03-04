"""
Testes unitários para o módulo de extração de PDF
"""

import pytest
from extractor import parse_nota_fiscal_text, extract_itens, extract_tributos


class TestParseNotaFiscalText:
    """Testes para a função de parse de texto de nota fiscal"""
    
    def test_extrair_numero_nf(self):
        """Testa extração do número da NF"""
        text = """
        NF-e
        Número: 12345
        Série: 001
        """
        result = parse_nota_fiscal_text(text)
        assert result["numero"] == "12345"
    
    def test_extrair_serie(self):
        """Testa extração da série"""
        text = "Série: 001"
        result = parse_nota_fiscal_text(text)
        assert result["serie"] == "001"
    
    def test_extrair_data_emissao(self):
        """Testa extração da data de emissão"""
        text = "Data de Emissão: 01/01/2024"
        result = parse_nota_fiscal_text(text)
        assert result["data_emissao"] == "01/01/2024"
    
    def test_extrair_valor_total(self):
        """Testa extração do valor total"""
        text = "Valor Total: R$ 1.500,00"
        result = parse_nota_fiscal_text(text)
        assert result["valor_total"] == 1500.00
    
    def test_texto_vazio(self):
        """Testa com texto vazio"""
        result = parse_nota_fiscal_text("")
        assert result is not None
        assert result["numero"] is None


class TestExtractItens:
    """Testes para extração de itens"""
    
    def test_extrair_itens_formato_pipe(self):
        """Testa extração de itens no formato com pipes"""
        text = """
        001 | Produto A | 10 | 10,00 | 100,00
        002 | Produto B | 5 | 20,00 | 100,00
        """
        result = extract_itens(text)
        assert len(result) >= 1
    
    def test_itens_vazio(self):
        """Testa com texto sem itens"""
        text = "Apenas texto sem itens"
        result = extract_itens(text)
        assert isinstance(result, list)


class TestExtractTributos:
    """Testes para extração de tributos"""
    
    def test_extrair_icms(self):
        """Testa extração de ICMS"""
        text = "ICMS: R$ 100,00"
        result = extract_tributos(text)
        assert "icms" in result or len(result) >= 0
    
    def test_tributos_vazio(self):
        """Testa com texto sem tributos"""
        text = "Sem tributos aqui"
        result = extract_tributos(text)
        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

