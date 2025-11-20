"""Utilitario de linha de comando para o validador CNAB."""

import os
from .base import (
    BANCOS_CNAB,
    detectar_layout,
    identificar_banco,
    validar_linha_digitavel_boleto,
    validar_tamanho_linhas,
)
from .cnab240 import (
    detectar_cnab240_itau_sisdeb,
    gerar_resumo_remessa_cnab240,
    listar_titulos_cnab240,
    validar_cnab240_itau_sisdeb,
    validar_cnab240_sicredi,
    validar_codigo_banco_consistente,
    validar_convenio_carteira_nosso_numero_bb,
    validar_dados_cedente_vs_arquivo,
    validar_estrutura_basica_cnab240,
    validar_lotes_cnab240,
    validar_qtd_registros_lote_cnab240,
    validar_segmentos_avancados_bb,
    validar_segmentos_por_layout,
    validar_sequencia_registros_lote,
    validar_totais_arquivo_cnab240,
)
from .cnab400 import (
    validar_cnab400_bb,
    validar_cnab400_brb,
    validar_cnab400_bradesco,
    validar_cnab400_caixa,
    validar_cnab400_itau,
    validar_cnab400_santander,
    validar_cnab400_sicredi,
)


def main():
    print("=== Validador simples de arquivos CNAB 240/400 ===")
    caminho = input("Informe o caminho completo do arquivo de remessa (.txt): ").strip()

    if not os.path.isfile(caminho):
        print("Erro: arquivo nao encontrado. Verifique o caminho e tente novamente.")
        return

    with open(caminho, "r", encoding="latin-1") as f:
        linhas = f.readlines()

    if not linhas:
        print("Erro: arquivo esta vazio.")
        return

    layout = detectar_layout(linhas)

    if isinstance(layout, set):
        tamanhos_str = sorted(list(layout))
        print("Nao foi possivel identificar um layout unico (240 ou 400).")
        print(f"Tamanhos de linha encontrados: {tamanhos_str}")
        print(f"Exemplo do primeiro tamanho encontrado: {tamanhos_str[0] if tamanhos_str else 'n/a'}")
        print("Provavelmente ha linhas com tamanhos diferentes ou o arquivo nao e CNAB padrao.")
        return

    print(f"OK. Layout detectado: CNAB {layout}")

    erros_tamanho = validar_tamanho_linhas(linhas, layout)
    if not erros_tamanho:
        print("OK. Todas as linhas estao com o tamanho correto.")
    else:
        print("Erros de tamanho de linha:")
        for erro in erros_tamanho:
            print("   -", erro)

    if layout == 240:
        print("\n=== Analisando estrutura basica CNAB 240 ===")
        codigo_banco, nome_banco = identificar_banco(linhas[0])
        print(f"Banco detectado pelo header: {codigo_banco} - {nome_banco}")

        erros_estrutura = validar_estrutura_basica_cnab240(linhas)
        if erros_estrutura:
            print("Problemas na estrutura do arquivo:")
            for erro in erros_estrutura:
                print("   -", erro)
        else:
            print("OK. Estrutura basica (header/trailer/tipos de registro) esta OK.")

        print("\n=== Validando consistencia do codigo do banco em todas as linhas ===")
        erros_banco = validar_codigo_banco_consistente(linhas, codigo_banco)
        if erros_banco:
            print("Inconsistencias de codigo de banco:")
            for erro in erros_banco:
                print("   -", erro)
        else:
            print("OK. Todas as linhas possuem o mesmo codigo de banco do header.")

        print("\n=== Validando estrutura de lotes (Header/Detalhes/Trailer) ===")
        erros_lotes = validar_lotes_cnab240(linhas)
        if erros_lotes:
            print("Problemas na estrutura de lotes:")
            for erro in erros_lotes:
                print("   -", erro)
        else:
            print("OK. Estrutura de lotes esta OK (header, detalhes e trailer).")

        print("\n=== Validando sequencia de registros dentro de cada lote ===")
        erros_seq = validar_sequencia_registros_lote(linhas)
        if erros_seq:
            print("Problemas na sequencia dos registros:")
            for erro in erros_seq:
                print("   -", erro)
        else:
            print("OK. Sequencia dos registros nos lotes esta OK.")

        print("\n=== Validacoes especificas por layout configurado (Segmentos) ===")
        erros_seg, avisos_seg = validar_segmentos_por_layout(codigo_banco, linhas)
        if avisos_seg:
            print("Avisos em segmentos:")
            for aviso in avisos_seg:
                print("   -", aviso)
        if erros_seg:
            print("Erros em segmentos (P, Q, etc.):")
            for erro in erros_seg:
                print("   -", erro)
        else:
            print("Nenhum erro encontrado nos segmentos configurados para este banco.")
    else:
        print("\n=== Analisando estrutura CNAB 400 ===")
        header_bruto = linhas[0].rstrip("\r\n")
        codigo_banco_arquivo = header_bruto[76:79] if len(header_bruto) >= 79 else ""
        # BRB: header comeca com DCB e codigo nao vem no slot 076-079; forca 070 ao detectar layout DCB/075
        if codigo_banco_arquivo.strip() == "" and header_bruto.startswith("DCB"):
            codigo_banco_arquivo = "070"
        elif codigo_banco_arquivo.strip() == "" and len(header_bruto) >= 9 and header_bruto[6:9] == "075":
            codigo_banco_arquivo = "070"
        elif codigo_banco_arquivo.strip() == "":
            for linha in linhas:
                reg = linha.rstrip("\r\n")
                if reg.startswith("01") and len(reg) >= 153:
                    codigo_banco_arquivo = reg[150:153]
                    break
        if codigo_banco_arquivo == "341":
            analise = validar_cnab400_itau(linhas)
        elif codigo_banco_arquivo == "748":
            analise = validar_cnab400_sicredi(linhas)
        elif codigo_banco_arquivo == "104":
            analise = validar_cnab400_caixa(linhas)
        elif codigo_banco_arquivo == "237":
            analise = validar_cnab400_bradesco(linhas)
        elif codigo_banco_arquivo == "033":
            analise = validar_cnab400_santander(linhas)
        elif codigo_banco_arquivo == "070":
            analise = validar_cnab400_brb(linhas)
        else:
            analise = validar_cnab400_bb(linhas)

        codigo_banco = analise.get("codigo_banco") or "???"
        nome_banco = analise.get("nome_banco") or "Banco nao identificado"
        print(f"Banco detectado: {codigo_banco} - {nome_banco}")

        if analise.get("erros_header"):
            print("\nProblemas no header:")
            for erro in analise["erros_header"]:
                print("   -", erro)
        else:
            print("\nHeader verificado sem erros criticos.")

        if analise.get("erros_registros"):
            print("\nProblemas nos registros de detalhe:")
            for erro in analise["erros_registros"]:
                print("   -", erro)
        else:
            print("\nNenhum erro critico encontrado nos registros de detalhe.")

        if analise.get("erros_trailer"):
            print("\nProblemas no trailer/sequencia:")
            for erro in analise["erros_trailer"]:
                print("   -", erro)
        else:
            print("\nTrailer e sequencia geral consistentes.")

        if analise.get("avisos"):
            print("\nAvisos:")
            for aviso in analise["avisos"]:
                print("   -", aviso)

        resumo = analise.get("resumo") or {}
        print("\n=== Resumo rapido ===")
        print(f"Titulos: {resumo.get('qtd_titulos', 0)}")
        print(f"Valor total: R$ {resumo.get('valor_total_reais', 0.0):.2f}")
        venc_min = resumo.get("vencimento_min")
        venc_max = resumo.get("vencimento_max")
        if venc_min:
            print("Vencimento mais antigo:", venc_min.strftime("%d/%m/%Y"))
        if venc_max:
            print("Vencimento mais recente:", venc_max.strftime("%d/%m/%Y"))
        print(f"Registros opcionais (tipo 5): {resumo.get('qtd_registros_tipo5', 0)}")


if __name__ == "__main__":
    main()
