"""Fun??es utilit?rias compartilhadas entre validadores CNAB 400."""

from datetime import datetime

def _campo_cnab400(linha: str, pos_inicio: int, pos_fim: int) -> str:
    """
    Retorna o trecho da linha entre as posições informadas (1-based, inclusive).
    """
    if pos_inicio < 1 or pos_fim < pos_inicio:
        return ""
    if len(linha) < pos_inicio:
        return ""
    fim = min(pos_fim, len(linha))
    return linha[pos_inicio - 1:fim]

def _parse_data_cnab400(valor: str):
    valor = (valor or "").strip()
    if not valor or valor == "000000" or len(valor) != 6 or not valor.isdigit():
        return None
    dia = int(valor[0:2])
    mes = int(valor[2:4])
    ano = int(valor[4:6])
    ano_full = 1900 + ano if ano >= 70 else 2000 + ano
    try:
        return datetime(ano_full, mes, dia)
    except ValueError:
        return None

def _formatar_data_br(dt):
    if not dt:
        return None
    return dt.strftime("%d/%m/%Y")

def _parse_valor_cnab400(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return 0
    if not raw.isdigit():
        return None
    return int(raw)
