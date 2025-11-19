import os

# ----------------------------
#  DETECÇÃO DE LAYOUT
# ----------------------------

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


# ----------------------------
#  DETECÇÃO DO BANCO
# ----------------------------

def identificar_banco(header_line):
    """
    Identifica o banco pelo código de compensação (posições 1 a 3 do arquivo, 3 dígitos).
    """
    codigo = header_line[0:3]

    bancos = {
        "001": "Banco do Brasil",
        "104": "Caixa Econômica Federal",
        "237": "Bradesco",
        "341": "Itaú Unibanco",
        "033": "Santander",
        "756": "Sicoob",
        "748": "Sicredi",
    }

    nome = bancos.get(codigo, "Banco não mapeado neste validador")
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


# ----------------------------
#  VALIDAÇÃO ESTRUTURAL CNAB 240
# ----------------------------

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

def validar_convenio_carteira_nosso_numero_bb(linhas):
    """
    Validações avançadas específicas do Banco do Brasil (CNAB 240):
    - Lê Convênio, Carteira e variação do Header de Lote (registro tipo 1).
    - Confere se o convênio tem tamanho coerente (4, 6 ou 7 dígitos úteis).
    - Confere valores de carteira mais usuais (11, 12, 17, 31, 51).
    - Verifica se o Nosso Número (Segmento P) está coerente com o convênio:
        * Convênio 4 ou 6 dígitos -> Nosso Número com 12 dígitos (convênio+sequencial+DV)
        * Convênio 7 dígitos       -> Nosso Número com 17 dígitos (convênio+sequencial)
        * Os primeiros dígitos do Nosso Número devem começar pelo convênio.
    Tudo em modo permissivo: retorna apenas avisos (erros fica normalmente vazio).
    """

    erros = []
    avisos = []

    # 1) Mapear por lote o convênio / carteira a partir do Header de Lote (tipo de registro '1')
    lotes_info = {}

    for idx, linha in enumerate(linhas, start=1):
        l = linha.rstrip("\r\n")
        if len(l) < 60:
            continue

        tipo_reg = l[7:8]   # posição 8 (1-based)
        lote = l[3:7]       # posições 4-7 (1-based)

        if tipo_reg != "1":
            continue

        # Conforme manual de particularidades do BB:
        # BB1 (convênio de cobrança)   -> pos. 34-42 (9 posições)
        # BB3 (nº da carteira cobrança)-> pos. 47-48 (2 posições)
        # BB4 (variação da carteira)   -> pos. 49-51 (3 posições) :contentReference[oaicite:3]{index=3}
        convenio_raw = l[33:42]        # 34-42 (1-based)
        carteira_raw = l[46:48]        # 47-48
        variacao_raw = l[48:51]        # 49-51

        convenio = convenio_raw.strip()
        carteira = carteira_raw.strip()
        variacao = variacao_raw.strip()

        info = {
            "linha_header": idx,
            "convenio_raw": convenio_raw,
            "convenio": convenio,
            "carteira": carteira,
            "variacao": variacao,
        }
        lotes_info[lote] = info

        # --- Validações de convênio no header de lote ---
        if not convenio:
            avisos.append(
                f"Linha {idx} (Lote {lote}, Header de Lote): "
                "Convênio de cobrança não informado no campo específico (posições 34-42). "
                "Verifique se o convênio foi configurado corretamente no arquivo."
            )
        else:
            if not convenio.isdigit():
                avisos.append(
                    f"Linha {idx} (Lote {lote}, Header de Lote): "
                    f"Convênio '{convenio}' contém caracteres não numéricos. "
                    "O Banco do Brasil trabalha com convênios numéricos."
                )
            else:
                conv_digits = convenio.lstrip("0")
                conv_len = len(conv_digits)
                if conv_len not in (4, 6, 7):
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Header de Lote): "
                        f"Convênio '{conv_digits}' possui {conv_len} dígitos úteis. "
                        "Pelas regras do BB, convênios de cobrança costumam ter 4, 6 ou 7 dígitos. "
                        "Confirme se o convênio está correto com o banco."
                    )

        # --- Validações básicas da carteira no header de lote ---
        if carteira:
            if not carteira.isdigit():
                avisos.append(
                    f"Linha {idx} (Lote {lote}, Header de Lote): "
                    f"Número da carteira de cobrança '{carteira}' não é numérico."
                )
            else:
                carteiras_mais_comuns = {"11", "12", "17", "31", "51"}
                if carteira not in carteiras_mais_comuns:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Header de Lote): "
                        f"Carteira de cobrança '{carteira}' não está entre as carteiras mais usuais "
                        "(11, 12, 17, 31, 51). Isso pode ser apenas um caso especial, mas vale conferir "
                        "com seu gerente/Banco do Brasil."
                    )

    # 2) Para cada Segmento P, conferir formação do Nosso Número x convênio
    for idx, linha in enumerate(linhas, start=1):
        l = linha.rstrip("\r\n")
        if len(l) < 60:
            continue

        tipo_reg = l[7:8]
        if tipo_reg != "3":
            continue

        lote = l[3:7]
        segmento = l[13:14]

        if segmento != "P":
            continue

        info_lote = lotes_info.get(lote)
        if not info_lote:
            # Se não achar o header do lote, não tem como validar convênio x Nosso Número
            continue

        convenio = info_lote.get("convenio") or ""
        if not convenio or not convenio.isdigit():
            # Sem convênio numérico, não aplicamos as regras de amarração com o Nosso Número
            continue

        conv_digits = convenio.lstrip("0")
        conv_len = len(conv_digits)

        # Segmento P - Identificação do Título no Banco (Nosso Número) = pos. 38-57 (20) :contentReference[oaicite:4]{index=4}
        campo_nn = l[37:57]
        nn_bruto = campo_nn.rstrip()  # tira espaços à direita, mantendo alinhamento à esquerda
        nn_compacto = nn_bruto.replace(" ", "")

        if not nn_compacto:
            # Nosso Número em branco – pode ser caso em que o BB gera
            avisos.append(
                f"Linha {idx} (Lote {lote}, Seg. P): Nosso Número não informado. "
                "Pelas regras do BB, isso é permitido quando o banco gera o número, "
                "mas confirme se é esse o comportamento desejado."
            )
            continue

        # Considerar apenas dígitos para checagem de tamanho/convênio
        nn_digitos = "".join(ch for ch in nn_compacto if ch.isdigit())
        tam_nn = len(nn_digitos)

        # Regras do manual do BB para composição do Nosso Número em função do convênio :contentReference[oaicite:5]{index=5}
        if conv_len in (4, 6):
            # Convênio 4 ou 6 dígitos -> Nosso Número com 12 dígitos (convênio + sequencial + DV)
            if tam_nn != 12:
                avisos.append(
                    f"Linha {idx} (Lote {lote}, Seg. P): Convênio de {conv_len} dígitos ({conv_digits}) "
                    f"normalmente utiliza Nosso Número com 12 dígitos (convênio + sequencial + DV), "
                    f"mas foram encontrados {tam_nn} dígitos em '{nn_bruto}'. "
                    "Confira se a montagem do Nosso Número está correta."
                )

            if tam_nn >= conv_len:
                prefixo = nn_digitos[:conv_len]
                if prefixo != conv_digits:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. P): Os primeiros {conv_len} dígitos do Nosso Número "
                        f"'{nn_bruto}' ({prefixo}) não conferem com o convênio do Header de Lote ({conv_digits}). "
                        "Verifique se o convênio usado na montagem do Nosso Número está correto."
                    )

        elif conv_len == 7:
            # Convênio 7 dígitos -> Nosso Número com 17 dígitos (convênio + sequencial)
            if tam_nn != 17:
                avisos.append(
                    f"Linha {idx} (Lote {lote}, Seg. P): Convênio de 7 dígitos ({conv_digits}) "
                    f"normalmente utiliza Nosso Número com 17 dígitos (convênio + sequencial), "
                    f"mas foram encontrados {tam_nn} dígitos em '{nn_bruto}'. "
                    "Confira se a montagem do Nosso Número está correta."
                )

            if tam_nn >= 7:
                prefixo = nn_digitos[:7]
                if prefixo != conv_digits:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. P): Os 7 primeiros dígitos do Nosso Número "
                        f"'{nn_bruto}' ({prefixo}) não conferem com o convênio do Header de Lote ({conv_digits}). "
                        "Verifique se o convênio usado na montagem do Nosso Número está correto."
                    )

        # Opcional: validar código da carteira (C006) do Segmento P x carteira do Header de Lote
        if len(l) >= 59:
            codigo_carteira = l[57:58]  # pos. 58 (1 dígito) :contentReference[oaicite:6]{index=6}
            numero_carteira = info_lote.get("carteira") or ""
            if numero_carteira and not codigo_carteira.strip():
                avisos.append(
                    f"Linha {idx} (Lote {lote}, Seg. P): Número da carteira no Header de Lote é '{numero_carteira}', "
                    "mas o campo 'Código da Carteira' no Segmento P (posição 58) está em branco. "
                    "Verifique se o código foi informado conforme o cadastro da carteira no banco."
                )

    return erros, avisos


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


# ----------------------------
#  LAYOUT CONFIGURÁVEL – CNAB 240
#  (por enquanto: Banco do Brasil 001, Segmentos P e Q)
# ----------------------------

ESTADOS_BR = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES",
    "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
    "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}

# start/end são índices Python (0-based), end é exclusivo
# Layout comum FEBRABAN para Segmentos P e Q (usado pela maioria dos bancos)
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


def limpar_numero(s: str) -> str:
    """
    Remove todos os caracteres que não são dígitos.
    """
    return "".join(ch for ch in (s or "") if ch.isdigit())

from datetime import datetime, timedelta

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

def validar_dados_cedente_vs_arquivo(codigo_banco: str, linhas, dados_conta):
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

    return erros, avisos

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

def validar_segmentos_avancados_bb(linhas):
    """
    Validações adicionais (modo permissivo: geram avisos) para:
    - Banco do Brasil (001), CNAB 240
    focadas em Segmentos P e Q.
    """

    avisos = []
    erros = []  # vamos praticamente não usar erros aqui (modo permissivo)

    # Posições fixas CNAB 240 BB para itens genéricos
    # tipo_registro = pos 8 (idx 7) => '3'
    # lote = pos 4-7 (idx 3-7)
    # segmento = pos 14 (idx 13)
    # código de movimento: pos 16-17 (2 dígitos, idx 15-17)
    cod_mov_start = 15
    cod_mov_end = 17

    # códigos de movimento mais comuns / permitidos
    codigos_mov_validos = {
        "01",  # entrada de títulos
        "02",  # pedido de baixa
        "04",  # concessão de abatimento
        "05",  # cancelamento de abatimento
        "06",  # alteração de vencimento
        "09",  # instrução de protesto
        "10",  # sustação de protesto
        "18",  # sustação de protesto / baixa
        "31",  # alteração de outros dados
    }

    # Para usar o layout cadastrado (P/Q) que já está em LAYOUTS_CNAB240
    layout_bb = LAYOUTS_CNAB240.get("001", {})
    campos_p = layout_bb.get("P", {})
    campos_q = layout_bb.get("Q", {})

    cfg_venc = campos_p.get("data_vencimento")
    cfg_valor = campos_p.get("valor_titulo")
    cfg_nosso = campos_p.get("nosso_numero")

    cfg_tipo_insc = campos_q.get("tipo_inscricao")
    cfg_doc_sac = campos_q.get("documento_sacado")
    cfg_nome_sac = campos_q.get("nome_sacado")
    cfg_endereco = campos_q.get("endereco_sacado")
    cfg_bairro = campos_q.get("bairro_sacado")
    cfg_cep = campos_q.get("cep_sacado")
    cfg_cidade = campos_q.get("cidade_sacado")
    cfg_uf = campos_q.get("uf_sacado")

    hoje = datetime.today().date()
    ufs_validas = {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES",
        "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
        "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
        "SP", "SE", "TO"
    }

    for idx, linha in enumerate(linhas, start=1):
        if not linha or linha.strip() == "":
            continue
        linha = linha.rstrip("\r\n")
        if len(linha) < 160:  # só considera linhas de detalhe com tamanho razoável
            continue

        tipo_registro = linha[7:8]
        segmento = linha[13:14].upper()

        # ---------------- Segmento P ----------------
        if tipo_registro == "3" and segmento == "P":
            lote = linha[3:7]

            # Código de movimento
            cod_mov = linha[cod_mov_start:cod_mov_end].strip()
            if cod_mov and (not cod_mov.isdigit() or len(cod_mov) != 2):
                avisos.append(
                    f"Linha {idx} (Lote {lote}, Seg. P): código de movimento '{cod_mov}' fora do padrão de 2 dígitos."
                )
            elif cod_mov and cod_mov not in codigos_mov_validos:
                avisos.append(
                    f"Linha {idx} (Lote {lote}, Seg. P): código de movimento '{cod_mov}' não está na lista de códigos mais comuns. "
                    "Verifique se está de acordo com o manual do banco."
                )

            # Data de vencimento
            if cfg_venc:
                s, e = cfg_venc["start"], cfg_venc["end"]
                if len(linha) >= e:
                    data_raw = linha[s:e].strip()
                    if data_raw and (not data_raw.isdigit() or len(data_raw) != 8):
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): data de vencimento '{data_raw}' não está no formato DDMMAAAA."
                        )
                    elif data_raw.isdigit():
                        dia = int(data_raw[0:2])
                        mes = int(data_raw[2:4])
                        ano = int(data_raw[4:8])
                        try:
                            dt = datetime(ano, mes, dia).date()
                            if dt < hoje:
                                avisos.append(
                                    f"Linha {idx} (Lote {lote}, Seg. P): data de vencimento {dt.strftime('%d/%m/%Y')} está no passado em relação à data atual."
                                )
                        except ValueError:
                            avisos.append(
                                f"Linha {idx} (Lote {lote}, Seg. P): data de vencimento '{data_raw}' é inválida."
                            )

            # Valor do título
            if cfg_valor:
                s, e = cfg_valor["start"], cfg_valor["end"]
                if len(linha) >= e:
                    valor_raw = linha[s:e].strip()
                    if not valor_raw.isdigit():
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): valor do título '{valor_raw}' não é numérico."
                        )
                    else:
                        valor_cent = int(valor_raw)
                        if valor_cent == 0:
                            avisos.append(
                                f"Linha {idx} (Lote {lote}, Seg. P): valor do título é zero. Verifique se está correto."
                            )

            # Nosso número (validação de formato, não de regra exata de DV)
            if cfg_nosso:
                s, e = cfg_nosso["start"], cfg_nosso["end"]
                if len(linha) >= e:
                    nn_raw = linha[s:e].strip()
                    if not nn_raw:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): Nosso Número em branco."
                        )
                    else:
                        # Permite dígitos e, eventualmente, um 'X'
                        permitido = set("0123456789Xx")
                        if any(ch not in permitido for ch in nn_raw):
                            avisos.append(
                                f"Linha {idx} (Lote {lote}, Seg. P): Nosso Número '{nn_raw}' contém caracteres inválidos."
                            )
                        if len(nn_raw) < 5:
                            avisos.append(
                                f"Linha {idx} (Lote {lote}, Seg. P): Nosso Número '{nn_raw}' parece muito curto. "
                                "Verifique se está de acordo com o convênio/carteira."
                            )

            # Juros de mora (código, data, valor) - campos padrão CNAB 240
            # Código de Juros de Mora: posição 118 (1 dígito)
            # Data de Juros de Mora:   posições 119-126 (DDMMAAAA)
            # Valor/Taxa Juros Mora:   posições 127-141 (15 dígitos, valor em centavos)
            if len(linha) >= 141:
                cod_juros = linha[117:118].strip()
                data_juros_raw = linha[118:126].strip()
                valor_juros_raw = linha[126:141].strip()

                # Códigos mais usuais: 0=sem juros, 1=valor ao dia, 2=taxa mensal, 3=isento
                if cod_juros and cod_juros not in {"0", "1", "2", "3"}:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. P): código de juros de mora '{cod_juros}' "
                        "não está entre os códigos usuais (0, 1, 2, 3). Verifique o manual do BB."
                    )

                if cod_juros in {"1", "2", "3"}:
                    # Quando há juros, data e valor tornam-se relevantes
                    if not data_juros_raw or not data_juros_raw.isdigit() or len(data_juros_raw) != 8:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): código de juros '{cod_juros}' informado, "
                            f"mas a data de início dos juros '{data_juros_raw}' não está no formato DDMMAAAA."
                        )
                    else:
                        dia_j = int(data_juros_raw[0:2])
                        mes_j = int(data_juros_raw[2:4])
                        ano_j = int(data_juros_raw[4:8])
                        try:
                            _ = datetime(ano_j, mes_j, dia_j).date()
                        except ValueError:
                            avisos.append(
                                f"Linha {idx} (Lote {lote}, Seg. P): data de início dos juros '{data_juros_raw}' é inválida."
                            )

                    if not valor_juros_raw or not valor_juros_raw.isdigit():
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): código de juros '{cod_juros}' informado, "
                            f"mas o valor/taxa de juros '{valor_juros_raw}' não é numérico."
                        )
                    else:
                        if int(valor_juros_raw) == 0:
                            avisos.append(
                                f"Linha {idx} (Lote {lote}, Seg. P): código de juros '{cod_juros}' informado, "
                                "mas o valor/taxa de juros está zerado. Verifique se o campo foi preenchido corretamente."
                            )

                # Caso o código esteja em branco ou '0' (sem juros), mas campos de data/valor venham preenchidos
                if cod_juros in ("", "0"):
                    campo_data_preenchido = data_juros_raw and data_juros_raw.strip("0")
                    campo_valor_preenchido = valor_juros_raw and valor_juros_raw.strip("0")
                    if campo_data_preenchido or campo_valor_preenchido:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): código de juros indica 'sem juros' (0 ou vazio), "
                            "mas há informação preenchida em data/valor de juros. Verifique se o código está coerente."
                        )

            # Desconto 1 (código, data, valor) - campos padrão CNAB 240
            # Código do Desconto 1: posição 142 (1 dígito)
            # Data do Desconto 1:   posições 143-150 (DDMMAAAA)
            # Valor do Desconto 1:  posições 151-165 (15 dígitos, valor em centavos)
            if len(linha) >= 165:
                cod_desc1 = linha[141:142].strip()
                data_desc1_raw = linha[142:150].strip()
                valor_desc1_raw = linha[150:165].strip()

                # Códigos mais usuais para desconto: 0=sem desconto, 1=valor fixo, 2=percentual, 3=valor por dia, etc.
                if cod_desc1 and cod_desc1 not in {"0", "1", "2", "3"}:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. P): código de desconto 1 '{cod_desc1}' "
                        "não está entre os códigos usuais (0, 1, 2, 3). Verifique o manual do BB."
                    )

                if cod_desc1 in {"1", "2", "3"}:
                    # Quando há desconto, data e valor tornam-se obrigatórios na prática
                    if not data_desc1_raw or not data_desc1_raw.isdigit() or len(data_desc1_raw) != 8:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): código de desconto '{cod_desc1}' informado, "
                            f"mas a data do desconto '{data_desc1_raw}' não está no formato DDMMAAAA."
                        )
                    else:
                        dia_d = int(data_desc1_raw[0:2])
                        mes_d = int(data_desc1_raw[2:4])
                        ano_d = int(data_desc1_raw[4:8])
                        try:
                            _ = datetime(ano_d, mes_d, dia_d).date()
                        except ValueError:
                            avisos.append(
                                f"Linha {idx} (Lote {lote}, Seg. P): data do desconto '{data_desc1_raw}' é inválida."
                            )

                    if not valor_desc1_raw or not valor_desc1_raw.isdigit():
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): código de desconto '{cod_desc1}' informado, "
                            f"mas o valor do desconto '{valor_desc1_raw}' não é numérico."
                        )
                    else:
                        if int(valor_desc1_raw) == 0:
                            avisos.append(
                                f"Linha {idx} (Lote {lote}, Seg. P): código de desconto '{cod_desc1}' informado, "
                                "mas o valor do desconto está zerado. Verifique se o campo foi preenchido corretamente."
                            )

            # Protesto e Baixa/Devolução - campos padrão CNAB 240 (Segmento P)
            # Código para Protesto:        posição 221 (1 dígito)
            # Número de Dias para Protesto:posição 222-223 (2 dígitos)
            # Código para Baixa/Devolução: posição 224 (1 dígito)
            # Dias para Baixa/Devolução:   posição 225-227 (3 dígitos)
            if len(linha) >= 227:
                cod_prot = linha[220:221].strip()
                dias_prot_raw = linha[221:223].strip()
                cod_baixa = linha[223:224].strip()
                dias_baixa_raw = linha[224:227].strip()

                # --- PROTESTO ---
                # Códigos usuais (podem variar por banco, mas em geral):
                # '1' = Protestar dias corridos
                # '2' = Protestar dias úteis
                # '3' = Não protestar
                if cod_prot and cod_prot not in {"1", "2", "3"}:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. P): código de protesto '{cod_prot}' "
                        "não está entre os códigos usuais (1=protestar dias corridos, "
                        "2=protestar dias úteis, 3=não protestar). Confirme no manual/BB."
                    )

                if cod_prot in {"1", "2"}:
                    # Quando há protesto, os dias tornam-se relevantes
                    if not dias_prot_raw or not dias_prot_raw.isdigit():
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): código de protesto '{cod_prot}' informado, "
                            f"mas o número de dias para protesto '{dias_prot_raw}' não é numérico."
                        )
                    else:
                        dias_prot = int(dias_prot_raw)
                        if dias_prot <= 0:
                            avisos.append(
                                f"Linha {idx} (Lote {lote}, Seg. P): código de protesto '{cod_prot}' informado, "
                                "mas o número de dias para protesto é zero ou negativo. Verifique."
                            )
                        elif dias_prot > 999:
                            avisos.append(
                                f"Linha {idx} (Lote {lote}, Seg. P): número de dias para protesto ({dias_prot}) "
                                "parece excessivo. Verifique se o valor está correto."
                            )

                # Código indica 'não protestar' ou em branco, mas dias preenchidos
                if cod_prot in ("", "3"):
                    if dias_prot_raw and dias_prot_raw.strip("0"):
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): código de protesto indica 'não protestar' "
                            "(3 ou vazio), mas há dias para protesto preenchidos ('{dias_prot_raw}'). "
                            "Verifique se o código está coerente."
                        )

                # --- BAIXA / DEVOLUÇÃO ---
                # Códigos usuais (exemplo): 1=Baixar/Devolver após dias, 2=Não baixar/devolver, etc.
                if cod_baixa and cod_baixa not in {"1", "2"}:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. P): código de baixa/devolução '{cod_baixa}' "
                        "não está entre os códigos usuais esperados (ex.: 1 ou 2). Verifique no manual/BB."
                    )

                if cod_baixa == "1":
                    # Baixar/devolver após X dias
                    if not dias_baixa_raw or not dias_baixa_raw.isdigit():
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): código de baixa/devolução '{cod_baixa}' informado, "
                            f"mas o número de dias para baixa/devolução '{dias_baixa_raw}' não é numérico."
                        )
                    else:
                        dias_baixa = int(dias_baixa_raw)
                        if dias_baixa <= 0:
                            avisos.append(
                                f"Linha {idx} (Lote {lote}, Seg. P): código de baixa/devolução '{cod_baixa}' informado, "
                                "mas o número de dias para baixa/devolução é zero ou negativo. Verifique."
                            )
                        elif dias_baixa > 999:
                            avisos.append(
                                f"Linha {idx} (Lote {lote}, Seg. P): número de dias para baixa/devolução ({dias_baixa}) "
                                "parece excessivo. Verifique se o valor está correto."
                            )

                # Código em branco ou diferente de '1', mas dias preenchidos
                if cod_baixa in ("", "2"):
                    if dias_baixa_raw and dias_baixa_raw.strip("0"):
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): código de baixa/devolução indica "
                            "'não baixar/devolver automaticamente', mas há dias para baixa/devolução "
                            f"preenchidos ('{dias_baixa_raw}'). Verifique se o código está coerente."
                        )


                # Código '0' (sem desconto) ou vazio, mas campos de data/valor preenchidos
                if cod_desc1 in ("", "0"):
                    campo_data_preenchido = data_desc1_raw and data_desc1_raw.strip("0")
                    campo_valor_preenchido = valor_desc1_raw and valor_desc1_raw.strip("0")
                    if campo_data_preenchido or campo_valor_preenchido:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. P): código de desconto indica 'sem desconto' (0 ou vazio), "
                            "mas há informação preenchida em data/valor de desconto. Verifique se o código está coerente."
                        )

                        # --- Coerência entre datas: emissão, vencimento, desconto e juros ---
            # Segmento P - Data de vencimento: posições 78-85 (DDMMAAAA)
            # Segmento P - Data de emissão:   posições 110-117 (DDMMAAAA)
            data_venc_raw = linha[77:85].strip() if len(linha) >= 85 else ""
            data_emis_raw = linha[109:117].strip() if len(linha) >= 117 else ""

            dt_venc = _parse_data_ddmmaaaa(data_venc_raw)
            dt_emis = _parse_data_ddmmaaaa(data_emis_raw)

            # 1) Emissão não deve ser posterior ao vencimento
            if dt_emis and dt_venc and dt_emis > dt_venc:
                avisos.append(
                    f"Linha {idx} (Lote {lote}, Seg. P): data de emissão do título "
                    f"({data_emis_raw}) é posterior à data de vencimento ({data_venc_raw}). "
                    "Verifique a coerência entre emissão e vencimento."
                )

            # Para as próximas regras, vamos buscar também data de desconto 1 e data de juros
            data_desc1_raw = ""
            cod_desc1 = ""
            if len(linha) >= 150:
                # Código do desconto 1: posição 142
                # Data do desconto 1:   posições 143-150
                cod_desc1 = linha[141:142].strip()
                data_desc1_raw = linha[142:150].strip()

            data_juros_raw = ""
            if len(linha) >= 126:
                # Data do juros de mora: posições 119-126 (C019)
                data_juros_raw = linha[118:126].strip()

            dt_desc1 = _parse_data_ddmmaaaa(data_desc1_raw)
            dt_juros = _parse_data_ddmmaaaa(data_juros_raw)

            # 2) Desconto 1 x emissão x vencimento
            if dt_venc and dt_emis and dt_desc1 and cod_desc1 in {"1", "2"}:
                if not (dt_emis <= dt_desc1 <= dt_venc):
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. P): para código de desconto '{cod_desc1}', "
                        f"a data do desconto ({data_desc1_raw}) deveria estar entre a data de emissão "
                        f"({data_emis_raw}) e a data de vencimento ({data_venc_raw}). "
                        "Verifique a regra de desconto neste título."
                    )

            if dt_venc and dt_desc1 and cod_desc1 == "3":
                if dt_desc1 != dt_venc:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. P): para código de desconto '3', "
                        f"a data do desconto ({data_desc1_raw}) deveria ser igual à data de vencimento "
                        f"({data_venc_raw}). Verifique a configuração do desconto."
                    )

            # 3) Data de início dos juros de mora deve ser depois da data de vencimento
            if dt_venc and dt_juros:
                if dt_juros <= dt_venc:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. P): data de início dos juros de mora "
                        f"({data_juros_raw}) deveria ser posterior à data de vencimento "
                        f"({data_venc_raw}), conforme regras FEBRABAN. Verifique."
                    )

            if dt_venc and dt_desc1 and cod_desc1 == "3":
                if dt_desc1 != dt_venc:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. P): para código de desconto '3', "
                        f"a data do desconto ({data_desc1_raw}) deveria ser igual à data de vencimento "
                        f"({data_venc_raw}). Verifique a configuração do desconto."
                    )

            # 3) Data de início dos juros de mora deve ser depois da data de vencimento
            # (C019: Data do Juros de Mora > Data de Vencimento) 
            if dt_venc and dt_juros:
                if dt_juros <= dt_venc:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. P): data de início dos juros de mora "
                        f"({data_juros_raw}) deveria ser posterior à data de vencimento "
                        f"({data_venc_raw}), conforme regras FEBRABAN. Verifique."
                    )

        # ---------------- Segmento Q ----------------
        if tipo_registro == "3" and segmento == "Q":
            lote = linha[3:7]

            # Tipo de inscrição e documento do sacado
            tipo_insc = None
            doc_sacado = ""

            if cfg_tipo_insc and len(linha) >= cfg_tipo_insc["end"]:
                s, e = cfg_tipo_insc["start"], cfg_tipo_insc["end"]
                tipo_insc = linha[s:e].strip()

            if cfg_doc_sac and len(linha) >= cfg_doc_sac["end"]:
                s, e = cfg_doc_sac["start"], cfg_doc_sac["end"]
                doc_raw = linha[s:e].strip()
                doc_sacado = limpar_numero(doc_raw)

            if tipo_insc in ("01", "02") and doc_sacado:

                # Validação de CPF (01)
                if tipo_insc == "01":
                    if len(doc_sacado) != 11:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. Q): Tipo informado é CPF (01), "
                            f"mas o documento possui {len(doc_sacado)} dígitos — formato incompatível com CPF. "
                            "Verifique se o tipo de inscrição está coerente com o documento."
                        )
                    elif not validar_cpf(doc_sacado):
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. Q): Documento informado é CPF (01), "
                            f"mas '{doc_sacado}' não passou na validação dos dígitos verificadores. "
                            "Verifique se o documento está correto."
                        )

                # Validação de CNPJ (02)
                elif tipo_insc == "02":
                    if len(doc_sacado) != 14:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. Q): Tipo informado é CNPJ (02), "
                            f"mas o documento possui {len(doc_sacado)} dígitos — formato incompatível com CNPJ. "
                            "Verifique se o tipo de inscrição está coerente com o documento."
                        )
                    elif not validar_cnpj(doc_sacado):
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. Q): Documento informado é CNPJ (02), "
                            f"mas '{doc_sacado}' não passou na validação dos dígitos verificadores. "
                            "Verifique se o documento está correto."
                        )

            # Nome do sacado
            if cfg_nome_sac and len(linha) >= cfg_nome_sac["end"]:
                s, e = cfg_nome_sac["start"], cfg_nome_sac["end"]
                nome = linha[s:e].strip()
                if len(nome) < 3:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. Q): nome do sacado muito curto ('{nome}')."
                    )

            # Endereço, cidade, UF, CEP
            if cfg_endereco and len(linha) >= cfg_endereco["end"]:
                s, e = cfg_endereco["start"], cfg_endereco["end"]
                endereco = linha[s:e].strip()
                if not endereco:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. Q): endereço do sacado em branco."
                    )

            if cfg_cidade and len(linha) >= cfg_cidade["end"]:
                s, e = cfg_cidade["start"], cfg_cidade["end"]
                cidade = linha[s:e].strip()
                if not cidade:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. Q): cidade do sacado em branco."
                    )

            if cfg_uf and len(linha) >= cfg_uf["end"]:
                s, e = cfg_uf["start"], cfg_uf["end"]
                uf = linha[s:e].strip().upper()
                if uf and uf not in ufs_validas:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. Q): UF do sacado '{uf}' não é um estado brasileiro válido."
                    )

            if cfg_cep and len(linha) >= cfg_cep["end"]:
                s, e = cfg_cep["start"], cfg_cep["end"]
                cep = linha[s:e].strip()
                cep_num = limpar_numero(cep)
                if not cep_num or len(cep_num) != 8:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. Q): CEP do sacado '{cep}' não possui 8 dígitos numéricos."
                    )
        
            # ---------------- Segmento R ----------------
            elif segmento == "R":
                lote = linha[3:7]

                # Só faz sentido validar se tiver pelo menos até os campos de multa
                if len(linha) < 90:
                    continue

                # ===================== DESCONTO 2 =====================
                # Cód. Desc. 2:   posição 18 (1 dígito)
                # Data Desc. 2:   posições 19-26 (DDMMAAAA)
                # Valor Desc. 2:  posições 27-41 (15 dígitos, em centavos)
                cod_desc2 = linha[17:18].strip()
                data_desc2_raw = linha[18:26].strip()
                valor_desc2_raw = linha[26:41].strip()

                if cod_desc2 and cod_desc2 not in {"0", "1", "2", "3"}:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. R): código de Desconto 2 '{cod_desc2}' "
                        "não está entre os códigos usuais (0, 1, 2, 3). Verifique o manual do banco."
                    )

                if cod_desc2 in {"1", "2", "3"}:
                    # Data obrigatória na prática
                    dt_desc2 = _parse_data_ddmmaaaa(data_desc2_raw)
                    if not dt_desc2:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): código de Desconto 2 '{cod_desc2}' informado, "
                            f"mas a data do desconto 2 '{data_desc2_raw}' não está em formato DDMMAAAA ou é inválida."
                        )

                    # Valor numérico e > 0
                    if not valor_desc2_raw or not valor_desc2_raw.isdigit():
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): código de Desconto 2 '{cod_desc2}' informado, "
                            f"mas o valor do desconto 2 '{valor_desc2_raw}' não é numérico."
                        )
                    elif int(valor_desc2_raw) == 0:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): código de Desconto 2 '{cod_desc2}' informado, "
                            "mas o valor do desconto 2 está zerado. Verifique se o campo foi preenchido corretamente."
                        )

                # Código 0 ou em branco, mas campos de data/valor preenchidos
                if cod_desc2 in ("", "0"):
                    campo_data_preenchido = data_desc2_raw and data_desc2_raw.strip("0")
                    campo_valor_preenchido = valor_desc2_raw and valor_desc2_raw.strip("0")
                    if campo_data_preenchido or campo_valor_preenchido:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): código de Desconto 2 indica 'sem desconto' "
                            "(0 ou vazio), mas há data/valor de desconto 2 preenchidos. Verifique coerência."
                        )

                # ===================== DESCONTO 3 =====================
                # Cód. Desc. 3:   posição 42 (1 dígito)
                # Data Desc. 3:   posições 43-50 (DDMMAAAA)
                # Valor Desc. 3:  posições 51-65 (15 dígitos, em centavos)
                cod_desc3 = linha[41:42].strip()
                data_desc3_raw = linha[42:50].strip()
                valor_desc3_raw = linha[50:65].strip()

                if cod_desc3 and cod_desc3 not in {"0", "1", "2", "3"}:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. R): código de Desconto 3 '{cod_desc3}' "
                        "não está entre os códigos usuais (0, 1, 2, 3). Verifique o manual do banco."
                    )

                if cod_desc3 in {"1", "2", "3"}:
                    dt_desc3 = _parse_data_ddmmaaaa(data_desc3_raw)
                    if not dt_desc3:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): código de Desconto 3 '{cod_desc3}' informado, "
                            f"mas a data do desconto 3 '{data_desc3_raw}' não está em formato DDMMAAAA ou é inválida."
                        )

                    if not valor_desc3_raw or not valor_desc3_raw.isdigit():
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): código de Desconto 3 '{cod_desc3}' informado, "
                            f"mas o valor do desconto 3 '{valor_desc3_raw}' não é numérico."
                        )
                    elif int(valor_desc3_raw) == 0:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): código de Desconto 3 '{cod_desc3}' informado, "
                            "mas o valor do desconto 3 está zerado. Verifique se o campo foi preenchido corretamente."
                        )

                if cod_desc3 in ("", "0"):
                    campo_data_preenchido = data_desc3_raw and data_desc3_raw.strip("0")
                    campo_valor_preenchido = valor_desc3_raw and valor_desc3_raw.strip("0")
                    if campo_data_preenchido or campo_valor_preenchido:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): código de Desconto 3 indica 'sem desconto' "
                            "(0 ou vazio), mas há data/valor de desconto 3 preenchidos. Verifique coerência."
                        )

                # ===================== MULTA (SEGMENTO R) =====================
                # Cód. Multa:     posição 66 (1 caractere)
                # Data Multa:     posições 67-74 (DDMMAAAA)
                # Valor/Percent.: posições 75-89 (15 dígitos, em centavos ou percentual * 100)
                cod_multa = linha[65:66].strip()
                data_multa_raw = linha[66:74].strip()
                valor_multa_raw = linha[74:89].strip()

                if cod_multa and cod_multa not in {"0", "1", "2", "3"}:
                    avisos.append(
                        f"Linha {idx} (Lote {lote}, Seg. R): código de multa '{cod_multa}' "
                        "não está entre os códigos usuais (0=sem multa, 1=valor, 2=percentual, 3=isento). "
                        "Verifique o manual do banco."
                    )

                if cod_multa in {"1", "2"}:
                    dt_multa = _parse_data_ddmmaaaa(data_multa_raw)
                    if not dt_multa:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): código de multa '{cod_multa}' informado, "
                            f"mas a data da multa '{data_multa_raw}' não está em formato DDMMAAAA ou é inválida."
                        )

                    if not valor_multa_raw or not valor_multa_raw.isdigit():
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): código de multa '{cod_multa}' informado, "
                            f"mas o valor/percentual da multa '{valor_multa_raw}' não é numérico."
                        )
                    elif int(valor_multa_raw) == 0:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): código de multa '{cod_multa}' informado, "
                            "mas o valor/percentual da multa está zerado. Verifique se o campo foi preenchido corretamente."
                        )

                if cod_multa in ("", "0", "3"):
                    campo_data_preenchido = data_multa_raw and data_multa_raw.strip("0")
                    campo_valor_preenchido = valor_multa_raw and valor_multa_raw.strip("0")
                    if campo_data_preenchido or campo_valor_preenchido:
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): código de multa indica 'sem multa/isento' "
                            "(0, 3 ou vazio), mas há data/valor de multa preenchidos. Verifique coerência."
                        )

                # ===================== DÉBITO AUTOMÁTICO (opcional) =====================
                # Se qualquer campo de débito estiver preenchido, checa consistência básica
                banco_deb = linha[207:210].strip() if len(linha) >= 210 else ""
                ag_deb = linha[210:215].strip() if len(linha) >= 215 else ""
                conta_deb = linha[216:228].strip() if len(linha) >= 228 else ""

                if banco_deb or ag_deb or conta_deb:
                    # Se usou débito, pelo menos banco e agência/conta devem ser numéricos
                    if banco_deb and not banco_deb.isdigit():
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): banco para débito automático '{banco_deb}' não é numérico."
                        )
                    if ag_deb and not ag_deb.isdigit():
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): agência para débito automático '{ag_deb}' não é numérica."
                        )
                    if conta_deb and not conta_deb.isdigit():
                        avisos.append(
                            f"Linha {idx} (Lote {lote}, Seg. R): conta corrente para débito automático '{conta_deb}' não é numérica."
                        )

        
    for idx, linha in enumerate(linhas, start=1):
      l = linha.rstrip("\r\n")
      if len(l) < 20:
        continue

      tipo_registro = l[7:8]
      if tipo_registro == "3":
        segmento = l[13:14]

        if segmento == "P":
            lote = l[3:7]

            # ... várias validações aqui (vencimento, valor, nosso número, juros, desconto, protesto/baixa etc)


    return erros, avisos

# ----------------------------
#  PROGRAMA PRINCIPAL
# ----------------------------

def main():
    print("=== Validador simples de arquivos CNAB 240/400 ===")
    caminho = input("Informe o caminho completo do arquivo de remessa (.txt): ").strip()

    if not os.path.isfile(caminho):
        print("❌ Arquivo não encontrado. Verifique o caminho e tente novamente.")
        return

    # Lê todas as linhas do arquivo
    with open(caminho, "r", encoding="latin-1") as f:
        linhas = f.readlines()

    if not linhas:
        print("❌ Arquivo está vazio.")
        return

    # 1) Detecta layout (240 ou 400)
    layout = detectar_layout(linhas)

    if isinstance(layout, set):
        print("⚠ Não foi possível identificar um layout único (240 ou 400).")
        print(f"Tamanhos de linha encontrados: {layout}")
        print("Provavelmente há linhas com tamanhos diferentes ou o arquivo não é CNAB padrão.")
        return

    print(f"✅ Layout detectado: CNAB {layout}")

    # 2) Valida tamanho das linhas
    erros_tamanho = validar_tamanho_linhas(linhas, layout)

    if not erros_tamanho:
        print("✅ Todas as linhas estão com o tamanho correto.")
    else:
        print("❌ Problemas de tamanho de linha encontrados:")
        for erro in erros_tamanho:
            print("   -", erro)

    # 3) Se for CNAB 240, faz validações extras de estrutura
    if layout == 240:
        print("\n=== Analisando estrutura básica CNAB 240 ===")

        # Detecta banco pelo header
        codigo_banco, nome_banco = identificar_banco(linhas[0])
        print(f"🏦 Banco detectado pelo header: {codigo_banco} - {nome_banco}")

        erros_estrutura = validar_estrutura_basica_cnab240(linhas)

        if not erros_estrutura:
            print("✅ Estrutura básica (header/trailer/tipos de registro) está OK.")
        else:
            print("❌ Foram encontrados problemas na estrutura do arquivo:")
            for erro in erros_estrutura:
                print("   -", erro)

        # 4) Valida código de banco em todas as linhas
        print("\n=== Validando consistência do código do banco em todas as linhas ===")
        erros_banco = validar_codigo_banco_consistente(linhas, codigo_banco)

        if not erros_banco:
            print("✅ Todas as linhas possuem o mesmo código de banco do header.")
        else:
            print("❌ Inconsistências de código de banco encontradas:")
            for erro in erros_banco:
                print("   -", erro)

        # 5) Valida lotes (header/trailer/detalhes)
        print("\n=== Validando estrutura de lotes (Header/Detalhes/Trailer) ===")
        erros_lotes = validar_lotes_cnab240(linhas)

        if not erros_lotes:
            print("✅ Estrutura de lotes está OK (header, detalhes e trailer).")
        else:
            print("❌ Problemas na estrutura de lotes:")
            for erro in erros_lotes:
                print("   -", erro)

        # 6) Valida sequência de registros no lote
        print("\n=== Validando sequência de registros dentro de cada lote ===")
        erros_seq = validar_sequencia_registros_lote(linhas)

        if not erros_seq:
            print("✅ Sequência dos registros nos lotes está OK.")
        else:
            print("❌ Problemas na sequência dos registros:")
            for erro in erros_seq:
                print("   -", erro)

        # 7) Validações de segmentos baseadas no layout configurado
        print("\n=== Validações específicas por layout configurado (Segmentos) ===")
        erros_seg, avisos_seg = validar_segmentos_por_layout(codigo_banco, linhas)

        if avisos_seg:
            print("⚠ Avisos em segmentos:")
            for aviso in avisos_seg:
                print("   -", aviso)

        if erros_seg:
            print("❌ Erros em segmentos (P, Q, etc.):")
            for erro in erros_seg:
                print("   -", erro)
        else:
            print("✅ Nenhum erro encontrado nos segmentos configurados para este banco.")
    else:
        print("\n(Validações específicas de estrutura ainda não implementadas para CNAB 400.)")


if __name__ == "__main__":
    main()