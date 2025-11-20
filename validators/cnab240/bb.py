"""Validações específicas do Banco do Brasil para CNAB 240."""

from datetime import datetime
from ..base import _parse_data_ddmmaaaa, limpar_numero
from .common import LAYOUTS_CNAB240

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
