"""Validacoes e deteccao do layout CNAB 240 SISDEB do Itau."""

from ..base import _parse_data_ddmmaaaa
from ..cnab400.utils import _formatar_data_br

ITAU_SISDEB_TIPOS_MOEDA = {"REA", "USD", "FAJ", "IDT"}

ITAU_SISDEB_TIPOS_MORA_REAL = {"00", "01", "03"}

def detectar_cnab240_itau_sisdeb(linhas):
    """
    Detecta se o arquivo CNAB 240 do Itau esta usando o layout SISDEB (segmento 'A' nos detalhes).
    """
    for linha in linhas:
        if not linha or linha.strip() == "":
            continue
        registro = linha.rstrip("\r\n")
        if len(registro) < 14:
            continue
        tipo = registro[7:8]
        if tipo == "3":
            segmento = registro[13:14].upper()
            if segmento == "A":
                return True
            return False
    return False

def _campo_posicional(linha: str, inicio: int, fim: int) -> str:
    """
    Retorna o trecho da linha entre as posicoes (1-based, inclusive).
    """
    if inicio < 1 or fim < inicio:
        return ""
    if len(linha) < inicio:
        return ""
    return linha[inicio - 1:fim]

def _parse_decimal_str(valor: str, casas_decimais: int):
    valor = (valor or "").strip()
    if not valor:
        return 0
    if not valor.isdigit():
        return None
    return int(valor)

def validar_cnab240_itau_sisdeb(linhas):
    """
    Validaes especficas do layout SISDEB CNAB 240 do Itau (segmento A).
    Retorna um dicionrio com erros por tipo, avisos, resumo e lista de ttulos.
    """
    erros_header = []
    erros_lotes = []
    erros_detalhes = []
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

    header_arquivo = None
    trailer_arquivo = None
    total_registros_contados = 0
    total_lotes_contados = 0

    lotes_info = {}

    for numero_linha, linha in enumerate(linhas, start=1):
        if not linha or linha.strip() == "":
            continue
        registro = linha.rstrip("\r\n")
        if len(registro) < 8:
            erros_detalhes.append(
                f"Linha {numero_linha}: registro com menos de 8 caracteres, impossivel identificar o tipo."
            )
            continue

        tipo = registro[7:8]

        if tipo not in {"0", "1", "3", "5", "9"}:
            erros_detalhes.append(
                f"Linha {numero_linha}: tipo de registro '{tipo}' nao pertence ao layout SISDEB (0,1,3,5,9)."
            )
            continue

        total_registros_contados += 1

        if tipo == "0":
            if header_arquivo is not None:
                erros_header.append(
                    f"Linha {numero_linha}: foi encontrado mais de um header de arquivo nao CNAB 240."
                )
            header_arquivo = registro

            codigo_banco = _campo_posicional(registro, 1, 3)
            if codigo_banco != "341":
                erros_header.append(f"Linha {numero_linha}: codigo do banco no header deve ser 341.")

            codigo_lote = _campo_posicional(registro, 4, 7)
            if codigo_lote != "0000":
                erros_header.append(
                    f"Linha {numero_linha}: header de arquivo deve informar lote '0000', encontrado '{codigo_lote}'."
                )

            tipo_reg = _campo_posicional(registro, 8, 8)
            if tipo_reg != "0":
                erros_header.append(
                    f"Linha {numero_linha}: header de arquivo deve ter tipo de registro '0', encontrado '{tipo_reg}'."
                )

            tipo_insc = _campo_posicional(registro, 18, 18)
            if tipo_insc not in {"1", "2"}:
                erros_header.append(
                    f"Linha {numero_linha}: tipo de inscricao da empresa (pos. 018) deve ser '1' ou '2'."
                )
            numero_insc = _campo_posicional(registro, 19, 32).strip()
            if not numero_insc:
                erros_header.append(
                    f"Linha {numero_linha}: numero de inscricao da empresa (pos. 019-032) nao informado."
                )
            elif not numero_insc.isdigit():
                erros_header.append(
                    f"Linha {numero_linha}: numero de inscricao da empresa deve ser numerico."
                )

            convenio = _campo_posicional(registro, 33, 45).strip()
            if not convenio:
                erros_header.append(
                    f"Linha {numero_linha}: codigo do convenio (pos. 033-045) nao informado."
                )

            agencia = _campo_posicional(registro, 54, 57).strip()
            if not agencia or not agencia.isdigit():
                erros_header.append(
                    f"Linha {numero_linha}: agncia do header (pos. 054-057) deve conter 4 digitos."
                )
            conta = _campo_posicional(registro, 66, 70).strip()
            if not conta or not conta.isdigit():
                erros_header.append(
                    f"Linha {numero_linha}: conta do header (pos. 066-070) deve conter 5 digitos."
                )

        elif tipo == "1":
            lote = _campo_posicional(registro, 4, 7)
            total_lotes_contados += 1

            if lote in lotes_info:
                erros_lotes.append(
                    f"Linha {numero_linha}: lote {lote} possui mais de um header."
                )

            lotes_info[lote] = {
                "detalhes": 0,
                "valor_centavos": 0,
                "quantidade_moeda": 0,
                "registros": 1,
                "trailer_processado": False,
                "linha": numero_linha,
            }

            codigo_banco = _campo_posicional(registro, 1, 3)
            if codigo_banco != "341":
                erros_lotes.append(
                    f"Linha {numero_linha}: lotes do Itau devem ser enviados com codigo de banco 341."
                )

            tipo_operacao = _campo_posicional(registro, 9, 9).upper()
            if tipo_operacao != "D":
                erros_lotes.append(
                    f"Linha {numero_linha}: tipo de operacao (pos. 009) deve ser 'D' para debitos."
                )

            tipo_servico = _campo_posicional(registro, 10, 11)
            if tipo_servico != "05":
                erros_lotes.append(
                    f"Linha {numero_linha}: tipo de servico no header de lote (pos. 010-011) deve ser '05'."
                )

            forma_lcto = _campo_posicional(registro, 12, 13)
            if forma_lcto != "50":
                erros_lotes.append(
                    f"Linha {numero_linha}: forma de lancamento (pos. 012-013) deve ser '50'."
                )

            versao_layout = _campo_posicional(registro, 14, 16)
            if versao_layout != "030":
                avisos.append(
                    f"Linha {numero_linha}: versao do layout no header de lote (pos. 014-016) deveria ser '030'."
                )

            tipo_insc = _campo_posicional(registro, 18, 18)
            if tipo_insc not in {"1", "2"}:
                erros_lotes.append(
                    f"Linha {numero_linha}: tipo de inscricao da empresa creditada (pos. 018) deve ser '1' ou '2'."
                )

            numero_insc = _campo_posicional(registro, 19, 32).strip()
            if not numero_insc or not numero_insc.isdigit():
                erros_lotes.append(
                    f"Linha {numero_linha}: numero de inscricao (pos. 019-032) do header de lote deve ser numerico."
                )

            convenio = _campo_posicional(registro, 33, 45).strip()
            if not convenio:
                erros_lotes.append(
                    f"Linha {numero_linha}: convenio (pos. 033-045) no header de lote nao informado."
                )

            agencia = _campo_posicional(registro, 54, 57).strip()
            conta = _campo_posicional(registro, 66, 70).strip()
            if not agencia or not agencia.isdigit():
                erros_lotes.append(
                    f"Linha {numero_linha}: agncia no header de lote (pos. 054-057) deve conter 4 digitos."
                )
            if not conta or not conta.isdigit():
                erros_lotes.append(
                    f"Linha {numero_linha}: conta no header de lote (pos. 066-070) deve conter 5 digitos."
                )

        elif tipo == "3":
            lote = _campo_posicional(registro, 4, 7)
            info_lote = lotes_info.get(lote)
            if not info_lote:
                erros_detalhes.append(
                    f"Linha {numero_linha}: registro detalhe do lote {lote} sem header correspondente."
                )
                continue

            info_lote["detalhes"] += 1
            info_lote["registros"] += 1

            segmento = _campo_posicional(registro, 14, 14).upper()
            if segmento != "A":
                erros_detalhes.append(
                    f"Linha {numero_linha}: segmento nos detalhes deve ser 'A', encontrado '{segmento}'."
                )

            codigo_mov = _campo_posicional(registro, 15, 17).strip()
            if not codigo_mov or not codigo_mov.isdigit():
                erros_detalhes.append(
                    f"Linha {numero_linha}: codigo da instruo para movimento (pos. 015-017) deve conter 3 digitos."
                )

            camera = _campo_posicional(registro, 18, 20)
            if camera != "000":
                erros_detalhes.append(
                    f"Linha {numero_linha}: codigo da camara (pos. 018-020) deve ser '000'."
                )

            codigo_banco = _campo_posicional(registro, 21, 23)
            if codigo_banco != "341":
                erros_detalhes.append(
                    f"Linha {numero_linha}: codigo do banco (pos. 021-023) deve ser 341."
                )

            agencia_debitada = _campo_posicional(registro, 25, 28).strip()
            conta_debitada = _campo_posicional(registro, 37, 41).strip()
            dac = _campo_posicional(registro, 43, 43).strip()
            if not agencia_debitada or not agencia_debitada.isdigit():
                erros_detalhes.append(
                    f"Linha {numero_linha}: agncia debitada (pos. 025-028) deve ser numrica."
                )
            if not conta_debitada or not conta_debitada.isdigit():
                erros_detalhes.append(
                    f"Linha {numero_linha}: conta debitada (pos. 037-041) deve ser numrica."
                )
            if dac and not dac.isdigit():
                erros_detalhes.append(
                    f"Linha {numero_linha}: DAC da agncia/conta (pos. 043) deve ser numerico."
                )

            nome_debitado = _campo_posicional(registro, 44, 73).strip()
            if not nome_debitado:
                erros_detalhes.append(
                    f"Linha {numero_linha}: nome do debitado (pos. 044-073) nao informado."
                )

            seu_numero = _campo_posicional(registro, 74, 88).strip()
            data_agendada_raw = _campo_posicional(registro, 94, 101)
            data_agendada = _parse_data_ddmmaaaa(data_agendada_raw)
            if not data_agendada:
                erros_detalhes.append(
                    f"Linha {numero_linha}: data agendada (pos. 094-101) invlida."
                )

            tipo_moeda = _campo_posicional(registro, 102, 104).strip().upper()
            if tipo_moeda not in ITAU_SISDEB_TIPOS_MOEDA:
                erros_detalhes.append(
                    f"Linha {numero_linha}: tipo de moeda (pos. 102-104) deve ser um dos valores permitidos ({', '.join(sorted(ITAU_SISDEB_TIPOS_MOEDA))})."
                )

            quantidade_raw = _campo_posicional(registro, 105, 119)
            quantidade_valor = _parse_decimal_str(quantidade_raw, 5)
            if quantidade_valor is None:
                erros_detalhes.append(
                    f"Linha {numero_linha}: quantidade/IOF (pos. 105-119) deve conter apenas digitos."
                )
                quantidade_valor = 0

            valor_raw = _campo_posicional(registro, 120, 134)
            valor_centavos = _parse_decimal_str(valor_raw, 2)
            if valor_centavos is None:
                erros_detalhes.append(
                    f"Linha {numero_linha}: valor agendado (pos. 120-134) deve conter apenas digitos."
                )
                valor_centavos = 0

            if tipo_moeda == "REA" and valor_centavos == 0:
                erros_detalhes.append(
                    f"Linha {numero_linha}: para moeda 'REA', o valor agendado deve ser maior que zero."
                )

            if tipo_moeda != "REA" and quantidade_valor == 0:
                avisos.append(
                    f"Linha {numero_linha}: para moeda diferente de 'REA', o campo quantidade (pos. 105-119) deveria conter o valor a debitar."
                )

            nosso_numero = _campo_posicional(registro, 135, 154).strip()
            if nosso_numero:
                avisos.append(
                    f"Linha {numero_linha}: o campo Nosso Nmero (pos. 135-154) deve ficar em branco na remessa SISDEB."
                )

            data_cobrada = _campo_posicional(registro, 155, 162).strip()
            if data_cobrada:
                avisos.append(
                    f"Linha {numero_linha}: data cobrada (pos. 155-162) deve permanecer em branco na remessa."
                )
            valor_cobrado_raw = _campo_posicional(registro, 163, 177).strip()
            if valor_cobrado_raw and valor_cobrado_raw.strip("0") != "":
                avisos.append(
                    f"Linha {numero_linha}: valor cobrado (pos. 163-177) deve permanecer zerado na remessa."
                )

            tipo_mora = _campo_posicional(registro, 178, 179).strip()
            valor_mora_raw = _campo_posicional(registro, 180, 196)
            valor_mora = _parse_decimal_str(valor_mora_raw, 5)
            if valor_mora is None:
                erros_detalhes.append(
                    f"Linha {numero_linha}: valor da mora (pos. 180-196) deve conter apenas digitos."
                )
                valor_mora = 0

            if tipo_moeda == "REA":
                if tipo_mora not in ITAU_SISDEB_TIPOS_MORA_REAL:
                    erros_detalhes.append(
                        f"Linha {numero_linha}: tipo da mora (pos. 178-179) deve ser 00, 01 ou 03 para moeda 'REA'."
                    )
                if tipo_mora == "00" and valor_mora != 0:
                    erros_detalhes.append(
                        f"Linha {numero_linha}: tipo da mora '00' exige valor de mora zerado."
                    )
            else:
                if tipo_mora and not tipo_mora.isdigit():
                    erros_detalhes.append(
                        f"Linha {numero_linha}: tipo da mora (pos. 178-179) deve ser numerico."
                    )

            documento_debitado = _campo_posicional(registro, 217, 230).strip()
            if not documento_debitado or not documento_debitado.isdigit():
                erros_detalhes.append(
                    f"Linha {numero_linha}: numero de inscricao do debitado (pos. 217-230) deve ser numerico."
                )

            ocorrencias = _campo_posicional(registro, 231, 240).strip()
            if ocorrencias:
                avisos.append(
                    f"Linha {numero_linha}: campo de ocorrncias (pos. 231-240) deve permanecer em branco na remessa."
                )

            info_lote["valor_centavos"] += valor_centavos
            info_lote["quantidade_moeda"] += quantidade_valor

            resumo["qtd_titulos"] += 1
            resumo["valor_total_centavos"] += valor_centavos

            if data_agendada:
                if resumo["vencimento_min"] is None or data_agendada < resumo["vencimento_min"]:
                    resumo["vencimento_min"] = data_agendada
                if resumo["vencimento_max"] is None or data_agendada > resumo["vencimento_max"]:
                    resumo["vencimento_max"] = data_agendada

            titulos.append(
                {
                    "lote": lote,
                    "sequencia": _campo_posicional(registro, 9, 13).strip(),
                    "nosso_numero": nosso_numero or "",
                    "seu_numero": seu_numero or "",
                    "data_vencimento_str": _formatar_data_br(data_agendada),
                    "valor_centavos": valor_centavos,
                    "valor_reais": valor_centavos / 100.0,
                    "sacado_documento": documento_debitado,
                    "sacado_nome": nome_debitado,
                    "sacado_endereco": "",
                    "sacado_bairro": "",
                    "sacado_cep": "",
                    "sacado_cidade": "",
                    "sacado_uf": "",
                    "itau_tipo_moeda": tipo_moeda,
                    "itau_quantidade_moeda": quantidade_valor,
                    "itau_codigo_movimento": codigo_mov,
                    "itau_agencia_debitada": agencia_debitada,
                    "itau_conta_debitada": conta_debitada,
                }
            )

        elif tipo == "5":
            lote = _campo_posicional(registro, 4, 7)
            info_lote = lotes_info.get(lote)
            if not info_lote:
                erros_trailer.append(
                    f"Linha {numero_linha}: trailer do lote {lote} encontrado sem header correspondente."
                )
                continue

            info_lote["registros"] += 1
            info_lote["trailer_processado"] = True

            qtd_registros = _campo_posicional(registro, 18, 23).strip()
            if not qtd_registros or not qtd_registros.isdigit():
                erros_trailer.append(
                    f"Linha {numero_linha}: quantidade de registros (pos. 018-023) deve ser numrica."
                )
            else:
                if int(qtd_registros) != info_lote["registros"]:
                    erros_trailer.append(
                        f"Linha {numero_linha}: lote {lote} informa {int(qtd_registros)} registros no trailer, mas foram encontrados {info_lote['registros']} (header + detalhes + trailer)."
                    )

            total_valor_raw = _campo_posicional(registro, 24, 41).strip()
            total_valor = _parse_decimal_str(total_valor_raw, 2)
            if total_valor is None:
                erros_trailer.append(
                    f"Linha {numero_linha}: total de valores (pos. 024-041) deve conter apenas digitos."
                )
            else:
                if total_valor != info_lote["valor_centavos"]:
                    erros_trailer.append(
                        f"Linha {numero_linha}: soma dos valores do lote {lote} (R$ {info_lote['valor_centavos'] / 100:.2f}) difere do total informado no trailer."
                    )

            total_quantidade_raw = _campo_posicional(registro, 42, 59).strip()
            total_quantidade = _parse_decimal_str(total_quantidade_raw, 5)
            if total_quantidade is None:
                erros_trailer.append(
                    f"Linha {numero_linha}: total da quantidade de moedas (pos. 042-059) deve conter apenas digitos."
                )
            else:
                if total_quantidade != info_lote["quantidade_moeda"]:
                    erros_trailer.append(
                        f"Linha {numero_linha}: somatorio da quantidade/IOF do lote {lote} difere do informado no trailer."
                    )

        elif tipo == "9":
            if trailer_arquivo is not None:
                erros_trailer.append("Foram encontrados dois trailers de arquivo (tipo 9).")
            trailer_arquivo = registro

    if header_arquivo is None:
        erros_header.append("Arquivo CNAB 240 do Itau sem header (tipo 0).")

    if trailer_arquivo is None:
        erros_trailer.append("Arquivo CNAB 240 do Itau sem trailer (tipo 9).")
    else:
        codigo_lote = _campo_posicional(trailer_arquivo, 4, 7)
        if codigo_lote != "9999":
            erros_trailer.append(
                "Trailer de arquivo (pos. 004-007) deve conter '9999'."
            )

        qtd_lotes = _campo_posicional(trailer_arquivo, 18, 23).strip()
        if qtd_lotes and qtd_lotes.isdigit():
            if int(qtd_lotes) != total_lotes_contados:
                erros_trailer.append(
                    f"Trailer do arquivo informa {int(qtd_lotes)} lotes, mas foram encontrados {total_lotes_contados} headers de lote."
                )
        else:
            erros_trailer.append(
                "Trailer do arquivo deve informar a quantidade de lotes (pos. 018-023)."
            )

        qtd_registros = _campo_posicional(trailer_arquivo, 24, 29).strip()
        if qtd_registros and qtd_registros.isdigit():
            if int(qtd_registros) != total_registros_contados:
                erros_trailer.append(
                    f"Trailer do arquivo informa {int(qtd_registros)} registros, mas foram encontrados {total_registros_contados} do tipo 0/1/3/5/9."
                )
        else:
            erros_trailer.append(
                "Trailer do arquivo deve informar a quantidade de registros (pos. 024-029)."
            )

    for lote, info in lotes_info.items():
        if not info["trailer_processado"]:
            erros_trailer.append(
                f"O lote {lote} nao possui trailer (registro tipo 5)."
            )

    resumo["valor_total_reais"] = resumo["valor_total_centavos"] / 100.0

    return {
        "erros_header": erros_header,
        "erros_lotes": erros_lotes,
        "erros_detalhes": erros_detalhes,
        "erros_trailer": erros_trailer,
        "avisos": avisos,
        "titulos": titulos,
        "resumo": resumo,
    }
