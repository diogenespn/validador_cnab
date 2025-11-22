"""Validacoes especificas do CNAB 400 da Caixa."""

from .utils import _campo_cnab400, _formatar_data_br, _parse_data_cnab400, _parse_valor_cnab400

def validar_cnab400_caixa(linhas):
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
                erros_header.append("Foi encontrado mais de um header no arquivo.")
                continue
            if _campo_cnab400(registro, 2, 2) != "1":
                erros_header.append("Header: identificação da remessa (pos. 002) deve ser '1'.")
            literal_remessa = _campo_cnab400(registro, 3, 9).strip().upper()
            if literal_remessa not in {"REMESSA", "TESTE"}:
                avisos.append("Header: literal de remessa (pos. 003-009) deveria ser 'REMESSA'.")
            servico = _campo_cnab400(registro, 10, 11)
            if servico != "01":
                erros_header.append("Header: código do serviço (pos. 010-011) deve ser '01'.")
            literal_servico = _campo_cnab400(registro, 12, 26).strip().upper()
            if literal_servico != "COBRANCA":
                avisos.append("Header: literal do serviço (pos. 012-026) deveria ser 'COBRANCA'.")
            agencia = _campo_cnab400(registro, 27, 30).strip()
            if not agencia.isdigit():
                erros_header.append("Header: código da agência (pos. 027-030) deve ser numérico.")
            codigo_benef = _campo_cnab400(registro, 31, 37).strip()
            if not codigo_benef.isdigit():
                erros_header.append("Header: código do beneficiário (pos. 031-037) deve ser numérico.")
            nome_empresa = _campo_cnab400(registro, 47, 76).strip()
            if not nome_empresa:
                avisos.append("Header: nome da empresa (pos. 047-076) não informado.")
            codigo_banco = _campo_cnab400(registro, 77, 79)
            if codigo_banco != "104":
                erros_header.append("Header: código do banco (pos. 077-079) deve ser 104.")
            nome_banco = _campo_cnab400(registro, 80, 94).strip()
            if "CAIXA" not in nome_banco.upper():
                avisos.append("Header: nome do banco (pos. 080-094) deveria mencionar 'CAIXA'.")
            data_geracao = _parse_data_cnab400(_campo_cnab400(registro, 95, 100))
            if not data_geracao:
                erros_header.append("Header: data de geração (pos. 095-100) inválida.")
            versao_layout = _campo_cnab400(registro, 101, 103).strip()
            if not versao_layout.isdigit():
                avisos.append("Header: versão do layout (pos. 101-103) não informada.")
            sequencial = _campo_cnab400(registro, 390, 394).strip()
            if not sequencial or not sequencial.isdigit():
                erros_header.append("Header: número sequencial do arquivo (pos. 390-394) deve ser numérico.")
            header_info = {
                "nome_beneficiario": nome_empresa,
                "agencia": agencia,
                "agencia_dv": "",
                "conta": codigo_benef,
                "conta_dv": "",
                "numero_convenio_lider": None,
                "sequencial_remessa": seq_raw,
                "data_gravacao": data_geracao.date() if data_geracao else None,
                "codigo_banco": "104",
                "nome_banco": "Caixa",
            }

        elif tipo == "1":
            banco = _campo_cnab400(registro, 78, 80)
            if banco and banco != "104":
                erros_registros.append(
                    f"Linha {numero_linha}: código do banco (pos. 078-080) deve ser 104."
                )
            nosso_numero = _campo_cnab400(registro, 63, 72).strip()
            if nosso_numero and not nosso_numero.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: Nosso Número (pos. 063-072) deve conter apenas dígitos."
                )
            especie = _campo_cnab400(registro, 107, 108).strip()
            comando = _campo_cnab400(registro, 109, 110).strip()
            if comando and not comando.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: código de comando (pos. 109-110) deve conter 2 dígitos."
                )
            numero_documento = _campo_cnab400(registro, 111, 120).strip()
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
            agencia_cobradora = _campo_cnab400(registro, 143, 146).strip()
            if agencia_cobradora and not agencia_cobradora.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: agência cobradora (pos. 143-146) deve ser numérica."
                )
            nome_pagador = _campo_cnab400(registro, 234, 253).strip()
            if not nome_pagador:
                erros_registros.append(
                    f"Linha {numero_linha}: nome do pagador (pos. 234-253) não informado."
                )
            documento_pagador = _campo_cnab400(registro, 221, 234).strip()
            if documento_pagador and not documento_pagador.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: documento do pagador (pos. 221-234) deve ser numérico."
                )
            endereco_pagador = _campo_cnab400(registro, 275, 314).strip()
            cep_pagador = _campo_cnab400(registro, 327, 334).strip()
            if cep_pagador and (len(cep_pagador) != 8 or not cep_pagador.isdigit()):
                erros_registros.append(
                    f"Linha {numero_linha}: CEP do pagador (pos. 327-334) deve conter 8 dígitos."
                )
            dias_protesto = _campo_cnab400(registro, 275, 276).strip()

            titulo = {
                "lote": "",
                "sequencia": seq_raw,
                "nosso_numero": nosso_numero,
                "seu_numero": numero_documento or "",
                "data_vencimento_str": _formatar_data_br(data_venc),
                "valor_centavos": valor_centavos,
                "valor_reais": valor_centavos / 100.0,
                "sacado_documento": documento_pagador,
                "sacado_nome": nome_pagador,
                "sacado_endereco": endereco_pagador,
                "sacado_bairro": "",
                "sacado_cep": cep_pagador,
                "sacado_cidade": "",
                "sacado_uf": "",
                "comando": comando,
                "carteira": especie,
                "caixa_dias_protesto": dias_protesto,
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

        elif tipo in {"2", "7", "8"}:
            if not ultimo_detalhe:
                erros_registros.append(
                    f"Linha {numero_linha}: registro opcional tipo {tipo} sem detalhe anterior."
                )
            else:
                texto = _campo_cnab400(registro, 2, 394).rstrip()
                if texto:
                    ultimo_detalhe.setdefault("caixa_mensagens", []).append(f"Tipo {tipo}: {texto}")

        elif tipo == "9":
            if trailer_processado:
                erros_trailer.append("Foram encontrados dois trailers no arquivo.")
            trailer_processado = True
            if _campo_cnab400(registro, 2, 2) != "1":
                erros_trailer.append("Trailer: identificação da remessa deve ser '1'.")
            codigo_banco = _campo_cnab400(registro, 3, 5)
            if codigo_banco != "104":
                erros_trailer.append("Trailer: código do banco deve ser 104.")

        else:
            erros_registros.append(
                f"Linha {numero_linha}: tipo de registro '{tipo}' não reconhecido para o layout da Caixa."
            )

    if not header_info:
        erros_header.append("Arquivo CNAB 400 da Caixa sem header (tipo 0).")
    if not trailer_processado:
        erros_trailer.append("Arquivo CNAB 400 da Caixa sem trailer (tipo 9).")

    resumo["valor_total_reais"] = resumo["valor_total_centavos"] / 100.0

    return {
        "codigo_banco": "104",
        "nome_banco": "Caixa Econômica Federal",
        "erros_header": erros_header,
        "erros_registros": erros_registros,
        "erros_trailer": erros_trailer,
        "avisos": avisos,
        "titulos": titulos,
        "resumo": resumo,
        "header_info": header_info,
    }
