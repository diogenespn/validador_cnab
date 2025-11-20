"""Rotinas comuns do CNAB 240."""

from datetime import datetime
from ..base import ESTADOS_BR, limpar_numero
from ..cnab400.utils import _campo_cnab400

def validar_estrutura_basica_cnab240(linhas):
    """
    Faz validações gerais de estrutura para CNAB 240:
    - Tipo de registro em cada linha (posição 8)
    - Header de arquivo (primeira linha) deve ser tipo '0'
    - Trailer de arquivo (última linha) deve ser tipo '9'
    """
    erros = []

    # Header = primeira linha
    header = linhas[0].rstrip("\n\r")
    tipo_header = header[7:8]  # posição 8 no layout -> índice 7 em Python

    if tipo_header != "0":
        erros.append(
            "Header de arquivo inválido: tipo de registro na linha 1 é "
            f"'{tipo_header}', esperado '0'."
        )

    # Trailer = última linha não vazia
    ultima_linha_idx = len(linhas) - 1
    while ultima_linha_idx >= 0 and linhas[ultima_linha_idx].strip() == "":
        ultima_linha_idx -= 1

    if ultima_linha_idx < 0:
        erros.append("Arquivo não possui linhas válidas (todas em branco).")
        return erros

    trailer = linhas[ultima_linha_idx].rstrip("\n\r")
    tipo_trailer = trailer[7:8]

    if tipo_trailer != "9":
        erros.append(
            "Trailer de arquivo inválido: tipo de registro na linha "
            f"{ultima_linha_idx + 1} é '{tipo_trailer}', esperado '9'."
        )

    # Validação dos tipos de registro em todas as linhas
    tipos_validos = {"0", "1", "2", "3", "4", "5", "9"}
    # OBS: alguns bancos nem usam todos, mas esses são os previstos na FEBRABAN

    for i, linha in enumerate(linhas, start=1):
        if linha.strip() == "":
            continue  # ignora linha totalmente em branco
        if len(linha.rstrip("\n\r")) < 8:
            erros.append(
                f"Linha {i}: muito curta para ler o tipo de registro (menos de 8 caracteres)."
            )
            continue

        tipo_registro = linha[7:8]
        if tipo_registro not in tipos_validos:
            erros.append(
                f"Linha {i}: tipo de registro '{tipo_registro}' inválido "
                f"(esperado um de {sorted(tipos_validos)})."
            )

    return erros

def validar_codigo_banco_consistente(linhas, codigo_banco_esperado):
    """
    Verifica se todas as linhas têm o mesmo código de banco do header (posições 1 a 3).
    """
    erros = []
    for i, linha in enumerate(linhas, start=1):
        if linha.strip() == "":
            continue
        codigo = linha[0:3]
        if codigo != codigo_banco_esperado:
            erros.append(
                f"Linha {i}: código do banco '{codigo}' diferente do header "
                f"'{codigo_banco_esperado}'."
            )
            
    return erros

def validar_lotes_cnab240(linhas):
    """
    Valida a existência de header e trailer de lote para cada lote.
    - Lote: posições 4 a 7 (índices 3 a 7 em Python)
    - Tipo de registro: posição 8 (índice 7)
      0 = Header Arquivo
      1 = Header Lote
      3 = Detalhe
      5 = Trailer Lote
      9 = Trailer Arquivo
    """
    erros = []

    lotes = {}  # {numero_lote: {"header": False, "trailer": False, "tem_detalhe": False}}

    for i, linha in enumerate(linhas, start=1):
        if linha.strip() == "":
            continue

        if len(linha.rstrip("\n\r")) < 8:
            erros.append(f"Linha {i}: muito curta para ler lote/tipo de registro.")
            continue

        tipo = linha[7:8]
        numero_lote = linha[3:7]

        # Header e trailer de arquivo (tipo 0 e 9) usam lote "0000" em geral, ignoramos aqui
        if tipo in {"0", "9"}:
            continue

        if numero_lote not in lotes:
            lotes[numero_lote] = {
                "header": False,
                "trailer": False,
                "tem_detalhe": False,
            }

        if tipo == "1":
            lotes[numero_lote]["header"] = True
        elif tipo == "5":
            lotes[numero_lote]["trailer"] = True
        elif tipo == "3":
            lotes[numero_lote]["tem_detalhe"] = True

    for numero_lote, info in lotes.items():
        if not info["header"]:
            erros.append(f"Lote {numero_lote}: não possui Header de Lote (tipo 1).")
        if not info["trailer"]:
            erros.append(f"Lote {numero_lote}: não possui Trailer de Lote (tipo 5).")
        if not info["tem_detalhe"]:
            erros.append(
                f"Lote {numero_lote}: não possui registros de detalhe (tipo 3)."
            )

    return erros

def validar_qtd_registros_lote_cnab240(linhas):
    """
    Validação avançada (CNAB 240):
    - Confere se a quantidade de registros informada no trailer de cada lote
      (posições 18-23, campo 'Quantidade de Registros no Lote', padrão FEBRABAN)
      bate com a quantidade real de linhas daquele lote no arquivo.

    Se houver divergência, gera erro para o lote correspondente.
    """

    erros = []

    # Mapa de lotes: lote -> { "linhas_idx": [números de linha], "trailer": (idx, linha) }
    lotes = {}

    for idx, linha in enumerate(linhas, start=1):
        l = linha.rstrip("\r\n")
        if len(l) < 8:
            continue

        # Posição 4-7 (1-based) => índice 3-7 (0-based)
        lote = l[3:7]
        # Posição 8 (1-based) => índice 7 (0-based)
        tipo = l[7:8]

        # Ignora header de arquivo (tipo 0) e trailer de arquivo (tipo 9)
        # Trabalhamos apenas com registros que pertencem a algum lote: tipos 1, 3, 5 (e eventualmente 2 e 4)
        if lote.strip() == "" or tipo in ("0", "9"):
            continue

        info = lotes.setdefault(lote, {"linhas_idx": [], "trailer": None})
        info["linhas_idx"].append(idx)

        # Trailer de lote: tipo de registro = '5'
        if tipo == "5":
            info["trailer"] = (idx, l)

    # Agora conferimos cada lote que tem trailer
    for lote, info in lotes.items():
        trailer = info["trailer"]
        if not trailer:
            # Já deve ser apontado em outras validações (estrutura de lotes), então aqui só ignoramos
            continue

        idx_trailer, l = trailer

        # Precisamos ao menos até a posição 23 (1-based) => índice 22 (0-based)
        if len(l) < 23:
            erros.append(
                f"Lote {lote}: trailer (linha {idx_trailer}) muito curto para conter a quantidade de registros "
                "nas posições 18-23."
            )
            continue

        # Posição 18-23 (1-based) => índices 17-23 (0-based)
        qtd_str = l[17:23]
        if not qtd_str.isdigit():
            erros.append(
                f"Lote {lote}: quantidade de registros no trailer (linha {idx_trailer}) "
                f"'{qtd_str}' não é numérica."
            )
            continue

        qtd_trailer = int(qtd_str)

        # Quantidade real de linhas pertencentes ao lote
        qtd_real = len(info["linhas_idx"])

        if qtd_real != qtd_trailer:
            erros.append(
                f"Lote {lote}: quantidade de registros informada no trailer ({qtd_trailer}) "
                f"é diferente da quantidade real de linhas do lote ({qtd_real})."
            )

    return erros

def validar_totais_arquivo_cnab240(linhas):
    """
    Validação avançada (CNAB 240):
    - Confere se a quantidade de lotes e a quantidade de registros informadas
      no trailer de arquivo (registro tipo 9) batem com o arquivo real.

    Padrão FEBRABAN para registro tipo 9:
      - Posição 8 (1-based)  => tipo de registro = '9'
      - Posição 18-23        => quantidade de lotes do arquivo
      - Posição 24-29        => quantidade de registros do arquivo
    """

    erros = []

    if not linhas:
        return erros

    # Localiza o trailer de arquivo (tipo de registro = '9' na posição 8)
    trailer = None
    idx_trailer = None
    for idx, linha in enumerate(linhas, start=1):
        l = linha.rstrip("\r\n")
        if len(l) < 29:
            continue
        tipo = l[7:8]
        if tipo == "9":
            trailer = l
            idx_trailer = idx
            break

    if trailer is None:
        # Se não há trailer, a validação básica de estrutura já deveria acusar isso.
        return erros

    # Extrai quantidades do trailer
    qtd_lotes_str = trailer[17:23]
    qtd_regs_str = trailer[23:29]

    if not qtd_lotes_str.isdigit():
        erros.append(
            f"Trailer de arquivo (linha {idx_trailer}): quantidade de lotes '{qtd_lotes_str}' não é numérica."
        )
        return erros

    if not qtd_regs_str.isdigit():
        erros.append(
            f"Trailer de arquivo (linha {idx_trailer}): quantidade de registros '{qtd_regs_str}' não é numérica."
        )
        return erros

    qtd_lotes_trailer = int(qtd_lotes_str)
    qtd_regs_trailer = int(qtd_regs_str)

    # Conta lotes reais no arquivo (registros tipo 1 na posição 8)
    qtd_lotes_real = 0
    for linha in linhas:
        l = linha.rstrip("\r\n")
        if len(l) < 8:
            continue
        tipo = l[7:8]
        if tipo == "1":
            qtd_lotes_real += 1

    # Quantidade real de registros do arquivo = total de linhas
    qtd_regs_real = len(linhas)

    if qtd_lotes_real != qtd_lotes_trailer:
        erros.append(
            f"Trailer de arquivo: quantidade de lotes informada ({qtd_lotes_trailer}) "
            f"é diferente da quantidade real de lotes ({qtd_lotes_real})."
        )

    if qtd_regs_real != qtd_regs_trailer:
        erros.append(
            f"Trailer de arquivo: quantidade de registros informada ({qtd_regs_trailer}) "
            f"é diferente da quantidade real de registros ({qtd_regs_real})."
        )

    return erros

def validar_sequencia_registros_lote(linhas):
    """
    Valida o número sequencial do registro no lote **apenas** para:
    - Registro de detalhe (tipo 3)

    Campo: posições 9 a 13 (índices 8 a 13)

    Ignoramos header/trailer de arquivo (0 e 9) e header/trailer de lote (1 e 5),
    porque em alguns layouts esses campos podem ser usados de outra forma ou ficar em branco.
    """
    erros = []

    registros_por_lote = {}  # {numero_lote: [(seq, linha_idx), ...]}

    for idx, linha in enumerate(linhas, start=1):
        if linha.strip() == "":
            continue

        if len(linha.rstrip("\n\r")) < 13:
            # Muito curta pra ter essa info, mas como só olhamos tipo 3, deixamos passar
            continue

        tipo = linha[7:8]

        # Só vamos validar tipo 3 (detalhe)
        if tipo != "3":
            continue

        numero_lote = linha[3:7]
        seq_str = linha[8:13]

        if not seq_str.isdigit():
            erros.append(
                f"Linha {idx}: no lote {numero_lote}, número sequencial "
                f"'{seq_str}' não é numérico (tipo de registro {tipo})."
            )
            continue

        seq = int(seq_str)

        if numero_lote not in registros_por_lote:
            registros_por_lote[numero_lote] = []
        registros_por_lote[numero_lote].append((seq, idx))

    # Agora verificamos se a sequência está crescente de 1 em 1 dentro de cada lote
    for numero_lote, registros in registros_por_lote.items():
        # registros estão na ordem do arquivo; vamos validar relação com o anterior
        prev_seq = None
        for seq, linha_idx in registros:
            if prev_seq is None:
                prev_seq = seq
                continue

            esperado = prev_seq + 1
            if seq != esperado:
                erros.append(
                    f"Linha {linha_idx}: no lote {numero_lote}, número sequencial é "
                    f"{seq}, esperado {esperado}."
                )
            prev_seq = seq

    return erros

LAYOUT_CNAB240_COMUM_PQ = {
    "P": {
        "nosso_numero": {
            "start": 37,
            "end": 57,  # posições 38-57
            "type": "alfanumerico",
            "required": True,
        },
        "data_vencimento": {
            "start": 77,
            "end": 85,  # posições 78-85 (DDMMAAAA)
            "type": "data_ddmmaaaa",
            "required": True,
        },
        "valor_titulo": {
            "start": 85,
            "end": 100,  # posições 86-100
            "type": "valor",
            "required": True,
        },
    },
    "Q": {
        "tipo_inscricao": {
            "start": 15,
            "end": 17,  # pos 16-17
            "type": "lista",
            "required": True,
            "allowed": ["01", "02"],  # 01 CPF, 02 CNPJ (padrão)
        },
        "documento_sacado": {
            "start": 17,
            "end": 32,  # pos 18-32
            "type": "numero",
            "required": True,
            "no_all_zeros": True,
        },
        "nome_sacado": {
            "start": 33,
            "end": 73,  # pos 34-73
            "type": "texto",
            "required": True,
            "min_len": 3,
        },
        "endereco_sacado": {
            "start": 73,
            "end": 113,  # pos 74-113
            "type": "texto",
            "required": True,
        },
        "bairro_sacado": {
            "start": 113,
            "end": 128,  # pos 114-128
            "type": "texto",
            "required": False,
        },
        "cep_sacado": {
            "start": 128,
            "end": 136,  # pos 129-136
            "type": "cep",
            "required": True,
        },
        "cidade_sacado": {
            "start": 136,
            "end": 151,  # pos 137-151
            "type": "texto",
            "required": True,
        },
        "uf_sacado": {
            "start": 151,
            "end": 153,  # pos 152-153
            "type": "uf",
            "required": True,
        },
    },
}

LAYOUTS_CNAB240 = {
    # Banco do Brasil
    "001": LAYOUT_CNAB240_COMUM_PQ,

    # Banco de Brasília (BRB)
    "070": LAYOUT_CNAB240_COMUM_PQ,

    # Caixa Econômica Federal
    "104": LAYOUT_CNAB240_COMUM_PQ,

    # Bradesco
    "237": LAYOUT_CNAB240_COMUM_PQ,

    # Itaú
    "341": LAYOUT_CNAB240_COMUM_PQ,

    # Santander
    "033": LAYOUT_CNAB240_COMUM_PQ,

    # Sicoob
    "756": LAYOUT_CNAB240_COMUM_PQ,

    # Sicredi
    "748": LAYOUT_CNAB240_COMUM_PQ,
}

def validar_segmentos_por_layout(codigo_banco, linhas):
    """
    Valida Segmentos (P, Q, etc.) com base no LAYOUTS_CNAB240.
    Percorre apenas registros de detalhe (tipo 3) e aplica as regras de cada campo.
    """
    erros = []
    avisos = []

    layout_banco = LAYOUTS_CNAB240.get(codigo_banco)
    if not layout_banco:
        avisos.append(
            f"Não há layout de segmentos configurado para o banco {codigo_banco}."
        )
        return erros, avisos

    for numero_linha, linha in enumerate(linhas, start=1):
        if linha.strip() == "":
            continue

        linha = linha.rstrip("\n\r")
        if len(linha) < 15:
            continue

        tipo_registro = linha[7:8]
        if tipo_registro != "3":
            continue

        segmento = linha[13:14].upper()
        if segmento not in layout_banco:
            continue

        campos = layout_banco[segmento]

        for nome_campo, spec in campos.items():
            start = spec["start"]
            end = spec["end"]
            raw = linha[start:end]
            valor = raw.strip()
            label = f"Linha {numero_linha} (Segmento {segmento} - {nome_campo})"
            pos_str = f"(posições {start + 1}-{end})"
            required = spec.get("required", False)

            # Obrigatório em branco
            if not valor:
                if required:
                    erros.append(f"{label}: campo obrigatório em branco {pos_str}.")
                continue

            tipo = spec["type"]

            if tipo == "numero":
                if not valor.isdigit():
                    erros.append(
                        f"{label}: valor '{raw}' contém caracteres não numéricos {pos_str}."
                    )
                elif spec.get("no_all_zeros") and set(valor) == {"0"}:
                    erros.append(
                        f"{label}: valor não pode ser composto apenas por zeros {pos_str}."
                    )

            elif tipo == "alfanumerico":
                if not valor.isalnum():
                    avisos.append(
                        f"{label}: valor '{valor}' contém caracteres não alfanuméricos {pos_str}."
                    )

            elif tipo == "texto":
                min_len = spec.get("min_len", 0)
                if len(valor) < min_len:
                    avisos.append(
                        f"{label}: texto muito curto (tamanho {len(valor)}, "
                        f"mínimo {min_len}) {pos_str}."
                    )

            elif tipo == "lista":
                allowed = spec.get("allowed", [])
                if valor not in allowed:
                    erros.append(
                        f"{label}: valor '{valor}' inválido (esperado um de {allowed}) {pos_str}."
                    )

            elif tipo == "data_ddmmaaaa":
                if len(valor) != 8 or not valor.isdigit():
                    erros.append(
                        f"{label}: data '{raw}' com formato inválido "
                        f"(esperado DDMMAAAA numérico) {pos_str}."
                    )
                else:
                    dia = int(valor[0:2])
                    mes = int(valor[2:4])
                    ano = int(valor[4:8])
                    if not (1 <= dia <= 31 and 1 <= mes <= 12 and 1900 <= ano <= 2099):
                        erros.append(
                            f"{label}: data '{valor}' fora de faixa válida {pos_str}."
                        )

            elif tipo == "valor":
                if not valor.isdigit():
                    erros.append(
                        f"{label}: valor '{raw}' não é numérico {pos_str}."
                    )
                else:
                    centavos = int(valor)
                    if centavos <= 0:
                        erros.append(
                            f"{label}: valor deve ser maior que zero {pos_str}."
                        )

            elif tipo == "cep":
                if not valor.isdigit() or len(valor) != 8:
                    erros.append(
                        f"{label}: CEP '{raw}' inválido (esperado 8 dígitos) {pos_str}."
                    )
                elif valor == "00000000":
                    erros.append(
                        f"{label}: CEP não pode ser '00000000' {pos_str}."
                    )

            elif tipo == "uf":
                if valor not in ESTADOS_BR:
                    erros.append(
                        f"{label}: UF '{raw}' inválida (não é um estado brasileiro conhecido) {pos_str}."
                    )

    return erros, avisos

def validar_dados_cedente_vs_arquivo(codigo_banco: str, linhas, dados_conta, layout: int = 240):
    """
    Compara os dados informados pelo usuário (banco, agência, conta, documento, nome)
    com o que está no arquivo de remessa.

    Por enquanto implementado para:
    - Banco do Brasil (001), CNAB 240

    'dados_conta' é um dicionário com:
      - banco
      - agencia
      - conta
      - documento (CPF/CNPJ)
      - nome (razão social)
    """
    erros = []
    avisos = []

    if not dados_conta:
        return erros, avisos

    # Se o usuário informou banco e for diferente do detectado
    banco_inf = (dados_conta.get("banco") or "").strip()
    if banco_inf and banco_inf != codigo_banco:
        erros.append(
            f"Banco informado ({banco_inf}) é diferente do banco detectado no arquivo ({codigo_banco})."
        )

    # Por enquanto, tratamos só Banco do Brasil
    if codigo_banco != "001":
        # Se ele informou alguma coisa, avisamos que ainda não comparamos
        if any((dados_conta.get("agencia"), dados_conta.get("conta"),
                dados_conta.get("documento"), dados_conta.get("nome"))):
            avisos.append(
                f"Validação dos dados da conta/titular ainda não implementada para o banco {codigo_banco}."
            )
        return erros, avisos

    # --- Banco do Brasil (001) ---

    if layout == 240:
        # Header de arquivo = primeira linha
        header = linhas[0].rstrip("\r\n")

        # CNPJ do cedente no header (índices 17-30 -> pos. 18-31)
        cnpj_arquivo = header[17:31].strip() if len(header) >= 31 else ""
        # Nome do cedente (índices 72-101 -> pos. 73-102), 30 caracteres
        nome_cedente_arquivo = header[72:102].strip() if len(header) >= 102 else ""

        # Documento informado (CPF/CNPJ)
        doc_inf = limpar_numero(dados_conta.get("documento", ""))
        doc_arq = limpar_numero(cnpj_arquivo)

        if doc_inf and doc_arq and doc_inf != doc_arq:
            erros.append(
                f"Documento do titular informado ({doc_inf}) é diferente do documento do cedente no arquivo ({doc_arq})."
            )

        # Nome informado x nome no arquivo (cedente)
        nome_inf = (dados_conta.get("nome") or "").strip()
        if nome_inf and nome_cedente_arquivo:
            nome_inf_upper = nome_inf.upper()
            nome_arq_upper = nome_cedente_arquivo.upper()
            # Se um não contém o outro (considerando possíveis truncamentos), consideramos divergência leve (aviso)
            if nome_inf_upper not in nome_arq_upper and nome_arq_upper not in nome_inf_upper:
                avisos.append(
                    "Nome/Razão social informada difere do nome do cedente no arquivo: "
                    f"informado '{nome_inf}', arquivo '{nome_cedente_arquivo}'."
                )

        # Procurar primeiro header de lote (tipo de registro = '1')
        header_lote = None
        for linha in linhas[1:]:
            linha_limpa = linha.rstrip("\r\n")
            if len(linha_limpa) >= 8 and linha_limpa[7:8] == "1":
                header_lote = linha_limpa
                break

        if header_lote:
            # No BB CNAB 240, header de lote:
            # Agência mantenedora da conta: índices 53-57 (5 dígitos)
            # DV agência: índice 58
            # Conta: índices 59-70 (12 dígitos)
            # DV conta: índice 71
            if len(header_lote) >= 72:
                agencia_arq_raw = header_lote[53:58]
                conta_arq_raw = header_lote[59:71]

                agencia_arq = limpar_numero(agencia_arq_raw)
                conta_arq = limpar_numero(conta_arq_raw)

                # Agência
                ag_inf = limpar_numero(dados_conta.get("agencia", ""))
                if ag_inf and agencia_arq:
                    if ag_inf.lstrip("0") != agencia_arq.lstrip("0"):
                        erros.append(
                            f"Agência informada ({ag_inf}) é diferente da agência no arquivo ({agencia_arq})."
                        )

                # Conta
                conta_inf = limpar_numero(dados_conta.get("conta", ""))
                if conta_inf and conta_arq:
                    if conta_inf.lstrip("0") != conta_arq.lstrip("0"):
                        erros.append(
                            f"Conta informada ({conta_inf}) é diferente da conta no arquivo ({conta_arq})."
                        )
            else:
                avisos.append(
                    "Header de lote encontrado, mas muito curto para ler agência/conta."
                )
        else:
            avisos.append("Nenhum Header de Lote (tipo 1) encontrado para validar agência/conta.")
    elif layout == 400:
        header = None
        for linha in linhas:
            linha_limpa = linha.rstrip("\r\n")
            if linha_limpa and linha_limpa[0:1] == "0":
                header = linha_limpa
                break

        if not header:
            avisos.append("Não foi possível localizar o header do arquivo CNAB 400 para validar os dados do cedente.")
            return erros, avisos

        agencia_arq = _campo_cnab400(header, 27, 30).strip()
        conta_arq = _campo_cnab400(header, 32, 39).strip()
        nome_cedente_arquivo = _campo_cnab400(header, 47, 76).strip()

        doc_arq = ""
        for linha in linhas:
            linha_limpa = linha.rstrip("\r\n")
            if linha_limpa and linha_limpa[0:1] == "7":
                doc_arq = limpar_numero(_campo_cnab400(linha_limpa, 4, 17))
                break

        doc_inf = limpar_numero(dados_conta.get("documento", ""))
        if doc_inf and doc_arq and doc_inf != doc_arq:
            erros.append(
                f"Documento do titular informado ({doc_inf}) é diferente do documento do beneficiário no arquivo ({doc_arq})."
            )

        nome_inf = (dados_conta.get("nome") or "").strip()
        if nome_inf and nome_cedente_arquivo:
            nome_inf_upper = nome_inf.upper()
            nome_arq_upper = nome_cedente_arquivo.upper()
            if nome_inf_upper not in nome_arq_upper and nome_arq_upper not in nome_inf_upper:
                avisos.append(
                    "Nome/Razão social informada difere do nome do cedente no header: "
                    f"informado '{nome_inf}', arquivo '{nome_cedente_arquivo}'."
                )

        ag_inf = limpar_numero(dados_conta.get("agencia", ""))
        if ag_inf and agencia_arq:
            if ag_inf.lstrip("0") != agencia_arq.lstrip("0"):
                erros.append(
                    f"Agência informada ({ag_inf}) é diferente da agência do header ({agencia_arq})."
                )

        conta_inf = limpar_numero(dados_conta.get("conta", ""))
        if conta_inf and conta_arq:
            if conta_inf.lstrip("0") != conta_arq.lstrip("0"):
                erros.append(
                    f"Conta informada ({conta_inf}) é diferente da conta do header ({conta_arq})."
                )
    else:
        avisos.append(
            f"Validação dos dados informados ainda não está disponível para o layout CNAB {layout}."
        )

    return erros, avisos

def gerar_resumo_remessa_cnab240(codigo_banco: str, linhas):
    """
    Gera um resumo da remessa com base nos Segmentos P:
    - quantidade de títulos
    - valor total
    - menor e maior vencimento

    Por enquanto implementado usando o layout configurado para o banco 001 (Banco do Brasil).
    """
    resumo = {
        "qtd_titulos": 0,
        "valor_total_centavos": 0,
        "valor_total_reais": 0.0,
        "vencimento_min": None,   # datetime
        "vencimento_max": None,   # datetime
    }

    layout_banco = LAYOUTS_CNAB240.get(codigo_banco)
    if not layout_banco or "P" not in layout_banco:
        return resumo

    campos_p = layout_banco["P"]
    cfg_venc = campos_p.get("data_vencimento")
    cfg_valor = campos_p.get("valor_titulo")

    if not cfg_venc or not cfg_valor:
        return resumo

    start_venc = cfg_venc["start"]
    end_venc = cfg_venc["end"]
    start_valor = cfg_valor["start"]
    end_valor = cfg_valor["end"]

    for linha in linhas:
        if linha.strip() == "":
            continue
        linha = linha.rstrip("\r\n")
        if len(linha) < max(end_venc, end_valor, 14):
            continue

        tipo_registro = linha[7:8]
        segmento = linha[13:14].upper()

        if tipo_registro != "3" or segmento != "P":
            continue

        # Data de vencimento
        data_raw = linha[start_venc:end_venc].strip()
        dt = None
        if len(data_raw) == 8 and data_raw.isdigit():
            dia = int(data_raw[0:2])
            mes = int(data_raw[2:4])
            ano = int(data_raw[4:8])
            try:
                if 1 <= dia <= 31 and 1 <= mes <= 12 and 1900 <= ano <= 2099:
                    dt = datetime(ano, mes, dia)
            except ValueError:
                dt = None

        # Valor
        valor_raw = linha[start_valor:end_valor].strip()
        if valor_raw.isdigit():
            valor_cent = int(valor_raw)
        else:
            valor_cent = 0  # se estiver inválido, ignora neste resumo

        # Atualiza resumo
        resumo["qtd_titulos"] += 1
        resumo["valor_total_centavos"] += valor_cent

        if dt:
            if resumo["vencimento_min"] is None or dt < resumo["vencimento_min"]:
                resumo["vencimento_min"] = dt
            if resumo["vencimento_max"] is None or dt > resumo["vencimento_max"]:
                resumo["vencimento_max"] = dt

    # Calcula valor em reais
    resumo["valor_total_reais"] = resumo["valor_total_centavos"] / 100.0

    return resumo

def listar_titulos_cnab240(codigo_banco: str, linhas):
    """
    Retorna uma lista de títulos encontrados na remessa CNAB 240 para o banco informado.

    Cada item da lista é um dicionário com:
      - lote
      - sequencia
      - nosso_numero
      - data_vencimento_str (dd/mm/aaaa ou None)
      - valor_centavos
      - valor_reais
      - sacado_documento
      - sacado_nome
      - sacado_endereco / bairro / cidade / UF / CEP
    """

    titulos = []

    layout_banco = LAYOUTS_CNAB240.get(codigo_banco)
    if not layout_banco:
        return titulos

    campos_p = layout_banco.get("P")
    campos_q = layout_banco.get("Q")

    if not campos_p:
        return titulos

    cfg_nosso = campos_p.get("nosso_numero")
    cfg_venc = campos_p.get("data_vencimento")
    cfg_valor = campos_p.get("valor_titulo")

    if not (cfg_nosso and cfg_venc and cfg_valor):
        return titulos

    start_nosso, end_nosso = cfg_nosso["start"], cfg_nosso["end"]
    start_venc, end_venc = cfg_venc["start"], cfg_venc["end"]
    start_valor, end_valor = cfg_valor["start"], cfg_valor["end"]

    # Campos do sacado (Segmento Q) — inicialização
    start_doc_sacado = end_doc_sacado = None
    start_nome_sacado = end_nome_sacado = None
    start_endereco = end_endereco = None
    start_bairro = end_bairro = None
    start_cep = end_cep = None
    start_cidade = end_cidade = None
    start_uf = end_uf = None

    if campos_q:
        cfg_doc_sac = campos_q.get("documento_sacado")
        cfg_nome_sac = campos_q.get("nome_sacado")
        cfg_endereco = campos_q.get("endereco_sacado")
        cfg_bairro = campos_q.get("bairro_sacado")
        cfg_cep = campos_q.get("cep_sacado")
        cfg_cidade = campos_q.get("cidade_sacado")
        cfg_uf = campos_q.get("uf_sacado")

        if cfg_doc_sac:
            start_doc_sacado, end_doc_sacado = cfg_doc_sac["start"], cfg_doc_sac["end"]
        if cfg_nome_sac:
            start_nome_sacado, end_nome_sacado = cfg_nome_sac["start"], cfg_nome_sac["end"]
        if cfg_endereco:
            start_endereco, end_endereco = cfg_endereco["start"], cfg_endereco["end"]
        if cfg_bairro:
            start_bairro, end_bairro = cfg_bairro["start"], cfg_bairro["end"]
        if cfg_cep:
            start_cep, end_cep = cfg_cep["start"], cfg_cep["end"]
        if cfg_cidade:
            start_cidade, end_cidade = cfg_cidade["start"], cfg_cidade["end"]
        if cfg_uf:
            start_uf, end_uf = cfg_uf["start"], cfg_uf["end"]

    total_linhas = len(linhas)

    for idx, linha in enumerate(linhas):
        if not linha or linha.strip() == "":
            continue
        linha = linha.rstrip("\r\n")
        if len(linha) < max(end_nosso, end_venc, end_valor, 14):
            continue

        tipo_registro = linha[7:8]
        segmento = linha[13:14].upper()

        if tipo_registro != "3" or segmento != "P":
            continue

        lote = linha[3:7]
        sequencia = linha[8:13]

        # Nosso número
        nosso_numero = linha[start_nosso:end_nosso].strip()

        # Data de vencimento
        data_raw = linha[start_venc:end_venc].strip()
        data_vencimento_str = None
        if len(data_raw) == 8 and data_raw.isdigit():
            dia = int(data_raw[0:2])
            mes = int(data_raw[2:4])
            ano = int(data_raw[4:8])
            try:
                if 1 <= dia <= 31 and 1 <= mes <= 12 and 1900 <= ano <= 2099:
                    dt = datetime(ano, mes, dia)
                    data_vencimento_str = dt.strftime("%d/%m/%Y")
            except ValueError:
                data_vencimento_str = None

        # Valor
        valor_raw = linha[start_valor:end_valor].strip()
        if valor_raw.isdigit():
            valor_centavos = int(valor_raw)
        else:
            valor_centavos = 0
        valor_reais = valor_centavos / 100.0

        # Dados do sacado a partir do Segmento Q logo em seguida (padrão)
        sacado_documento = ""
        sacado_nome = ""
        sacado_endereco = ""
        sacado_bairro = ""
        sacado_cep = ""
        sacado_cidade = ""
        sacado_uf = ""
        # ---------------- Dados adicionais do Segmento R (descontos 2/3 e multa) ----------------
        desc2_codigo = ""
        desc2_data_str = None
        desc2_valor_reais = 0.0

        desc3_codigo = ""
        desc3_data_str = None
        desc3_valor_reais = 0.0

        multa_codigo = ""
        multa_data_str = None
        multa_valor_reais = 0.0

        # Tenta localizar Segmento R logo após P/Q (nos próximos 2 registros)
        for delta in (1, 2):
            idx_r = idx + delta
            if idx_r >= total_linhas:
                continue

            prox_r = linhas[idx_r].rstrip("\r\n")
            if len(prox_r) < 90:
                continue

            tipo_reg_r = prox_r[7:8]
            segmento_r = prox_r[13:14].upper()
            lote_r = prox_r[3:7]

            if tipo_reg_r == "3" and segmento_r == "R" and lote_r == lote:
                # Desconto 2
                cod2 = prox_r[17:18].strip()
                data2_raw = prox_r[18:26].strip()
                valor2_raw = prox_r[26:41].strip()

                if cod2:
                    desc2_codigo = cod2
                if len(data2_raw) == 8 and data2_raw.isdigit():
                    dia2 = int(data2_raw[0:2])
                    mes2 = int(data2_raw[2:4])
                    ano2 = int(data2_raw[4:8])
                    try:
                        dt2 = datetime(ano2, mes2, dia2)
                        desc2_data_str = dt2.strftime("%d/%m/%Y")
                    except ValueError:
                        desc2_data_str = None
                if valor2_raw.isdigit():
                    desc2_valor_reais = int(valor2_raw) / 100.0

                # Desconto 3
                cod3 = prox_r[41:42].strip()
                data3_raw = prox_r[42:50].strip()
                valor3_raw = prox_r[50:65].strip()

                if cod3:
                    desc3_codigo = cod3
                if len(data3_raw) == 8 and data3_raw.isdigit():
                    dia3 = int(data3_raw[0:2])
                    mes3 = int(data3_raw[2:4])
                    ano3 = int(data3_raw[4:8])
                    try:
                        dt3 = datetime(ano3, mes3, dia3)
                        desc3_data_str = dt3.strftime("%d/%m/%Y")
                    except ValueError:
                        desc3_data_str = None
                if valor3_raw.isdigit():
                    desc3_valor_reais = int(valor3_raw) / 100.0

                # Multa
                codm = prox_r[65:66].strip()
                datam_raw = prox_r[66:74].strip()
                valorm_raw = prox_r[74:89].strip()

                if codm:
                    multa_codigo = codm
                if len(datam_raw) == 8 and datam_raw.isdigit():
                    diam = int(datam_raw[0:2])
                    mesm = int(datam_raw[2:4])
                    anom = int(datam_raw[4:8])
                    try:
                        dtm = datetime(anom, mesm, diam)
                        multa_data_str = dtm.strftime("%d/%m/%Y")
                    except ValueError:
                        multa_data_str = None
                if valorm_raw.isdigit():
                    multa_valor_reais = int(valorm_raw) / 100.0

                # achou um R válido, não precisa olhar mais
                break


        # Tenta ler Segmento Q (logo após o P)
        if idx + 1 < total_linhas:
            prox = linhas[idx + 1].rstrip("\r\n")

            if len(prox) >= 153:  # tamanho mínimo do Q
                tipo_reg_prox = prox[7:8]
                segmento_prox = prox[13:14].upper()
                lote_prox = prox[3:7]

                if tipo_reg_prox == "3" and segmento_prox == "Q" and lote_prox == lote:

                    # Documento
                    if start_doc_sacado is not None:
                        raw = prox[start_doc_sacado:end_doc_sacado]
                        sacado_documento = limpar_numero(raw.strip())

                    # Nome
                    if start_nome_sacado is not None:
                        sacado_nome = prox[start_nome_sacado:end_nome_sacado].strip()

                    # Endereço
                    if start_endereco is not None:
                        sacado_endereco = prox[start_endereco:end_endereco].strip()

                    # Bairro
                    if start_bairro is not None:
                        sacado_bairro = prox[start_bairro:end_bairro].strip()

                    # CEP
                    if start_cep is not None:
                        sacado_cep = prox[start_cep:end_cep].strip()

                    # Cidade
                    if start_cidade is not None:
                        sacado_cidade = prox[start_cidade:end_cidade].strip()

                    # UF
                    if start_uf is not None:
                        sacado_uf = prox[start_uf:end_uf].strip()

        titulos.append(
            {
                "lote": lote,
                "sequencia": sequencia,
                "nosso_numero": nosso_numero,
                "data_vencimento_str": data_vencimento_str,
                "valor_centavos": valor_centavos,
                "valor_reais": valor_reais,
                "sacado_documento": sacado_documento,
                "sacado_nome": sacado_nome,
                "sacado_endereco": sacado_endereco,
                "sacado_bairro": sacado_bairro,
                "sacado_cep": sacado_cep,
                "sacado_cidade": sacado_cidade,
                "sacado_uf": sacado_uf,

                # Dados Segmento R (se existirem)
                "r_desc2_codigo": desc2_codigo,
                "r_desc2_data_str": desc2_data_str,
                "r_desc2_valor_reais": desc2_valor_reais,
                "r_desc3_codigo": desc3_codigo,
                "r_desc3_data_str": desc3_data_str,
                "r_desc3_valor_reais": desc3_valor_reais,
                "r_multa_codigo": multa_codigo,
                "r_multa_data_str": multa_data_str,
                "r_multa_valor_reais": multa_valor_reais,
            }
        )

    return titulos
