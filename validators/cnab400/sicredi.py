"""Validacoes especificas do CNAB 400 do Sicredi."""

from .constants import (
    CNAB400_SICREDI_CODIGO_BANCO,
    CNAB400_SICREDI_ESPECIES,
    CNAB400_SICREDI_TIPO_CARTEIRA,
    CNAB400_SICREDI_TIPO_COBRANCA,
    CNAB400_SICREDI_TIPO_DESCONTO,
    CNAB400_SICREDI_TIPO_IMPRESSAO,
    CNAB400_SICREDI_TIPO_IMPRESSAO_BOLETO,
    CNAB400_SICREDI_TIPO_JUROS,
    CNAB400_SICREDI_TIPO_MOEDA,
    CNAB400_SICREDI_TIPO_POSTAGEM,
)
from .utils import _campo_cnab400, _formatar_data_br, _parse_data_cnab400, _parse_valor_cnab400

def validar_cnab400_sicredi(linhas):
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
    }
    header_info = None
    ultimo_seq = 0
    trailer_processado = False
    ultimo_detalhe = None

    def _parse_data_aaaammdd(valor: str):
        valor = (valor or "").strip()
        if not valor or len(valor) != 8 or not valor.isdigit():
            return None
        ano = int(valor[0:4])
        mes = int(valor[4:6])
        dia = int(valor[6:8])
        try:
            return datetime(ano, mes, dia)
        except ValueError:
            return None

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
                    f"Linha {numero_linha}: sequência do registro {seq:06d} não segue a ordem esperada ({ultimo_seq + 1:06d})."
                )
            ultimo_seq = seq
        else:
            erros_registros.append(
                f"Linha {numero_linha}: sequência (pos. 395-400) inválida ou vazia."
            )

        if tipo == "0":
            if header_info:
                erros_header.append("Foi encontrado mais de um registro header no arquivo CNAB 400.")
                continue
            if _campo_cnab400(registro, 2, 2) != "1":
                erros_header.append("Header: identificação da remessa (pos. 002) deve ser '1'.")
            literal_remessa = _campo_cnab400(registro, 3, 9).strip().upper()
            if literal_remessa != "REMESSA":
                avisos.append("Header: literal de remessa (pos. 003-009) deveria ser 'REMESSA'.")
            if _campo_cnab400(registro, 10, 11) != "01":
                erros_header.append("Header: código do serviço (pos. 010-011) deve ser '01'.")
            literal_servico = _campo_cnab400(registro, 12, 19).strip().upper()
            if literal_servico != "COBRANCA":
                avisos.append("Header: literal de serviço (pos. 012-019) deveria ser 'COBRANCA'.")
            codigo_benef = _campo_cnab400(registro, 27, 31).strip()
            if not codigo_benef.isdigit():
                erros_header.append("Header: código do beneficiário (pos. 027-031) deve ser numérico.")
            doc_benef = _campo_cnab400(registro, 32, 45).strip()
            if not doc_benef.isdigit():
                erros_header.append("Header: CPF/CNPJ do beneficiário (pos. 032-045) deve ser numérico.")
            codigo_banco = _campo_cnab400(registro, 77, 79)
            if codigo_banco != CNAB400_SICREDI_CODIGO_BANCO:
                erros_header.append(
                    f"Header: código do banco (pos. 077-079) deve ser {CNAB400_SICREDI_CODIGO_BANCO}."
                )
            literal_banco = _campo_cnab400(registro, 80, 94).strip().upper()
            if "SICREDI" not in literal_banco:
                avisos.append("Header: literal do banco (pos. 080-094) deveria mencionar 'SICREDI'.")
            data_geracao = _parse_data_aaaammdd(_campo_cnab400(registro, 95, 102))
            if not data_geracao:
                erros_header.append("Header: data de geração (pos. 095-102) inválida (AAAAMMDD).")
            numero_remessa = _campo_cnab400(registro, 111, 117).strip()
            if not numero_remessa or not numero_remessa.isdigit():
                erros_header.append("Header: número da remessa (pos. 111-117) deve ser numérico.")
            header_info = {
                "nome_beneficiario": "",
                "agencia": "",
                "agencia_dv": "",
                "conta": codigo_benef,
                "conta_dv": "",
                "numero_convenio_lider": None,
                "sequencial_remessa": numero_remessa,
                "data_gravacao": data_geracao.date() if data_geracao else None,
                "codigo_banco": CNAB400_SICREDI_CODIGO_BANCO,
                "nome_banco": "Sicredi",
                "documento": doc_benef,
            }

        elif tipo == "1":
            tipo_cobranca = _campo_cnab400(registro, 2, 2).strip().upper()
            if tipo_cobranca not in CNAB400_SICREDI_TIPO_COBRANCA:
                erros_registros.append(
                    f"Linha {numero_linha}: tipo de cobrança (pos. 002) inválido para Sicredi."
                )
            tipo_carteira = _campo_cnab400(registro, 3, 3).strip().upper()
            if tipo_carteira not in CNAB400_SICREDI_TIPO_CARTEIRA:
                erros_registros.append(
                    f"Linha {numero_linha}: tipo de carteira (pos. 003) inválido."
                )
            tipo_impressao = _campo_cnab400(registro, 4, 4).strip().upper()
            if tipo_impressao not in CNAB400_SICREDI_TIPO_IMPRESSAO:
                erros_registros.append(
                    f"Linha {numero_linha}: tipo de impressão (pos. 004) deve ser 'A' ou 'B'."
                )
            tipo_boleto = _campo_cnab400(registro, 6, 6).strip().upper()
            tipo_moeda = _campo_cnab400(registro, 17, 17).strip().upper()
            if tipo_moeda not in CNAB400_SICREDI_TIPO_MOEDA:
                erros_registros.append(
                    f"Linha {numero_linha}: tipo de moeda (pos. 017) inválido."
                )
            tipo_desconto = _campo_cnab400(registro, 18, 18).strip().upper()
            if tipo_desconto not in CNAB400_SICREDI_TIPO_DESCONTO:
                erros_registros.append(
                    f"Linha {numero_linha}: tipo de desconto (pos. 018) inválido."
                )
            tipo_juros = _campo_cnab400(registro, 19, 19).strip().upper()
            if tipo_juros not in CNAB400_SICREDI_TIPO_JUROS:
                erros_registros.append(
                    f"Linha {numero_linha}: tipo de juros (pos. 019) inválido."
                )
            nosso_numero = _campo_cnab400(registro, 48, 56).strip()
            if nosso_numero and not nosso_numero.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: Nosso Número (pos. 048-056) deve conter apenas dígitos."
                )
            data_instrucao = _campo_cnab400(registro, 63, 70).strip()
            if data_instrucao and len(data_instrucao) != 8:
                avisos.append(
                    f"Linha {numero_linha}: data de instrução (pos. 063-070) deveria estar em AAAAMMDD."
                )
            postagem = _campo_cnab400(registro, 72, 72).strip().upper()
            if postagem and postagem not in CNAB400_SICREDI_TIPO_POSTAGEM:
                erros_registros.append(
                    f"Linha {numero_linha}: postagem (pos. 072) deve ser 'S' ou 'N'."
                )
            impressao_boleto = _campo_cnab400(registro, 74, 74).strip().upper()
            if impressao_boleto and impressao_boleto not in CNAB400_SICREDI_TIPO_IMPRESSAO_BOLETO:
                erros_registros.append(
                    f"Linha {numero_linha}: impressão do boleto (pos. 074) deve ser 'A' ou 'B'."
                )
            seu_numero = _campo_cnab400(registro, 111, 120).strip()
            if not seu_numero:
                erros_registros.append(
                    f"Linha {numero_linha}: seu número (pos. 111-120) não informado."
                )
            data_venc = _parse_data_cnab400(_campo_cnab400(registro, 121, 126))
            if not data_venc:
                erros_registros.append(
                    f"Linha {numero_linha}: data de vencimento (pos. 121-126) inválida."
                )
            valor_centavos = _parse_valor_cnab400(_campo_cnab400(registro, 127, 139))
            if valor_centavos is None:
                erros_registros.append(
                    f"Linha {numero_linha}: valor do título (pos. 127-139) deve conter apenas dígitos."
                )
                valor_centavos = 0
            especie = _campo_cnab400(registro, 149, 149).strip().upper()
            if especie and especie not in CNAB400_SICREDI_ESPECIES:
                erros_registros.append(
                    f"Linha {numero_linha}: espécie de documento (pos. 149) inválida."
                )
            aceite = _campo_cnab400(registro, 150, 150).strip().upper()
            if aceite and aceite not in {"S", "N"}:
                erros_registros.append(
                    f"Linha {numero_linha}: campo Aceite (pos. 150) deve ser 'S' ou 'N'."
                )
            data_emissao = _parse_data_cnab400(_campo_cnab400(registro, 151, 156))
            if not data_emissao:
                erros_registros.append(
                    f"Linha {numero_linha}: data de emissão (pos. 151-156) inválida."
                )
            instrucao_protesto = _campo_cnab400(registro, 157, 158).strip()
            dias_protesto = _campo_cnab400(registro, 159, 160).strip()
            if dias_protesto and not dias_protesto.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: dias para protesto (pos. 159-160) deve ser numérico."
                )
            juros_centavos = _parse_valor_cnab400(_campo_cnab400(registro, 161, 173))
            if juros_centavos is None:
                erros_registros.append(
                    f"Linha {numero_linha}: juros (pos. 161-173) deve conter apenas dígitos."
                )
                juros_centavos = 0
            data_desc = _campo_cnab400(registro, 174, 179).strip()
            if data_desc and data_desc != "000000":
                if not _parse_data_cnab400(data_desc):
                    erros_registros.append(
                        f"Linha {numero_linha}: data limite para desconto (pos. 174-179) inválida."
                    )
            desconto_centavos = _parse_valor_cnab400(_campo_cnab400(registro, 180, 192))
            if desconto_centavos is None:
                erros_registros.append(
                    f"Linha {numero_linha}: valor do desconto (pos. 180-192) deve conter dígitos."
                )
                desconto_centavos = 0
            instrucao_negativacao = _campo_cnab400(registro, 193, 194).strip()
            dias_negativacao = _campo_cnab400(registro, 195, 196).strip()
            if dias_negativacao and not dias_negativacao.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: dias para negativação (pos. 195-196) deve ser numérico."
                )
            abatimento_centavos = _parse_valor_cnab400(_campo_cnab400(registro, 206, 218))
            if abatimento_centavos is None:
                erros_registros.append(
                    f"Linha {numero_linha}: valor do abatimento (pos. 206-218) deve conter dígitos."
                )
                abatimento_centavos = 0
            tipo_insc_pag = _campo_cnab400(registro, 219, 219).strip()
            if tipo_insc_pag not in {"1", "2"}:
                erros_registros.append(
                    f"Linha {numero_linha}: tipo de inscrição do pagador (pos. 219) deve ser 1 ou 2."
                )
            doc_pagador = _campo_cnab400(registro, 221, 234).strip()
            if not doc_pagador or not doc_pagador.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: CPF/CNPJ do pagador (pos. 221-234) deve ser numérico."
                )
            nome_pagador = _campo_cnab400(registro, 235, 274).strip()
            if not nome_pagador:
                erros_registros.append(
                    f"Linha {numero_linha}: nome do pagador (pos. 235-274) não informado."
                )
            endereco_pagador = _campo_cnab400(registro, 275, 314).strip()
            cep_pagador = _campo_cnab400(registro, 327, 334).strip()
            if cep_pagador and (len(cep_pagador) != 8 or not cep_pagador.isdigit()):
                erros_registros.append(
                    f"Linha {numero_linha}: CEP do pagador (pos. 327-334) inválido."
                )
            codigo_pagador_cliente = _campo_cnab400(registro, 335, 339).strip()
            beneficiario_final_doc = _campo_cnab400(registro, 340, 353).strip()
            beneficiario_final_nome = _campo_cnab400(registro, 354, 394).strip()

            titulo = {
                "lote": "",
                "sequencia": seq_raw,
                "nosso_numero": nosso_numero,
                "seu_numero": seu_numero,
                "data_vencimento_str": _formatar_data_br(data_venc),
                "valor_centavos": valor_centavos,
                "valor_reais": valor_centavos / 100.0,
                "sacado_documento": doc_pagador,
                "sacado_nome": nome_pagador,
                "sacado_endereco": endereco_pagador,
                "sacado_bairro": "",
                "sacado_cep": cep_pagador,
                "sacado_cidade": "",
                "sacado_uf": "",
                "comando": instrucao_protesto,
                "carteira": tipo_carteira,
                "sicredi_tipo_cobranca": tipo_cobranca,
                "sicredi_tipo_carteira": tipo_carteira,
                "sicredi_tipo_impressao": tipo_impressao,
                "sicredi_tipo_boleto": tipo_boleto,
                "sicredi_postagem": postagem,
                "sicredi_impressao_boleto": impressao_boleto,
                "sicredi_instrucao_protesto": instrucao_protesto,
                "sicredi_dias_protesto": dias_protesto,
                "sicredi_instrucao_negativacao": instrucao_negativacao,
                "sicredi_dias_negativacao": dias_negativacao,
                "sicredi_codigo_pagador_cliente": codigo_pagador_cliente,
                "sicredi_beneficiario_final_doc": beneficiario_final_doc,
                "sicredi_beneficiario_final_nome": beneficiario_final_nome,
                "sicredi_mensagens": [],
            }
            titulos.append(titulo)
            ultimo_detalhe = titulo
            resumo["qtd_titulos"] += 1
            resumo["valor_total_centavos"] += valor_centavos
            if data_venc:
                if resumo["vencimento_min"] is None or data_venc < resumo["vencimento_min"]:
                    resumo["vencimento_min"] = data_venc
                if resumo["vencimento_max"] is None or data_venc > resumo["vencimento_max"]:
                    resumo["vencimento_max"] = data_venc

        elif tipo in {"2", "5", "6", "7", "8"}:
            if not ultimo_detalhe:
                erros_registros.append(
                    f"Linha {numero_linha}: registro tipo {tipo} encontrado antes de um detalhe (tipo 1)."
                )
            else:
                texto = _campo_cnab400(registro, 2, 394).rstrip()
                if texto:
                    ultimo_detalhe.setdefault("sicredi_mensagens", []).append(f"Tipo {tipo}: {texto}")

        elif tipo == "9":
            trailer_processado = True
            if _campo_cnab400(registro, 2, 2) != "1":
                erros_trailer.append("Trailer: identificação do arquivo (pos. 002) deve ser '1'.")
            codigo_banco = _campo_cnab400(registro, 3, 5)
            if codigo_banco != CNAB400_SICREDI_CODIGO_BANCO:
                erros_trailer.append(
                    f"Trailer: código do banco (pos. 003-005) deve ser {CNAB400_SICREDI_CODIGO_BANCO}."
                )
        else:
            erros_registros.append(
                f"Linha {numero_linha}: tipo de registro '{tipo}' não faz parte do layout CNAB 400 do Sicredi."
            )

    if not header_info:
        erros_header.append("Arquivo CNAB 400 do Sicredi sem registro header (tipo 0).")
    if not trailer_processado:
        erros_trailer.append("Arquivo CNAB 400 do Sicredi sem registro trailer (tipo 9).")

    resumo["valor_total_reais"] = resumo["valor_total_centavos"] / 100.0

    return {
        "codigo_banco": CNAB400_SICREDI_CODIGO_BANCO,
        "nome_banco": "Sicredi",
        "erros_header": erros_header,
        "erros_registros": erros_registros,
        "erros_trailer": erros_trailer,
        "avisos": avisos,
        "titulos": titulos,
        "resumo": resumo,
        "header_info": header_info,
    }
