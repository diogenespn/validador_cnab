"""Validacoes especificas do CNAB 400 do Banco do Brasil."""

from collections import Counter
from datetime import datetime
from ..base import BANCOS_CNAB, ESTADOS_BR, limpar_numero
from .constants import (
    CNAB400_BB_AGENTES_NEGATIVACAO,
    CNAB400_BB_CARTEIRAS_VALIDAS,
    CNAB400_BB_COMANDOS_VALIDOS,
    CNAB400_BB_DIAS_PROTESTO_VALIDOS,
    CNAB400_BB_ESPECIES_VALIDAS,
    CNAB400_BB_INDICADOR_PARCIAL,
    CNAB400_BB_TIPOS_COBRANCA,
    CNAB400_BB_TIPOS_INSCRICAO_BENEF,
    CNAB400_BB_TIPOS_INSCRICAO_PAGADOR,
)
from .utils import _campo_cnab400, _formatar_data_br, _parse_data_cnab400, _parse_valor_cnab400

def _validar_header_cnab400_bb(linha: str, numero_linha: int):
    erros = []
    avisos = []
    info = {
        "linha": numero_linha,
        "agencia": "",
        "agencia_dv": "",
        "conta": "",
        "conta_dv": "",
        "nome_beneficiario": "",
        "numero_convenio_lider": "",
        "data_gravacao": None,
        "sequencial_remessa": "",
        "codigo_banco": "",
        "nome_banco": "",
    }

    if linha[0:1] != "0":
        erros.append(
            f"Linha {numero_linha}: header CNAB 400 deve começar com '0', encontrado '{linha[0:1]}'."
        )

    if _campo_cnab400(linha, 2, 2) != "1":
        erros.append(
            f"Linha {numero_linha}: tipo de operação (pos. 002) deve ser '1' para remessa."
        )

    tipo_extenso = _campo_cnab400(linha, 3, 9).strip().upper()
    if tipo_extenso not in {"REMESSA", "TESTE"}:
        avisos.append(
            f"Linha {numero_linha}: identificação por extenso do tipo de operação (pos. 003-009) não está como 'REMESSA' ou 'TESTE'."
        )

    if _campo_cnab400(linha, 10, 11) != "01":
        erros.append(
            f"Linha {numero_linha}: tipo de serviço (pos. 010-011) deve ser '01'."
        )

    if _campo_cnab400(linha, 12, 19).strip().upper() != "COBRANCA":
        avisos.append(
            f"Linha {numero_linha}: descrição do serviço (pos. 012-019) diferente de 'COBRANCA'."
        )

    complemento = _campo_cnab400(linha, 20, 26)
    if complemento.strip():
        avisos.append(
            f"Linha {numero_linha}: complemento do registro (pos. 020-026) deveria estar em branco."
        )

    agencia = _campo_cnab400(linha, 27, 30).strip()
    if not agencia or not agencia.isdigit():
        erros.append(
            f"Linha {numero_linha}: prefixo da agência (pos. 027-030) deve conter 4 dígitos."
        )
    info["agencia"] = agencia

    agencia_dv = _campo_cnab400(linha, 31, 31).strip()
    if not agencia_dv:
        erros.append(f"Linha {numero_linha}: DV da agência (pos. 031) não informado.")
    info["agencia_dv"] = agencia_dv

    conta = _campo_cnab400(linha, 32, 39).strip()
    if not conta or not conta.isdigit():
        erros.append(
            f"Linha {numero_linha}: conta corrente (pos. 032-039) deve conter 8 dígitos."
        )
    info["conta"] = conta

    conta_dv = _campo_cnab400(linha, 40, 40).strip()
    if not conta_dv:
        erros.append(f"Linha {numero_linha}: DV da conta corrente (pos. 040) não informado.")
    info["conta_dv"] = conta_dv

    if _campo_cnab400(linha, 41, 46) != "000000":
        erros.append(
            f"Linha {numero_linha}: complemento do registro (pos. 041-046) deve estar com '000000'."
        )

    nome_benef = _campo_cnab400(linha, 47, 76).strip()
    if not nome_benef:
        erros.append(
            f"Linha {numero_linha}: nome do beneficiário (pos. 047-076) não pode ficar em branco."
        )
    info["nome_beneficiario"] = nome_benef

    banco_raw = _campo_cnab400(linha, 77, 94)
    codigo_banco = banco_raw[0:3]
    if not codigo_banco.isdigit():
        erros.append(
            f"Linha {numero_linha}: código do banco (pos. 077-079) deve conter 3 dígitos."
        )
    info["codigo_banco"] = codigo_banco
    info["nome_banco"] = BANCOS_CNAB.get(codigo_banco, "Banco não mapeado neste validador")
    if not banco_raw.strip().startswith(codigo_banco):
        avisos.append(
            f"Linha {numero_linha}: campo 001BANCODOBRASIL (pos. 077-094) está com conteúdo inesperado."
        )

    data_grav_raw = _campo_cnab400(linha, 95, 100)
    data_gravacao = _parse_data_cnab400(data_grav_raw)
    if not data_gravacao:
        erros.append(
            f"Linha {numero_linha}: data de gravação (pos. 095-100) deve estar em DDMMAA."
        )
    info["data_gravacao"] = data_gravacao

    seq_remessa = _campo_cnab400(linha, 101, 107).strip()
    if not seq_remessa or not seq_remessa.isdigit():
        erros.append(
            f"Linha {numero_linha}: sequencial da remessa (pos. 101-107) deve conter dígitos."
        )
    info["sequencial_remessa"] = seq_remessa

    info["numero_convenio_lider"] = _campo_cnab400(linha, 130, 136).strip()
    if info["numero_convenio_lider"] and not info["numero_convenio_lider"].isdigit():
        erros.append(
            f"Linha {numero_linha}: número do convênio líder (pos. 130-136) deve ser numérico."
        )

    seq_reg = _campo_cnab400(linha, 395, 400).strip()
    if seq_reg != "000001":
        avisos.append(
            f"Linha {numero_linha}: sequência do registro no header (pos. 395-400) deveria ser '000001'."
        )

    return info, erros, avisos

def _validar_trailer_cnab400_bb(linha: str, numero_linha: int, ultimo_seq: int):
    erros = []
    avisos = []
    if linha[0:1] != "9":
        erros.append(
            f"Linha {numero_linha}: trailer CNAB 400 deve começar com '9'."
        )
    complemento = _campo_cnab400(linha, 2, 394)
    if complemento.strip():
        avisos.append(
            f"Linha {numero_linha}: trailer (pos. 002-394) deveria estar em branco."
        )
    seq = _campo_cnab400(linha, 395, 400).strip()
    if not seq or not seq.isdigit():
        erros.append(
            f"Linha {numero_linha}: sequência do trailer (pos. 395-400) deve conter 6 dígitos."
        )
    else:
        seq_int = int(seq)
        if ultimo_seq and seq_int != ultimo_seq:
            erros.append(
                f"Linha {numero_linha}: sequência do trailer é {seq}, mas o último registro anterior indicava {ultimo_seq:06d}."
            )
    return erros, avisos

def _validar_registro_detalhe_cnab400_bb(linha: str, numero_linha: int, header_info):
    erros = []
    avisos = []
    detalhe = {
        "linha": numero_linha,
        "sequencial_registro": _campo_cnab400(linha, 395, 400).strip(),
        "tipo_inscricao_beneficiario": "",
        "documento_beneficiario": "",
        "agencia": _campo_cnab400(linha, 18, 21).strip(),
        "agencia_dv": _campo_cnab400(linha, 22, 22).strip(),
        "conta": _campo_cnab400(linha, 23, 30).strip(),
        "conta_dv": _campo_cnab400(linha, 31, 31).strip(),
        "convenio_cobranca": _campo_cnab400(linha, 32, 38).strip(),
        "nosso_numero": _campo_cnab400(linha, 64, 80).strip(),
        "carteira": _campo_cnab400(linha, 107, 108).strip(),
        "variacao_carteira": _campo_cnab400(linha, 92, 94).strip(),
        "tipo_cobranca": _campo_cnab400(linha, 102, 106).strip().upper(),
        "comando": _campo_cnab400(linha, 109, 110).strip(),
        "seu_numero": _campo_cnab400(linha, 111, 120).strip(),
        "seu_numero_15": None,
        "data_vencimento": None,
        "data_vencimento_str": None,
        "valor_centavos": 0,
        "valor_reais": 0.0,
        "numero_banco": _campo_cnab400(linha, 140, 142).strip(),
        "agencia_cobradora": _campo_cnab400(linha, 143, 146).strip(),
        "nome_pagador": _campo_cnab400(linha, 235, 271).strip(),
        "documento_pagador": limpar_numero(_campo_cnab400(linha, 221, 234)),
        "tipo_inscricao_pagador": _campo_cnab400(linha, 219, 220).strip(),
        "endereco_pagador": _campo_cnab400(linha, 275, 314).strip(),
        "bairro_pagador": _campo_cnab400(linha, 315, 326).strip(),
        "cidade_pagador": _campo_cnab400(linha, 335, 349).strip(),
        "uf_pagador": _campo_cnab400(linha, 350, 351).strip().upper(),
        "cep_pagador": _campo_cnab400(linha, 327, 334).strip(),
        "observacoes": _campo_cnab400(linha, 352, 391).strip(),
        "instrucao1": _campo_cnab400(linha, 157, 158).strip(),
        "instrucao2": _campo_cnab400(linha, 159, 160).strip(),
        "juros_centavos": 0,
        "juros_reais": 0.0,
        "desconto_data_str": None,
        "desconto_valor_centavos": 0,
        "desconto_valor_reais": 0.0,
        "multa_codigo": None,
        "multa_data_str": None,
        "multa_valor_centavos": 0,
        "multa_valor_reais": 0.0,
        "valor_abatimento_centavos": 0,
        "valor_abatimento_reais": 0.0,
        "valor_iof_centavos": 0,
        "valor_iof_reais": 0.0,
        "data_emissao_str": None,
        "indicador_recebimento_parcial": _campo_cnab400(linha, 394, 394).strip().upper(),
        "dias_protesto": _campo_cnab400(linha, 392, 393).strip(),
        "agente_negativador": None,
        "emails_pagador": [],
        "opcional_desc2_data_str": None,
        "opcional_desc2_valor_reais": 0.0,
        "opcional_desc3_data_str": None,
        "opcional_desc3_valor_reais": 0.0,
    }

    if len(linha) < 400:
        erros.append(
            f"Linha {numero_linha}: registro possui menos de 400 caracteres."
        )

    if linha[0:1] != "7":
        erros.append(
            f"Linha {numero_linha}: registro tipo 7 esperado, encontrado '{linha[0:1]}'."
        )

    tipo_insc = _campo_cnab400(linha, 2, 3).strip()
    detalhe["tipo_inscricao_beneficiario"] = tipo_insc
    if tipo_insc not in CNAB400_BB_TIPOS_INSCRICAO_BENEF:
        erros.append(
            f"Linha {numero_linha}: tipo de inscrição do beneficiário (pos. 002-003) deve ser 01=CPF ou 02=CNPJ."
        )

    doc_benef = limpar_numero(_campo_cnab400(linha, 4, 17))
    detalhe["documento_beneficiario"] = doc_benef
    if not doc_benef:
        erros.append(
            f"Linha {numero_linha}: CPF/CNPJ do beneficiário (pos. 004-017) não informado."
        )
    elif tipo_insc == "01" and len(doc_benef) != 11:
        erros.append(
            f"Linha {numero_linha}: CPF do beneficiário deve ter 11 dígitos."
        )
    elif tipo_insc == "02" and len(doc_benef) != 14:
        erros.append(
            f"Linha {numero_linha}: CNPJ do beneficiário deve ter 14 dígitos."
        )

    agencia = detalhe["agencia"]
    if not agencia or not agencia.isdigit():
        erros.append(
            f"Linha {numero_linha}: prefixo da agência do beneficiário (pos. 018-021) deve conter 4 dígitos."
        )
    elif header_info and header_info.get("agencia") and agencia != header_info["agencia"]:
        erros.append(
            f"Linha {numero_linha}: prefixo da agência difere do header ({agencia} x {header_info['agencia']})."
        )

    conta = detalhe["conta"]
    if not conta or not conta.isdigit():
        erros.append(
            f"Linha {numero_linha}: conta corrente do beneficiário (pos. 023-030) deve ser numérica."
        )
    elif header_info and header_info.get("conta") and conta != header_info["conta"]:
        erros.append(
            f"Linha {numero_linha}: conta corrente difere da informada no header ({conta} x {header_info['conta']})."
        )

    carteira = detalhe["carteira"]
    if carteira and carteira not in CNAB400_BB_CARTEIRAS_VALIDAS:
        erros.append(
            f"Linha {numero_linha}: carteira de cobrança (pos. 107-108) '{carteira}' não está entre as carteiras válidas do BB."
        )
    elif not carteira:
        erros.append(
            f"Linha {numero_linha}: carteira de cobrança (pos. 107-108) não informada."
        )

    tipo_cobranca = detalhe["tipo_cobranca"]
    if carteira:
        validos = CNAB400_BB_TIPOS_COBRANCA.get(carteira, {""})
        if tipo_cobranca not in validos:
            erros.append(
                f"Linha {numero_linha}: tipo de cobrança '{tipo_cobranca}' não é aceito para a carteira {carteira}."
            )

    comando = detalhe["comando"]
    if not comando or comando not in CNAB400_BB_COMANDOS_VALIDOS:
        erros.append(
            f"Linha {numero_linha}: comando (pos. 109-110) '{comando}' não é reconhecido pelo manual do BB."
        )

    data_venc = _parse_data_cnab400(_campo_cnab400(linha, 121, 126))
    detalhe["data_vencimento"] = data_venc
    detalhe["data_vencimento_str"] = _formatar_data_br(data_venc)
    if not data_venc:
        erros.append(
            f"Linha {numero_linha}: data de vencimento (pos. 121-126) inválida."
        )

    valor_centavos = _parse_valor_cnab400(_campo_cnab400(linha, 127, 139))
    if valor_centavos is None:
        erros.append(
            f"Linha {numero_linha}: valor do título (pos. 127-139) deve conter apenas dígitos."
        )
        valor_centavos = 0
    detalhe["valor_centavos"] = valor_centavos
    detalhe["valor_reais"] = valor_centavos / 100.0

    numero_banco = detalhe["numero_banco"]
    if not numero_banco:
        erros.append(
            f"Linha {numero_linha}: número do banco (pos. 140-142) não informado."
        )
    elif not numero_banco.isdigit():
        erros.append(
            f"Linha {numero_linha}: número do banco (pos. 140-142) deve ser numérico."
        )
    elif header_info and header_info.get("codigo_banco") and numero_banco != header_info["codigo_banco"]:
        erros.append(
            f"Linha {numero_linha}: número do banco (pos. 140-142) difere do header ({numero_banco} x {header_info['codigo_banco']})."
        )

    ag_cobradora = detalhe["agencia_cobradora"]
    if ag_cobradora and not ag_cobradora.isdigit():
        erros.append(
            f"Linha {numero_linha}: prefixo da agência cobradora (pos. 143-146) deve conter 4 dígitos."
        )

    especie = _campo_cnab400(linha, 148, 149).strip()
    if especie not in CNAB400_BB_ESPECIES_VALIDAS:
        erros.append(
            f"Linha {numero_linha}: espécie do título (pos. 148-149) '{especie}' não está na lista permitida."
        )

    aceite = _campo_cnab400(linha, 150, 150).strip().upper()
    if aceite and aceite not in {"A", "N"}:
        erros.append(
            f"Linha {numero_linha}: aceite (pos. 150) deve ser 'A' ou 'N'."
        )

    data_emissao = _parse_data_cnab400(_campo_cnab400(linha, 151, 156))
    detalhe["data_emissao_str"] = _formatar_data_br(data_emissao)
    if not data_emissao:
        erros.append(
            f"Linha {numero_linha}: data de emissão (pos. 151-156) inválida."
        )
    elif data_venc and data_emissao > data_venc:
        erros.append(
            f"Linha {numero_linha}: data de emissão não pode ser posterior ao vencimento."
        )

    instrucao1 = detalhe["instrucao1"]
    instrucao2 = detalhe["instrucao2"]
    if instrucao1 and not instrucao1.isdigit():
        erros.append(
            f"Linha {numero_linha}: instrução codificada 1 (pos. 157-158) deve conter 2 dígitos."
        )
    if instrucao2 and not instrucao2.isdigit():
        erros.append(
            f"Linha {numero_linha}: instrução codificada 2 (pos. 159-160) deve conter 2 dígitos."
        )

    juros_centavos = _parse_valor_cnab400(_campo_cnab400(linha, 161, 173))
    if juros_centavos is None:
        erros.append(
            f"Linha {numero_linha}: juros de mora (pos. 161-173) deve conter apenas dígitos."
        )
        juros_centavos = 0
    detalhe["juros_centavos"] = juros_centavos
    detalhe["juros_reais"] = juros_centavos / 100.0

    campo_desc_data = _campo_cnab400(linha, 174, 179)
    campo_desc_valor = _campo_cnab400(linha, 180, 192)
    if comando in {"35", "36"}:
        codigo_multa = campo_desc_data[0:1].strip()
        if codigo_multa not in {"1", "2", "9"}:
            erros.append(
                f"Linha {numero_linha}: código da multa (pos. 174) deve ser 1, 2 ou 9 quando o comando for {comando}."
            )
        else:
            detalhe["multa_codigo"] = codigo_multa
        data_multa = _parse_data_cnab400(_campo_cnab400(linha, 175, 180))
        if codigo_multa in {"1", "2"} and not data_multa:
            erros.append(
                f"Linha {numero_linha}: data de início de multa (pos. 175-180) inválida."
            )
        detalhe["multa_data_str"] = _formatar_data_br(data_multa)
        valor_multa = _parse_valor_cnab400(_campo_cnab400(linha, 181, 192))
        if valor_multa is None:
            erros.append(
                f"Linha {numero_linha}: valor/percentual de multa (pos. 181-192) deve conter dígitos."
            )
            valor_multa = 0
        detalhe["multa_valor_centavos"] = valor_multa
        detalhe["multa_valor_reais"] = valor_multa / 100.0
    else:
        if campo_desc_data.strip() and campo_desc_data.strip() not in {"000000", "777777"}:
            data_desc = _parse_data_cnab400(campo_desc_data)
            if not data_desc:
                erros.append(
                    f"Linha {numero_linha}: data limite para desconto (pos. 174-179) inválida."
                )
            else:
                if data_venc and data_desc > data_venc:
                    erros.append(
                        f"Linha {numero_linha}: data limite para desconto maior que o vencimento."
                    )
                detalhe["desconto_data_str"] = _formatar_data_br(data_desc)
        elif campo_desc_data.strip() == "777777":
            detalhe["desconto_data_str"] = "Por dia (777777)"

        valor_desc = _parse_valor_cnab400(campo_desc_valor)
        if valor_desc is None:
            erros.append(
                f"Linha {numero_linha}: valor do desconto (pos. 180-192) deve conter dígitos."
            )
            valor_desc = 0
        if comando == "32" and valor_desc > 0:
            erros.append(
                f"Linha {numero_linha}: comando 32 (não conceder desconto) exige valor zerado no campo de desconto."
            )
        detalhe["desconto_valor_centavos"] = valor_desc
        detalhe["desconto_valor_reais"] = valor_desc / 100.0

    valor_iof = _parse_valor_cnab400(_campo_cnab400(linha, 193, 205))
    if valor_iof is None:
        erros.append(
            f"Linha {numero_linha}: valor do IOF (pos. 193-205) deve conter dígitos."
        )
        valor_iof = 0
    detalhe["valor_iof_centavos"] = valor_iof
    detalhe["valor_iof_reais"] = valor_iof / 100.0

    valor_abat = _parse_valor_cnab400(_campo_cnab400(linha, 206, 218))
    if valor_abat is None:
        erros.append(
            f"Linha {numero_linha}: valor do abatimento (pos. 206-218) deve conter dígitos."
        )
        valor_abat = 0
    detalhe["valor_abatimento_centavos"] = valor_abat
    detalhe["valor_abatimento_reais"] = valor_abat / 100.0

    tipo_insc_pag = detalhe["tipo_inscricao_pagador"]
    if tipo_insc_pag not in CNAB400_BB_TIPOS_INSCRICAO_PAGADOR:
        erros.append(
            f"Linha {numero_linha}: tipo de inscrição do pagador (pos. 219-220) inválido."
        )

    doc_pag = detalhe["documento_pagador"]
    if tipo_insc_pag in {"01", "02"} and not doc_pag:
        erros.append(
            f"Linha {numero_linha}: CPF/CNPJ do pagador obrigatório para o tipo informado."
        )
    elif tipo_insc_pag == "01" and doc_pag and len(doc_pag) != 11:
        erros.append(
            f"Linha {numero_linha}: CPF do pagador deve ter 11 dígitos."
        )
    elif tipo_insc_pag == "02" and doc_pag and len(doc_pag) != 14:
        erros.append(
            f"Linha {numero_linha}: CNPJ do pagador deve ter 14 dígitos."
        )

    if not detalhe["nome_pagador"]:
        erros.append(
            f"Linha {numero_linha}: nome do pagador (pos. 235-271) não informado."
        )

    cep = detalhe["cep_pagador"]
    if cep and (len(cep) != 8 or not cep.isdigit() or cep == "00000000"):
        erros.append(
            f"Linha {numero_linha}: CEP do pagador (pos. 327-334) inválido."
        )

    uf = detalhe["uf_pagador"]
    if uf and uf not in ESTADOS_BR:
        erros.append(
            f"Linha {numero_linha}: UF do pagador (pos. 350-351) inválida."
        )

    indicador = detalhe["indicador_recebimento_parcial"]
    if indicador and indicador not in CNAB400_BB_INDICADOR_PARCIAL:
        erros.append(
            f"Linha {numero_linha}: indicador de recebimento parcial (pos. 394) deve ser 'S', 'N' ou branco."
        )

    dias_protesto = detalhe["dias_protesto"]
    if dias_protesto and not dias_protesto.isdigit():
        erros.append(
            f"Linha {numero_linha}: dias para protesto/negativação (pos. 392-393) deve conter dígitos."
        )
    elif dias_protesto.isdigit():
        dias_int = int(dias_protesto)
        if comando == "01" and ("06" in {instrucao1, instrucao2}):
            if dias_int not in CNAB400_BB_DIAS_PROTESTO_VALIDOS:
                erros.append(
                    f"Linha {numero_linha}: número de dias para protesto fora da faixa permitida (06-29, 35 ou 40)."
                )

    nosso_numero = detalhe["nosso_numero"]
    if nosso_numero and not nosso_numero.isdigit():
        erros.append(
            f"Linha {numero_linha}: Nosso Número (pos. 064-080) deve conter apenas dígitos."
        )
    elif carteira in {"11", "31", "51"} and nosso_numero.strip("0"):
        erros.append(
            f"Linha {numero_linha}: carteiras {carteira} devem enviar Nosso Número zerado conforme o manual."
        )
    elif carteira in {"12", "15", "17"}:
        convenio = detalhe.get("convenio_cobranca", "")
        if nosso_numero and len(nosso_numero) != 17:
            avisos.append(
                f"Linha {numero_linha}: Nosso Número para a carteira {carteira} deveria conter 17 dígitos."
            )
        if nosso_numero and convenio and len(convenio) == 7 and not nosso_numero.startswith(convenio):
            avisos.append(
                f"Linha {numero_linha}: primeiros dígitos do Nosso Número não coincidem com o convênio informado ({convenio})."
            )

    return detalhe, erros, avisos

def _aplicar_registro_opcional_cnab400_bb(linha: str, numero_linha: int, detalhe):
    erros = []
    avisos = []
    tipo_servico = _campo_cnab400(linha, 2, 3).strip()

    if tipo_servico == "07":
        data2 = _parse_data_cnab400(_campo_cnab400(linha, 4, 9))
        valor2 = _parse_valor_cnab400(_campo_cnab400(linha, 10, 26))
        data3 = _parse_data_cnab400(_campo_cnab400(linha, 27, 32))
        valor3 = _parse_valor_cnab400(_campo_cnab400(linha, 33, 49))

        if data2:
            detalhe["opcional_desc2_data_str"] = _formatar_data_br(data2)
        if valor2 is None:
            erros.append(
                f"Linha {numero_linha}: valor do 2º desconto (tipo 5, pos. 010-026) deve conter dígitos."
            )
        else:
            detalhe["opcional_desc2_valor_reais"] = valor2 / 100.0

        if data3:
            detalhe["opcional_desc3_data_str"] = _formatar_data_br(data3)
        if valor3 is None:
            erros.append(
                f"Linha {numero_linha}: valor do 3º desconto (tipo 5, pos. 033-049) deve conter dígitos."
            )
        else:
            detalhe["opcional_desc3_valor_reais"] = valor3 / 100.0

    elif tipo_servico == "01":
        emails_raw = _campo_cnab400(linha, 4, 139).strip()
        if emails_raw:
            emails = [email.strip() for email in emails_raw.split(";") if email.strip()]
            detalhe["emails_pagador"].extend(emails)
            for email in emails:
                if "@" not in email:
                    avisos.append(
                        f"Linha {numero_linha}: endereço de e-mail '{email}' não contém '@'."
                    )
        else:
            avisos.append(
                f"Linha {numero_linha}: registro opcional de e-mail informado sem endereços."
            )

    elif tipo_servico == "03":
        seu_numero15 = _campo_cnab400(linha, 4, 18).strip()
        if seu_numero15:
            detalhe["seu_numero_15"] = seu_numero15
    elif tipo_servico == "08":
        codigo = _campo_cnab400(linha, 4, 5).strip()
        if codigo in CNAB400_BB_AGENTES_NEGATIVACAO:
            detalhe["agente_negativador"] = CNAB400_BB_AGENTES_NEGATIVACAO[codigo]
        else:
            erros.append(
                f"Linha {numero_linha}: código do agente negativador '{codigo}' inválido (esperado 10 ou 11)."
            )
    else:
        avisos.append(
            f"Linha {numero_linha}: registro opcional tipo 5 com tipo de serviço '{tipo_servico}' ainda não é tratado pelo validador."
        )

    return erros, avisos

def validar_cnab400_bb(linhas):
    erros_header = []
    erros_registros = []
    erros_trailer = []
    avisos = []
    titulos = []
    header_info = None
    codigo_banco = None
    nome_banco = None
    ultimo_seq = 0
    trailer_encontrado = False
    resumo = {
        "qtd_titulos": 0,
        "qtd_registros_tipo5": 0,
        "valor_total_centavos": 0,
        "valor_total_reais": 0.0,
        "vencimento_min": None,
        "vencimento_max": None,
        "comandos": [],
        "carteiras": [],
    }
    contagem_comandos = Counter()
    contagem_carteiras = Counter()
    ultimo_detalhe = None

    for numero_linha, linha in enumerate(linhas, start=1):
        if not linha or linha.strip() == "":
            continue
        linha_limpa = linha.rstrip("\r\n")
        tipo = linha_limpa[0:1]

        seq_raw = _campo_cnab400(linha_limpa, 395, 400).strip()
        if seq_raw and seq_raw.isdigit():
            seq = int(seq_raw)
            if ultimo_seq and seq != ultimo_seq + 1:
                erros_registros.append(
                    f"Linha {numero_linha}: sequência do registro (pos. 395-400) fora da ordem esperada (esperado {ultimo_seq + 1:06d})."
                )
            ultimo_seq = seq
        else:
            erros_registros.append(
                f"Linha {numero_linha}: sequência do registro (pos. 395-400) deve conter 6 dígitos."
            )

        if tipo == "0":
            if header_info:
                erros_header.append("Foram encontrados dois registros header no arquivo.")
                continue
            info, err, avis = _validar_header_cnab400_bb(linha_limpa, numero_linha)
            header_info = info
            erros_header.extend(err)
            avisos.extend(avis)
            codigo_banco = info.get("codigo_banco")
            nome_banco = info.get("nome_banco")
        elif tipo == "7":
            detalhe, err, avis = _validar_registro_detalhe_cnab400_bb(linha_limpa, numero_linha, header_info)
            erros_registros.extend(err)
            avisos.extend(avis)
            titulos.append(detalhe)
            resumo["qtd_titulos"] += 1
            valor_cent = detalhe.get("valor_centavos") or 0
            resumo["valor_total_centavos"] += valor_cent
            dt = detalhe.get("data_vencimento")
            if dt:
                if resumo["vencimento_min"] is None or dt < resumo["vencimento_min"]:
                    resumo["vencimento_min"] = dt
                if resumo["vencimento_max"] is None or dt > resumo["vencimento_max"]:
                    resumo["vencimento_max"] = dt
            comando = detalhe.get("comando")
            if comando:
                contagem_comandos[comando] += 1
            carteira = detalhe.get("carteira")
            if carteira:
                contagem_carteiras[carteira] += 1
            ultimo_detalhe = detalhe
        elif tipo == "5":
            resumo["qtd_registros_tipo5"] += 1
            if not ultimo_detalhe:
                erros_registros.append(
                    f"Linha {numero_linha}: registro opcional tipo 5 sem um registro 7 imediatamente anterior."
                )
            else:
                err_opt, avis_opt = _aplicar_registro_opcional_cnab400_bb(linha_limpa, numero_linha, ultimo_detalhe)
                erros_registros.extend(err_opt)
                avisos.extend(avis_opt)
        elif tipo == "9":
            if trailer_encontrado:
                erros_trailer.append("Foram encontrados dois trailers no arquivo.")
                continue
            err_trailer, avis_trailer = _validar_trailer_cnab400_bb(linha_limpa, numero_linha, ultimo_seq)
            erros_trailer.extend(err_trailer)
            avisos.extend(avis_trailer)
            trailer_encontrado = True
        else:
            erros_registros.append(
                f"Linha {numero_linha}: tipo de registro '{tipo}' não faz parte do CNAB 400 do BB."
            )

    if not header_info:
        erros_header.append("Arquivo CNAB 400 sem registro header (tipo 0).")
    if not trailer_encontrado:
        erros_trailer.append("Arquivo CNAB 400 sem registro trailer (tipo 9).")

    if codigo_banco and codigo_banco != "001":
        erros_header.append(
            f"CNAB 400 implementado apenas para o Banco do Brasil (001). Arquivo indica banco {codigo_banco}."
        )

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
        "codigo_banco": codigo_banco,
        "nome_banco": nome_banco or BANCOS_CNAB.get(codigo_banco or "", "Banco não mapeado neste validador"),
        "erros_header": erros_header,
        "erros_registros": erros_registros,
        "erros_trailer": erros_trailer,
        "avisos": avisos,
        "titulos": titulos,
        "resumo": resumo,
        "header_info": header_info,
    }
