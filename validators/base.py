"""Shared utilities and helpers for CNAB validators."""

from datetime import datetime, timedelta

BANCOS_CNAB = {
    "001": "Banco do Brasil",
    "070": "Banco de Brasília (BRB)",
    "104": "Caixa Economica Federal",
    "208": "BTG Pactual",
    "237": "Bradesco",
    "341": "Itau Unibanco",
    "033": "Santander",
    "756": "Sicoob",
    "748": "Sicredi",
}

def detectar_layout(linhas):
    """
    Tenta identificar se o arquivo é CNAB 240 ou 400
    olhando o tamanho das linhas.
    """
    tamanhos = set(len(linha.rstrip("\n\r")) for linha in linhas if linha.strip() != "")

    if tamanhos == {240}:
        return 240
    elif tamanhos == {400}:
        return 400
    else:
        # Pode ter mistura ou linhas com tamanho errado
        return tamanhos  # retorna o conjunto de tamanhos encontrados

def validar_tamanho_linhas(linhas, layout_esperado):
    """
    Verifica se TODAS as linhas têm o tamanho correto (240 ou 400).
    Retorna lista de erros encontrados.
    """
    erros = []
    for numero_linha, linha in enumerate(linhas, start=1):
        tamanho = len(linha.rstrip("\n\r"))
        if tamanho != layout_esperado and linha.strip() != "":
            erros.append(
                f"Linha {numero_linha}: tamanho {tamanho}, esperado {layout_esperado}"
            )
    return erros

def identificar_banco(header_line):
    """
    Identifica o banco pelo código de compensação (posições 1 a 3 do arquivo, 3 dígitos).
    """
    codigo = header_line[0:3]

    nome = BANCOS_CNAB.get(codigo, "Banco não mapeado neste validador")
    return codigo, nome

def _parse_data_ddmmaaaa(valor):
    """
    Converte uma string DDMMAAAA em date.
    Retorna None se estiver vazia, com tamanho errado ou inválida.
    """
    if not valor or not valor.isdigit() or len(valor) != 8:
        return None
    dia = int(valor[0:2])
    mes = int(valor[2:4])
    ano = int(valor[4:8])
    try:
        return datetime(ano, mes, dia).date()
    except ValueError:
        return None

def limpar_numero(s: str) -> str:
    """
    Remove todos os caracteres que não são dígitos.
    """
    return "".join(ch for ch in (s or "") if ch.isdigit())

def validar_cpf(cpf: str) -> bool:
    cpf = limpar_numero(cpf)
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False

    soma = 0
    for i in range(9):
        soma += int(cpf[i]) * (10 - i)
    resto = (soma * 10) % 11
    if resto == 10:
        resto = 0
    if resto != int(cpf[9]):
        return False

    soma = 0
    for i in range(10):
        soma += int(cpf[i]) * (11 - i)
    resto = (soma * 10) % 11
    if resto == 10:
        resto = 0
    if resto != int(cpf[10]):
        return False

    return True

def validar_cnpj(cnpj: str) -> bool:
    cnpj = limpar_numero(cnpj)
    if len(cnpj) != 14:
        return False
    if cnpj == cnpj[0] * 14:
        return False

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1

    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    dv1 = 0 if resto < 2 else 11 - resto
    if dv1 != int(cnpj[12]):
        return False

    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    dv2 = 0 if resto < 2 else 11 - resto
    if dv2 != int(cnpj[13]):
        return False

    return True

def modulo10(numero: str) -> int:
    """
    Calcula o dígito verificador pelo módulo 10 (usado nos 3 primeiros campos da linha digitável).
    """
    soma = 0
    multiplicador = 2
    for d in reversed(numero):
        n = int(d)
        prod = n * multiplicador
        # se resultado tiver 2 dígitos, soma os dígitos
        if prod >= 10:
            prod = (prod // 10) + (prod % 10)
        soma += prod
        multiplicador = 1 if multiplicador == 2 else 2

    resto = soma % 10
    dv = (10 - resto) % 10
    return dv

def modulo11_boleto(numero: str) -> int:
    """
    Calcula o dígito verificador geral do boleto (módulo 11, conforme padrão FEBRABAN).
    Regra usual:
      - pesos de 2 a 9 (repetindo) da direita para a esquerda
      - DV = 11 - (soma % 11)
      - se resultado em [0, 1, 10, 11], utiliza-se '1' (padrão mais comum).
    """
    soma = 0
    peso = 2
    for d in reversed(numero):
        n = int(d)
        soma += n * peso
        peso += 1
        if peso > 9:
            peso = 2

    resto = soma % 11
    dv = 11 - resto
    if dv in (0, 1, 10, 11):
        dv = 1
    return dv

def validar_linha_digitavel_boleto(linha: str):
    """
    Valida uma linha digitável de boleto bancário (47 dígitos, padrão cobrança).

    Retorna (erros, infos), onde:
      - erros: lista de mensagens de erro (DV incorreto, tamanho, etc.)
      - infos: dicionário com dados extraídos (banco, valor, vencimento, código de barras, etc.)
    """
    erros = []
    infos = {}

    numeros = limpar_numero(linha)

    if len(numeros) != 47:
        erros.append(
            f"Tamanho inválido: esperado 47 dígitos, recebido {len(numeros)}."
        )
        return erros, infos

    d = numeros  # atalho

    # Campos da linha digitável (padrão 47 dígitos):
    # Campo 1:  1-9   + DV (10)
    # Campo 2: 11-20  + DV (21)
    # Campo 3: 22-31  + DV (32)
    # Campo 4: DV geral (33)
    # Campo 5: fator de vencimento (34-37) + valor (38-47)

    campo1 = d[0:9]
    dv1 = int(d[9])

    campo2 = d[10:20]
    dv2 = int(d[20])

    campo3 = d[21:31]
    dv3 = int(d[31])

    dv_geral = int(d[32])

    fator = d[33:37]
    valor_str = d[37:47]

    # 1) Validar DVs dos 3 campos com módulo 10
    if modulo10(campo1) != dv1:
        erros.append(
            f"Dígito verificador do Campo 1 inválido. Esperado {modulo10(campo1)}, encontrado {dv1}."
        )

    if modulo10(campo2) != dv2:
        erros.append(
            f"Dígito verificador do Campo 2 inválido. Esperado {modulo10(campo2)}, encontrado {dv2}."
        )

    if modulo10(campo3) != dv3:
        erros.append(
            f"Dígito verificador do Campo 3 inválido. Esperado {modulo10(campo3)}, encontrado {dv3}."
        )

    # 2) Montar código de barras (44 dígitos) a partir da linha digitável
    # Estrutura (boleto bancário padrão):
    #   - banco: d[0:3]
    #   - moeda: d[3]
    #   - DV geral: d[32]
    #   - fator: d[33:37]
    #   - valor: d[37:47]
    #   - campo livre: d[4:9] + d[10:20] + d[21:31]
    banco = d[0:3]
    moeda = d[3]
    campo_livre = d[4:9] + d[10:20] + d[21:31]

    codigo_barras_sem_dv = banco + moeda + fator + valor_str + campo_livre
    # banco(3) + moeda(1) + fator(4) + valor(10) + campo livre(25) => 43 dígitos
    if len(codigo_barras_sem_dv) != 43:
        erros.append(
            "Falha ao montar código de barras (tamanho diferente de 43 sem DV)."
        )
        return erros, infos

    dv_geral_calculado = modulo11_boleto(codigo_barras_sem_dv)
    if dv_geral_calculado != dv_geral:
        erros.append(
            f"Dígito verificador geral inválido. Esperado {dv_geral_calculado}, encontrado {dv_geral}."
        )

    # Monta o código de barras completo (44 dígitos)
    codigo_barras = banco + moeda + str(dv_geral) + fator + valor_str + campo_livre
    infos["codigo_barras"] = codigo_barras
    infos["banco"] = banco
    infos["moeda"] = moeda

    # 3) Interpretar fator de vencimento
    if fator == "0000":
        infos["vencimento"] = "Sem data de vencimento (fator 0000)"
    else:
        try:
            base = datetime(1997, 10, 7)
            dias = int(fator)
            dt = base + timedelta(days=dias)
            infos["vencimento"] = dt.strftime("%d/%m/%Y")
        except Exception:
            erros.append(f"Fator de vencimento '{fator}' inválido.")
            infos["vencimento"] = None

    # 4) Interpretar valor
    if valor_str.isdigit():
        valor_centavos = int(valor_str)
        infos["valor_centavos"] = valor_centavos
        infos["valor_reais"] = valor_centavos / 100.0
    else:
        erros.append(f"Valor '{valor_str}' não é numérico.")
        infos["valor_centavos"] = None
        infos["valor_reais"] = None

    return erros, infos

ESTADOS_BR = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES",
    "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
    "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}
