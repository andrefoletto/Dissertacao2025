# -*- coding: utf-8 -*-
"""
Atualiza curvas de carga em pu para o ano de 2034, a partir do ano-base de 2025.

Premissa:
- Crescimento linear da carga: 0,5% ao ano
- Período considerado: 2025 até 2034 = 9 anos
- Fator aplicado: 1 + 0,005 * 9 = 1,045

Formato esperado dos CSV:
coluna 1: hora decimal do ano
coluna 2: potência ativa em pu
coluna 3: potência reativa em pu

O script sobrescreve os arquivos originais nas mesmas pastas.
ATENÇÃO: execute apenas uma vez sobre os arquivos ainda não corrigidos para 2034.
Para evitar aplicação duplicada acidental, o script cria um arquivo de controle
".ajuste_cargas_2034_aplicado.flag" em cada pasta processada com sucesso.
"""

from pathlib import Path
import pandas as pd

# =============================================================================
# Configurações
# =============================================================================

ANO_BASE = 2025
ANO_ALVO = 2034

ANOS_CRESCIMENTO = ANO_ALVO - ANO_BASE
TAXA_CRESCIMENTO_ANUAL = 0.005  # 0,5% ao ano, crescimento linear

FATOR_CRESCIMENTO = 1 + TAXA_CRESCIMENTO_ANUAL * ANOS_CRESCIMENTO

# Proteção contra execução duplicada na mesma pasta
USAR_ARQUIVO_CONTROLE = True
ARQUIVO_CONTROLE = ".ajuste_cargas_2034_aplicado.flag"

PASTAS = [
    Path(r"C:\Users\afole\OneDrive\Dissertacao2025\Cargas_Especiais_ano_2034"),
    Path(r"C:\Users\afole\OneDrive\Dissertacao2025\Cargas_Estimadas_com_residuo_ano_2034"),
    Path(r"C:\Users\afole\OneDrive\Dissertacao2025\Cargas_Medidas_ano_2034"),
]

# =============================================================================
# Processamento
# =============================================================================

total_processados = 0
total_erros = 0
total_pastas_puladas = 0

print("=" * 78)
print("ATUALIZAÇÃO DAS CURVAS DE CARGA PARA O ANO DE 2034")
print(f"Ano-base: {ANO_BASE}")
print(f"Ano-alvo: {ANO_ALVO}")
print(f"Crescimento linear anual: {TAXA_CRESCIMENTO_ANUAL * 100:.2f}%")
print(f"Anos considerados: {ANOS_CRESCIMENTO}")
print(f"Crescimento total linear: {(FATOR_CRESCIMENTO - 1) * 100:.2f}%")
print(f"Fator aplicado em P_pu e Q_pu: {FATOR_CRESCIMENTO:.6f}")
print("ATENÇÃO: este ajuste é multiplicativo e deve ser executado apenas uma vez.")
print("=" * 78)

for pasta in PASTAS:
    erros_pasta = 0
    processados_pasta = 0
    flag_path = pasta / ARQUIVO_CONTROLE

    print(f"\nPasta: {pasta}")

    if not pasta.exists():
        print(f"[ERRO] Pasta não encontrada: {pasta}")
        total_erros += 1
        continue

    if USAR_ARQUIVO_CONTROLE and flag_path.exists():
        print(f"[PULADO] Ajuste de 2034 já aplicado anteriormente nesta pasta.")
        print(f"Arquivo de controle encontrado: {flag_path}")
        total_pastas_puladas += 1
        continue

    arquivos_csv = sorted(pasta.glob("*.csv"))
    print(f"Arquivos CSV encontrados: {len(arquivos_csv)}")

    if not arquivos_csv:
        print("[AVISO] Nenhum arquivo CSV encontrado nesta pasta.")
        continue

    for arquivo in arquivos_csv:
        try:
            # Lê CSV sem cabeçalho: hora_decimal, P_pu, Q_pu
            df = pd.read_csv(
                arquivo,
                header=None,
                sep=",",
                decimal=".",
                encoding="utf-8"
            )

            # Verificação mínima
            if df.shape[1] < 3:
                raise ValueError(
                    f"Arquivo possui apenas {df.shape[1]} colunas. "
                    "Esperadas pelo menos 3."
                )

            # Converte as três primeiras colunas para numérico
            df.iloc[:, 0] = pd.to_numeric(df.iloc[:, 0], errors="raise")
            df.iloc[:, 1] = pd.to_numeric(df.iloc[:, 1], errors="raise")
            df.iloc[:, 2] = pd.to_numeric(df.iloc[:, 2], errors="raise")

            # Multiplica somente P_pu e Q_pu.
            # A coluna de hora decimal permanece inalterada.
            df.iloc[:, 1] = df.iloc[:, 1] * FATOR_CRESCIMENTO
            df.iloc[:, 2] = df.iloc[:, 2] * FATOR_CRESCIMENTO

            # Sobrescreve o arquivo original, mantendo sem cabeçalho e sem índice
            df.to_csv(
                arquivo,
                index=False,
                header=False,
                sep=",",
                decimal=".",
                float_format="%.15g",
                encoding="utf-8"
            )

            total_processados += 1
            processados_pasta += 1
            print(f"[OK] {arquivo.name}")

        except Exception as e:
            total_erros += 1
            erros_pasta += 1
            print(f"[ERRO] {arquivo.name}: {e}")

    # Cria o arquivo de controle somente se a pasta foi processada sem erros
    if USAR_ARQUIVO_CONTROLE and processados_pasta > 0 and erros_pasta == 0:
        flag_path.write_text(
            "Ajuste das cargas para 2034 aplicado com sucesso.\n"
            f"Ano-base: {ANO_BASE}\n"
            f"Ano-alvo: {ANO_ALVO}\n"
            f"Taxa anual linear: {TAXA_CRESCIMENTO_ANUAL:.6f}\n"
            f"Anos considerados: {ANOS_CRESCIMENTO}\n"
            f"Crescimento total linear: {(FATOR_CRESCIMENTO - 1) * 100:.2f}%\n"
            f"Fator aplicado: {FATOR_CRESCIMENTO:.6f}\n"
            f"Arquivos processados nesta pasta: {processados_pasta}\n",
            encoding="utf-8"
        )
        print(f"[OK] Arquivo de controle criado: {flag_path}")

print("\n" + "=" * 78)
print("PROCESSAMENTO CONCLUÍDO")
print(f"Arquivos processados: {total_processados}")
print(f"Pastas puladas por arquivo de controle: {total_pastas_puladas}")
print(f"Erros: {total_erros}")
print(f"Crescimento total linear: {(FATOR_CRESCIMENTO - 1) * 100:.2f}%")
print(f"Fator aplicado em P_pu e Q_pu: {FATOR_CRESCIMENTO:.6f}")
print("=" * 78)
