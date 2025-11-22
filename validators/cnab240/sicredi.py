"""Validacoes especificas do Sicredi para CNAB 240."""

from ..base import ESTADOS_BR
from .common import LAYOUT_CNAB240_COMUM_PQ, LAYOUTS_CNAB240

def validar_cnab240_sicredi(linhas):
    """
    Validações básicas específicas para o layout CNAB 240 do Sicredi.
    Retorna dicionário com erros de header/segmentos e avisos.
    """
    erros_header = []
    erros_segmentos = []
    avisos = []

    layout_campos = LAYOUTS_CNAB240.get("748", LAYOUT_CNAB240_COMUM_PQ)
    campos_p = layout_campos.get("P", {})
    campos_q = layout_campos.get("Q", {})

    if not linhas:
        return {
            "erros_header": erros_header,
            "erros_segmentos": erros_segmentos,
            "avisos": avisos,
        }

    header = linhas[0].rstrip("\r\n")
    if header[0:3] != "748":
        erros_header.append("Header do arquivo: código do banco deve ser 748 (Sicredi).")
    literal = header[79:94].strip().upper()
    if "SICREDI" not in literal:
        avisos.append("Header do arquivo: literal do banco deveria conter 'SICREDI'.")

    literal_remessa = header[2:9].strip().upper()
    if literal_remessa != "REMESSA":
        avisos.append("Header do arquivo: literal 'REMESSA' não encontrado.")
    literal_servico = header[11:19].strip().upper()
    if literal_servico != "COBRANCA":
        avisos.append("Header do arquivo: literal do serviço devia ser 'COBRANCA'.")

    data_header = header[94:102]
    if not (len(data_header) == 8 and data_header.isdigit()):
        erros_header.append("Header do arquivo: data de geração (pos. 95-102) deve estar em AAAAMMDD.")

    ultimo_segmento_p = None

    for numero_linha, linha in enumerate(linhas, start=1):
        if not linha or linha.strip() == "":
            continue
        linha = linha.rstrip("\r\n")
        if len(linha) < 240:
            continue

        tipo_registro = linha[7:8]
        if tipo_registro == "1":
            servico = linha[9:11]
            if servico != "01":
                erros_header.append(
                    f"Linha {numero_linha}: header de lote deve possuir código de serviço '01'."
                )
            tipo_operacao = linha[8:9]
            if tipo_operacao not in {"1"}:
                erros_header.append(
                    f"Linha {numero_linha}: header de lote deveria indicar operação '1' (cobrança registrada)."
                )
        elif tipo_registro == "3":
            segmento = linha[13:14].upper()
            if segmento == "P":
                ultimo_segmento_p = linha
                if linha[0:3] != "748":
                    erros_segmentos.append(
                        f"Linha {numero_linha} (Segmento P): código do banco deve ser 748."
                    )
                if campos_p:
                    nosso_cfg = campos_p.get("nosso_numero")
                    if nosso_cfg:
                        nosso = linha[nosso_cfg["start"]:nosso_cfg["end"]].strip()
                        if nosso and not nosso.isdigit():
                            erros_segmentos.append(
                                f"Linha {numero_linha} (Segmento P): nosso número deve conter somente dígitos."
                            )
                    venc_cfg = campos_p.get("data_vencimento")
                    if venc_cfg:
                        data_venc = linha[venc_cfg["start"]:venc_cfg["end"]].strip()
                        if len(data_venc) != 8 or not data_venc.isdigit():
                            erros_segmentos.append(
                                f"Linha {numero_linha} (Segmento P): data de vencimento inválida (esperado DDMMAAAA)."
                            )
                    valor_cfg = campos_p.get("valor_titulo")
                    if valor_cfg:
                        valor_raw = linha[valor_cfg["start"]:valor_cfg["end"]].strip()
                        if not valor_raw.isdigit():
                            erros_segmentos.append(
                                f"Linha {numero_linha} (Segmento P): valor do título deve conter somente dígitos."
                            )
                        elif int(valor_raw) == 0:
                            erros_segmentos.append(
                                f"Linha {numero_linha} (Segmento P): valor do título não pode ser zero."
                            )
                cod_mov = linha[15:17]
                if not cod_mov.isdigit():
                    erros_segmentos.append(
                        f"Linha {numero_linha} (Segmento P): código de movimento (pos. 16-17) deve ser numérico."
                    )
            elif segmento == "Q":
                if not ultimo_segmento_p:
                    erros_segmentos.append(
                        f"Linha {numero_linha} (Segmento Q): encontrado antes do correspondente Segmento P."
                    )
                if campos_q:
                    tipo_cfg = campos_q.get("tipo_inscricao")
                    if tipo_cfg:
                        tipo = linha[tipo_cfg["start"]:tipo_cfg["end"]].strip()
                        if tipo not in {"01", "02"}:
                            erros_segmentos.append(
                                f"Linha {numero_linha} (Segmento Q): tipo de inscrição do sacado deve ser 01 ou 02."
                            )
                    doc_cfg = campos_q.get("documento_sacado")
                    if doc_cfg:
                        doc = linha[doc_cfg["start"]:doc_cfg["end"]].strip()
                        if not doc.isdigit():
                            erros_segmentos.append(
                                f"Linha {numero_linha} (Segmento Q): documento do sacado deve conter apenas dígitos."
                            )
                        elif doc == "0" * len(doc):
                            erros_segmentos.append(
                                f"Linha {numero_linha} (Segmento Q): documento do sacado não pode ser todo zero."
                            )
                    nome_cfg = campos_q.get("nome_sacado")
                    if nome_cfg:
                        nome = linha[nome_cfg["start"]:nome_cfg["end"]].strip()
                        if not nome:
                            erros_segmentos.append(
                                f"Linha {numero_linha} (Segmento Q): nome do sacado não informado."
                            )
                    endereco_cfg = campos_q.get("endereco_sacado")
                    if endereco_cfg:
                        endereco = linha[endereco_cfg["start"]:endereco_cfg["end"]].strip()
                        if not endereco:
                            erros_segmentos.append(
                                f"Linha {numero_linha} (Segmento Q): endereço do sacado não informado."
                            )
                    cep_cfg = campos_q.get("cep_sacado")
                    if cep_cfg:
                        cep = linha[cep_cfg["start"]:cep_cfg["end"]].strip()
                        if len(cep) != 8 or not cep.isdigit():
                            erros_segmentos.append(
                                f"Linha {numero_linha} (Segmento Q): CEP do sacado deve conter 8 dígitos."
                            )
                    uf_cfg = campos_q.get("uf_sacado")
                    if uf_cfg:
                        uf = linha[uf_cfg["start"]:uf_cfg["end"]].strip().upper()
                        if uf not in ESTADOS_BR:
                            erros_segmentos.append(
                                f"Linha {numero_linha} (Segmento Q): UF '{uf}' do sacado é inválida."
                            )
            elif segmento in {"R", "S", "Y"}:
                if not ultimo_segmento_p:
                    erros_segmentos.append(
                        f"Linha {numero_linha} (Segmento {segmento}): deve estar associado a um Segmento P anterior."
                    )
        elif tipo_registro == "5":
            ultimo_segmento_p = None

    return {
        "erros_header": erros_header,
        "erros_segmentos": erros_segmentos,
        "avisos": avisos,
    }
