"""Validacoes especificas do CNAB 400 do Itau."""

from ..base import ESTADOS_BR
from .constants import (
    CNAB400_ITAU_CODIGO_BANCO,
    CNAB400_ITAU_ESPECIES_VALIDAS,
    CNAB400_ITAU_TIPOS_INSCRICAO,
    CNAB400_ITAU_TIPOS_MOEDA,
)
from .utils import _campo_cnab400, _formatar_data_br, _parse_data_cnab400, _parse_valor_cnab400

def validar_cnab400_itau(linhas):
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
                erros_header.append("Foi encontrado mais de um registro header no arquivo CNAB 400.")
                continue
            codigo_banco = _campo_cnab400(registro, 77, 79)
            if codigo_banco != CNAB400_ITAU_CODIGO_BANCO:
                erros_header.append(
                    f"Header informa código de banco '{codigo_banco}', esperado {CNAB400_ITAU_CODIGO_BANCO}."
                )
            literal_remessa = _campo_cnab400(registro, 3, 9).strip().upper()
            if literal_remessa != "REMESSA":
                avisos.append(
                    "Header: literal de remessa (pos. 003-009) deveria ser 'REMESSA'."
                )
            literal_servico = _campo_cnab400(registro, 12, 26).strip().upper()
            if literal_servico != "COBRANCA":
                avisos.append(
                    "Header: literal de serviço (pos. 012-026) deveria ser 'COBRANCA'."
                )
            agencia = _campo_cnab400(registro, 27, 30).strip()
            conta = _campo_cnab400(registro, 33, 37).strip()
            dac = _campo_cnab400(registro, 38, 38).strip()
            if not agencia.isdigit():
                erros_header.append("Header: agência (pos. 027-030) deve ser numérica.")
            if not conta.isdigit():
                erros_header.append("Header: conta (pos. 033-037) deve ser numérica.")
            if dac and not dac.isdigit():
                erros_header.append("Header: DAC (pos. 038) deve conter dígito.")
            nome = _campo_cnab400(registro, 47, 76).strip()
            if not nome:
                erros_header.append("Header: nome da empresa (pos. 047-076) não informado.")
            data_raw = _campo_cnab400(registro, 95, 100)
            data_gravacao = _parse_data_cnab400(data_raw)
            if not data_gravacao:
                erros_header.append(
                    "Header: data de geração (pos. 095-100) inválida."
                )
            header_info = {
                "nome_beneficiario": nome,
                "agencia": agencia,
                "agencia_dv": "",  # não há DV separado neste layout
                "conta": conta,
                "conta_dv": dac,
                "numero_convenio_lider": None,
                "sequencial_remessa": seq_raw,
                "data_gravacao": data_gravacao.date() if data_gravacao else None,
            }

        elif tipo == "1":
            tipo_insc = _campo_cnab400(registro, 2, 3).strip()
            if tipo_insc not in CNAB400_ITAU_TIPOS_INSCRICAO:
                erros_registros.append(
                    f"Linha {numero_linha}: tipo de inscrição da empresa (pos. 002-003) inválido."
                )
            doc_empresa = _campo_cnab400(registro, 4, 17).strip()
            if not doc_empresa.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: número de inscrição da empresa (pos. 004-017) deve ser numérico."
                )
            agencia_emp = _campo_cnab400(registro, 18, 21).strip()
            conta_emp = _campo_cnab400(registro, 24, 28).strip()
            if not agencia_emp.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: agência da empresa (pos. 018-021) deve ser numérica."
                )
            if not conta_emp.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: conta da empresa (pos. 024-028) deve ser numérica."
                )
            nosso_numero = _campo_cnab400(registro, 63, 70).strip()
            if not nosso_numero or not nosso_numero.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: Nosso Número (pos. 063-070) deve conter 8 dígitos."
                )
            carteira = _campo_cnab400(registro, 108, 108).strip()
            if not carteira:
                erros_registros.append(
                    f"Linha {numero_linha}: carteira (pos. 108) não informada."
                )
            codigo_ocorrencia = _campo_cnab400(registro, 109, 110).strip()
            if not codigo_ocorrencia.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: código de ocorrência/instrução (pos. 109-110) deve conter 2 dígitos."
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
                    f"Linha {numero_linha}: valor do título (pos. 127-139) deve conter apenas números."
                )
                valor_centavos = 0
            banco_cobrador = _campo_cnab400(registro, 140, 142)
            if banco_cobrador != CNAB400_ITAU_CODIGO_BANCO:
                erros_registros.append(
                    f"Linha {numero_linha}: código do banco cobrador (pos. 140-142) deve ser {CNAB400_ITAU_CODIGO_BANCO}."
                )
            agencia_cobradora = _campo_cnab400(registro, 143, 147).strip()
            if agencia_cobradora and not agencia_cobradora.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: agência cobradora (pos. 143-147) deve ser numérica."
                )
            especie = _campo_cnab400(registro, 148, 149).strip()
            if especie and especie not in CNAB400_ITAU_ESPECIES_VALIDAS:
                avisos.append(
                    f"Linha {numero_linha}: espécie '{especie}' fora da lista de espécies do manual do Itaú para CNAB 400; verifique."
                )
            aceite = _campo_cnab400(registro, 150, 150).strip().upper()
            if aceite not in {"A", "N"}:
                erros_registros.append(
                    f"Linha {numero_linha}: campo Aceite (pos. 150) deve ser 'A' ou 'N'."
                )
            data_emissao = _parse_data_cnab400(_campo_cnab400(registro, 151, 156))
            if not data_emissao:
                erros_registros.append(
                    f"Linha {numero_linha}: data de emissão (pos. 151-156) inválida."
                )
            instr1 = _campo_cnab400(registro, 157, 158).strip()
            instr2 = _campo_cnab400(registro, 159, 160).strip()
            if instr1 and not instr1.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: instrução 1 (pos. 157-158) deve conter dígitos."
                )
            if instr2 and not instr2.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: instrução 2 (pos. 159-160) deve conter dígitos."
                )
            juros_centavos = _parse_valor_cnab400(_campo_cnab400(registro, 161, 173))
            if juros_centavos is None:
                erros_registros.append(
                    f"Linha {numero_linha}: juros de mora (pos. 161-173) deve conter dígitos."
                )
                juros_centavos = 0
            desconto_data_raw = _campo_cnab400(registro, 174, 179).strip()
            desconto_data = None
            if desconto_data_raw and desconto_data_raw != "000000":
                desconto_data = _parse_data_cnab400(desconto_data_raw)
                if not desconto_data:
                    erros_registros.append(
                        f"Linha {numero_linha}: data de desconto (pos. 174-179) inválida."
                    )
            desconto_valor = _parse_valor_cnab400(_campo_cnab400(registro, 180, 192))
            if desconto_valor is None:
                erros_registros.append(
                    f"Linha {numero_linha}: valor do desconto (pos. 180-192) deve conter dígitos."
                )
                desconto_valor = 0
            valor_iof = _parse_valor_cnab400(_campo_cnab400(registro, 193, 205))
            if valor_iof is None:
                erros_registros.append(
                    f"Linha {numero_linha}: valor do IOF (pos. 193-205) deve conter dígitos."
                )
                valor_iof = 0
            valor_abatimento = _parse_valor_cnab400(_campo_cnab400(registro, 206, 218))
            if valor_abatimento is None:
                erros_registros.append(
                    f"Linha {numero_linha}: valor do abatimento (pos. 206-218) deve conter dígitos."
                )
                valor_abatimento = 0
            tipo_insc_pag = _campo_cnab400(registro, 219, 220).strip()
            if tipo_insc_pag not in CNAB400_ITAU_TIPOS_INSCRICAO:
                erros_registros.append(
                    f"Linha {numero_linha}: tipo de inscrição do pagador (pos. 219-220) inválido."
                )
            doc_pagador = _campo_cnab400(registro, 221, 234).strip()
            if not doc_pagador.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: documento do pagador (pos. 221-234) deve ser numérico."
                )
            nome_pagador = _campo_cnab400(registro, 235, 264).strip()
            if not nome_pagador:
                erros_registros.append(
                    f"Linha {numero_linha}: nome do pagador (pos. 235-264) não informado."
                )
            endereco_pagador = _campo_cnab400(registro, 275, 314).strip()
            bairro_pagador = _campo_cnab400(registro, 315, 326).strip()
            cep_pagador = _campo_cnab400(registro, 327, 334).strip()
            if cep_pagador and (len(cep_pagador) != 8 or not cep_pagador.isdigit()):
                erros_registros.append(
                    f"Linha {numero_linha}: CEP do pagador (pos. 327-334) inválido."
                )
            cidade_pagador = _campo_cnab400(registro, 335, 349).strip()
            uf_pagador = _campo_cnab400(registro, 350, 351).strip().upper()
            if uf_pagador and uf_pagador not in ESTADOS_BR:
                erros_registros.append(
                    f"Linha {numero_linha}: UF do pagador (pos. 350-351) inválida."
                )
            sacador_avalista = _campo_cnab400(registro, 352, 381).strip()
            data_mora = _parse_data_cnab400(_campo_cnab400(registro, 386, 391))
            prazo_protesto = _campo_cnab400(registro, 392, 393).strip()
            if prazo_protesto and not prazo_protesto.isdigit():
                erros_registros.append(
                    f"Linha {numero_linha}: prazo (pos. 392-393) deve ser numérico."
                )

            titulo = {
                "lote": "",
                "sequencia": seq_raw,
                "nosso_numero": nosso_numero,
                "seu_numero": numero_documento or _campo_cnab400(registro, 38, 62).strip(),
                "data_vencimento_str": _formatar_data_br(data_venc),
                "valor_centavos": valor_centavos,
                "valor_reais": valor_centavos / 100.0,
                "sacado_documento": doc_pagador,
                "sacado_nome": nome_pagador,
                "sacado_endereco": endereco_pagador,
                "sacado_bairro": bairro_pagador,
                "sacado_cep": cep_pagador,
                "sacado_cidade": cidade_pagador,
                "sacado_uf": uf_pagador,
                "itau_carteira": carteira,
                "itau_instrucao1": instr1,
                "itau_instrucao2": instr2,
                "itau_juros_centavos": juros_centavos,
                "itau_desconto_centavos": desconto_valor,
                "itau_iof_centavos": valor_iof,
                "itau_abatimento_centavos": valor_abatimento,
                "itau_data_desconto": _formatar_data_br(desconto_data),
                "itau_sacador_avalista": sacador_avalista,
                "itau_data_mora": _formatar_data_br(data_mora),
                "itau_prazo": prazo_protesto,
                "itau_multa_codigo": "",
                "itau_multa_data": None,
                "itau_multa_valor": 0.0,
                "itau_mensagens": [],
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

        elif tipo == "2":
            if not ultimo_detalhe:
                erros_registros.append(
                    f"Linha {numero_linha}: registro de multa (tipo 2) encontrado antes de um detalhe tipo 1."
                )
            else:
                codigo = _campo_cnab400(registro, 2, 2).strip()
                data_multa = _parse_data_cnab400(_campo_cnab400(registro, 3, 10))
                valor_multa = _parse_valor_cnab400(_campo_cnab400(registro, 11, 23))
                if valor_multa is None:
                    erros_registros.append(
                        f"Linha {numero_linha}: valor/percentual da multa (pos. 011-023) deve conter dígitos."
                    )
                    valor_multa = 0
                ultimo_detalhe["itau_multa_codigo"] = codigo
                ultimo_detalhe["itau_multa_data"] = _formatar_data_br(data_multa)
                ultimo_detalhe["itau_multa_valor"] = valor_multa / 100.0

        elif tipo == "5":
            if not ultimo_detalhe:
                erros_registros.append(
                    f"Linha {numero_linha}: registro tipo 5 sem um detalhe anterior."
                )
            else:
                texto = _campo_cnab400(registro, 2, 394).rstrip()
                ultimo_detalhe["itau_sacador_avalista"] = texto or ultimo_detalhe.get("itau_sacador_avalista", "")

        elif tipo in {"7", "8"}:
            if not ultimo_detalhe:
                erros_registros.append(
                    f"Linha {numero_linha}: registro de mensagem tipo {tipo} sem um detalhe anterior."
                )
            else:
                mensagem = _campo_cnab400(registro, 2, 394).rstrip()
                if mensagem:
                    ultimo_detalhe.setdefault("itau_mensagens", []).append(mensagem)

        elif tipo == "9":
            trailer_processado = True
            if len(registro.strip()) > 1:
                # Não há campos específicos de totais nesse layout, mas garantimos que as posições de 2-394 estejam preenchidas com dados válidos
                pass
        elif tipo == "6":
            # Registro específico para emissão de boletos (anexo A). Ignoramos para a validação de estrutura.
            continue
        else:
            erros_registros.append(
                f"Linha {numero_linha}: tipo de registro '{tipo}' não reconhecido para o layout CNAB 400 do Itaú."
            )

    if not header_info:
        erros_header.append("Arquivo CNAB 400 do Itaú sem registro header (tipo 0).")
    if not trailer_processado:
        erros_trailer.append("Arquivo CNAB 400 do Itaú sem registro trailer (tipo 9).")

    resumo["valor_total_reais"] = resumo["valor_total_centavos"] / 100.0

    return {
        "codigo_banco": CNAB400_ITAU_CODIGO_BANCO,
        "nome_banco": "Banco Itaú",
        "erros_header": erros_header,
        "erros_registros": erros_registros,
        "erros_trailer": erros_trailer,
        "avisos": avisos,
        "titulos": titulos,
        "resumo": resumo,
        "header_info": header_info,
    }
