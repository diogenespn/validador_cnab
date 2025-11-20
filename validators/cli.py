"""Utilit?rio de linha de comando para o validador CNAB."""

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
        print("\n=== Analisando estrutura CNAB 400 (Banco do Brasil) ===")
        analise = validar_cnab400_bb(linhas)
        codigo_banco = analise.get("codigo_banco") or "???"
        nome_banco = analise.get("nome_banco") or "Banco não identificado"
        print(f"Banco detectado: {codigo_banco} - {nome_banco}")

        if analise.get("erros_header"):
            print("\n❌ Problemas no header:")
            for erro in analise["erros_header"]:
                print("   -", erro)
        else:
            print("\n✅ Header verificado sem erros críticos.")

        if analise.get("erros_registros"):
            print("\n❌ Problemas nos registros de detalhe:")
            for erro in analise["erros_registros"]:
                print("   -", erro)
        else:
            print("\n✅ Nenhum erro crítico encontrado nos registros tipo 7.")

        if analise.get("erros_trailer"):
            print("\n❌ Problemas no trailer/seqüência:")
            for erro in analise["erros_trailer"]:
                print("   -", erro)
        else:
            print("\n✅ Trailer e sequência geral consistentes.")

        if analise.get("avisos"):
            print("\n⚠ Avisos:")
            for aviso in analise["avisos"]:
                print("   -", aviso)

        resumo = analise.get("resumo") or {}
        print("\n=== Resumo rápido ===")
        print(f"Títulos: {resumo.get('qtd_titulos', 0)}")
        print(f"Valor total: R$ {resumo.get('valor_total_reais', 0.0):.2f}")
        venc_min = resumo.get("vencimento_min")
        venc_max = resumo.get("vencimento_max")
        if venc_min:
            print("Vencimento mais antigo:", venc_min.strftime("%d/%m/%Y"))
        if venc_max:
            print("Vencimento mais recente:", venc_max.strftime("%d/%m/%Y"))
        print(f"Registros opcionais (tipo 5): {resumo.get('qtd_registros_tipo5', 0)}")
