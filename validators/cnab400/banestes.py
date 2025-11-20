"""Validações básicas do CNAB 400 do Banestes."""

from collections import Counter
from ..base import BANCOS_CNAB, limpar_numero
from .utils import _campo_cnab400, _formatar_data_br, _parse_data_cnab400, _parse_valor_cnab400

BANESTES_CODIGO_BANCO = "021"


def validar_cnab400_banestes(linhas):
    erros_header = []
    erros_registros = []
    erros_trailer = []
    avisos = []
    titulos = []

    resumo = {
        "qtd_titulos": 0,
        "valor_total_centavos": 0,
        "valor_total_reais": 0.0,
        "vencimento_min": None,
        "vencimento_max": None,
        "qtd_registros_tipo5": 0,
        "comandos": [],
        "carteiras": [],
    }

    header_info = None
    ultimo_seq = 0
    trailer_processado = False
    contagem_comandos = Counter()
    contagem_carteiras = Counter()

    for numero_linha, linha in enumerate(linhas, start=1):
        if not linha or linha.strip() == "":
            continue

        registro = linha.rstrip("\r\n")
        if len(registro) < 400:
            erros_registros.append(
                f"Linha {numero_linha}: registro com menos de 400 caracteres."
            )
            continue

        tipo = registro[0:1]

        seq_raw = _campo_cnab400(registro, 395, 400).strip()
        if seq_raw and seq_raw.isdigit():
            seq = int(seq_raw)
            if ultimo_seq and seq != ultimo_seq + 1:
                erros_registros.append(
                    f"Linha {numero_linha}: sequencia {seq:06d} fora da ordem esperada ({ultimo_seq + 1:06d})."
                )
            ultimo_seq = seq
        else:
            erros_registros.append(
                f"Linha {numero_linha}: sequencia (pos. 395-400) invalida ou vazia."
            )

        if tipo == "0":
            if header_info:
                erros_header.append(
                    "Foi encontrado mais de um registro header no arquivo CNAB 400."
                )
                continue

            codigo_banco = _campo_cnab400(registro, 77, 79)
            if codigo_banco != BANESTES_CODIGO_BANCO:
                erros_header.append(
                    f"Header: codigo do banco (pos. 077-079) deve ser {BANESTES_CODIGO_BANCO}."
                )

            nome_benef = _campo_cnab400(registro, 47, 76).strip()
            agencia = _campo_cnab400(registro, 27, 30).strip()
            agencia_dv = _campo_cnab400(registro, 31, 31).strip()
            conta = _campo_cnab400(registro, 32, 39).strip()
            conta_dv = _campo_cnab400(registro, 40, 40).strip()
            data_gravacao = _parse_data_cnab400(_campo_cnab400(registro, 95, 100))
            sequencial_remessa = _campo_cnab400(registro, 111, 117).strip()
            documento = limpar_numero(_campo_cnab400(registro, 18, 31))

            header_info = {
                "nome_beneficiario": nome_benef,
                "agencia": agencia,
                "agencia_dv": agencia_dv,
                "conta": conta,
                "conta_dv": conta_dv,
                "numero_convenio_lider": None,
                "sequencial_remessa": sequencial_remessa,
                "data_gravacao": data_gravacao.date() if data_gravacao else None,
                "codigo_banco": codigo_banco or BANESTES_CODIGO_BANCO,
                "nome_banco": BANCOS_CNAB.get(codigo_banco, "Banestes"),
                "documento": documento,
            }

        elif tipo == "1":
            nosso_numero = _campo_cnab400(registro, 64, 80).strip()
            if not nosso_numero:
                nosso_numero = _campo_cnab400(registro, 48, 56).strip()

            seu_numero = _campo_cnab400(registro, 111, 120).strip()
            data_venc = _parse_data_cnab400(_campo_cnab400(registro, 121, 126))
            valor_centavos = _parse_valor_cnab400(_campo_cnab400(registro, 127, 139)) or 0
            comando = _campo_cnab400(registro, 109, 110).strip()
            carteira = _campo_cnab400(registro, 107, 108).strip()
            doc_pagador = limpar_numero(_campo_cnab400(registro, 220, 233))
            nome_pagador = _campo_cnab400(registro, 234, 274).strip()

            titulos.append(
                {
                    "lote": "",
                    "sequencia": seq_raw,
                    "nosso_numero": nosso_numero,
                    "seu_numero": seu_numero,
                    "data_vencimento_str": _formatar_data_br(data_venc),
                    "valor_centavos": valor_centavos,
                    "valor_reais": valor_centavos / 100.0,
                    "sacado_documento": doc_pagador,
                    "sacado_nome": nome_pagador,
                    "sacado_endereco": "",
                    "sacado_bairro": "",
                    "sacado_cep": "",
                    "sacado_cidade": "",
                    "sacado_uf": "",
                    "comando": comando,
                    "carteira": carteira,
                }
            )

            resumo["qtd_titulos"] += 1
            resumo["valor_total_centavos"] += valor_centavos
            if data_venc:
                if resumo["vencimento_min"] is None or data_venc < resumo["vencimento_min"]:
                    resumo["vencimento_min"] = data_venc
                if resumo["vencimento_max"] is None or data_venc > resumo["vencimento_max"]:
                    resumo["vencimento_max"] = data_venc

            if comando:
                contagem_comandos[comando] += 1
            if carteira:
                contagem_carteiras[carteira] += 1

        elif tipo == "5":
            resumo["qtd_registros_tipo5"] += 1

        elif tipo == "9":
            trailer_processado = True
            codigo_banco_trailer = _campo_cnab400(registro, 3, 5).strip()
            if codigo_banco_trailer and codigo_banco_trailer != BANESTES_CODIGO_BANCO:
                erros_trailer.append(
                    f"Trailer: codigo do banco (pos. 003-005) deveria ser {BANESTES_CODIGO_BANCO}."
                )

            qtd_titulos_trailer = _campo_cnab400(registro, 18, 25).strip()
            if qtd_titulos_trailer.isdigit():
                qtd_trailer = int(qtd_titulos_trailer)
                if resumo["qtd_titulos"] and resumo["qtd_titulos"] != qtd_trailer:
                    avisos.append(
                        f"Trailer informa {qtd_trailer} titulos, mas foram encontrados {resumo['qtd_titulos']} registros tipo 1."
                    )

            valor_total_trailer = _campo_cnab400(registro, 26, 39).strip()
            if valor_total_trailer.isdigit():
                valor_trailer = int(valor_total_trailer)
                if resumo["valor_total_centavos"] and resumo["valor_total_centavos"] != valor_trailer:
                    avisos.append(
                        "Valor total do trailer difere do somatorio calculado a partir dos registros tipo 1."
                    )
        else:
            avisos.append(
                f"Linha {numero_linha}: tipo de registro '{tipo}' nao mapeado para o layout CNAB 400 do Banestes."
            )

    if not header_info:
        erros_header.append("Header do arquivo CNAB 400 nao foi localizado.")
    if not trailer_processado:
        erros_trailer.append("Trailer do arquivo (registro tipo 9) nao foi encontrado.")

    resumo["valor_total_reais"] = resumo["valor_total_centavos"] / 100.0
    resumo["comandos"] = [
        {"codigo": codigo, "quantidade": quantidade}
        for codigo, quantidade in sorted(contagem_comandos.items())
    ]
    resumo["carteiras"] = [
        {"codigo": codigo, "quantidade": quantidade}
        for codigo, quantidade in sorted(contagem_carteiras.items())
    ]

    return {
        "codigo_banco": BANESTES_CODIGO_BANCO,
        "nome_banco": BANCOS_CNAB.get(BANESTES_CODIGO_BANCO, "Banestes"),
        "erros_header": erros_header,
        "erros_registros": erros_registros,
        "erros_trailer": erros_trailer,
        "avisos": avisos,
        "resumo": resumo,
        "header_info": header_info,
        "titulos": titulos,
    }
