# %% Celula 001 - Imports + parametros de caminho
from pathlib import Path
import re
import numpy as np
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")

FP_SIM2 = WORK_DIR / "Simulacao 002" / "Tabela_demanda_consumo_por_posto_SIM2_2025.csv"

FP_SIM3 = WORK_DIR / "Simulacao 003 segmentos" / "Tabela_demanda_consumo_por_posto_SIM3_2025.csv"  # barra 0016
FP_SIM4 = WORK_DIR / "Simulacao 004 segmentos" / "Tabela_demanda_consumo_por_posto_SIM4_2025.csv"  # barra 0700
FP_SIM5 = WORK_DIR / "Simulacao 005 segmentos" / "Tabela_demanda_consumo_por_posto_SIM5_2025.csv"  # barra 1250
FP_SIM6 = WORK_DIR / "Simulacao 006 segmentos" / "Tabela_demanda_consumo_por_posto_SIM6_2025.csv"  # barra 1630
FP_SIM7 = WORK_DIR / "Simulacao 007 segmentos" / "Tabela_demanda_consumo_por_posto_SIM7_2025.csv"  # barra 1950
FP_SIM8 = WORK_DIR / "Simulacao 008 segmentos" / "Tabela_demanda_consumo_por_posto_SIM8_2025.csv"  # barra 2220
FP_SIM9 = WORK_DIR / "Simulacao 009 segmentos" / "Tabela_demanda_consumo_por_posto_SIM9_2025.csv"  # barra 2380

CENARIOS = [
    {"sim": "SIM3", "barra":   16, "fp": FP_SIM3},
    {"sim": "SIM4", "barra":  700, "fp": FP_SIM4},
    {"sim": "SIM5", "barra": 1250, "fp": FP_SIM5},
    {"sim": "SIM6", "barra": 1630, "fp": FP_SIM6},
    {"sim": "SIM7", "barra": 1950, "fp": FP_SIM7},
    {"sim": "SIM8", "barra": 2220, "fp": FP_SIM8},
    {"sim": "SIM9", "barra": 2380, "fp": FP_SIM9},
]

OUT_DIR = WORK_DIR / "23 Comparativos barras menos perdas 1MW 3MWh"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MESES_ORD = ["JAN","FEV","MAR","ABR","MAI","JUN","JUL","AGO","SET","OUT","NOV","DEZ"]

# %% Celula 002 - Funcoes utilitarias (leitura + custos)
def _clean_columns(cols) -> list[str]:
    out = []
    for c in cols:
        s = str(c).replace("\ufeff", "").strip().strip('"').strip()
        s = re.sub(r"\s+", " ", s)  # colapsa espacos (evita mismatch por "  ")
        out.append(s)
    return out


def _read_table_full(fp: Path) -> pd.DataFrame:
    if not fp.exists():
        raise FileNotFoundError(fp)
    df = pd.read_csv(fp, encoding="utf-8-sig", engine="python")
    df.columns = _clean_columns(df.columns)
    if "MES" not in df.columns:
        if "Mes" in df.columns:
            df = df.rename(columns={"Mes": "MES"})
        else:
            raise ValueError(f"Coluna 'MES' nao encontrada em: {fp}")
    df["MES"] = df["MES"].astype(str).str.strip().str.upper()
    return df


def _only_months(df_full: pd.DataFrame) -> pd.DataFrame:
    df_m = df_full[df_full["MES"].isin(MESES_ORD)].copy()
    df_m["MES"] = pd.Categorical(df_m["MES"], categories=MESES_ORD, ordered=True)
    df_m = df_m.sort_values("MES").reset_index(drop=True)
    return df_m


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _monthly_total_cost(df_m: pd.DataFrame) -> pd.Series:
    # 1) Preferencial: coluna pronta
    if "R$TOTAL_MES" in df_m.columns:
        return _to_num(df_m["R$TOTAL_MES"]).fillna(0.0)

    # 2) Fallback robusto:
    #    soma todas as colunas monetarias (qualquer coluna contendo "R$"),
    #    exceto a coluna MES.
    money_cols = [c for c in df_m.columns if ("R$" in c) and (c != "MES")]
    if not money_cols:
        raise ValueError(
            "Nao encontrei 'R$TOTAL_MES' nem colunas monetarias contendo 'R$'. "
            f"Colunas disponiveis: {list(df_m.columns)}"
        )

    return df_m[money_cols].apply(_to_num).fillna(0.0).sum(axis=1)


def _annual_total(df_full: pd.DataFrame, df_m: pd.DataFrame) -> float:
    # 1) Se existir R$TOTAL_MES e linha TOTAIS, usa direto (mais confiavel)
    if "R$TOTAL_MES" in df_full.columns:
        row = df_full[df_full["MES"] == "TOTAIS"]
        if not row.empty:
            v = pd.to_numeric(row["R$TOTAL_MES"].iloc[0], errors="coerce")
            if pd.notna(v):
                return float(v)

    # 2) Se existir linha R$TOTAL (alguns arquivos antigos do SIM2)
    if (df_full["MES"] == "R$TOTAL").any():
        r = df_full[df_full["MES"] == "R$TOTAL"].iloc[0]
        # tenta pegar qualquer coluna monetaria com valor numerico
        for c in [c for c in df_full.columns if "R$" in c]:
            v = pd.to_numeric(r[c], errors="coerce")
            if pd.notna(v):
                return float(v)

    # 3) Fallback: soma mensal
    return float(_monthly_total_cost(df_m).sum())


# %% Celula 003 - Leitura do caso base (SIM2) + custo mensal e anual
base_full = _read_table_full(FP_SIM2)
base_m = _only_months(base_full)

base_cost_m = _monthly_total_cost(base_m)
base_total = _annual_total(base_full, base_m)

print("[SIM2] Custo anual (R$):", base_total)
print("[SIM2] Soma mensal confere (R$):", float(base_cost_m.sum()))

# %% Celula 004 - Comparativos mensais SIM2 vs cada cenario (salva CSV por cenario)
comparativos = []
resumo_anual = []

for c in CENARIOS:
    sim = c["sim"]
    barra = int(c["barra"])
    fp = c["fp"]

    df_full = _read_table_full(fp)
    df_m = _only_months(df_full)

    cost_m = _monthly_total_cost(df_m)
    total = _annual_total(df_full, df_m)

    # Junta por MES (garante mesma ordem)
    df_cmp = pd.DataFrame({
        "MES": MESES_ORD,
        "R$SIM2": base_cost_m.reindex(range(len(MESES_ORD))).to_numpy(dtype=float),
        f"R${sim}": cost_m.reindex(range(len(MESES_ORD))).to_numpy(dtype=float),
    })

    df_cmp["Economia_R$"] = (df_cmp["R$SIM2"] - df_cmp[f"R${sim}"]).round(2)
    df_cmp["Economia_%"] = np.where(
        df_cmp["R$SIM2"] == 0,
        np.nan,
        (df_cmp["Economia_R$"] / df_cmp["R$SIM2"] * 100).round(3),
    )

    # Linha TOTAIS
    tot = {
        "MES": "TOTAIS",
        "R$SIM2": float(df_cmp["R$SIM2"].sum()),
        f"R${sim}": float(df_cmp[f"R${sim}"].sum()),
        "Economia_R$": float(df_cmp["Economia_R$"].sum()),
        "Economia_%": (np.nan if float(df_cmp["R$SIM2"].sum()) == 0 else float(df_cmp["Economia_R$"].sum() / df_cmp["R$SIM2"].sum() * 100)),
    }
    df_cmp = pd.concat([df_cmp, pd.DataFrame([tot])], ignore_index=True)

    out_cmp = OUT_DIR / f"03_Comparativo_mensal_SIM2_vs_{sim}.csv"
    df_cmp.to_csv(out_cmp, index=False, encoding="utf-8-sig")
    print("[OK] Salvo:", out_cmp)

    # Guarda resumo anual
    economia_rs = base_total - total
    economia_pct = np.nan if base_total == 0 else (economia_rs / base_total * 100)

    resumo_anual.append({
        "Cenario": f"{sim}_{barra}",
        "Barra": barra,
        "R$TOTAL_ANO": float(total),
        "Economia_R$_vs_SIM2": float(economia_rs),
        "Economia_%_vs_SIM2": float(economia_pct),
    })

# %% Celula 005 - Resumo anual + ordenacao por menor custo (salva CSV)
resumo_df = pd.DataFrame(resumo_anual)

# Ordena por menor custo anual (melhor)
resumo_df_ord = resumo_df.sort_values(["R$TOTAL_ANO", "Barra"]).reset_index(drop=True)

out1 = OUT_DIR / "01_Resumo_anual_barras.csv"
out2 = OUT_DIR / "02_Resumo_anual_barras_ordenado.csv"

resumo_df.to_csv(out1, index=False, encoding="utf-8-sig")
resumo_df_ord.to_csv(out2, index=False, encoding="utf-8-sig")

print("\n[DONE] Resumos anuais:")
print(" -", out1)
print(" -", out2)
print("\nTop (menor custo anual):")
print(resumo_df_ord.head(10))
