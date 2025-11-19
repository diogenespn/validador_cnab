from flask import Flask, render_template, request
from validador_cnab import (
    detectar_layout,
    validar_tamanho_linhas,
    identificar_banco,
    validar_estrutura_basica_cnab240,
    validar_codigo_banco_consistente,
    validar_lotes_cnab240,
    validar_sequencia_registros_lote,
    validar_segmentos_por_layout,
    validar_dados_cedente_vs_arquivo,
    validar_linha_digitavel_boleto,
    gerar_resumo_remessa_cnab240,
    listar_titulos_cnab240,
    validar_segmentos_avancados_bb,
    validar_qtd_registros_lote_cnab240,
    validar_totais_arquivo_cnab240,
    validar_convenio_carteira_nosso_numero_bb,
)


def validar_nosso_numero_duplicado_titulos(titulos):
    """
    Procura títulos com o mesmo Nosso Número na lista de títulos já extraída
    (resultado de listar_titulos_cnab240).
    Retorna uma lista de avisos em texto.
    """
    avisos = []
    vistos = {}  # chave = Nosso Número, valor = primeiro título onde apareceu

    for t in titulos:
        nn = (t.get("nosso_numero") or "").strip()
        if not nn:
            continue

        chave = nn

        if chave in vistos:
            primeiro = vistos[chave]
            avisos.append(
                (
                    "Títulos com o mesmo Nosso Número '{nn}': primeiro em "
                    "Lote {lote1}, Seq {seq1}; depois em Lote {lote2}, Seq {seq2}."
                ).format(
                    nn=nn,
                    lote1=primeiro.get("lote"),
                    seq1=primeiro.get("sequencia"),
                    lote2=t.get("lote"),
                    seq2=t.get("sequencia"),
                )
            )
        else:
            vistos[chave] = t

    return avisos


def agrupar_avisos_segmentos(avisos):
    """
    Separa avisos por tipo:
    - Segmento P
    - Segmento Q
    - Segmento R
    - Convênio / Carteira / Nosso Número
    - Outros
    """
    grupos = {
        "p": [],
        "q": [],
        "r": [],
        "conv": [],
        "outros": [],
    }

    for msg in avisos:
        m = msg.lower()

        if "segmento p" in m or "seg. p" in m:
            grupos["p"].append(msg)

        elif "segmento q" in m or "seg. q" in m:
            grupos["q"].append(msg)

        elif "segmento r" in m or "seg. r" in m:
            grupos["r"].append(msg)

        elif (
            "convênio" in m
            or "convenio" in m
            or "carteira" in m
            or "nosso número" in m
            or "nosso numero" in m
        ):
            grupos["conv"].append(msg)

        else:
            grupos["outros"].append(msg)

    return grupos



app = Flask(__name__)


@app.route("/")
def index():
    """
    Página inicial: formulário para enviar o arquivo de remessa
    e (opcionalmente) os dados da conta/titular.
    """
    return render_template("index.html")


@app.route("/validar", methods=["POST"])
def validar():
    """
    Recebe o arquivo de remessa + dados da conta/titular,
    executa as validações usando o motor do validador_cnab.py
    e devolve os resultados para a página resultado.html.
    """
    arquivo = request.files.get("arquivo")
    if not arquivo:
        return "Nenhum arquivo enviado.", 400

    # Lê conteúdo do arquivo em memória
    conteudo = arquivo.read().decode("latin-1", errors="ignore")
    linhas = conteudo.splitlines()

    # Dados da conta/titular digitados pelo usuário
    dados_conta = {
        "banco": (request.form.get("banco") or "").strip(),
        "agencia": (request.form.get("agencia") or "").strip(),
        "conta": (request.form.get("conta") or "").strip(),
        "documento": (request.form.get("documento") or "").strip(),
        "nome": (request.form.get("nome") or "").strip(),
    }

    # Estrutura padrão do resultado que será enviada ao template
    resultado = {
        "layout": None,
        "codigo_banco": None,
        "nome_banco": None,
        "erros_tamanho": [],
        "erros_estrutura": [],
        "erros_banco": [],
        "erros_lotes": [],
        "erros_sequencia": [],
        "erros_segmentos": [],
        "avisos_segmentos": [],
        "avisos_segmentos_p": [],
        "avisos_segmentos_q": [],
        "avisos_segmentos_r": [],
        "avisos_segmentos_convenio": [],
        "avisos_segmentos_outros": [],
        "erros_dados_conta": [],
        "avisos_dados_conta": [],
        "resumo_remessa": None,
        "titulos": [],
    }

    # 1) Detecta layout do arquivo (240 ou 400)
    layout = detectar_layout(linhas)
    resultado["layout"] = layout

    # Se detectar um conjunto de tamanhos (layout inconsistente)
    if isinstance(layout, set):
        resultado["erros_tamanho"].append(
            f"Não foi possível identificar um layout único (240 ou 400). "
            f"Tamanhos de linha encontrados: {layout}."
        )
        return render_template("resultado.html", resultado=resultado, dados_conta=dados_conta)

    # 2) Validação de tamanho de linhas
    resultado["erros_tamanho"] = validar_tamanho_linhas(linhas, layout)

    # 3) Validações específicas para CNAB 240
    if layout == 240 and linhas:
        # Banco (código e nome) a partir do header de arquivo
        codigo_banco, nome_banco = identificar_banco(linhas[0])
        resultado["codigo_banco"] = codigo_banco
        resultado["nome_banco"] = nome_banco

        # Estrutura básica (header/trailer/tipos de registro) + totais do arquivo
        erros_estrutura_basica = validar_estrutura_basica_cnab240(linhas)
        erros_totais_arquivo = validar_totais_arquivo_cnab240(linhas)
        resultado["erros_estrutura"] = erros_estrutura_basica + erros_totais_arquivo

        # Consistência do código do banco em todas as linhas
        resultado["erros_banco"] = validar_codigo_banco_consistente(linhas, codigo_banco)

        # Estrutura de lotes: validação básica + validação avançada (qtd de registros)
        erros_lotes_basicos = validar_lotes_cnab240(linhas)
        erros_lotes_qtd = validar_qtd_registros_lote_cnab240(linhas)
        resultado["erros_lotes"] = erros_lotes_basicos + erros_lotes_qtd

        # Sequência de registros dentro dos lotes
        resultado["erros_sequencia"] = validar_sequencia_registros_lote(linhas)

        # Validações de segmentos P/Q/etc. conforme layout cadastrado
        erros_seg, avisos_seg = validar_segmentos_por_layout(codigo_banco, linhas)

        # Validações avançadas (modo permissivo) específicas do Banco do Brasil (001)
        if codigo_banco == "001":
            # 1) Regras avançadas de Segmentos (P, Q, etc.) que você já tinha
            erros_extra, avisos_extra = validar_segmentos_avancados_bb(linhas)
            erros_seg.extend(erros_extra)
            avisos_seg.extend(avisos_extra)

            # 2) Regras de convênio / carteira / Nosso Número (novas)
            erros_conv, avisos_conv = validar_convenio_carteira_nosso_numero_bb(linhas)
            erros_seg.extend(erros_conv)
            avisos_seg.extend(avisos_conv)

        resultado["erros_segmentos"] = erros_seg
        resultado["avisos_segmentos"] = avisos_seg

        # Agrupar avisos de segmentos por tipo (P, Q, R, convênio/carteira/NN, outros)
        grupos = agrupar_avisos_segmentos(avisos_seg)
        resultado["avisos_segmentos_p"] = grupos["p"]
        resultado["avisos_segmentos_q"] = grupos["q"]
        resultado["avisos_segmentos_r"] = grupos["r"]
        resultado["avisos_segmentos_convenio"] = grupos["conv"]
        resultado["avisos_segmentos_outros"] = grupos["outros"]


        # Conferência dos dados da conta/titular informados x dados do arquivo
        erros_dados, avisos_dados = validar_dados_cedente_vs_arquivo(
            codigo_banco, linhas, dados_conta
        )
        resultado["erros_dados_conta"] = erros_dados
        resultado["avisos_dados_conta"] = avisos_dados

        # Resumo da remessa (qtd de títulos, valor total, vencimentos)
        resumo = gerar_resumo_remessa_cnab240(codigo_banco, linhas)
        resultado["resumo_remessa"] = resumo

        # Lista detalhada de títulos (Segmentos P + Q)
        titulos = listar_titulos_cnab240(codigo_banco, linhas)
        resultado["titulos"] = titulos

        # Validação avançada: detectar títulos com Nosso Número duplicado (BB)
        if codigo_banco == "001" and resultado["titulos"]:
            avisos_nn_dup = validar_nosso_numero_duplicado_titulos(resultado["titulos"])
            if avisos_nn_dup:
                resultado["avisos_segmentos"].extend(avisos_nn_dup)

                # reagrupa
                grupos = agrupar_avisos_segmentos(resultado["avisos_segmentos"])
                resultado["avisos_segmentos_p"] = grupos["p"]
                resultado["avisos_segmentos_q"] = grupos["q"]
                resultado["avisos_segmentos_r"] = grupos["r"]
                resultado["avisos_segmentos_convenio"] = grupos["conv"]
                resultado["avisos_segmentos_outros"] = grupos["outros"]


    # TODO: futuras validações para CNAB 400
    # elif layout == 400:
    #     ...

    return render_template("resultado.html", resultado=resultado, dados_conta=dados_conta)


@app.route("/boleto", methods=["GET", "POST"])
def boleto():
    """
    Página para validação da linha digitável de boleto.
    """
    erros = []
    infos = {}
    linha_digitavel = ""

    if request.method == "POST":
        linha_digitavel = (request.form.get("linha_digitavel") or "").strip()
        erros, infos = validar_linha_digitavel_boleto(linha_digitavel)

    return render_template(
        "boleto.html",
        erros=erros,
        infos=infos,
        linha_digitavel=linha_digitavel,
    )


if __name__ == "__main__":
    # debug=True é útil durante o desenvolvimento
    app.run(debug=True)
