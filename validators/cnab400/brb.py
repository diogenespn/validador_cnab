"""Validações específicas do CNAB 400 do Banco de Brasília (BRB) – versão 075."""

from datetime import datetime

from ..base import BANCOS_CNAB, ESTADOS_BR, limpar_numero
from .utils import _campo_cnab400, _formatar_data_br, _parse_valor_cnab400

INSTRUCOES_PERMITIDAS = {
    "00", "01", "02", "03", "04", "05", "06", "08", "09", "13", "94"
}


def _parse_data_ddmmaaaa(valor: str):
    valor = (valor or "").strip()
    if len(valor) != 8 or not valor.isdigit():
        return None
    d, m, a = int(valor[:2]), int(valor[2:4]), int(valor[4:])
    try:
        return datetime(a, m, d)
    except ValueError:
        return None


def validar_cnab400_brb(linhas):
    erros_header = []
    erros_registros = []
    avisos = []
    titulos = []
    resumo = {
        "qtd_titulos": 0,
        "valor_total_centavos": 0,
        "valor_total_reais": 0.0,
        "vencimento_min": None,
        "vencimento_max": None,
    }

    if not linhas:
        erros_header.append("Arquivo vazio.")
        return {
            "codigo_banco": "070",
            "nome_banco": BANCOS_CNAB.get("070", "Banco de Brasília"),
            "erros_header": erros_header,
            "erros_registros": erros_registros,
            "erros_trailer": [],
            "avisos": avisos,
            "titulos": titulos,
            "resumo": resumo,
            "header_info": None,
        }

    # Header
    header = linhas[0].rstrip("\r\n")
    if len(header) != 400:
        erros_header.append(
            f"Header deve conter 400 posições, encontrado {len(header)}."
        )

    literal = _campo_cnab400(header, 1, 3)
    if literal != "DCB":
        erros_header.append("Header: Literal DCB (pos. 001-003) deve ser 'DCB'.")

    versao = _campo_cnab400(header, 4, 6)
    if versao != "001":
        erros_header.append("Header: Versão (pos. 004-006) deve ser '001'.")

    arquivo = _campo_cnab400(header, 7, 9)
    if arquivo != "075":
        erros_header.append("Header: Arquivo (pos. 007-009) deve ser '075'.")

    codigo_benef = _campo_cnab400(header, 10, 19)
    if not codigo_benef.isdigit() or len(codigo_benef) != 10:
        erros_header.append("Header: Código do Beneficiário (pos. 010-019) deve ter 10 dígitos.")

    data_fmt = _campo_cnab400(header, 20, 27)
    dt_fmt = _parse_data_ddmmaaaa(data_fmt)
    if not dt_fmt:
        erros_header.append("Header: Data de Formatação (pos. 020-027) deve estar em AAAAMMDD.")

    hora_fmt = _campo_cnab400(header, 28, 33)
    if not (len(hora_fmt) == 6 and hora_fmt.isdigit()):
        erros_header.append("Header: Hora da Formatação (pos. 028-033) deve conter 6 dígitos (HHMMSS).")
    else:
        hh, mm, ss = int(hora_fmt[:2]), int(hora_fmt[2:4]), int(hora_fmt[4:])
        if not (0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59):
            erros_header.append("Header: Hora da Formatação fora do intervalo válido (HHMMSS).")

    qtd_reg_header = _campo_cnab400(header, 34, 39)
    if not qtd_reg_header.isdigit():
        erros_header.append("Header: Quantidade de Registros (pos. 034-039) deve ser numérica.")
    qtd_reg_informada = int(qtd_reg_header) if qtd_reg_header.isdigit() else None

    header_info = {
        "codigo_banco": "070",
        "nome_banco": BANCOS_CNAB.get("070", "Banco de Brasília"),
        "agencia": "",
        "conta": codigo_benef,
        "data_gravacao": dt_fmt.date() if dt_fmt else None,
    }

    # Registros de detalhe (não há trailer)
    for numero_linha, linha in enumerate(linhas[1:], start=2):
        if not linha or linha.strip() == "":
            continue
        registro = linha.rstrip("\r\n")
        if len(registro) != 400:
            erros_registros.append(
                f"Linha {numero_linha}: registro deve conter 400 posições, encontrado {len(registro)}."
            )
            continue

        ident = _campo_cnab400(registro, 1, 2)
        if ident != "01":
            erros_registros.append(
                f"Linha {numero_linha}: Identificação do Registro (pos. 001-002) deve ser '01'."
            )

        conta_benef = _campo_cnab400(registro, 3, 12)
        if not conta_benef.isdigit() or len(conta_benef) != 10:
            erros_registros.append(
                f"Linha {numero_linha}: Código do Beneficiário (pos. 003-012) deve ter 10 dígitos."
            )
        elif codigo_benef.isdigit() and conta_benef != codigo_benef:
            avisos.append(
                f"Linha {numero_linha}: conta do beneficiário diverge do header ({conta_benef} x {codigo_benef})."
            )

        doc_pagador = _campo_cnab400(registro, 13, 26).strip()
        tipo_pessoa = _campo_cnab400(registro, 122, 122)
        doc_limpo = limpar_numero(doc_pagador)
        if tipo_pessoa not in {"1", "2"}:
            erros_registros.append(
                f"Linha {numero_linha}: Código Tipo Pessoa (pos. 122) deve ser 1=CPF ou 2=CNPJ."
            )
        else:
            if tipo_pessoa == "1" and len(doc_limpo) != 11:
                erros_registros.append(
                    f"Linha {numero_linha}: CPF do pagador deve ter 11 dígitos."
                )
            if tipo_pessoa == "2" and len(doc_limpo) != 14:
                erros_registros.append(
                    f"Linha {numero_linha}: CNPJ do pagador deve ter 14 dígitos."
                )

        nome_pag = _campo_cnab400(registro, 27, 61).strip()
        if not nome_pag:
            erros_registros.append(
                f"Linha {numero_linha}: Nome do Pagador (pos. 027-061) é obrigatório."
            )

        endereco_pag = _campo_cnab400(registro, 62, 96).strip()
        cidade_pag = _campo_cnab400(registro, 97, 111).strip()
        if not endereco_pag:
            avisos.append(
                f"Linha {numero_linha}: Endereço do Pagador (pos. 062-096) em branco."
            )
        if not cidade_pag:
            avisos.append(
                f"Linha {numero_linha}: Cidade do Pagador (pos. 097-111) em branco."
            )

        uf = _campo_cnab400(registro, 112, 113).upper()
        if uf and uf not in ESTADOS_BR:
            erros_registros.append(
                f"Linha {numero_linha}: UF do Pagador (pos. 112-113) inválida."
            )

        cep = _campo_cnab400(registro, 114, 121)
        if not (len(cep) == 8 and cep.isdigit()) or cep == "00000000":
            erros_registros.append(
                f"Linha {numero_linha}: CEP do Pagador (pos. 114-121) deve conter 8 dígitos válidos."
            )

        seu_numero = _campo_cnab400(registro, 123, 135).strip()
        if not seu_numero:
            erros_registros.append(
                f"Linha {numero_linha}: Número do Documento/Seu Número (pos. 123-135) é obrigatório."
            )

        modalidade = _campo_cnab400(registro, 136, 136)
        if modalidade not in {"1", "2", "3"}:
            erros_registros.append(
                f"Linha {numero_linha}: Modalidade da Cobrança (pos. 136) deve ser 1, 2 ou 3."
            )

        data_emissao = _parse_data_ddmmaaaa(_campo_cnab400(registro, 137, 144))
        if not data_emissao:
            erros_registros.append(
                f"Linha {numero_linha}: Data de Emissão do Título (pos. 137-144) inválida."
            )

        tipo_doc = _campo_cnab400(registro, 145, 146)
        if tipo_doc not in {"21", "22", "25", "31", "32", "39"}:
            erros_registros.append(
                f"Linha {numero_linha}: Código Tipo Documento (pos. 145-146) fora da lista permitida."
            )

        natureza = _campo_cnab400(registro, 147, 147)
        if natureza != "0":
            erros_registros.append(
                f"Linha {numero_linha}: Código da Natureza (pos. 147) deve ser 0."
            )

        cond_pagto = _campo_cnab400(registro, 148, 148)
        if cond_pagto != "0":
            erros_registros.append(
                f"Linha {numero_linha}: Código da Condição Pagto (pos. 148) deve ser 0 (No vencimento)."
            )

        moeda = _campo_cnab400(registro, 149, 150)
        if moeda != "02":
            erros_registros.append(
                f"Linha {numero_linha}: Código da Moeda (pos. 149-150) deve ser 02 (Real)."
            )

        numero_banco = _campo_cnab400(registro, 151, 153)
        if numero_banco != "070":
            erros_registros.append(
                f"Linha {numero_linha}: Número do Banco (pos. 151-153) deve ser 070."
            )

        ag_cobradora = _campo_cnab400(registro, 154, 157)
        if not (ag_cobradora.isdigit() and len(ag_cobradora) == 4):
            erros_registros.append(
                f"Linha {numero_linha}: Agência Cobradora (pos. 154-157) deve conter 4 dígitos."
            )

        praca = _campo_cnab400(registro, 158, 187).strip()
        if not praca:
            avisos.append(
                f"Linha {numero_linha}: Praça de Cobrança (pos. 158-187) em branco."
            )

        vencimento = _parse_data_ddmmaaaa(_campo_cnab400(registro, 188, 195))
        if not vencimento:
            erros_registros.append(
                f"Linha {numero_linha}: Data de Vencimento (pos. 188-195) inválida."
            )

        valor_titulo = _parse_valor_cnab400(_campo_cnab400(registro, 196, 209))
        if valor_titulo is None:
            erros_registros.append(
                f"Linha {numero_linha}: Valor do Título (pos. 196-209) deve conter dígitos."
            )
            valor_titulo = 0
        elif valor_titulo <= 0:
            erros_registros.append(
                f"Linha {numero_linha}: Valor do Título deve ser maior que zero."
            )

        nosso_numero = _campo_cnab400(registro, 210, 221)
        if not (len(nosso_numero) == 12 and nosso_numero.isdigit()):
            erros_registros.append(
                f"Linha {numero_linha}: Nosso Número (pos. 210-221) deve ter 12 dígitos."
            )
        else:
            if nosso_numero[1:7].strip("0") == "":
                avisos.append(
                    f"Linha {numero_linha}: Nosso Número parece zerado no trecho de sequencial (pos. 002-007)."
                )
            if nosso_numero[7:10] != "070":
                erros_registros.append(
                    f"Linha {numero_linha}: Nosso Número deve conter '070' nas pos. 008-010."
                )

        tipo_juros = _campo_cnab400(registro, 222, 223)
        if tipo_juros not in {"00", "50", "51"}:
            erros_registros.append(
                f"Linha {numero_linha}: Código do Tipo de Juros (pos. 222-223) deve ser 00, 50 ou 51."
            )

        valor_juros = _parse_valor_cnab400(_campo_cnab400(registro, 224, 237))
        if valor_juros is None:
            erros_registros.append(
                f"Linha {numero_linha}: Valor do Juro (pos. 224-237) deve conter dígitos."
            )
        elif tipo_juros == "00" and valor_juros != 0:
            avisos.append(
                f"Linha {numero_linha}: Tipo de juros 00 exige valor zerado."
            )

        valor_abat = _parse_valor_cnab400(_campo_cnab400(registro, 238, 251))
        if valor_abat is None:
            erros_registros.append(
                f"Linha {numero_linha}: Valor do Abatimento (pos. 238-251) deve conter dígitos."
            )

        cod_desc = _campo_cnab400(registro, 252, 253)
        if cod_desc not in {"00", "52", "53"}:
            erros_registros.append(
                f"Linha {numero_linha}: Código do Desconto (pos. 252-253) deve ser 00, 52 ou 53."
            )

        data_desc_raw = _campo_cnab400(registro, 254, 261)
        data_desc = _parse_data_ddmmaaaa(data_desc_raw) if data_desc_raw.strip("0") else None
        if data_desc_raw.strip() and not data_desc and data_desc_raw != "00000000":
            erros_registros.append(
                f"Linha {numero_linha}: Data limite para Desconto (pos. 254-261) inválida."
            )

        valor_desc = _parse_valor_cnab400(_campo_cnab400(registro, 262, 275))
        if valor_desc is None:
            erros_registros.append(
                f"Linha {numero_linha}: Valor do Desconto (pos. 262-275) deve conter dígitos."
            )
        elif cod_desc == "00" and valor_desc != 0:
            avisos.append(
                f"Linha {numero_linha}: Código de desconto 00 deveria trazer valor zerado."
            )
        elif cod_desc in {"52", "53"} and valor_desc == 0:
            avisos.append(
                f"Linha {numero_linha}: Código de desconto {cod_desc} exige valor informado."
            )

        instr1 = _campo_cnab400(registro, 276, 277)
        prazo1 = _campo_cnab400(registro, 278, 279)
        if instr1 not in INSTRUCOES_PERMITIDAS:
            erros_registros.append(
                f"Linha {numero_linha}: Código da 1ª Instrução (pos. 276-277) inválido."
            )
        if prazo1 and not prazo1.isdigit():
            erros_registros.append(
                f"Linha {numero_linha}: Prazo da 1ª Instrução (pos. 278-279) deve ser numérico."
            )

        instr2 = _campo_cnab400(registro, 280, 281)
        prazo2 = _campo_cnab400(registro, 282, 283)
        if instr2 not in INSTRUCOES_PERMITIDAS:
            erros_registros.append(
                f"Linha {numero_linha}: Código da 2ª Instrução (pos. 280-281) inválido."
            )
        if prazo2 and not prazo2.isdigit():
            erros_registros.append(
                f"Linha {numero_linha}: Prazo da 2ª Instrução (pos. 282-283) deve ser numérico."
            )

        taxa_ref = _campo_cnab400(registro, 284, 288)
        if taxa_ref and not taxa_ref.isdigit():
            erros_registros.append(
                f"Linha {numero_linha}: Taxa ref. (pos. 284-288) deve conter dígitos."
            )

        emitente = _campo_cnab400(registro, 289, 328).strip()
        if not emitente:
            avisos.append(
                f"Linha {numero_linha}: Emitente do Título (pos. 289-328) em branco."
            )

        branco = _campo_cnab400(registro, 369, 397)
        if branco.strip():
            avisos.append(
                f"Linha {numero_linha}: campo reservado (pos. 369-397) deveria estar em branco."
            )

        titulos.append(
            {
                "lote": "",
                "sequencia": str(numero_linha - 1),
                "nosso_numero": nosso_numero.strip(),
                "seu_numero": seu_numero,
                "data_vencimento_str": _formatar_data_br(vencimento),
                "valor_centavos": valor_titulo or 0,
                "valor_reais": (valor_titulo or 0) / 100.0,
                "sacado_documento": doc_limpo,
                "sacado_nome": nome_pag,
                "sacado_endereco": endereco_pag,
                "sacado_bairro": "",
                "sacado_cep": cep,
                "sacado_cidade": cidade_pag,
                "sacado_uf": uf,
            }
        )

        resumo["qtd_titulos"] += 1
        resumo["valor_total_centavos"] += valor_titulo or 0
        if vencimento:
            if resumo["vencimento_min"] is None or vencimento < resumo["vencimento_min"]:
                resumo["vencimento_min"] = vencimento
            if resumo["vencimento_max"] is None or vencimento > resumo["vencimento_max"]:
                resumo["vencimento_max"] = vencimento

    total_registros_real = len([l for l in linhas if l.strip()])
    if qtd_reg_informada is not None and qtd_reg_informada != total_registros_real:
        erros_header.append(
            f"Header: Quantidade de Registros informada ({qtd_reg_informada}) difere do total real ({total_registros_real})."
        )

    resumo["valor_total_reais"] = resumo["valor_total_centavos"] / 100.0

    return {
        "codigo_banco": "070",
        "nome_banco": BANCOS_CNAB.get("070", "Banco de Brasília"),
        "erros_header": erros_header,
        "erros_registros": erros_registros,
        "erros_trailer": [],  # BRB não usa trailer
        "avisos": avisos,
        "titulos": titulos,
        "resumo": resumo,
        "header_info": header_info,
    }
