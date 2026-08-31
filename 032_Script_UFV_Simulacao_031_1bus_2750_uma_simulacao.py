# -*- coding: utf-8 -*-
# =============================================================================
# 032_Script_UFV_Simulacao_031_1bus_2750_uma_simulacao.py
#
# Regras deste script:
#   - Sem acentos em comentarios e strings pt-br.
#   - Celulas independentes: cada celula define suas variaveis e funcoes locais.
#   - Uma celula pode depender APENAS de arquivos de entrada/saida.
#
# =============================================================================

# %% Celula 001 - PASSO UNICO: simulacao segmentada da rede base (monitores + EnergyMeter)
# ======================================================================================
# Saidas:
#   Simulacao 031 segmentos/
#     UFSM_Mon_<KEY>_sNNNNN_<POSTO>.csv     (1 por monitor por segmento)
#     EXP_MTR_GERAL_<SEG_TAG>.csv           (1 por segmento)
#
# Requisitos:
#   - Posto_tarifario_simulacao.csv
#   - C:\Users\afole\OneDrive\Dissertacao2025\UFV_poa_2025.csv
#   - C:\Users\afole\OneDrive\Dissertacao2025\UFV_tmod_2025.csv
#
# Observacao:
#   - Esta versao nao possui BESS nem cargas auxiliares associadas ao BESS.
#   - Inclui UFV1 ~ 792 kWp em U013 (BT do trafo UFV8001_1000), coerente com o arranjo
#     validado no PVsyst: 1760 modulos de 450 W, 88 strings x 20 modulos,
#     8 inversores x 100 kW, 11 strings por inversor.
# ======================================================================================

import os
from pathlib import Path
import numpy as np
import pandas as pd
from py_dss_interface import DSS

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
os.chdir(WORK_DIR)

ARQ_POSTO = WORK_DIR / "Posto_tarifario_simulacao.csv"
ARQ_POA_UFV1 = WORK_DIR / "UFV_poa_2025.csv"
ARQ_TMOD_UFV1 = WORK_DIR / "UFV_tmod_2025.csv"

DT_H = 0.25
TOTAL_NPTS = 35040

MON_SPECS = {
    "GERAL":       {"element": "line.0015_0016", "terminal": 1},
    "LADO1":       {"element": "line.0016_0017", "terminal": 1},
    "LADO2":       {"element": "line.0016_0018", "terminal": 1},
    "0700_ANTES":  {"element": "line.0690_0700", "terminal": 1},
    "0700_DEPOIS": {"element": "line.0700_0710", "terminal": 1},
    "1250_ANTES":  {"element": "line.1120_1250", "terminal": 1},
    "1250_DEPOIS": {"element": "line.1250_1260", "terminal": 1},
    "1630_ANTES":  {"element": "line.1620_1630", "terminal": 1},
    "1630_DEPOIS": {"element": "line.1630_1640", "terminal": 1},
    "1950_ANTES":  {"element": "line.1940_1950", "terminal": 1},
    "1950_DEPOIS": {"element": "line.1950_1960", "terminal": 1},
    "2220_ANTES":  {"element": "line.2070_2220", "terminal": 1},
    "2220_DEPOIS": {"element": "line.2220_2230", "terminal": 1},
    "2380_ANTES":  {"element": "line.2370_2380", "terminal": 1},
    "2380_DEPOIS": {"element": "line.2380_2390", "terminal": 1},
    "2750_ANTES":  {"element": "line.2740_2750", "terminal": 1},
    "2750_DEPOIS": {"element": "line.2750_2760", "terminal": 1},
    "TR_UFV1_MT":  {"element": "transformer.UFV8001_1000", "terminal": 1},
    "TR_UFV1_BT":  {"element": "transformer.UFV8001_1000", "terminal": 2},
}
MON_KEYS = list(MON_SPECS.keys())

DIR_PASS2 = WORK_DIR / "Simulacao 031 segmentos"
DIR_PASS2.mkdir(parents=True, exist_ok=True)


def hour_sec_from_hora_decimal(h: float, dt_h: float) -> tuple[int, int, float]:
    hq = round(round(float(h) / dt_h) * dt_h, 10)
    hour_int = int(np.floor(hq))
    sec_int = int(round((hq - hour_int) * 3600.0))
    if sec_int >= 3600:
        hour_int += 1
        sec_int -= 3600
    return hour_int, sec_int, hq


def _build_circuit_pass2(dss: DSS, posto: str, seg_tag: str) -> dict[str, str]:
    posto = str(posto).strip().upper()
    if posto not in ["PONTA", "FORA_PONTA"]:
        raise ValueError(f"Posto invalido: {posto}")

    dss.text("Clear")
    dss.text(f'cd "{WORK_DIR}"')
    dss.text(
        "New Circuit.UFSM bus1=0010 basekv=13.8 phases=3 "
        "puZ0=[1.24 2.50] puZ1=[0.43 0.98] puZ2=[0.43 0.98]"
    )

    dss.text('Redirect "UFSM_wiredata.dss"')
    dss.text('Redirect "UFSM_linhas.dss"')
    dss.text('Redirect "UFSM_chaves.dss"')
    dss.text('Redirect "UFSM_caps.dss"')
    dss.text('Redirect "UFSM_trafos_medidos.dss"')
    dss.text('Redirect "UFSM_trafos_cargas_especiais.dss"')
    dss.text('Redirect "UFSM_trafos_estimados.dss"')
    dss.text('Redirect "UFSM_cargas_medidas.dss"')
    dss.text('Redirect "UFSM_cargas_especiais.dss"')
    dss.text('Redirect "UFSM_cargas_estimadas_com_residuo.dss"')

    # UFV1 em 2750 -> trafo 13.8 / 0.38 kV -> barra BT U013
    dss.text("New line.2750_U011 phases=3 bus1=2750 bus2=U011 length=0.0200 units=km Geometry=UG_trefoil_25")
    dss.text("New line.U011_U012 phases=3 bus1=U011 bus2=U012 Switch=y enable=true")
    dss.text(
        "New transformer.UFV8001_1000 XHL=6.0 windings=2 %loadloss=1.46 %noloadloss=0.29 %imag=1.5 "
        "wdg=1 bus=U012 kv=13.8 kva=1000 conn=delta "
        "wdg=2 bus=U013 kv=0.38 kva=1000 conn=wye"
    )

    # === CURVAS DE EFICIENCIA E TEMPERATURA ===
    # Curva de eficiencia do inversor Huawei SUN2000-100KTL-M1/M2 (aproximacao CC/CA)
    dss.text("New XYCurve.Eff_Huawei100k npts=10")
    dss.text("~ xarray=[0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0]")
    dss.text("~ yarray=[0.970 0.980 0.986 0.989 0.991 0.992 0.993 0.993 0.992 0.991]")

    # Curva de potencia x temperatura do modulo Trina 450 Wp (gammaP = -0.34 %/°C)
    dss.text("New XYCurve.P_T_Trina450 npts=10")
    dss.text("~ xarray=[0 10 20 25 30 35 40 45 50 55]")
    dss.text("~ yarray=[1.085 1.051 1.017 1.000 0.983 0.966 0.949 0.932 0.915 0.898]")

    # Curvas anuais de irradiancia POA e temperatura do modulo - 2025
    dss.text(f'New Loadshape.Irrad_UFV1 npts={TOTAL_NPTS} interval=0 csvfile="{ARQ_POA_UFV1}"')
    dss.text(f'New Tshape.Temp_UFV1     npts={TOTAL_NPTS} interval=0 csvfile="{ARQ_TMOD_UFV1}"')

    # === SISTEMA FOTOVOLTAICO ~792 kWp (8 x 100 kW) ===
    # Usa shapes anuais (yearly / Tyearly), coerentes com Set Mode=Yearly
    # 1760 modulos x 450 Wp = 792.0 kWp
    # 88 strings x 20 modulos
    # 11 strings por inversor -> 220 modulos/inversor -> 99.0 kWpdc por inversor
    for i in range(1, 9):
        dss.text(
            f"New PVSystem.UFV8001_INV{i} phases=3 bus1=U013 kv=0.38 "
            f"pmpp=99.0 kVA=100 pf=1.0 conn=wye "
            f"%cutin=0.1 %cutout=0.1 "
            f"effcurve=Eff_Huawei100k P-TCurve=P_T_Trina450 "
            f"yearly=Irrad_UFV1 Tyearly=Temp_UFV1"
        )

    mon_names: dict[str, str] = {}
    for key in MON_KEYS:
        spec = MON_SPECS[key]
        mname = f"{key}_{seg_tag}"
        mon_names[key] = mname
        dss.text(f"New Monitor.{mname} element={spec['element']} terminal={spec['terminal']} mode=1 ppolar=no")

    dss.text("New Energymeter.GERAL element=line.0015_0016 terminal=1")

    dss.text("Set VoltageBases=[13.8,0.38,0.22]")
    dss.text("CalcVoltageBases")
    return mon_names


def _find_exported_monitor_file(export_dir: Path, mon_name: str) -> Path:
    cands = sorted(export_dir.glob(f"*{mon_name}*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        cands2 = sorted(export_dir.glob("Mon_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if cands2:
            return cands2[0]
        raise FileNotFoundError(f"Nenhum CSV do monitor contendo '{mon_name}' em {export_dir}")
    return cands[0]


def _export_meter_and_rename(export_dir: Path, seg_tag: str) -> Path:
    src = export_dir / "EXP_MTR_GERAL.csv"
    if not src.exists():
        raise FileNotFoundError(f"Nao achei {src} apos Export Meter /m")

    dst = export_dir / f"EXP_MTR_GERAL_{seg_tag}.csv"
    if dst.exists():
        dst.unlink()
    src.rename(dst)
    return dst


def _run_segment_pass2(
    dss: DSS,
    hora_ini: float,
    n_steps: int,
    mon_names: dict[str, str],
    seg_tag: str,
    seg_idx: int,
    posto: str,
) -> tuple[dict[str, Path], Path]:

    hour_int, sec_int, hora_q = hour_sec_from_hora_decimal(hora_ini, DT_H)

    print(
        f"[SOLVE] seg={int(seg_idx):05d} posto={posto} "
        f"hora_ini={hora_q:.2f}h -> Hour={hour_int} Sec={sec_int} "
        f"DT={DT_H:.2f}h n_steps={int(n_steps)}"
    )

    dss.text(f"Set Mode=Yearly Hour={hour_int} Sec={sec_int} StepSize={DT_H}h Number={int(n_steps)}")
    dss.text("Solve")

    dss.text(f'cd "{DIR_PASS2}"')

    mon_paths: dict[str, Path] = {}
    for key, mname in mon_names.items():
        dss.text(f"Export Monitors {mname}")
        fp = _find_exported_monitor_file(DIR_PASS2, mname)
        dst = DIR_PASS2 / f"UFSM_Mon_{key}_s{int(seg_idx):05d}_{posto}.csv"
        if dst.exists():
            dst.unlink()
        fp.rename(dst)
        mon_paths[key] = dst

    exp_mtr = DIR_PASS2 / "EXP_MTR_GERAL.csv"
    if exp_mtr.exists():
        exp_mtr.unlink()

    dss.text("Export Meter /m")
    mtr_fp = _export_meter_and_rename(DIR_PASS2, seg_tag)

    dss.text(f'cd "{WORK_DIR}"')
    return mon_paths, mtr_fp


# ---- ler posto e formar segmentos ----
if not ARQ_POSTO.exists():
    raise FileNotFoundError(ARQ_POSTO)

posto_df = pd.read_csv(ARQ_POSTO, encoding="utf-8-sig", sep=None, engine="python")
posto_df.columns = posto_df.columns.astype(str).str.replace("\ufeff", "", regex=False).str.strip()

for c in ["Hora_decimal", "Posto_horario"]:
    if c not in posto_df.columns:
        raise ValueError(f"Coluna {c!r} nao encontrada. Colunas: {list(posto_df.columns)}")

posto_df = posto_df[["Hora_decimal", "Posto_horario"]].copy()
posto_df["Hora_decimal"] = pd.to_numeric(posto_df["Hora_decimal"], errors="coerce")
posto_df["Posto_horario"] = posto_df["Posto_horario"].astype(str).str.strip().str.upper()
posto_df = posto_df.dropna(subset=["Hora_decimal"]).sort_values("Hora_decimal").reset_index(drop=True)

posto_df["seg_id"] = (posto_df["Posto_horario"] != posto_df["Posto_horario"].shift(1)).cumsum()
segments = (
    posto_df.groupby("seg_id", as_index=False)
    .agg(
        posto=("Posto_horario", "first"),
        hora_ini=("Hora_decimal", "first"),
        n_steps=("Hora_decimal", "size"),
    )
)

for i, row in segments.iterrows():
    posto = str(row["posto"]).upper()
    hora_ini = float(row["hora_ini"])
    n_steps = int(row["n_steps"])

    seg_tag = f"S{i:05d}_{posto}"

    dss = DSS()
    mon_names = _build_circuit_pass2(dss=dss, posto=posto, seg_tag=seg_tag)

    mon_paths, mtr_fp = _run_segment_pass2(
        dss=dss,
        hora_ini=hora_ini,
        n_steps=n_steps,
        mon_names=mon_names,
        seg_tag=seg_tag,
        seg_idx=i,
        posto=posto,
    )

    print(
        f"[OK] {seg_tag}: hora_ini={hora_ini:.2f}h steps={n_steps} | meter={mtr_fp.name}"
    )

print("[DONE] PASSO UNICO concluido.")

# %% Celula 002 - emenda monitores (todos)
# =============================================================================
# Entrada:
#   Simulacao 031 segmentos/UFSM_Mon_<KEY>_s*.csv
# Saida:
#   Simulacao 031 segmentos/Monitor_<KEY>_anual.csv
# Remove:
#   UFSM_Mon_<KEY>_s*.csv
# =============================================================================

from pathlib import Path
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
DIR_PASS2 = WORK_DIR / "Simulacao 031 segmentos"

def infer_mon_keys(dir_seg: Path) -> list[str]:
    files = sorted(dir_seg.glob("UFSM_Mon_*_s*.csv"))
    if not files:
        raise FileNotFoundError(f"Nao encontrei UFSM_Mon_*_s*.csv em {dir_seg}")
    keys = set()
    for fp in files:
        stem = fp.stem  # UFSM_Mon_<KEY>_s00012_PONTA
        rest = stem[len("UFSM_Mon_"):]
        mon = rest.split("_s", 1)[0]
        keys.add(mon)
    return sorted(keys)

for mon_key in infer_mon_keys(DIR_PASS2):
    out_fp = DIR_PASS2 / f"Monitor_{mon_key}_anual.csv"
    files = sorted(DIR_PASS2.glob(f"UFSM_Mon_{mon_key}_s*.csv"))

    dfs = [pd.read_csv(fp, encoding="utf-8-sig", sep=None, engine="python") for fp in files]
    merged = pd.concat(dfs, ignore_index=True)

    if len(merged) != 35040:
        raise ValueError(f"[{mon_key}] Emenda gerou {len(merged)} linhas (esperado 35040).")

    merged.to_csv(out_fp, index=False, encoding="utf-8-sig")
    print(f"OK - {mon_key}: anual gerado: {out_fp.name} | linhas: {len(merged)}")

    for fp in files:
        fp.unlink()
    print(f"[CLEAN] Segmentados removidos ({mon_key}).")

# %% Celula 003 - junta EnergyMeter (segmentos + TOTAL)
# =============================================================================
# Entrada:
#   Simulacao 031 segmentos/EXP_MTR_GERAL_*.csv
# Saida:
#   Simulacao 031 segmentos/EXP_MTR_GERAL_anual.csv
# Remove:
#   EXP_MTR_GERAL_*.csv
# =============================================================================

from pathlib import Path
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
DIR_PASS2 = WORK_DIR / "Simulacao 031 segmentos"
OUT_FP = DIR_PASS2 / "EXP_MTR_GERAL_anual.csv"

files = sorted([p for p in DIR_PASS2.glob("EXP_MTR_GERAL_*.csv") if p.name.lower() != OUT_FP.name.lower()])
if not files:
    raise FileNotFoundError(f"Nenhum EXP_MTR_GERAL_*.csv em {DIR_PASS2}")

def norm_cols(cols):
    return [str(c).strip().strip('"').strip() for c in cols]

def infer_tag_from_name(fp: Path) -> str:
    name = fp.stem
    if name.upper().startswith("EXP_MTR_GERAL_"):
        return name[len("EXP_MTR_GERAL_"):]
    return name

dfs = []
base_cols = None
for fp in files:
    dfm = pd.read_csv(fp, sep=",", engine="python")
    if dfm.empty:
        raise ValueError(f"Arquivo vazio: {fp}")
    dfm.columns = norm_cols(dfm.columns)
    if base_cols is None:
        base_cols = list(dfm.columns)
    else:
        if set(dfm.columns) != set(base_cols):
            raise ValueError(f"Colunas diferentes em {fp}")
        dfm = dfm.reindex(columns=base_cols)

    row = dfm.iloc[[0]].copy()
    if "Segmento" not in row.columns:
        row.insert(0, "Segmento", infer_tag_from_name(fp))
    dfs.append(row)

seg_df = pd.concat(dfs, ignore_index=True)

id_cols = {"Year", "LDCurve", "Hour", "Meter", "Segmento"}
cols = list(seg_df.columns)
max_cols = [c for c in cols if ("Max" in c) and (c not in id_cols)]
energy_cols = [c for c in cols if (c not in id_cols) and (("kWh" in c) or ("kvarh" in c) or ("kVArh" in c))]
num_cols = [c for c in cols if (c not in id_cols) and (c not in max_cols)]
other_sum_cols = [c for c in num_cols if c not in energy_cols]

total = {c: "" for c in cols}
total["Segmento"] = "TOTAL"
if "Meter" in cols:
    total["Meter"] = "GERAL"
if "Year" in cols:
    total["Year"] = seg_df["Year"].iloc[0] if "Year" in seg_df.columns else 0
if "LDCurve" in cols:
    total["LDCurve"] = ""
if "Hour" in cols:
    h = pd.to_numeric(seg_df["Hour"], errors="coerce")
    total["Hour"] = float(h.max()) if h.notna().any() else ""

for c in energy_cols + other_sum_cols:
    v = pd.to_numeric(seg_df[c], errors="coerce").fillna(0.0)
    total[c] = float(v.sum())

for c in max_cols:
    v = pd.to_numeric(seg_df[c], errors="coerce")
    total[c] = float(v.max()) if v.notna().any() else 0.0

out_df = pd.concat([seg_df, pd.DataFrame([total])], ignore_index=True)
out_df.to_csv(OUT_FP, index=False, encoding="utf-8-sig")
print("OK - EnergyMeter anual salvo em:", OUT_FP)

for fp in files:
    fp.unlink()
print("[CLEAN] Segmentados removidos (EnergyMeter).")

# %% Celula 004 - monitores -> curvas trifasicas (SHIFT DIREITA + mascara de apagao RGE)
# =============================================================================
# Entradas:
#   Simulacao 031 segmentos/Monitor_<KEY>_anual.csv
#   01_mascara_apagao_RGE_2025.csv
# Saidas:
#   Simulacao 031 segmentos/Curva_de_Carga_<KEY>_sim_31.csv
# Remove:
#   Monitor_<KEY>_anual.csv
# =============================================================================

from pathlib import Path
import numpy as np
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
DIR_PASS2 = WORK_DIR / "Simulacao 031 segmentos"
ARQ_MASCARA = WORK_DIR / "01_mascara_apagao_RGE_2025.csv"

DT_H = 0.25
TOTAL_NPTS = 35040
hora = np.round(np.arange(0.0, 8760.0, DT_H), 10)

cols_vals = ["P1 (kW)", "Q1 (kvar)", "P2 (kW)", "Q2 (kvar)", "P3 (kW)", "Q3 (kvar)"]

files = sorted(DIR_PASS2.glob("Monitor_*_anual.csv"))
if not files:
    raise FileNotFoundError(f"Nao encontrei Monitor_*_anual.csv em {DIR_PASS2}")

# -------------------------
# Leitura da mascara de apagao
# Esperado:
#   Hora_decimal, apagao_total
# onde:
#   apagao_total = 1  -> apaga totalmente carga/geracao
#   apagao_total = 0  -> mantem normalmente
# -------------------------
if not ARQ_MASCARA.exists():
    raise FileNotFoundError(f"Nao encontrei a mascara de apagao: {ARQ_MASCARA}")

mask_df = pd.read_csv(ARQ_MASCARA, encoding="utf-8-sig", sep=None, engine="python")
mask_df.columns = mask_df.columns.astype(str).str.replace("\ufeff", "", regex=False).str.strip()

for c in ["Hora_decimal", "apagao_total"]:
    if c not in mask_df.columns:
        raise ValueError(f"Coluna {c!r} nao encontrada em {ARQ_MASCARA}. Colunas: {list(mask_df.columns)}")

mask_df = mask_df[["Hora_decimal", "apagao_total"]].copy()
mask_df["Hora_decimal"] = pd.to_numeric(mask_df["Hora_decimal"], errors="coerce")
mask_df["apagao_total"] = pd.to_numeric(mask_df["apagao_total"], errors="coerce").fillna(0).astype(int)

if mask_df["Hora_decimal"].isna().any():
    raise ValueError("Ha valores invalidos em Hora_decimal na mascara de apagao.")

mask_df = mask_df.sort_values("Hora_decimal").reset_index(drop=True)

if len(mask_df) != TOTAL_NPTS:
    raise ValueError(
        f"Mascara com tamanho inesperado: {len(mask_df)} (esperado {TOTAL_NPTS})."
    )

if not np.allclose(mask_df["Hora_decimal"].to_numpy(), hora, atol=1e-9):
    raise ValueError(
        "Hora_decimal da mascara nao coincide com a grade anual esperada de 15 min."
    )

apagao = mask_df["apagao_total"].to_numpy(dtype=int)
apagao_bool = apagao == 1

for in_fp in files:
    mon_key = in_fp.stem.replace("Monitor_", "").replace("_anual", "")
    out_fp = DIR_PASS2 / f"Curva_de_Carga_{mon_key}_sim_31.csv"

    mon = pd.read_csv(in_fp, encoding="utf-8-sig", sep=None, engine="python")
    mon.columns = mon.columns.astype(str).str.replace("\ufeff", "", regex=False).str.strip()

    missing = [c for c in cols_vals if c not in mon.columns]
    if missing:
        raise ValueError(f"[{mon_key}] Colunas faltando: {missing}")

    for c in cols_vals:
        mon[c] = pd.to_numeric(mon[c], errors="coerce")

    if mon[cols_vals].isna().any().any():
        raise ValueError(f"[{mon_key}] NaN nas colunas eletricas.")

    if len(mon) != TOTAL_NPTS:
        raise ValueError(f"[{mon_key}] Tamanho inesperado: {len(mon)} (esperado {TOTAL_NPTS}).")

    vals = mon[cols_vals].to_numpy(copy=True)

    # SHIFT anual unico para a DIREITA
    vals = np.vstack([vals[0:1, :], vals[0:-1, :]])

    # Aplicacao da mascara de apagao:
    # se apagao_total == 1, zera todas as grandezas trifasicas
    vals[apagao_bool, :] = 0.0

    df_out = pd.DataFrame(vals, columns=cols_vals)
    df_out.insert(0, "Hora_decimal", hora)

    df_out["P_3f_S"] = df_out["P1 (kW)"] + df_out["P2 (kW)"] + df_out["P3 (kW)"]
    df_out["Q_3f_S"] = df_out["Q1 (kvar)"] + df_out["Q2 (kvar)"] + df_out["Q3 (kvar)"]

    df_out[["Hora_decimal", "P_3f_S", "Q_3f_S"]].to_csv(
        out_fp, index=False, encoding="utf-8-sig"
    )

    in_fp.unlink()

    n_apagoes = int(apagao_bool.sum())
    print(
        f"[OK] {mon_key}: {out_fp.name} | removido: {in_fp.name} | "
        f"SHIFT DIREITA + mascara apagao aplicada ({n_apagoes} pontos zerados)"
    )

# %% Celula 005 - resumo do EnergyMeter (linha TOTAL)
# =============================================================================
# Entrada:
#   Simulacao 031 segmentos/EXP_MTR_GERAL_anual.csv
# Saida:
#   Simulacao 031 segmentos/Resumo_EnergyMeter_Geral_Sim31.csv
# =============================================================================

from pathlib import Path
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
DIR_PASS2 = WORK_DIR / "Simulacao 031 segmentos"

IN_FP  = DIR_PASS2 / "EXP_MTR_GERAL_anual.csv"
OUT_FP = DIR_PASS2 / "Resumo_EnergyMeter_Geral_Sim31.csv"

if not IN_FP.exists():
    raise FileNotFoundError(IN_FP)

df = pd.read_csv(IN_FP, sep=",", engine="python")
df.columns = [str(c).strip().strip('"') for c in df.columns]

if "Segmento" not in df.columns:
    raise KeyError("Coluna Segmento nao encontrada.")

df["Segmento"] = df["Segmento"].astype(str).str.strip()
df_tot = df[df["Segmento"].str.upper() == "TOTAL"].copy()
if df_tot.empty:
    raise ValueError("Nao encontrei linha TOTAL.")

row = df_tot.iloc[-1]

def get_num(col_name: str) -> float:
    if col_name not in df.columns:
        raise KeyError(f"Coluna ausente: {col_name}")
    return float(pd.to_numeric(row[col_name], errors="coerce"))

kwh_fornecido     = get_num("kWh")
kwh_carga         = get_num("Zone kWh")
zone_losses_kwh   = get_num("Zone Losses kWh")
line_losses_kwh   = get_num("Line Losses")
trafo_losses_kwh  = get_num("Transformer Losses")
noload_losses_kwh = get_num("No Load Losses kWh")
cobre_losses_kwh  = trafo_losses_kwh - noload_losses_kwh

resumo = pd.DataFrame(
    [
        ["kWh fornecido (EnergyMeter kWh)", kwh_fornecido],
        ["kWh da carga (Zone kWh)", kwh_carga],
        ["Zone losses (Zone Losses kWh)", zone_losses_kwh],
        ["Perdas na linha MT (Line Losses kWh)", line_losses_kwh],
        ["Perdas nos trafos (Transformer Losses kWh)", trafo_losses_kwh],
        ["Perdas em vazio ferro (No Load Losses kWh)", noload_losses_kwh],
        ["Perdas em carga cobre (Transformer - NoLoad) kWh", cobre_losses_kwh],
    ],
    columns=["Descricao", "Valor"],
)

resumo.to_csv(OUT_FP, index=False, encoding="utf-8-sig")
print("OK - Resumo salvo em:", OUT_FP)

# %% Celula 006 - ENERGIA e DEMANDA MAX por mes e posto (SIM2 vs SIM31)
# =============================================================================
# Entradas:
#   META: 00_dados_de_entrada_ano_letivo_2025_15min.csv
#         (Hora_decimal, Mes, Posto)
#   SIM2:  Simulacao 002/Curva_de_Carga_GERAL_sim_2.csv
#         (Hora_decimal, P_3f_S, Q_3f_S)
#   SIM31: Simulacao 031 segmentos/Curva_de_Carga_GERAL_sim_31.csv
#         (Hora_decimal, P_3f_S, Q_3f_S)
#
# Saida:
#   Simulacao 031 segmentos/01_Integralizacao_Mensal_SIM2_x_SIM31_2025.csv
#
# OBSERVACAO:
#   - P > 0  -> consumo da rede
#   - P < 0  -> injecao na rede
#   - A integralizacao mensal separa, por posto tarifario:
#       * consumo ativo da rede
#       * injecao ativa na rede
#       * demanda maxima de importacao
#       * demanda maxima de exportacao
# =============================================================================

from pathlib import Path
import numpy as np
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
SIM2_DIR = WORK_DIR / "Simulacao 002"
SIM31_DIR = WORK_DIR / "Simulacao 031 segmentos"

META_FP = WORK_DIR / "00_dados_de_entrada_ano_letivo_2025_15min.csv"
SIM2_FP = SIM2_DIR / "Curva_de_Carga_GERAL_sim_2.csv"
SIM31_FP = SIM31_DIR / "Curva_de_Carga_GERAL_sim_31.csv"
OUT_FP  = SIM31_DIR / "01_Integralizacao_Mensal_SIM2_x_SIM31_2025.csv"

DT_H = 0.25

mes_order = [
    "JANEIRO","FEVEREIRO","MARCO","ABRIL","MAIO","JUNHO",
    "JULHO","AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO"
]

def norm_posto(x: str) -> str:
    s = str(x).strip().upper()
    s = s.replace(" ", "_").replace("-", "_")
    while "__" in s:
        s = s.replace("__", "_")
    if s in ["FORA_PONTA", "FORA_PTA", "FORAPTA", "FORAPONT", "FORA"]:
        return "FORA_PONTA"
    if s in ["PONTA", "PTA"]:
        return "PONTA"
    if "FORA" in s:
        return "FORA_PONTA"
    if "PONTA" in s:
        return "PONTA"
    return s

def make_k(h: pd.Series) -> np.ndarray:
    hh = pd.to_numeric(h, errors="coerce")
    return np.rint(hh.to_numpy(dtype=float) * 4).astype("int64")

for fp in [META_FP, SIM2_FP, SIM31_FP]:
    if not fp.exists():
        raise FileNotFoundError(fp)

meta = pd.read_csv(META_FP, dtype=str, encoding="utf-8-sig")
sim2 = pd.read_csv(SIM2_FP, encoding="utf-8-sig", sep=None, engine="python")
sim31 = pd.read_csv(SIM31_FP, encoding="utf-8-sig", sep=None, engine="python")

for name, dfx, req in [
    ("META", meta, ["Hora_decimal", "Mes", "Posto"]),
    ("SIM2", sim2, ["Hora_decimal", "P_3f_S", "Q_3f_S"]),
    ("SIM31", sim31, ["Hora_decimal", "P_3f_S", "Q_3f_S"]),
]:
    miss = [c for c in req if c not in dfx.columns]
    if miss:
        raise ValueError(f"Missing columns in {name}: {miss}. Available: {list(dfx.columns)}")

meta["Hora_decimal"] = pd.to_numeric(meta["Hora_decimal"], errors="coerce")
meta["Mes"] = meta["Mes"].astype(str).str.strip().str.upper()
meta["Posto"] = meta["Posto"].apply(norm_posto)
meta = meta.dropna(subset=["Hora_decimal", "Mes", "Posto"]).copy()

for dfx in (sim2, sim31):
    dfx["Hora_decimal"] = pd.to_numeric(dfx["Hora_decimal"], errors="coerce")
    dfx["P_3f_S"] = pd.to_numeric(dfx["P_3f_S"], errors="coerce")
    dfx["Q_3f_S"] = pd.to_numeric(dfx["Q_3f_S"], errors="coerce")
    dfx.dropna(subset=["Hora_decimal", "P_3f_S", "Q_3f_S"], inplace=True)

meta["k"] = make_k(meta["Hora_decimal"])
sim2["k"] = make_k(sim2["Hora_decimal"])
sim31["k"] = make_k(sim31["Hora_decimal"])

meta = meta[["k", "Mes", "Posto"]].drop_duplicates(subset=["k"], keep="first").copy()
sim2 = sim2[["k", "P_3f_S", "Q_3f_S"]].drop_duplicates(subset=["k"], keep="first").copy()
sim31 = sim31[["k", "P_3f_S", "Q_3f_S"]].drop_duplicates(subset=["k"], keep="first").copy()

df2 = meta.merge(sim2, on="k", how="left").rename(columns={"P_3f_S": "P_SIM2", "Q_3f_S": "Q_SIM2"})
df31 = meta.merge(sim31, on="k", how="left").rename(columns={"P_3f_S": "P_SIM31", "Q_3f_S": "Q_SIM31"})

# -----------------------------------------------------------------------------
# Separacao entre consumo da rede (P > 0) e injecao na rede (P < 0)
# -----------------------------------------------------------------------------
for dfx, tag in [(df2, "SIM2"), (df31, "SIM31")]:
    pcol = f"P_{tag}"

    # Potencias instantaneas separadas
    dfx[f"P_cons_{tag}_kW"] = dfx[pcol].clip(lower=0)
    dfx[f"P_inj_{tag}_kW"] = (-dfx[pcol]).clip(lower=0)

    # Energias ativas no intervalo
    dfx[f"E_cons_{tag}_kWh"] = dfx[f"P_cons_{tag}_kW"] * DT_H
    dfx[f"E_inj_{tag}_kWh"] = dfx[f"P_inj_{tag}_kW"] * DT_H

    # Reativo apenas mantido como diagnostico
    dfx[f"E_Q_{tag}_kVArh"] = dfx[f"Q_{tag}"] * DT_H

group_cols = ["Mes", "Posto"]

agg2 = df2.groupby(group_cols, dropna=False).agg(
    N_pontos_SIM2=("P_SIM2", lambda s: int(s.notna().sum())),
    Consumo_P_SIM2_kWh=("E_cons_SIM2_kWh", "sum"),
    Injecao_P_SIM2_kWh=("E_inj_SIM2_kWh", "sum"),
    Consumo_Q_SIM2_kVArh=("E_Q_SIM2_kVArh", "sum"),
    DemandaMax_P_SIM2_kW=("P_cons_SIM2_kW", "max"),
    DemandaMax_Inj_SIM2_kW=("P_inj_SIM2_kW", "max"),
).reset_index()

agg31 = df31.groupby(group_cols, dropna=False).agg(
    N_pontos_SIM31=("P_SIM31", lambda s: int(s.notna().sum())),
    Consumo_P_SIM31_kWh=("E_cons_SIM31_kWh", "sum"),
    Injecao_P_SIM31_kWh=("E_inj_SIM31_kWh", "sum"),
    Consumo_Q_SIM31_kVArh=("E_Q_SIM31_kVArh", "sum"),
    DemandaMax_P_SIM31_kW=("P_cons_SIM31_kW", "max"),
    DemandaMax_Inj_SIM31_kW=("P_inj_SIM31_kW", "max"),
).reset_index()

agg = agg2.merge(agg31, on=group_cols, how="outer")

meta_counts = meta.groupby(group_cols, dropna=False).agg(
    N_pontos_META=("Posto", "size")
).reset_index()

agg = agg.merge(meta_counts, on=group_cols, how="left")

# preencher NaN numericos com zero
num_cols = [c for c in agg.columns if c not in ["Mes", "Posto"]]
for c in num_cols:
    agg[c] = pd.to_numeric(agg[c], errors="coerce").fillna(0.0)

agg["Mes"] = pd.Categorical(agg["Mes"], categories=mes_order, ordered=True)
agg = agg.sort_values(["Mes", "Posto"]).reset_index(drop=True)

agg.to_csv(OUT_FP, index=False, encoding="utf-8")
print("DONE. Saved:", OUT_FP, "| Rows:", len(agg))

# %% Celula 007 - SIMULACAO 031: Tabela de custos (SIM2 vs SIM31 - 2025)
# =============================================================================
# Entrada:
#   Simulacao 031 segmentos/01_Integralizacao_Mensal_SIM2_x_SIM31_2025.csv
#
# Saidas (todas em Simulacao 031 segmentos):
#   Tabela_demanda_consumo_por_posto_SIM2_2025.csv
#   Tabela_demanda_consumo_por_posto_SIM31_2025.csv
#   Tabela_demanda_consumo_por_posto_SIM2_vs_SIM31_2025.csv
#
# HIPOTESE ADOTADA:
#   - Pior cenario de 2029+:
#         credito do excedente vale apenas TE SEM IMPOSTOS (ICMS abatido)
#         TUSD-E nao e compensada
#   - Compensacao no mesmo posto tarifario:
#         Injecao FORA_PONTA -> compensa FORA_PONTA
#         Injecao PONTA      -> compensa PONTA
#   - Credito acumulado em kWh mes a mes, separado por posto
#   - Demanda continua sendo cobrada normalmente
# =============================================================================

from pathlib import Path
import numpy as np
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
SIM31_DIR = WORK_DIR / "Simulacao 031 segmentos"
SIM31_DIR.mkdir(parents=True, exist_ok=True)

IN_FP     = SIM31_DIR / "01_Integralizacao_Mensal_SIM2_x_SIM31_2025.csv"
OUT_SIM2  = SIM31_DIR / "Tabela_demanda_consumo_por_posto_SIM2_2025.csv"
OUT_SIM31 = SIM31_DIR / "Tabela_demanda_consumo_por_posto_SIM31_2025.csv"
OUT_CMP   = SIM31_DIR / "Tabela_demanda_consumo_por_posto_SIM2_vs_SIM31_2025.csv"

# -------------------------
# DEMANDAS CONTRATADAS POR SIMULACAO
# -------------------------
CONTR_SIM2  = {"DCFP": 5000.0, "DCP": 3000.0}
CONTR_SIM31 = {"DCFP": 5000.0, "DCP": 3000.0}

# -------------------------
# TARIFAS
# -------------------------
TARIFAS = {
    "DCFP"       : 32.84,
    "DCP"        : 83.34,
    "DCFP_c"     : 27.26,
    "DCP_c"      : 69.17,
    "UFP"        : 65.68,
    "UP"         : 166.68,
    "CFP_TUSD"   : 0.15,
    "CP_TUSD"    : 0.15,
    "CFP_TE"     : 0.37,  # TE com impostos (Consumo)
    "CP_TE"      : 0.59,  # TE com impostos (Consumo)
    "CFP_TE_COMP": 0.29,  # TE sem impostos (Crédito)
    "CP_TE_COMP" : 0.46,  # TE sem impostos (Crédito)
}

# -------------------------
# MAPA DE MESES + ORDEM CRONOLOGICA
# -------------------------
MES_MAP = {
    "JANEIRO": "JAN", "FEVEREIRO": "FEV", "MARCO": "MAR", "ABRIL": "ABR",
    "MAIO": "MAI", "JUNHO": "JUN", "JULHO": "JUL", "AGOSTO": "AGO",
    "SETEMBRO": "SET", "OUTUBRO": "OUT", "NOVEMBRO": "NOV", "DEZEMBRO": "DEZ",
}
MESES_ORD = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]

if not IN_FP.exists():
    raise FileNotFoundError(IN_FP)

df = pd.read_csv(IN_FP, encoding="utf-8")
df.columns = (
    df.columns.astype(str)
    .str.replace("\ufeff", "", regex=False)
    .str.strip()
    .str.replace(r"\s+", " ", regex=True)
)

def tabela_custos(df_in: pd.DataFrame, fonte: str, DCFP: float, DCP: float) -> pd.DataFrame:
    colE = f"Consumo_P_{fonte}_kWh"
    colI = f"Injecao_P_{fonte}_kWh"
    colD = f"DemandaMax_P_{fonte}_kW"
    colDinj = f"DemandaMax_Inj_{fonte}_kW"

    req = ["Mes", "Posto", colE, colI, colD]
    miss = [c for c in req if c not in df_in.columns]
    if miss:
        raise ValueError(f"Colunas faltando para {fonte}: {miss}")

    cols_use = ["Mes", "Posto", colE, colI, colD]
    if colDinj in df_in.columns:
        cols_use.append(colDinj)

    d = df_in[cols_use].copy()
    d["Mes"] = d["Mes"].astype(str).str.strip().str.upper()
    d["Posto"] = d["Posto"].astype(str).str.strip().str.upper()

    d["MES"] = d["Mes"].map(MES_MAP)
    if d["MES"].isna().any():
        bad = d.loc[d["MES"].isna(), "Mes"].unique().tolist()
        raise ValueError(f"Meses nao mapeados: {bad}")

    fp = d[d["Posto"] == "FORA_PONTA"].set_index("MES").copy()
    p  = d[d["Posto"] == "PONTA"].set_index("MES").copy()

    presentes = set(fp.index).intersection(set(p.index))
    meses = [m for m in MESES_ORD if m in presentes]

    if len(meses) == 0:
        raise ValueError(f"Nenhum par PONTA/FORA_PONTA encontrado para {fonte}.")

    out = pd.DataFrame({
        "MES": meses,
        "DMFP (kW)": pd.to_numeric(fp.loc[meses, colD], errors="coerce").fillna(0).round(0).astype("Int64"),
        "DMP (kW)" : pd.to_numeric(p.loc[meses,  colD], errors="coerce").fillna(0).round(0).astype("Int64"),

        "CFP_rede (kWh)": pd.to_numeric(fp.loc[meses, colE], errors="coerce").fillna(0).round(0).astype("Int64"),
        "CP_rede (kWh)" : pd.to_numeric(p.loc[meses,  colE], errors="coerce").fillna(0).round(0).astype("Int64"),

        "Inj_FP (kWh)": pd.to_numeric(fp.loc[meses, colI], errors="coerce").fillna(0).round(0).astype("Int64"),
        "Inj_P (kWh)" : pd.to_numeric(p.loc[meses,  colI], errors="coerce").fillna(0).round(0).astype("Int64"),
    })

    if colDinj in d.columns:
        out["DemMax_Inj_FP (kW)"] = pd.to_numeric(fp.loc[meses, colDinj], errors="coerce").fillna(0).round(0).astype("Int64")
        out["DemMax_Inj_P (kW)"]  = pd.to_numeric(p.loc[meses,  colDinj], errors="coerce").fillna(0).round(0).astype("Int64")

    # -------------------------------------------------------------------------
    # Credito acumulado em kWh por posto tarifario
    # -------------------------------------------------------------------------
    credito_fp = 0.0
    credito_p  = 0.0

    cred_ini_fp, cred_ini_p = [], []
    comp_fp, comp_p = [], []
    fat_fp, fat_p = [], []
    exc_fp, exc_p = [], []
    cred_fim_fp, cred_fim_p = [], []

    for _, row in out.iterrows():
        cfp = float(row["CFP_rede (kWh)"])
        cp  = float(row["CP_rede (kWh)"])
        ifp = float(row["Inj_FP (kWh)"])
        ip  = float(row["Inj_P (kWh)"])

        disponivel_fp = credito_fp + ifp
        disponivel_p  = credito_p  + ip

        compensada_fp = min(cfp, disponivel_fp)
        compensada_p  = min(cp,  disponivel_p)

        faturavel_fp = cfp - compensada_fp
        faturavel_p  = cp  - compensada_p

        excedente_fp = max(0.0, disponivel_fp - cfp)
        excedente_p  = max(0.0, disponivel_p  - cp)

        novo_credito_fp = disponivel_fp - compensada_fp
        novo_credito_p  = disponivel_p  - compensada_p

        cred_ini_fp.append(round(credito_fp, 2))
        cred_ini_p.append(round(credito_p, 2))
        comp_fp.append(round(compensada_fp, 2))
        comp_p.append(round(compensada_p, 2))
        fat_fp.append(round(faturavel_fp, 2))
        fat_p.append(round(faturavel_p, 2))
        exc_fp.append(round(excedente_fp, 2))
        exc_p.append(round(excedente_p, 2))
        cred_fim_fp.append(round(novo_credito_fp, 2))
        cred_fim_p.append(round(novo_credito_p, 2))

        credito_fp = novo_credito_fp
        credito_p  = novo_credito_p

    out["Credito_ini_FP (kWh)"] = cred_ini_fp
    out["Credito_ini_P (kWh)"]  = cred_ini_p
    out["Comp_FP (kWh)"]        = comp_fp
    out["Comp_P (kWh)"]         = comp_p
    out["CFP_fat (kWh)"]        = fat_fp
    out["CP_fat (kWh)"]         = fat_p
    out["Excedente_FP (kWh)"]   = exc_fp
    out["Excedente_P (kWh)"]    = exc_p
    out["Credito_fim_FP (kWh)"] = cred_fim_fp
    out["Credito_fim_P (kWh)"]  = cred_fim_p

    # -------------------------------------------------------------------------
    # Ultrapassagens (5% tolerancia)
    # -------------------------------------------------------------------------
    out["UFP (kW)"] = (out["DMFP (kW)"].astype(float) - DCFP).clip(lower=0)
    out.loc[out["DMFP (kW)"].astype(float) <= 1.05 * DCFP, "UFP (kW)"] = 0

    out["UP (kW)"] = (out["DMP (kW)"].astype(float) - DCP).clip(lower=0)
    out.loc[out["DMP (kW)"].astype(float) <= 1.05 * DCP, "UP (kW)"] = 0

    # Complemento ate a contratada
    out["DCFP_c (kW)"] = (DCFP - out["DMFP (kW)"].astype(float)).clip(lower=0)
    out["DCP_c (kW)"]  = (DCP  - out["DMP (kW)"].astype(float)).clip(lower=0)

    # -------------------------------------------------------------------------
    # R$
    # Pior cenario 2029+:
    #   - TUSD sobre TODO o consumo da rede (injetado não compensa TUSD)
    #   - TE: Cobra-se a TE bruta (0.37/0.59) sobre TODO o consumo, 
    #         e abate-se o Crédito (0.29/0.46) gerado pela injeção compensada.
    # -------------------------------------------------------------------------
    out["DCFP (R$32,84)"]   = (out["DMFP (kW)"].astype(float) * TARIFAS["DCFP"]).round(2)
    out["DCP  (R$83,34)"]   = (out["DMP (kW)"].astype(float)  * TARIFAS["DCP"]).round(2)
    out["DCFP_c (R$27,26)"] = (out["DCFP_c (kW)"]             * TARIFAS["DCFP_c"]).round(2)
    out["DCP_c  (R$69,17)"] = (out["DCP_c (kW)"]              * TARIFAS["DCP_c"]).round(2)
    out["UFP  (R$65,68)"]   = (out["UFP (kW)"]                * TARIFAS["UFP"]).round(2)
    out["UP   (R$166,68)"]  = (out["UP (kW)"]                 * TARIFAS["UP"]).round(2)

    # TUSD incide sobre todo consumo da rede
    out["CFP_rede (R$0,15) TUSD"] = (out["CFP_rede (kWh)"].astype(float) * TARIFAS["CFP_TUSD"]).round(2)
    out["CP_rede  (R$0,15) TUSD"] = (out["CP_rede (kWh)"].astype(float)  * TARIFAS["CP_TUSD"]).round(2)

    # Custos TE Brutos (sobre todo consumo)
    custo_te_fp_bruto = out["CFP_rede (kWh)"].astype(float) * TARIFAS["CFP_TE"]
    custo_te_p_bruto  = out["CP_rede (kWh)"].astype(float)  * TARIFAS["CP_TE"]

    # Abatimentos TE (Créditos valorados SEM ICMS)
    out["Credito_FP (R$0,29) TE"] = (out["Comp_FP (kWh)"].astype(float) * TARIFAS["CFP_TE_COMP"]).round(2)
    out["Credito_P  (R$0,46) TE"] = (out["Comp_P (kWh)"].astype(float)  * TARIFAS["CP_TE_COMP"]).round(2)

    # Custo Final TE (Bruto - Créditos)
    out["CFP_fat (R$ TE Liquido)"] = (custo_te_fp_bruto - out["Credito_FP (R$0,29) TE"]).round(2)
    out["CP_fat  (R$ TE Liquido)"] = (custo_te_p_bruto  - out["Credito_P  (R$0,46) TE"]).round(2)

    cols_rs = [
        "DCFP (R$32,84)", "DCP  (R$83,34)", "DCFP_c (R$27,26)", "DCP_c  (R$69,17)",
        "UFP  (R$65,68)", "UP   (R$166,68)",
        "CFP_rede (R$0,15) TUSD", "CP_rede  (R$0,15) TUSD",
        "CFP_fat (R$ TE Liquido)", "CP_fat  (R$ TE Liquido)",
    ]
    out["R$TOTAL_MES"] = out[cols_rs].sum(axis=1).round(2)

    totais = {
        "MES": "TOTAIS",
        "DMFP (kW)": int(pd.to_numeric(out["DMFP (kW)"], errors="coerce").max()),
        "DMP (kW)" : int(pd.to_numeric(out["DMP (kW)"], errors="coerce").max()),

        "CFP_rede (kWh)": float(pd.to_numeric(out["CFP_rede (kWh)"], errors="coerce").sum()),
        "CP_rede (kWh)" : float(pd.to_numeric(out["CP_rede (kWh)"], errors="coerce").sum()),
        "Inj_FP (kWh)"  : float(pd.to_numeric(out["Inj_FP (kWh)"], errors="coerce").sum()),
        "Inj_P (kWh)"   : float(pd.to_numeric(out["Inj_P (kWh)"], errors="coerce").sum()),

        "Comp_FP (kWh)" : float(pd.to_numeric(out["Comp_FP (kWh)"], errors="coerce").sum()),
        "Comp_P (kWh)"  : float(pd.to_numeric(out["Comp_P (kWh)"], errors="coerce").sum()),
        "CFP_fat (kWh)": float(pd.to_numeric(out["CFP_fat (kWh)"], errors="coerce").sum()),
        "CP_fat (kWh)" : float(pd.to_numeric(out["CP_fat (kWh)"], errors="coerce").sum()),

        "Excedente_FP (kWh)": float(pd.to_numeric(out["Excedente_FP (kWh)"], errors="coerce").sum()),
        "Excedente_P (kWh)" : float(pd.to_numeric(out["Excedente_P (kWh)"], errors="coerce").sum()),

        "Credito_fim_FP (kWh)": float(out["Credito_fim_FP (kWh)"].iloc[-1]),
        "Credito_fim_P (kWh)" : float(out["Credito_fim_P (kWh)"].iloc[-1]),

        "R$TOTAL_MES": float(pd.to_numeric(out["R$TOTAL_MES"], errors="coerce").sum()),
    }

    return pd.concat([out, pd.DataFrame([totais])], ignore_index=True)

# Tabelas individuais
tab2 = tabela_custos(df, "SIM2", DCFP=CONTR_SIM2["DCFP"], DCP=CONTR_SIM2["DCP"])
tab31 = tabela_custos(df, "SIM31", DCFP=CONTR_SIM31["DCFP"], DCP=CONTR_SIM31["DCP"])

tab2.to_csv(OUT_SIM2, index=False, encoding="utf-8")
tab31.to_csv(OUT_SIM31, index=False, encoding="utf-8")

# -------------------------
# Comparativo (economia)
# -------------------------
t2 = tab2[tab2["MES"].isin(MESES_ORD)][["MES", "R$TOTAL_MES"]].rename(columns={"R$TOTAL_MES": "R$SIM2"})
t31 = tab31[tab31["MES"].isin(MESES_ORD)][["MES", "R$TOTAL_MES"]].rename(columns={"R$TOTAL_MES": "R$SIM31"})

cmp = t2.merge(t31, on="MES", how="inner")
cmp["MES"] = pd.Categorical(cmp["MES"], categories=MESES_ORD, ordered=True)
cmp = cmp.sort_values("MES").reset_index(drop=True)

cmp["Economia_R$"] = (cmp["R$SIM2"] - cmp["R$SIM31"]).round(2)
cmp["Economia_%"]  = np.where(
    cmp["R$SIM2"] == 0,
    np.nan,
    (cmp["Economia_R$"] / cmp["R$SIM2"] * 100).round(3)
)

tot = {
    "MES": "TOTAIS",
    "R$SIM2": float(cmp["R$SIM2"].sum()),
    "R$SIM31": float(cmp["R$SIM31"].sum()),
    "Economia_R$": float(cmp["Economia_R$"].sum()),
    "Economia_%": (
        np.nan if cmp["R$SIM2"].sum() == 0
        else float(cmp["Economia_R$"].sum() / cmp["R$SIM2"].sum() * 100)
    ),
}
cmp = pd.concat([cmp, pd.DataFrame([tot])], ignore_index=True)

cmp.to_csv(OUT_CMP, index=False, encoding="utf-8")

print("DONE. Saved (Simulacao 031 segmentos):")
print(" -", OUT_SIM2)
print(" -", OUT_SIM31)
print(" -", OUT_CMP)

print("\nDemandas contratadas usadas:")
print(" - SIM2: DCFP=5000, DCP=3000")
print(" - SIM31: DCFP=5000, DCP=3000")

print("\nResumo anual:")
print(cmp.tail(1))