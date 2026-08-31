# -*- coding: utf-8 -*-
# =============================================================================
# 023_Script_BESS_Simulacao_022_3bus_0700_2220_2380_duas_simulacoes_conjugado_4500_ano_2028_2031_2047.py
#
# Regras deste script:
#   - Sem acentos em comentarios e strings pt-br.
#   - Celulas independentes: cada celula define suas variaveis e funcoes locais.
#   - Uma celula pode depender APENAS de arquivos de entrada/saida.
#
# Pastas mantidas:
#   PASSO 1 (sem HVAC interno):
#     Simulacao 022 segmentos_pass1_sem_hvac_int_ano_2031_2047
#   PASSO 2 (simulacao completa final):
#     Simulacao 022 segmentos_ano_2031_2047
# =============================================================================

# %% Celula 001 - PASSO 1: simulacao segmentada somente com monitores dos BESS (sem EnergyMeter)
# ======================================================================================
# Saidas (PASSO 1):
#   Simulacao 022 segmentos_pass1_sem_hvac_int_ano_2031_2047/
#     UFSM_Mon_BESSM1_IN_sNNNNN_<POSTO>.csv   (1 por segmento)
#     UFSM_Mon_BESSM2_IN_sNNNNN_<POSTO>.csv   (1 por segmento)
#     UFSM_Mon_BESSM3_IN_sNNNNN_<POSTO>.csv   (1 por segmento)
#     SOC_por_segmento.csv
#
# Requisitos:
#   - Posto_tarifario_simulacao.csv (deslocado 1 step)
#   - BESS_HVAC_ENV_LoadShape_2025.csv
# ======================================================================================

import os
from pathlib import Path
import numpy as np
import pandas as pd
from py_dss_interface import DSS

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")

ARQ_POSTO = WORK_DIR / "Posto_tarifario_simulacao.csv"

DT_H = 0.25
TOTAL_NPTS = 35040

STORAGE_NAMES = ["BESSM1", "BESSM2", "BESSM3"]
STORAGE_CTRL = "C_BESSM123"
SOC_INICIAL = 50.0

TARGETS = {
    "PONTA":      {"kWtarget": 0,    "kWtargetLow": 0},
    "FORA_PONTA": {"kWtarget": 4995, "kWtargetLow": 3885},
}

# Reservas operacionais por banco:
# - FORA_PONTA: BESSM1 e BESSM2 usam somente o excedente degradado para peak-shave FP;
#               BESSM3 fica integralmente reservado para a ponta.
# - PONTA: todos ficam liberados ate a reserva minima tecnica.
BESS1_RESERVA_PONTA_PCT = 100.0 * 3000.0 / 5500.0  # 54.5454545%
BESS2_RESERVA_PONTA_PCT = 100.0 * 3000.0 / 5500.0  # 54.5454545%
BESS3_RESERVA_PONTA_PCT = 100.0
BESS_RESERVA_MIN_PONTA_PCT = 2.0

DIR_PASS1 = WORK_DIR / "Simulacao 022 segmentos_pass1_sem_hvac_int_ano_2031_2047"
DIR_PASS1.mkdir(parents=True, exist_ok=True)

# Limpa saidas antigas do PASSO 1 no inicio da Celula 001.
# Isto evita misturar arquivos de execucoes anteriores com a nova simulacao.
LIMPAR_SAIDAS_ANTERIORES_PASS1 = True
if LIMPAR_SAIDAS_ANTERIORES_PASS1:
    padroes_limpeza_pass1 = [
        "UFSM_Mon_BESSM*_IN_s*.csv",
        "Monitor_BESSM*_IN_anual.csv",
        "Curva_de_Carga_BESSM*_IN_sim_22.csv",
        "SOC_por_segmento.csv",
    ]
    removidos = 0
    for padrao in padroes_limpeza_pass1:
        for fp in DIR_PASS1.glob(padrao):
            if fp.is_file():
                fp.unlink()
                removidos += 1
    print(f"[CLEAN] PASSO 1: {removidos} arquivo(s) antigo(s) removido(s) em {DIR_PASS1}")

os.chdir(WORK_DIR)


def build_circuit_pass1(
    dss: DSS,
    soc_init_m1_pct: float,
    soc_init_m2_pct: float,
    soc_init_m3_pct: float,
    posto: str,
    seg_tag: str,
) -> dict[str, str]:
    posto = str(posto).strip().upper()
    if posto not in TARGETS:
        raise ValueError(f"Posto invalido: {posto}")

    kWtarget = TARGETS[posto]["kWtarget"]
    kWtargetLow = TARGETS[posto]["kWtargetLow"]

    if posto == "FORA_PONTA":
        reserve_m1_pct = BESS1_RESERVA_PONTA_PCT
        reserve_m2_pct = BESS2_RESERVA_PONTA_PCT
        reserve_m3_pct = BESS3_RESERVA_PONTA_PCT
    elif posto == "PONTA":
        reserve_m1_pct = BESS_RESERVA_MIN_PONTA_PCT
        reserve_m2_pct = BESS_RESERVA_MIN_PONTA_PCT
        reserve_m3_pct = BESS_RESERVA_MIN_PONTA_PCT
    else:
        raise ValueError(f"Posto invalido para reserve: {posto}")

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
    dss.text('Redirect "UFSM_cargas_medidas_ano_2047.dss"')
    dss.text('Redirect "UFSM_cargas_especiais_ano_2047.dss"')
    dss.text('Redirect "UFSM_cargas_estimadas_com_residuo_ano_2047.dss"')

    # BESSM1 em 0700
    dss.text("New line.0700_B011 phases=3 bus1=0700 bus2=B011 length=0.0150 units=km Geometry=UG_trefoil_25")
    dss.text("New line.B011_B012 phases=3 bus1=B011 bus2=B012 Switch=y enable=true")
    dss.text(
        "New transformer.BESSM1_1000 XHL=6.0 windings=2 %loadloss=1.46 %noloadloss=0.29 %imag=1.5 "
        "wdg=1 bus=B012 kv=13.8 kva=1000 conn=delta "
        "wdg=2 bus=B013 kv=0.38 kva=1000 conn=wye"
    )

    # BESSM2 em 2220
    dss.text("New line.2220_B021 phases=3 bus1=2220 bus2=B021 length=0.0150 units=km Geometry=UG_trefoil_25")
    dss.text("New line.B021_B022 phases=3 bus1=B021 bus2=B022 Switch=y enable=true")
    dss.text(
        "New transformer.BESSM2_1000 XHL=6.0 windings=2 %loadloss=1.46 %noloadloss=0.29 %imag=1.5 "
        "wdg=1 bus=B022 kv=13.8 kva=1000 conn=delta "
        "wdg=2 bus=B023 kv=0.38 kva=1000 conn=wye"
    )

    # BESSM3 em 2380
    dss.text("New line.2380_B031 phases=3 bus1=2380 bus2=B031 length=0.0150 units=km Geometry=UG_trefoil_25")
    dss.text("New line.B031_B032 phases=3 bus1=B031 bus2=B032 Switch=y enable=true")
    dss.text(
        "New transformer.BESSM3_1000 XHL=6.0 windings=2 %loadloss=1.46 %noloadloss=0.29 %imag=1.5 "
        "wdg=1 bus=B032 kv=13.8 kva=1000 conn=delta "
        "wdg=2 bus=B033 kv=0.38 kva=1000 conn=wye"
    )

    # HVAC externo (obrigatorio) para os tres bancos
    dss.text("New LoadShape.BESS_HVAC_ENV_LoadShape_2025 npts=35040 interval=0 CSVFile=BESS_HVAC_ENV_LoadShape_2025.csv")
    dss.text("New load.BESSM1_AC_ext phases=3 model=1 bus=B013 kv=0.38 kw=1000 conn=wye Yearly=BESS_HVAC_ENV_LoadShape_2025")
    dss.text("New load.BESSM2_AC_ext phases=3 model=1 bus=B023 kv=0.38 kw=1000 conn=wye Yearly=BESS_HVAC_ENV_LoadShape_2025")
    dss.text("New load.BESSM3_AC_ext phases=3 model=1 bus=B033 kv=0.38 kw=1000 conn=wye Yearly=BESS_HVAC_ENV_LoadShape_2025")

    # Curva eficiencia
    dss.text("New XYCurve.Eff npts=4 xarray=[0.1 0.2 0.4 1] yarray=[0.86 0.90 0.93 0.97]")

    dss.text(
        "New Storage.BESSM1 phases=3 bus1=B013 kv=0.38 "
        f"kWrated=673 kWhrated=4629.2 Effcurve=Eff %EffCharge=95 %EffDischarge=95 "
        f"%reserve={reserve_m1_pct} dispmode=external"
    )
    dss.text(
        "New Storage.BESSM2 phases=3 bus1=B023 kv=0.38 "
        f"kWrated=673 kWhrated=4629.2 Effcurve=Eff %EffCharge=95 %EffDischarge=95 "
        f"%reserve={reserve_m2_pct} dispmode=external"
    )
    dss.text(
        "New Storage.BESSM3 phases=3 bus1=B033 kv=0.38 "
        f"kWrated=693 kWhrated=2600.0 Effcurve=Eff %EffCharge=95 %EffDischarge=95 "
        f"%reserve={reserve_m3_pct} dispmode=external"
    )

    soc_init_m1_pct = max(0.0, min(100.0, float(soc_init_m1_pct)))
    soc_init_m2_pct = max(0.0, min(100.0, float(soc_init_m2_pct)))
    soc_init_m3_pct = max(0.0, min(100.0, float(soc_init_m3_pct)))
    dss.text(f"Storage.BESSM1.%stored={soc_init_m1_pct}")
    dss.text(f"Storage.BESSM2.%stored={soc_init_m2_pct}")
    dss.text(f"Storage.BESSM3.%stored={soc_init_m3_pct}")
    dss.text(f"Storage.BESSM1.%reserve={reserve_m1_pct}")
    dss.text(f"Storage.BESSM2.%reserve={reserve_m2_pct}")
    dss.text(f"Storage.BESSM3.%reserve={reserve_m3_pct}")

    dss.text(
        f"New StorageController.{STORAGE_CTRL} Element=line.0015_0016 terminal=1 "
        "ElementList=[BESSM1, BESSM2, BESSM3] MonPhase=AVG "
        f"ModeDischarge=PeakShave ModeCharge=PeakShaveLow "
        f"kWtarget={kWtarget} kWtargetLow={kWtargetLow}"
    )

    mon_names = {
        "BESSM1_IN": f"BESSM1_IN_{seg_tag}",
        "BESSM2_IN": f"BESSM2_IN_{seg_tag}",
        "BESSM3_IN": f"BESSM3_IN_{seg_tag}",
    }
    dss.text(f"New Monitor.{mon_names['BESSM1_IN']} element=line.B011_B012 terminal=1 mode=1 ppolar=no")
    dss.text(f"New Monitor.{mon_names['BESSM2_IN']} element=line.B021_B022 terminal=1 mode=1 ppolar=no")
    dss.text(f"New Monitor.{mon_names['BESSM3_IN']} element=line.B031_B032 terminal=1 mode=1 ppolar=no")

    dss.text("Set VoltageBases=[13.8,0.38,0.22]")
    dss.text("CalcVoltageBases")
    
    # Aumenta o limite de iterações do fluxo de potência e dos controles
    dss.text("Set Maxiterations=1000")
    dss.text("Set MaxControlIter=1000")
    
    return mon_names


def get_soc_pct(dss: DSS, storage_name: str) -> float:
    resp = dss.text(f"? Storage.{storage_name}.%stored")
    return float(str(resp).strip())


def find_exported_monitor_file(export_dir: Path, mon_name: str) -> Path:
    cands = sorted(export_dir.glob(f"*{mon_name}*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        cands2 = sorted(export_dir.glob("Mon_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if cands2:
            return cands2[0]
        raise FileNotFoundError(f"Nenhum CSV do monitor contendo '{mon_name}' em {export_dir}")
    return cands[0]


def hour_sec_from_hora_decimal(h: float, dt_h: float) -> tuple[int, int, float]:
    hq = round(round(float(h) / dt_h) * dt_h, 10)
    hour_int = int(np.floor(hq))
    sec_int = int(round((hq - hour_int) * 3600.0))
    if sec_int >= 3600:
        hour_int += 1
        sec_int -= 3600
    return hour_int, sec_int, hq


def run_one_segment_pass1(
    dss: DSS,
    export_dir: Path,
    hora_ini: float,
    n_steps: int,
    mon_names: dict[str, str],
    seg_idx: int,
    posto: str,
    soc_ini_m1: float,
    soc_ini_m2: float,
    soc_ini_m3: float,
) -> dict[str, Path]:

    hour_int, sec_int, hora_q = hour_sec_from_hora_decimal(hora_ini, DT_H)

    print(
        f"[SOLVE] seg={int(seg_idx):05d} posto={posto} "
        f"hora_ini={hora_q:.2f}h -> Hour={hour_int} Sec={sec_int} "
        f"DT={DT_H:.2f}h n_steps={int(n_steps)} | "
        f"SOC_ini_M1={float(soc_ini_m1):.3f}% | SOC_ini_M2={float(soc_ini_m2):.3f}% | "
        f"SOC_ini_M3={float(soc_ini_m3):.3f}%"
    )

    dss.text(f"Set Mode=Yearly Hour={hour_int} Sec={sec_int} StepSize={DT_H}h Number={int(n_steps)}")
    dss.text("Solve")

    dss.text(f'cd "{export_dir}"')

    out_paths = {}
    for key, mon_name in mon_names.items():
        dss.text(f"Export Monitors {mon_name}")
        fp = find_exported_monitor_file(export_dir, mon_name)
        dst = export_dir / f"UFSM_Mon_{key}_s{int(seg_idx):05d}_{posto}.csv"
        if dst.exists():
            dst.unlink()
        fp.rename(dst)
        out_paths[key] = dst

    dss.text(f'cd "{WORK_DIR}"')
    return out_paths


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
posto_df = posto_df.dropna(subset=["Hora_decimal", "Posto_horario"]).copy()

posto_df["k"] = np.rint(posto_df["Hora_decimal"].to_numpy(dtype=float) / DT_H).astype("int64")
posto_df = posto_df[(posto_df["k"] >= 0) & (posto_df["k"] < TOTAL_NPTS)].copy()
posto_df = posto_df.sort_values("k").drop_duplicates(subset=["k"], keep="first").reset_index(drop=True)
posto_df["Hora_decimal"] = posto_df["k"].astype(float) * DT_H

if len(posto_df) != TOTAL_NPTS:
    k_ok = set(posto_df["k"].astype(int).tolist())
    faltantes = [k for k in range(TOTAL_NPTS) if k not in k_ok]
    amostra_faltantes = faltantes[:20]
    raise ValueError(
        f"Posto_tarifario_simulacao.csv gerou {len(posto_df)} amostras anuais de 15 min "
        f"apos normalizacao; esperado {TOTAL_NPTS}. Primeiros k faltantes: {amostra_faltantes}"
    )

posto_df["seg_id"] = (posto_df["Posto_horario"] != posto_df["Posto_horario"].shift(1)).cumsum()
segments = (
    posto_df.groupby("seg_id", as_index=False)
    .agg(
        posto=("Posto_horario", "first"),
        hora_ini=("Hora_decimal", "first"),
        n_steps=("Hora_decimal", "size"),
    )
)

soc_atual_m1 = SOC_INICIAL
soc_atual_m2 = SOC_INICIAL
soc_atual_m3 = SOC_INICIAL
soc_log = []

for i, row in segments.iterrows():
    posto = str(row["posto"]).upper()
    hora_ini = float(row["hora_ini"])
    n_steps = int(row["n_steps"])
    seg_tag = f"S{i:05d}_{posto}"

    dss = DSS()
    mon_names = build_circuit_pass1(
        dss=dss,
        soc_init_m1_pct=soc_atual_m1,
        soc_init_m2_pct=soc_atual_m2,
        soc_init_m3_pct=soc_atual_m3,
        posto=posto,
        seg_tag=seg_tag,
    )

    soc_ini_m1 = get_soc_pct(dss, "BESSM1")
    soc_ini_m2 = get_soc_pct(dss, "BESSM2")
    soc_ini_m3 = get_soc_pct(dss, "BESSM3")

    mon_fps = run_one_segment_pass1(
        dss=dss,
        export_dir=DIR_PASS1,
        hora_ini=hora_ini,
        n_steps=n_steps,
        mon_names=mon_names,
        seg_idx=i,
        posto=posto,
        soc_ini_m1=soc_ini_m1,
        soc_ini_m2=soc_ini_m2,
        soc_ini_m3=soc_ini_m3,
    )

    soc_final_m1 = get_soc_pct(dss, "BESSM1")
    soc_final_m2 = get_soc_pct(dss, "BESSM2")
    soc_final_m3 = get_soc_pct(dss, "BESSM3")

    soc_log.append(
        {
            "segmento_idx": int(i),
            "posto": posto,
            "hora_ini": float(hora_ini),
            "n_steps": int(n_steps),
            "soc_inicial_m1_pct": float(soc_ini_m1),
            "soc_final_m1_pct": float(soc_final_m1),
            "soc_inicial_m2_pct": float(soc_ini_m2),
            "soc_final_m2_pct": float(soc_final_m2),
            "soc_inicial_m3_pct": float(soc_ini_m3),
            "soc_final_m3_pct": float(soc_final_m3),
            "monitor_bessm1_csv": str(mon_fps["BESSM1_IN"]),
            "monitor_bessm2_csv": str(mon_fps["BESSM2_IN"]),
            "monitor_bessm3_csv": str(mon_fps["BESSM3_IN"]),
        }
    )

    print(
        f"[OK] {seg_tag}: hora_ini={hora_ini:.2f}h steps={n_steps} | "
        f"M1 {soc_ini_m1:.3f}% -> {soc_final_m1:.3f}% | "
        f"M2 {soc_ini_m2:.3f}% -> {soc_final_m2:.3f}% | "
        f"M3 {soc_ini_m3:.3f}% -> {soc_final_m3:.3f}% | "
        f"{mon_fps['BESSM1_IN'].name} | {mon_fps['BESSM2_IN'].name} | {mon_fps['BESSM3_IN'].name}"
    )

    soc_atual_m1 = soc_final_m1
    soc_atual_m2 = soc_final_m2
    soc_atual_m3 = soc_final_m3

soc_log_df = pd.DataFrame(soc_log)
soc_log_fp = DIR_PASS1 / "SOC_por_segmento.csv"
soc_log_df.to_csv(soc_log_fp, index=False, encoding="utf-8-sig")
print("[DONE] PASSO 1 concluido. SOC log:", soc_log_fp)

# %% Celula 002 - PASSO 1: emenda monitores BESSM1_IN, BESSM2_IN e BESSM3_IN
# =============================================================================
# Entrada:
#   PASSO1/UFSM_Mon_BESSM1_IN_s*.csv
#   PASSO1/UFSM_Mon_BESSM2_IN_s*.csv
# Saidas:
#   PASSO1/Monitor_BESSM1_IN_anual.csv
#   PASSO1/Monitor_BESSM2_IN_anual.csv
# Remove:
#   UFSM_Mon_BESSM1_IN_s*.csv
#   UFSM_Mon_BESSM2_IN_s*.csv
# =============================================================================

from pathlib import Path
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
DIR_PASS1 = WORK_DIR / "Simulacao 022 segmentos_pass1_sem_hvac_int_ano_2031_2047"

for mon_base in ["BESSM1_IN", "BESSM2_IN", "BESSM3_IN"]:
    out_fp = DIR_PASS1 / f"Monitor_{mon_base}_anual.csv"
    files = sorted(DIR_PASS1.glob(f"UFSM_Mon_{mon_base}_s*.csv"))
    if not files:
        raise FileNotFoundError(f"Nenhum UFSM_Mon_{mon_base}_s*.csv em {DIR_PASS1}")

    dfs = [pd.read_csv(fp, encoding="utf-8-sig", sep=None, engine="python") for fp in files]
    merged = pd.concat(dfs, ignore_index=True)

    if len(merged) != 35040:
        raise ValueError(f"Emenda PASSO1 ({mon_base}) gerou {len(merged)} linhas (esperado 35040).")

    merged.to_csv(out_fp, index=False, encoding="utf-8-sig")
    print("OK - anual gerado:", out_fp, "| linhas:", len(merged))

    for fp in files:
        fp.unlink()
    print(f"[CLEAN] Segmentados removidos ({mon_base}).")

# %% Celula 003 - PASSO 1: monitores -> Curva_de_Carga_BESSM1_IN_sim_22.csv e BESSM2_IN (SHIFT DIREITA)
# =============================================================================
# Entradas:
#   PASSO1/Monitor_BESSM1_IN_anual.csv
#   PASSO1/Monitor_BESSM2_IN_anual.csv
# Saidas:
#   PASSO1/Curva_de_Carga_BESSM1_IN_sim_22.csv
#   PASSO1/Curva_de_Carga_BESSM2_IN_sim_22.csv
# Remove:
#   PASSO1/Monitor_BESSM1_IN_anual.csv
#   PASSO1/Monitor_BESSM2_IN_anual.csv
# =============================================================================

from pathlib import Path
import numpy as np
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
DIR_PASS1 = WORK_DIR / "Simulacao 022 segmentos_pass1_sem_hvac_int_ano_2031_2047"

DT_H = 0.25
TOTAL_NPTS = 35040
hora = np.round(np.arange(0.0, 8760.0, DT_H), 10)

cols_vals = ["P1 (kW)", "Q1 (kvar)", "P2 (kW)", "Q2 (kvar)", "P3 (kW)", "Q3 (kvar)"]

for mon_base in ["BESSM1_IN", "BESSM2_IN", "BESSM3_IN"]:
    in_fp = DIR_PASS1 / f"Monitor_{mon_base}_anual.csv"
    out_fp = DIR_PASS1 / f"Curva_de_Carga_{mon_base}_sim_22.csv"

    if not in_fp.exists():
        raise FileNotFoundError(in_fp)

    mon = pd.read_csv(in_fp, encoding="utf-8-sig", sep=None, engine="python")
    mon.columns = mon.columns.astype(str).str.replace("\ufeff", "", regex=False).str.strip()

    missing = [c for c in cols_vals if c not in mon.columns]
    if missing:
        raise ValueError(f"[{mon_base}] Colunas faltando: {missing}\nDetectadas: {list(mon.columns)}")

    for c in cols_vals:
        mon[c] = pd.to_numeric(mon[c], errors="coerce")
    if mon[cols_vals].isna().any().any():
        raise ValueError(f"[{mon_base}] NaN encontrado nas colunas eletricas.")

    if len(mon) != TOTAL_NPTS:
        raise ValueError(f"[{mon_base}] Monitor anual com tamanho inesperado: {len(mon)} (esperado {TOTAL_NPTS}).")

    vals = mon[cols_vals].to_numpy(copy=True)
    vals = np.vstack([vals[0:1, :], vals[0:-1, :]])

    df_out = pd.DataFrame(vals, columns=cols_vals)
    df_out.insert(0, "Hora_decimal", hora)
    df_out["P_3f_S"] = df_out["P1 (kW)"] + df_out["P2 (kW)"] + df_out["P3 (kW)"]
    df_out["Q_3f_S"] = df_out["Q1 (kvar)"] + df_out["Q2 (kvar)"] + df_out["Q3 (kvar)"]

    df_out[["Hora_decimal", "P_3f_S", "Q_3f_S"]].to_csv(out_fp, index=False, encoding="utf-8-sig")
    in_fp.unlink()

    print(f"[OK] Curva trifasica salva em: {out_fp}")
    print(f"[CLEAN] Monitor anual removido: {in_fp.name}")
    print("[INFO] SHIFT DIREITA aplicado (duplica 1a linha, remove ultima).")

# %% Celula 004 - PASSO 1: gera LoadShapes do HVAC interno para BESSM1, BESSM2 e BESSM3
# =============================================================================
# Entradas:
#   PASSO1/Curva_de_Carga_BESSM1_IN_sim_22.csv
#   PASSO1/Curva_de_Carga_BESSM2_IN_sim_22.csv
# Saidas (WORK_DIR):
#   BESSM1_HVAC_INT_PkW_2025.csv
#   BESSM1_HVAC_INT_LoadShape_2025.csv
#   BESSM1_HVAC_INT_AUD_2025.csv
#   BESSM2_HVAC_INT_PkW_2025.csv
#   BESSM2_HVAC_INT_LoadShape_2025.csv
#   BESSM2_HVAC_INT_AUD_2025.csv
# =============================================================================

from pathlib import Path
import numpy as np
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
DIR_PASS1 = WORK_DIR / "Simulacao 022 segmentos_pass1_sem_hvac_int_ano_2031_2047"

TOTAL_NPTS = 35040
DT_H = 0.25

HEAT_FRAC = 0.05
COP_INT = 3.0
P_BASE_KW = 1000.0

for mon_base, prefix in [("BESSM1_IN", "BESSM1"), ("BESSM2_IN", "BESSM2"), ("BESSM3_IN", "BESSM3")]:
    in_fp = DIR_PASS1 / f"Curva_de_Carga_{mon_base}_sim_22.csv"

    arq_out_pkw = WORK_DIR / f"{prefix}_HVAC_INT_PkW_2025.csv"
    arq_out_pu = WORK_DIR / f"{prefix}_HVAC_INT_LoadShape_2025.csv"
    arq_aud = WORK_DIR / f"{prefix}_HVAC_INT_AUD_2025.csv"

    if not in_fp.exists():
        raise FileNotFoundError(in_fp)

    df = pd.read_csv(in_fp, encoding="utf-8-sig", sep=None, engine="python")
    df.columns = df.columns.astype(str).str.replace("\ufeff", "", regex=False).str.strip()

    for c in ["Hora_decimal", "P_3f_S"]:
        if c not in df.columns:
            raise ValueError(f"[{prefix}] Coluna {c!r} ausente em {in_fp}. Colunas: {list(df.columns)}")

    hora_decimal = pd.to_numeric(df["Hora_decimal"], errors="coerce").to_numpy(dtype=float)
    p_bess_kw = pd.to_numeric(df["P_3f_S"], errors="coerce").fillna(0.0).to_numpy(dtype=float)

    if len(p_bess_kw) != TOTAL_NPTS or len(hora_decimal) != TOTAL_NPTS:
        raise ValueError(f"[{prefix}] Tamanho inesperado: hora={len(hora_decimal)}, P={len(p_bess_kw)} (esperado {TOTAL_NPTS}).")

    p_heat_kw = HEAT_FRAC * np.abs(p_bess_kw)
    p_int_kw = p_heat_kw / float(max(1e-9, COP_INT))
    pu_int = p_int_kw / float(max(1e-9, P_BASE_KW))

    pd.DataFrame({"hora_decimal": hora_decimal, "P_int_kW": p_int_kw}).to_csv(
        arq_out_pkw, index=False, encoding="utf-8-sig", float_format="%.6f"
    )
    pd.DataFrame({0: hora_decimal, 1: pu_int}).to_csv(
        arq_out_pu, index=False, header=False, float_format="%.6f"
    )

    aud = pd.DataFrame(
        {
            "hora_decimal": hora_decimal,
            "P_bess_kW": p_bess_kw,
            "HEAT_FRAC": float(HEAT_FRAC),
            "COP_INT": float(COP_INT),
            "P_heat_kW": p_heat_kw,
            "P_int_kW": p_int_kw,
            "P_BASE_KW": float(P_BASE_KW),
            "pu_int": pu_int,
        }
    )
    aud.to_csv(arq_aud, index=False, encoding="utf-8-sig", float_format="%.6f")

    energia_kwh = float(np.sum(p_int_kw) * DT_H)
    print(f"Celula 004 - HVAC interno {prefix}")
    print("Saidas:")
    print(" -", arq_out_pkw)
    print(" -", arq_out_pu)
    print(" -", arq_aud)
    print(f"Energia anual (kWh): {energia_kwh:.3f}")

# %% Celula 005 - PASSO 2: simulacao completa (todos os monitores + EnergyMeter) por segmentos
# ======================================================================================
# Saidas (PASSO 2):
#   Simulacao 022 segmentos_ano_2031_2047/
#     UFSM_Mon_<KEY>_sNNNNN_<POSTO>.csv     (1 por monitor por segmento)
#     EXP_MTR_GERAL_<SEG_TAG>.csv           (1 por segmento)
#     SOC_por_segmento.csv                   (SOC inicial/final por segmento)
#     SOC_15min_BESS_SIM22_2047.csv          (SOC dos tres bancos a cada 15 min)
#
# Requisitos:
#   - Posto_tarifario_simulacao.csv
#   - BESS_HVAC_ENV_LoadShape_2025.csv
#   - BESSM1_HVAC_INT_LoadShape_2025.csv
#   - BESSM2_HVAC_INT_LoadShape_2025.csv
# ======================================================================================

import os
from pathlib import Path
import numpy as np
import pandas as pd
from py_dss_interface import DSS

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
os.chdir(WORK_DIR)

ARQ_POSTO = WORK_DIR / "Posto_tarifario_simulacao.csv"

DT_H = 0.25
TOTAL_NPTS = 35040

STORAGE_NAMES = ["BESSM1", "BESSM2", "BESSM3"]
STORAGE_CTRL = "C_BESSM123"
SOC_INICIAL = 50.0

# Energias nominais efetivas no ano de analise usadas para converter SOC (%) em kWh.
BESS1_E_2047_KWH = 4629.2
BESS2_E_2047_KWH = 4629.2
BESS3_E_2047_KWH = 2600.0
BESS_TOTAL_E_2047_KWH = BESS1_E_2047_KWH + BESS2_E_2047_KWH + BESS3_E_2047_KWH

TARGETS = {
    "PONTA":      {"kWtarget": 0,    "kWtargetLow": 0},
    "FORA_PONTA": {"kWtarget": 4995, "kWtargetLow": 3885},
}

# Reservas operacionais por banco:
# - FORA_PONTA: BESSM1 e BESSM2 usam somente o excedente degradado para peak-shave FP;
#               BESSM3 fica integralmente reservado para a ponta.
# - PONTA: todos ficam liberados ate a reserva minima tecnica.
BESS1_RESERVA_PONTA_PCT = 100.0 * 3000.0 / 5500.0  # 54.5454545%
BESS2_RESERVA_PONTA_PCT = 100.0 * 3000.0 / 5500.0  # 54.5454545%
BESS3_RESERVA_PONTA_PCT = 100.0
BESS_RESERVA_MIN_PONTA_PCT = 2.0

MON_SPECS = {
    "GERAL":        {"element": "line.0015_0016", "terminal": 1},
    "BESSM1_IN":    {"element": "line.B011_B012", "terminal": 1},
    "BESSM2_IN":    {"element": "line.B021_B022", "terminal": 1},
    "BESSM3_IN":    {"element": "line.B031_B032", "terminal": 1},
    "LADO1":        {"element": "line.0016_0017", "terminal": 1},
    "LADO2":        {"element": "line.0016_0018", "terminal": 1},
    "0700_ANTES":   {"element": "line.0690_0700", "terminal": 1},
    "0700_DEPOIS":  {"element": "line.0700_0710", "terminal": 1},
    "1250_ANTES":   {"element": "line.1120_1250", "terminal": 1},
    "1250_DEPOIS":  {"element": "line.1250_1260", "terminal": 1},
    "1630_ANTES":   {"element": "line.1620_1630", "terminal": 1},
    "1630_DEPOIS":  {"element": "line.1630_1640", "terminal": 1},
    "1950_ANTES":   {"element": "line.1940_1950", "terminal": 1},
    "1950_DEPOIS":  {"element": "line.1950_1960", "terminal": 1},
    "2220_ANTES":   {"element": "line.2070_2220", "terminal": 1},
    "2220_DEPOIS":  {"element": "line.2220_2230", "terminal": 1},
    "2380_ANTES":   {"element": "line.2370_2380", "terminal": 1},
    "2380_DEPOIS":  {"element": "line.2380_2390", "terminal": 1},
}
MON_KEYS = list(MON_SPECS.keys())

DIR_PASS2 = WORK_DIR / "Simulacao 022 segmentos_ano_2031_2047"
DIR_PASS2.mkdir(parents=True, exist_ok=True)

# Limpa saidas antigas do PASSO 2 no inicio da Celula 005.
# Isto evita reaproveitar CSVs antigos de uma tentativa anterior, especialmente
# arquivos UFSM_Mon_*_s*.csv com apenas 1 linha por segmento.
LIMPAR_SAIDAS_ANTERIORES_PASS2 = True
if LIMPAR_SAIDAS_ANTERIORES_PASS2:
    padroes_limpeza = [
        "UFSM_Mon_*_s*.csv",
        "Monitor_*_anual.csv",
        "Curva_de_Carga_*_sim_22.csv",
        "EXP_MTR_GERAL*.csv",
        "Resumo_EnergyMeter_Geral_Sim22.csv",
        "SOC_por_segmento.csv",
        "SOC_15min_BESS_SIM22_2047.csv",
        "01_Integralizacao_Mensal_SIM22_2047.csv",
        "Tabela_demanda_consumo_por_posto_SIM22_2047.csv",
    ]
    removidos = 0
    for padrao in padroes_limpeza:
        for fp in DIR_PASS2.glob(padrao):
            if fp.is_file():
                fp.unlink()
                removidos += 1
    print(f"[CLEAN] PASSO 2: {removidos} arquivo(s) antigo(s) removido(s) em {DIR_PASS2}")


def hour_sec_from_hora_decimal(h: float, dt_h: float) -> tuple[int, int, float]:
    hq = round(round(float(h) / dt_h) * dt_h, 10)
    hour_int = int(np.floor(hq))
    sec_int = int(round((hq - hour_int) * 3600.0))
    if sec_int >= 3600:
        hour_int += 1
        sec_int -= 3600
    return hour_int, sec_int, hq


def _build_circuit_pass2(
    dss: DSS,
    soc_init_m1_pct: float,
    soc_init_m2_pct: float,
    soc_init_m3_pct: float,
    posto: str,
    seg_tag: str,
) -> dict[str, str]:
    posto = str(posto).strip().upper()
    if posto not in TARGETS:
        raise ValueError(f"Posto invalido: {posto}")

    kWtarget = TARGETS[posto]["kWtarget"]
    kWtargetLow = TARGETS[posto]["kWtargetLow"]
    
    if posto == "FORA_PONTA":
        reserve_m1_pct = BESS1_RESERVA_PONTA_PCT
        reserve_m2_pct = BESS2_RESERVA_PONTA_PCT
        reserve_m3_pct = BESS3_RESERVA_PONTA_PCT
    elif posto == "PONTA":
        reserve_m1_pct = BESS_RESERVA_MIN_PONTA_PCT
        reserve_m2_pct = BESS_RESERVA_MIN_PONTA_PCT
        reserve_m3_pct = BESS_RESERVA_MIN_PONTA_PCT
    else:
        raise ValueError(f"Posto invalido para reserve: {posto}")

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
    dss.text('Redirect "UFSM_cargas_medidas_ano_2047.dss"')
    dss.text('Redirect "UFSM_cargas_especiais_ano_2047.dss"')
    dss.text('Redirect "UFSM_cargas_estimadas_com_residuo_ano_2047.dss"')

    # BESSM1 em 0700
    dss.text("New line.0700_B011 phases=3 bus1=0700 bus2=B011 length=0.0150 units=km Geometry=UG_trefoil_25")
    dss.text("New line.B011_B012 phases=3 bus1=B011 bus2=B012 Switch=y enable=true")
    dss.text(
        "New transformer.BESSM1_1000 XHL=6.0 windings=2 %loadloss=1.46 %noloadloss=0.29 %imag=1.5 "
        "wdg=1 bus=B012 kv=13.8 kva=1000 conn=delta "
        "wdg=2 bus=B013 kv=0.38 kva=1000 conn=wye"
    )

    # BESSM2 em 2220
    dss.text("New line.2220_B021 phases=3 bus1=2220 bus2=B021 length=0.0150 units=km Geometry=UG_trefoil_25")
    dss.text("New line.B021_B022 phases=3 bus1=B021 bus2=B022 Switch=y enable=true")
    dss.text(
        "New transformer.BESSM2_1000 XHL=6.0 windings=2 %loadloss=1.46 %noloadloss=0.29 %imag=1.5 "
        "wdg=1 bus=B022 kv=13.8 kva=1000 conn=delta "
        "wdg=2 bus=B023 kv=0.38 kva=1000 conn=wye"
    )

    # BESSM3 em 2380
    dss.text("New line.2380_B031 phases=3 bus1=2380 bus2=B031 length=0.0150 units=km Geometry=UG_trefoil_25")
    dss.text("New line.B031_B032 phases=3 bus1=B031 bus2=B032 Switch=y enable=true")
    dss.text(
        "New transformer.BESSM3_1000 XHL=6.0 windings=2 %loadloss=1.46 %noloadloss=0.29 %imag=1.5 "
        "wdg=1 bus=B032 kv=13.8 kva=1000 conn=delta "
        "wdg=2 bus=B033 kv=0.38 kva=1000 conn=wye"
    )

    # HVAC externo + interno
    dss.text("New LoadShape.BESS_HVAC_ENV_LoadShape_2025 npts=35040 interval=0 CSVFile=BESS_HVAC_ENV_LoadShape_2025.csv")
    dss.text("New load.BESSM1_AC_ext phases=3 model=1 bus=B013 kv=0.38 kw=1000 conn=wye Yearly=BESS_HVAC_ENV_LoadShape_2025")
    dss.text("New load.BESSM2_AC_ext phases=3 model=1 bus=B023 kv=0.38 kw=1000 conn=wye Yearly=BESS_HVAC_ENV_LoadShape_2025")

    dss.text("New LoadShape.BESSM1_HVAC_INT_LoadShape_2025 npts=35040 interval=0 CSVFile=BESSM1_HVAC_INT_LoadShape_2025.csv")
    dss.text("New load.BESSM1_AC_int phases=3 model=1 bus=B013 kv=0.38 kw=1000 conn=wye Yearly=BESSM1_HVAC_INT_LoadShape_2025")

    dss.text("New LoadShape.BESSM2_HVAC_INT_LoadShape_2025 npts=35040 interval=0 CSVFile=BESSM2_HVAC_INT_LoadShape_2025.csv")
    dss.text("New load.BESSM2_AC_int phases=3 model=1 bus=B023 kv=0.38 kw=1000 conn=wye Yearly=BESSM2_HVAC_INT_LoadShape_2025")

    dss.text("New LoadShape.BESSM3_HVAC_INT_LoadShape_2025 npts=35040 interval=0 CSVFile=BESSM3_HVAC_INT_LoadShape_2025.csv")
    dss.text("New load.BESSM3_AC_int phases=3 model=1 bus=B033 kv=0.38 kw=1000 conn=wye Yearly=BESSM3_HVAC_INT_LoadShape_2025")

    dss.text("New XYCurve.Eff npts=4 xarray=[0.1 0.2 0.4 1] yarray=[0.86 0.90 0.93 0.97]")

    dss.text(
        "New Storage.BESSM1 phases=3 bus1=B013 kv=0.38 "
        f"kWrated=673 kWhrated=4629.2 Effcurve=Eff %EffCharge=95 %EffDischarge=95 "
        f"%reserve={reserve_m1_pct} dispmode=external"
    )
    dss.text(
        "New Storage.BESSM2 phases=3 bus1=B023 kv=0.38 "
        f"kWrated=673 kWhrated=4629.2 Effcurve=Eff %EffCharge=95 %EffDischarge=95 "
        f"%reserve={reserve_m2_pct} dispmode=external"
    )
    dss.text(
        "New Storage.BESSM3 phases=3 bus1=B033 kv=0.38 "
        f"kWrated=693 kWhrated=2600.0 Effcurve=Eff %EffCharge=95 %EffDischarge=95 "
        f"%reserve={reserve_m3_pct} dispmode=external"
    )

    soc_init_m1_pct = max(0.0, min(100.0, float(soc_init_m1_pct)))
    soc_init_m2_pct = max(0.0, min(100.0, float(soc_init_m2_pct)))
    soc_init_m3_pct = max(0.0, min(100.0, float(soc_init_m3_pct)))
    dss.text(f"Storage.BESSM1.%stored={soc_init_m1_pct}")
    dss.text(f"Storage.BESSM2.%stored={soc_init_m2_pct}")
    dss.text(f"Storage.BESSM3.%stored={soc_init_m3_pct}")
    dss.text(f"Storage.BESSM1.%reserve={reserve_m1_pct}")
    dss.text(f"Storage.BESSM2.%reserve={reserve_m2_pct}")
    dss.text(f"Storage.BESSM3.%reserve={reserve_m3_pct}")

    dss.text(
        f"New StorageController.{STORAGE_CTRL} Element=line.0015_0016 terminal=1 "
        "ElementList=[BESSM1, BESSM2, BESSM3] MonPhase=AVG "
        f"ModeDischarge=PeakShave ModeCharge=PeakShaveLow "
        f"kWtarget={kWtarget} kWtargetLow={kWtargetLow}"
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
    
    # Aumenta o limite de iterações do fluxo de potência e dos controles
    dss.text("Set Maxiterations=1000")
    dss.text("Set MaxControlIter=1000")
    
    return mon_names


def _get_soc_pct(dss: DSS, storage_name: str) -> float:
    resp = dss.text(f"? Storage.{storage_name}.%stored")
    return float(str(resp).strip())


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


def _count_csv_data_rows(fp: Path) -> int:
    """Conta linhas de dados de um CSV com cabecalho."""
    with open(fp, "r", encoding="utf-8-sig", errors="ignore") as f:
        n_linhas = sum(1 for _ in f)
    return max(0, n_linhas - 1)


def _run_segment_pass2(
    dss: DSS,
    hora_ini: float,
    n_steps: int,
    mon_names: dict[str, str],
    seg_tag: str,
    seg_idx: int,
    posto: str,
    soc_ini_m1: float,
    soc_ini_m2: float,
    soc_ini_m3: float,
) -> tuple[dict[str, Path], Path, pd.DataFrame]:

    hour_int, sec_int, hora_q = hour_sec_from_hora_decimal(hora_ini, DT_H)

    print(
        f"[SOLVE] seg={int(seg_idx):05d} posto={posto} "
        f"hora_ini={hora_q:.2f}h -> Hour={hour_int} Sec={sec_int} "
        f"DT={DT_H:.2f}h n_steps={int(n_steps)} | "
        f"SOC_ini_M1={float(soc_ini_m1):.3f}% | SOC_ini_M2={float(soc_ini_m2):.3f}% | "
        f"SOC_ini_M3={float(soc_ini_m3):.3f}%"
    )

    # Passada principal do segmento.
    # Importante: os monitores do OpenDSS precisam ser preenchidos em uma unica
    # simulacao com Number=n_steps. Quando a simulacao e feita por varios
    # comandos "Set Mode=Yearly ... Number=1", o buffer dos monitores pode ser
    # reinicializado e o arquivo exportado fica com apenas 1 linha por segmento.
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

        n_linhas_monitor = _count_csv_data_rows(dst)
        if n_linhas_monitor != int(n_steps):
            raise ValueError(
                f"[{key}] Monitor segmentado {dst.name} ficou com {n_linhas_monitor} linha(s), "
                f"mas o segmento tem n_steps={int(n_steps)}. "
                "Isto indica que o buffer do monitor do OpenDSS nao acumulou o segmento. "
                "Apague a pasta de saida e rode novamente a Celula 005 com esta versao corrigida."
            )

        mon_paths[key] = dst

    exp_mtr = DIR_PASS2 / "EXP_MTR_GERAL.csv"
    if exp_mtr.exists():
        exp_mtr.unlink()

    dss.text("Export Meter /m")
    mtr_fp = _export_meter_and_rename(DIR_PASS2, seg_tag)

    # Passada separada apenas para registrar o SOC em 15 min.
    # Esta segunda passada preserva os monitores corretos da passada principal.
    # O estado final usado no encadeamento dos segmentos vem desta passada SOC,
    # que parte do mesmo SOC inicial e percorre exatamente o mesmo segmento.
    print(f"[SOC] seg={int(seg_idx):05d} registrando SOC 15 min em passada separada.")
    dss_soc = DSS()
    _build_circuit_pass2(
        dss=dss_soc,
        soc_init_m1_pct=soc_ini_m1,
        soc_init_m2_pct=soc_ini_m2,
        soc_init_m3_pct=soc_ini_m3,
        posto=posto,
        seg_tag=f"{seg_tag}_SOC",
    )

    soc_rows = []
    for step_idx in range(int(n_steps)):
        hora_inicio = round(hora_q + step_idx * DT_H, 10)
        hora_fim = round(hora_inicio + DT_H, 10)
        hour_step, sec_step, hora_step_q = hour_sec_from_hora_decimal(hora_inicio, DT_H)

        dss_soc.text(f"Set Mode=Yearly Hour={hour_step} Sec={sec_step} StepSize={DT_H}h Number=1")
        dss_soc.text("Solve")

        soc_m1_pct = _get_soc_pct(dss_soc, "BESSM1")
        soc_m2_pct = _get_soc_pct(dss_soc, "BESSM2")
        soc_m3_pct = _get_soc_pct(dss_soc, "BESSM3")

        soc_m1_kwh = soc_m1_pct / 100.0 * BESS1_E_2047_KWH
        soc_m2_kwh = soc_m2_pct / 100.0 * BESS2_E_2047_KWH
        soc_m3_kwh = soc_m3_pct / 100.0 * BESS3_E_2047_KWH
        soc_total_kwh = soc_m1_kwh + soc_m2_kwh + soc_m3_kwh
        soc_total_pct_pond = 100.0 * soc_total_kwh / BESS_TOTAL_E_2047_KWH

        if posto == "FORA_PONTA":
            reserve_m1_pct_log = BESS1_RESERVA_PONTA_PCT
            reserve_m2_pct_log = BESS2_RESERVA_PONTA_PCT
            reserve_m3_pct_log = BESS3_RESERVA_PONTA_PCT
        elif posto == "PONTA":
            reserve_m1_pct_log = BESS_RESERVA_MIN_PONTA_PCT
            reserve_m2_pct_log = BESS_RESERVA_MIN_PONTA_PCT
            reserve_m3_pct_log = BESS_RESERVA_MIN_PONTA_PCT
        else:
            raise ValueError(f"Posto invalido para reserve: {posto}")

        soc_rows.append(
            {
                "k": int(round(hora_step_q / DT_H)),
                "segmento_idx": int(seg_idx),
                "posto": posto,
                "step_segmento": int(step_idx),
                "Hora_decimal": float(hora_step_q),
                "Hora_decimal_fim": float(hora_fim),
                "reserve_BESSM1_pct": float(reserve_m1_pct_log),
                "reserve_BESSM2_pct": float(reserve_m2_pct_log),
                "reserve_BESSM3_pct": float(reserve_m3_pct_log),
                "SOC_BESSM1_pct": float(soc_m1_pct),
                "SOC_BESSM2_pct": float(soc_m2_pct),
                "SOC_BESSM3_pct": float(soc_m3_pct),
                "SOC_BESSM1_kWh": float(soc_m1_kwh),
                "SOC_BESSM2_kWh": float(soc_m2_kwh),
                "SOC_BESSM3_kWh": float(soc_m3_kwh),
                "SOC_total_kWh": float(soc_total_kwh),
                "SOC_total_pct_ponderado": float(soc_total_pct_pond),
            }
        )

    dss_soc.text(f'cd "{WORK_DIR}"')
    dss.text(f'cd "{WORK_DIR}"')
    return mon_paths, mtr_fp, pd.DataFrame(soc_rows)


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
posto_df = posto_df.dropna(subset=["Hora_decimal", "Posto_horario"]).copy()

posto_df["k"] = np.rint(posto_df["Hora_decimal"].to_numpy(dtype=float) / DT_H).astype("int64")
posto_df = posto_df[(posto_df["k"] >= 0) & (posto_df["k"] < TOTAL_NPTS)].copy()
posto_df = posto_df.sort_values("k").drop_duplicates(subset=["k"], keep="first").reset_index(drop=True)
posto_df["Hora_decimal"] = posto_df["k"].astype(float) * DT_H

if len(posto_df) != TOTAL_NPTS:
    k_ok = set(posto_df["k"].astype(int).tolist())
    faltantes = [k for k in range(TOTAL_NPTS) if k not in k_ok]
    amostra_faltantes = faltantes[:20]
    raise ValueError(
        f"Posto_tarifario_simulacao.csv gerou {len(posto_df)} amostras anuais de 15 min "
        f"apos normalizacao; esperado {TOTAL_NPTS}. Primeiros k faltantes: {amostra_faltantes}"
    )

posto_df["seg_id"] = (posto_df["Posto_horario"] != posto_df["Posto_horario"].shift(1)).cumsum()
segments = (
    posto_df.groupby("seg_id", as_index=False)
    .agg(
        posto=("Posto_horario", "first"),
        hora_ini=("Hora_decimal", "first"),
        n_steps=("Hora_decimal", "size"),
    )
)

soc_atual_m1 = SOC_INICIAL
soc_atual_m2 = SOC_INICIAL
soc_atual_m3 = SOC_INICIAL
soc_log = []
soc_15min_log = []

for i, row in segments.iterrows():
    posto = str(row["posto"]).upper()
    hora_ini = float(row["hora_ini"])
    n_steps = int(row["n_steps"])

    seg_tag = f"S{i:05d}_{posto}"

    dss = DSS()
    mon_names = _build_circuit_pass2(
        dss=dss,
        soc_init_m1_pct=soc_atual_m1,
        soc_init_m2_pct=soc_atual_m2,
        soc_init_m3_pct=soc_atual_m3,
        posto=posto,
        seg_tag=seg_tag,
    )

    soc_ini_m1 = _get_soc_pct(dss, "BESSM1")
    soc_ini_m2 = _get_soc_pct(dss, "BESSM2")
    soc_ini_m3 = _get_soc_pct(dss, "BESSM3")

    mon_paths, mtr_fp, soc_15min_seg = _run_segment_pass2(
        dss=dss,
        hora_ini=hora_ini,
        n_steps=n_steps,
        mon_names=mon_names,
        seg_tag=seg_tag,
        seg_idx=i,
        posto=posto,
        soc_ini_m1=soc_ini_m1,
        soc_ini_m2=soc_ini_m2,
        soc_ini_m3=soc_ini_m3,
    )

    if soc_15min_seg.empty:
        soc_final_m1 = _get_soc_pct(dss, "BESSM1")
        soc_final_m2 = _get_soc_pct(dss, "BESSM2")
        soc_final_m3 = _get_soc_pct(dss, "BESSM3")
    else:
        soc_final_m1 = float(soc_15min_seg["SOC_BESSM1_pct"].iloc[-1])
        soc_final_m2 = float(soc_15min_seg["SOC_BESSM2_pct"].iloc[-1])
        soc_final_m3 = float(soc_15min_seg["SOC_BESSM3_pct"].iloc[-1])
        soc_15min_log.append(soc_15min_seg)

    soc_log.append(
        {
            "segmento_idx": int(i),
            "posto": posto,
            "hora_ini": float(hora_ini),
            "n_steps": int(n_steps),
            "soc_inicial_m1_pct": float(soc_ini_m1),
            "soc_final_m1_pct": float(soc_final_m1),
            "soc_inicial_m2_pct": float(soc_ini_m2),
            "soc_final_m2_pct": float(soc_final_m2),
            "soc_inicial_m3_pct": float(soc_ini_m3),
            "soc_final_m3_pct": float(soc_final_m3),
            "meter_csv": str(mtr_fp),
            "monitor_csvs": {k: str(v) for k, v in mon_paths.items()},
        }
    )

    print(
        f"[OK] {seg_tag}: hora_ini={hora_ini:.2f}h steps={n_steps} | "
        f"M1 {soc_ini_m1:.3f}% -> {soc_final_m1:.3f}% | "
        f"M2 {soc_ini_m2:.3f}% -> {soc_final_m2:.3f}% | "
        f"M3 {soc_ini_m3:.3f}% -> {soc_final_m3:.3f}% | meter={mtr_fp.name}"
    )

    soc_atual_m1 = soc_final_m1
    soc_atual_m2 = soc_final_m2
    soc_atual_m3 = soc_final_m3

soc_log_df = pd.DataFrame(soc_log)
soc_log_fp = DIR_PASS2 / "SOC_por_segmento.csv"
soc_log_df.to_csv(soc_log_fp, index=False, encoding="utf-8-sig")

if soc_15min_log:
    soc_15min_df = pd.concat(soc_15min_log, ignore_index=True)
else:
    soc_15min_df = pd.DataFrame(
        columns=[
            "segmento_idx",
            "posto",
            "step_segmento",
            "Hora_decimal",
            "Hora_decimal_fim",
            "SOC_BESSM1_pct",
            "SOC_BESSM2_pct",
            "SOC_BESSM3_pct",
            "SOC_BESSM1_kWh",
            "SOC_BESSM2_kWh",
            "SOC_BESSM3_kWh",
            "SOC_total_kWh",
            "SOC_total_pct_ponderado",
        ]
    )

if len(soc_15min_df) != TOTAL_NPTS:
    raise ValueError(f"SOC 15 min gerou {len(soc_15min_df)} linhas (esperado {TOTAL_NPTS}).")
if "k" not in soc_15min_df.columns:
    raise ValueError("Coluna k ausente no log SOC 15 min.")
if soc_15min_df["k"].duplicated().any():
    dup = soc_15min_df.loc[soc_15min_df["k"].duplicated(), "k"].head(20).tolist()
    raise ValueError(f"SOC 15 min possui k duplicado. Primeiros duplicados: {dup}")
if sorted(soc_15min_df["k"].astype(int).tolist()) != list(range(TOTAL_NPTS)):
    raise ValueError("SOC 15 min nao cobre exatamente k=0...35039.")

soc_15min_fp = DIR_PASS2 / "SOC_15min_BESS_SIM22_2047.csv"
soc_15min_df.to_csv(soc_15min_fp, index=False, encoding="utf-8-sig", float_format="%.6f")

print(f"[DONE] PASSO 2 concluido. Log por segmento salvo em: {soc_log_fp}")
print(f"[DONE] Curva de SOC 15 min salva em: {soc_15min_fp}")

# %% Celula 006 - PASSO 2: emenda monitores (todos)
# =============================================================================
# Entrada:
#   Simulacao 022 segmentos_ano_2031_2047/UFSM_Mon_<KEY>_s*.csv
# Saida:
#   Simulacao 022 segmentos_ano_2031_2047/Monitor_<KEY>_anual.csv
# Remove:
#   UFSM_Mon_<KEY>_s*.csv
# =============================================================================

from pathlib import Path
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
DIR_PASS2 = WORK_DIR / "Simulacao 022 segmentos_ano_2031_2047"

def infer_mon_keys(dir_seg: Path) -> list[str]:
    files = sorted(dir_seg.glob("UFSM_Mon_*_s*.csv"))
    if not files:
        raise FileNotFoundError(f"Nao encontrei UFSM_Mon_*_s*.csv em {dir_seg}")
    keys = set()
    for fp in files:
        stem = fp.stem
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
        raise ValueError(f"[{mon_key}] Emenda PASSO2 gerou {len(merged)} linhas (esperado 35040).")

    merged.to_csv(out_fp, index=False, encoding="utf-8-sig")
    print(f"OK - {mon_key}: anual gerado: {out_fp.name} | linhas: {len(merged)}")

    for fp in files:
        fp.unlink()
    print(f"[CLEAN] Segmentados removidos ({mon_key}).")

# %% Celula 007 - PASSO 2: junta EnergyMeter (segmentos + TOTAL)
# =============================================================================
# Entrada:
#   Simulacao 022 segmentos_ano_2031_2047/EXP_MTR_GERAL_*.csv
# Saida:
#   Simulacao 022 segmentos_ano_2031_2047/EXP_MTR_GERAL_anual.csv
# Remove:
#   EXP_MTR_GERAL_*.csv
# =============================================================================

from pathlib import Path
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
DIR_PASS2 = WORK_DIR / "Simulacao 022 segmentos_ano_2031_2047"
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

# %% Celula 008 - PASSO 2: monitores -> curvas trifasicas (SHIFT DIREITA)
# =============================================================================
# Entradas:
#   Simulacao 022 segmentos_ano_2031_2047/Monitor_<KEY>_anual.csv
# Saidas:
#   Simulacao 022 segmentos_ano_2031_2047/Curva_de_Carga_<KEY>_sim_22.csv
# Remove:
#   Monitor_<KEY>_anual.csv
# =============================================================================

from pathlib import Path
import numpy as np
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
DIR_PASS2 = WORK_DIR / "Simulacao 022 segmentos_ano_2031_2047"

DT_H = 0.25
TOTAL_NPTS = 35040
hora = np.round(np.arange(0.0, 8760.0, DT_H), 10)

cols_vals = ["P1 (kW)", "Q1 (kvar)", "P2 (kW)", "Q2 (kvar)", "P3 (kW)", "Q3 (kvar)"]

files = sorted(DIR_PASS2.glob("Monitor_*_anual.csv"))
if not files:
    raise FileNotFoundError(f"Nao encontrei Monitor_*_anual.csv em {DIR_PASS2}")

for in_fp in files:
    mon_key = in_fp.stem.replace("Monitor_", "").replace("_anual", "")
    out_fp = DIR_PASS2 / f"Curva_de_Carga_{mon_key}_sim_22.csv"

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
    vals = np.vstack([vals[0:1, :], vals[0:-1, :]])

    df_out = pd.DataFrame(vals, columns=cols_vals)
    df_out.insert(0, "Hora_decimal", hora)
    df_out["P_3f_S"] = df_out["P1 (kW)"] + df_out["P2 (kW)"] + df_out["P3 (kW)"]
    df_out["Q_3f_S"] = df_out["Q1 (kvar)"] + df_out["Q2 (kvar)"] + df_out["Q3 (kvar)"]

    df_out[["Hora_decimal", "P_3f_S", "Q_3f_S"]].to_csv(out_fp, index=False, encoding="utf-8-sig")
    in_fp.unlink()

    print(f"[OK] {mon_key}: {out_fp.name} | removido: {in_fp.name} | SHIFT DIREITA aplicado")

# %% Celula 009 - PASSO 2: resumo do EnergyMeter (linha TOTAL)
# =============================================================================
# Entrada:
#   Simulacao 022 segmentos_ano_2031_2047/EXP_MTR_GERAL_anual.csv
# Saida:
#   Simulacao 022 segmentos_ano_2031_2047/Resumo_EnergyMeter_Geral_Sim22.csv
# =============================================================================

from pathlib import Path
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")
DIR_PASS2 = WORK_DIR / "Simulacao 022 segmentos_ano_2031_2047"

IN_FP = DIR_PASS2 / "EXP_MTR_GERAL_anual.csv"
OUT_FP = DIR_PASS2 / "Resumo_EnergyMeter_Geral_Sim22.csv"

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

kwh_fornecido = get_num("kWh")
kwh_carga = get_num("Zone kWh")
zone_losses_kwh = get_num("Zone Losses kWh")
line_losses_kwh = get_num("Line Losses")
trafo_losses_kwh = get_num("Transformer Losses")
noload_losses_kwh = get_num("No Load Losses kWh")
cobre_losses_kwh = trafo_losses_kwh - noload_losses_kwh

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

# %% Celula 010 - ENERGIA e DEMANDA MAX por mes e posto (SIM22 - ANO 2047, BESS modular autofinanciado)
# =============================================================================
# Entradas:
#   META: 00_dados_de_entrada_ano_letivo_2025_15min.csv
#         Usado apenas como mapa anual de Hora_decimal, Mes e Posto.
#   SIM22: curva GERAL com BESS modular autofinanciado em operacao conjugada
#          para o ano 2047.
# Saida:
#   Simulacao 022 segmentos_ano_2031_2047/01_Integralizacao_Mensal_SIM22_2047.csv
#
# Observacao:
#   Esta celula nao compara com SIM2/RGE nem com outra simulacao.
#   Ela apenas integraliza a simulacao conjugada do ano 2047 por mes e posto.
#   Configuracao do despacho:
#     BESS1: instalado em 2028, 1 MW / 5,5 MWh, operando a 80% da potencia,
#            degradado em 2047 por fator 0,8416667 para 673 kW / 4629,2 kWh.
#     BESS2: instalado em 2028, 1 MW / 5,5 MWh, operando a 80% da potencia,
#            degradado em 2047 por fator 0,8416667 para 673 kW / 4629,2 kWh.
#     BESS3: instalado em 2031, 1 MW / 3,0 MWh, operando a 80% da potencia,
#            degradado em 2047 por fator 0,8666667 para 693 kW / 2600 kWh.
#     Alvo fora-ponta = 4995 kW; permissao de recarga fora-ponta = 3885 kW.
#     Em fora-ponta, BESS1/BESS2 usam reserva de 54,5455% e BESS3 usa reserva de 100%.
#     Em ponta, os tres bancos usam reserva minima tecnica de 2%.
#   A curva e lida diretamente pelo sufixo sim_22, sem fallback.
# =============================================================================

from pathlib import Path
import numpy as np
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")

ANO_ANALISE = 2047
SIM_TAG = "SIM22"

SIM22_DIR = WORK_DIR / "Simulacao 022 segmentos_ano_2031_2047"

META_FP = WORK_DIR / "00_dados_de_entrada_ano_letivo_2025_15min.csv"
SIM22_FP = SIM22_DIR / "Curva_de_Carga_GERAL_sim_22.csv"
OUT_FP = SIM22_DIR / f"01_Integralizacao_Mensal_{SIM_TAG}_{ANO_ANALISE}.csv"

DT_H = 0.25
TOTAL_NPTS = 35040

mes_order = [
    "JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
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


def clean_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )
    return df

def gerar_curva_geral_sim22_se_necessario(sim22_fp: Path, dir_pass2: Path) -> None:
    """
    Garante a existencia de Curva_de_Carga_GERAL_sim_22.csv.

    Prioridade:
      1) Usa o arquivo final, se ja existir e tiver 35040 linhas;
      2) Gera a curva a partir de Monitor_GERAL_anual.csv, se existir e tiver 35040 linhas;
      3) Emenda os UFSM_Mon_GERAL_s*.csv e gera a curva, se a soma der 35040 linhas.

    Se encontrar apenas uma linha por segmento, o problema esta na Celula 005:
    os monitores foram exportados sem acumular o segmento completo. Nesse caso,
    e necessario rerodar a Celula 005 desta versao padronizada.
    """
    dir_pass2.mkdir(parents=True, exist_ok=True)
    cols_vals = ["P1 (kW)", "Q1 (kvar)", "P2 (kW)", "Q2 (kvar)", "P3 (kW)", "Q3 (kvar)"]
    mon_anual_fp = dir_pass2 / "Monitor_GERAL_anual.csv"

    def _ler_monitor(fp: Path) -> pd.DataFrame:
        mon_local = pd.read_csv(fp, encoding="utf-8-sig", sep=None, engine="python")
        return clean_cols(mon_local)

    def _validar_e_gravar_curva(mon: pd.DataFrame, origem: str) -> None:
        mon = clean_cols(mon)
        missing = [c for c in cols_vals if c not in mon.columns]
        if missing:
            raise ValueError(f"[GERAL] Colunas faltando para gerar curva a partir de {origem}: {missing}. Detectadas: {list(mon.columns)}")

        for c in cols_vals:
            mon[c] = pd.to_numeric(mon[c], errors="coerce")
        if mon[cols_vals].isna().any().any():
            raise ValueError(f"[GERAL] NaN encontrado nas colunas eletricas do monitor em {origem}.")
        if len(mon) != TOTAL_NPTS:
            raise ValueError(
                f"[GERAL] Monitor anual gerado a partir de {origem} ficou com {len(mon)} linhas; esperado {TOTAL_NPTS}. "
                "Se apareceu uma linha por segmento, os CSVs UFSM_Mon_GERAL_s*.csv antigos estao ruins ou a Celula 005 antiga foi usada. "
                "Rode novamente a Celula 005 desta versao padronizada, que limpa a pasta antes de simular, e depois rode 006, 007, 008, 009, 010 e 011."
            )

        hora = np.round(np.arange(0.0, 8760.0, DT_H), 10)
        vals = mon[cols_vals].to_numpy(copy=True)
        vals = np.vstack([vals[0:1, :], vals[0:-1, :]])

        df_out = pd.DataFrame(vals, columns=cols_vals)
        df_out.insert(0, "Hora_decimal", hora)
        df_out["P_3f_S"] = df_out["P1 (kW)"] + df_out["P2 (kW)"] + df_out["P3 (kW)"]
        df_out["Q_3f_S"] = df_out["Q1 (kvar)"] + df_out["Q2 (kvar)"] + df_out["Q3 (kvar)"]
        df_out[["Hora_decimal", "P_3f_S", "Q_3f_S"]].to_csv(sim22_fp, index=False, encoding="utf-8-sig")
        print("[AUTO] Curva GERAL gerada em:", sim22_fp)

    if sim22_fp.exists():
        curva = pd.read_csv(sim22_fp, encoding="utf-8-sig", sep=None, engine="python")
        if len(curva) == TOTAL_NPTS:
            return
        print(f"[AUTO] Curva GERAL existente tem {len(curva)} linhas; removendo arquivo invalido: {sim22_fp.name}")
        sim22_fp.unlink()

    if mon_anual_fp.exists():
        mon_anual = _ler_monitor(mon_anual_fp)
        if len(mon_anual) == TOTAL_NPTS:
            print("[AUTO] Curva GERAL nao encontrada. Gerando a partir de Monitor_GERAL_anual.csv.")
            _validar_e_gravar_curva(mon_anual, mon_anual_fp.name)
            return
        print(f"[AUTO] Monitor_GERAL_anual.csv existe, mas tem {len(mon_anual)} linhas; removendo arquivo invalido.")
        mon_anual_fp.unlink()

    seg_files = sorted(dir_pass2.glob("UFSM_Mon_GERAL_s*.csv"))
    if not seg_files:
        raise FileNotFoundError(
            f"Nao encontrei {sim22_fp}. Tambem nao encontrei Monitor_GERAL_anual.csv nem UFSM_Mon_GERAL_s*.csv em {dir_pass2}. "
            "Execute antes a Celula 005 do PASSO 2 e depois a Celula 006 e a Celula 008."
        )

    print(f"[AUTO] Curva GERAL nao encontrada. Emendando {len(seg_files)} arquivos UFSM_Mon_GERAL_s*.csv.")
    dfs = []
    tamanhos = []
    for fp in seg_files:
        dfi = pd.read_csv(fp, encoding="utf-8-sig", sep=None, engine="python")
        dfs.append(dfi)
        tamanhos.append((fp.name, len(dfi)))

    total_linhas = sum(t for _, t in tamanhos)
    if total_linhas != TOTAL_NPTS:
        amostra = tamanhos[:10]
        raise ValueError(
            f"[GERAL] Emenda dos UFSM_Mon_GERAL_s*.csv resultou em {total_linhas} linhas; esperado {TOTAL_NPTS}. "
            f"Amostra de tamanhos: {amostra}. "
            "Se cada arquivo tem 1 linha, estes arquivos sao de uma execucao antiga/incorreta. "
            "Rode novamente a Celula 005 desta versao padronizada; ela limpa os arquivos antigos antes de simular."
        )

    mon = pd.concat(dfs, ignore_index=True)
    mon.to_csv(mon_anual_fp, index=False, encoding="utf-8-sig")
    print("[AUTO] Monitor anual GERAL salvo em:", mon_anual_fp)
    _validar_e_gravar_curva(mon, "UFSM_Mon_GERAL_s*.csv")



if not META_FP.exists():
    raise FileNotFoundError(META_FP)

gerar_curva_geral_sim22_se_necessario(SIM22_FP, SIM22_DIR)
if not SIM22_FP.exists():
    raise FileNotFoundError(SIM22_FP)

meta = pd.read_csv(META_FP, dtype=str, encoding="utf-8-sig")
sim22 = pd.read_csv(SIM22_FP, encoding="utf-8-sig", sep=None, engine="python")

meta = clean_cols(meta)
sim22 = clean_cols(sim22)

for name, dfx, req in [
    ("META", meta, ["Hora_decimal", "Mes", "Posto"]),
    (SIM_TAG, sim22, ["Hora_decimal", "P_3f_S", "Q_3f_S"]),
]:
    miss = [c for c in req if c not in dfx.columns]
    if miss:
        raise ValueError(f"Missing columns in {name}: {miss}. Available: {list(dfx.columns)}")

meta["Hora_decimal"] = pd.to_numeric(meta["Hora_decimal"], errors="coerce")
meta["Mes"] = meta["Mes"].astype(str).str.strip().str.upper()
meta["Posto"] = meta["Posto"].apply(norm_posto)
meta = meta.dropna(subset=["Hora_decimal", "Mes", "Posto"]).copy()

sim22["Hora_decimal"] = pd.to_numeric(sim22["Hora_decimal"], errors="coerce")
sim22["P_3f_S"] = pd.to_numeric(sim22["P_3f_S"], errors="coerce")
sim22["Q_3f_S"] = pd.to_numeric(sim22["Q_3f_S"], errors="coerce")
sim22.dropna(subset=["Hora_decimal", "P_3f_S", "Q_3f_S"], inplace=True)

meta["k"] = make_k(meta["Hora_decimal"])
sim22["k"] = make_k(sim22["Hora_decimal"])

meta = meta[(meta["k"] >= 0) & (meta["k"] < TOTAL_NPTS)].copy()
sim22 = sim22[(sim22["k"] >= 0) & (sim22["k"] < TOTAL_NPTS)].copy()

meta = meta[["k", "Mes", "Posto"]].drop_duplicates(subset=["k"], keep="first").copy()
sim22 = sim22[["k", "P_3f_S", "Q_3f_S"]].drop_duplicates(subset=["k"], keep="first").copy()

if len(meta) != TOTAL_NPTS:
    raise ValueError(f"META gerou {len(meta)} amostras anuais de 15 min; esperado {TOTAL_NPTS}.")
if len(sim22) != TOTAL_NPTS:
    raise ValueError(f"SIM22 gerou {len(sim22)} amostras anuais de 15 min; esperado {TOTAL_NPTS}.")

df16 = meta.merge(sim22, on="k", how="left").rename(
    columns={"P_3f_S": "P_SIM22", "Q_3f_S": "Q_SIM22"}
)

faltas_p = int(df16["P_SIM22"].isna().sum())
faltas_q = int(df16["Q_SIM22"].isna().sum())
if faltas_p or faltas_q:
    raise ValueError(
        f"Falha de alinhamento por Hora_decimal/k: "
        f"P_SIM22 faltas={faltas_p}, Q_SIM22 faltas={faltas_q}"
    )

df16["E_P_SIM22_kWh"] = df16["P_SIM22"] * DT_H
df16["E_Q_SIM22_kVArh"] = df16["Q_SIM22"] * DT_H

group_cols = ["Mes", "Posto"]

agg16 = df16.groupby(group_cols, dropna=False).agg(
    N_pontos_SIM22=("P_SIM22", lambda s: int(s.notna().sum())),
    Consumo_P_SIM22_kWh=("E_P_SIM22_kWh", "sum"),
    Consumo_Q_SIM22_kVArh=("E_Q_SIM22_kVArh", "sum"),
    DemandaMax_P_SIM22_kW=("P_SIM22", "max"),
    DemandaMax_Q_SIM22_kVAr=("Q_SIM22", "max"),
).reset_index()

meta_counts = meta.groupby(group_cols, dropna=False).agg(N_pontos_META=("Posto", "size")).reset_index()
agg = agg16.merge(meta_counts, on=group_cols, how="left")

agg["Mes"] = pd.Categorical(agg["Mes"], categories=mes_order, ordered=True)
agg = agg.sort_values(["Mes", "Posto"]).reset_index(drop=True)

agg.to_csv(OUT_FP, index=False, encoding="utf-8")
print("DONE. Saved:", OUT_FP, "| Rows:", len(agg))
print("SIM22 usado:", SIM22_FP)
print(agg[["Mes", "Posto", "N_pontos_META", "N_pontos_SIM22", "DemandaMax_P_SIM22_kW"]])

# %% Celula 011 - SIMULACAO 022: tabela de custos (SIM22 - ANO 2047, BESS conjugado 4500)
# =============================================================================
# Entrada:
#   Simulacao 022 segmentos_ano_2031_2047/01_Integralizacao_Mensal_SIM22_2047.csv
#
# Saida:
#   Simulacao 022 segmentos_ano_2031_2047/Tabela_demanda_consumo_por_posto_SIM22_2047.csv
#
# Demandas contratadas do ano 2047:
#   DCFP contratada com BESS = 4995 kW
#   Alvo operacional fora-ponta do despacho = 4500 * 1,11 = 4995 kW
#   Permissao para recarga fora-ponta = 3500 * 1,11 = 3885 kW
#   DCP sem BESS = 3000 * 1,11 = 3330 kW
#   DCP com BESS = 3330 - (673 + 673 + 693) = 1291 kW
#
# Banco de energia modular autofinanciado:
#   BESS1 instalado em 2028:
#     1 MW / 5,5 MWh nominal, operando a 80% da potencia nominal em 2028.
#     Em 2047: fator 0,8416667 -> 673 kW / 4629,2 kWh.
#     Possui excedente nominal de 2500 kWh para suprir energia de peak-shave fora-ponta.
#   BESS2 instalado em 2028:
#     1 MW / 5,5 MWh nominal, operando a 80% da potencia nominal em 2028.
#     Em 2047: fator 0,8416667 -> 673 kW / 4629,2 kWh.
#     Possui excedente nominal de 2500 kWh para suprir energia de peak-shave fora-ponta.
#   BESS3 instalado em 2031:
#     1 MW / 3,0 MWh nominal, operando a 80% da potencia nominal em 2031. Em 2047: fator 0,8666667 -> 693 kW / 2600 kWh.
#   Os bancos possuem energias efetivas diferentes em 2047.
#   BESS1 e BESS2 foram dimensionados com excedente para suprir peak-shave fora-ponta.
#   BESS3 possui somente os 3 MWh nominais necessarios para a ponta.
#   Em fora-ponta, BESS1/BESS2 usam reserva de 54,5455% e BESS3 usa reserva de 100%.
#   Em ponta, os tres bancos usam reserva minima tecnica de 2%.
#
# Observacao:
#   Esta celula nao gera tabela SIM2/RGE e nao gera comparativo.
# =============================================================================

from pathlib import Path
import pandas as pd

WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")

ANO_BASE_DADOS = 2025
ANO_ANALISE = 2047
SIM_TAG = "SIM22"

SIM22_DIR = WORK_DIR / "Simulacao 022 segmentos_ano_2031_2047"
SIM22_DIR.mkdir(parents=True, exist_ok=True)

IN_FP = SIM22_DIR / f"01_Integralizacao_Mensal_{SIM_TAG}_{ANO_ANALISE}.csv"
OUT_SIM22 = SIM22_DIR / f"Tabela_demanda_consumo_por_posto_{SIM_TAG}_{ANO_ANALISE}.csv"

# -------------------------
# Demandas contratadas e alvos do despacho
# -------------------------
# Fora-ponta: alvo operacional 4500 * 1,11 = 4995 kW; demanda contratada FP = 4995 kW
# Ponta sem BESS: 3000 * 1,11 = 3330 kW
# Ponta com BESS: 3330 - (673 + 673 + 693) = 1291 kW
DCP_SEM_BESS = 3330.0
DCFP_COM_BESS = 4995.0

KW_TARGET_FP = 4995.0
KW_TARGET_LOW_FP = 3885.0

# -------------------------
# BESS modular autofinanciado
# -------------------------
NUM_BESS = 3

BESS1_ANO_INSTALACAO = 2028
BESS1_P_NOMINAL_KW = 1000.0
BESS1_P_OPERACIONAL_2028_KW = 800.0
BESS1_E_NOMINAL_KWH = 5500.0
BESS1_E_BASE_PONTA_NOMINAL_KWH = 3000.0
BESS1_E_EXCEDENTE_FP_NOMINAL_KWH = 2500.0
BESS1_FATOR_DEGRADACAO_2047 = 0.8416666667
BESS1_P_2047_KW = round(BESS1_P_OPERACIONAL_2028_KW * BESS1_FATOR_DEGRADACAO_2047)
BESS1_E_2047_KWH = BESS1_E_NOMINAL_KWH * BESS1_FATOR_DEGRADACAO_2047
BESS1_E_EXCEDENTE_FP_2047_KWH = BESS1_E_EXCEDENTE_FP_NOMINAL_KWH * BESS1_FATOR_DEGRADACAO_2047

BESS2_ANO_INSTALACAO = 2028
BESS2_P_NOMINAL_KW = 1000.0
BESS2_P_OPERACIONAL_2028_KW = 800.0
BESS2_E_NOMINAL_KWH = 5500.0
BESS2_FATOR_DEGRADACAO_2047 = 0.8416666667
BESS2_P_2047_KW = round(BESS2_P_OPERACIONAL_2028_KW * BESS2_FATOR_DEGRADACAO_2047)
BESS2_E_2047_KWH = BESS2_E_NOMINAL_KWH * BESS2_FATOR_DEGRADACAO_2047

BESS3_ANO_INSTALACAO = 2031
BESS3_P_NOMINAL_KW = 1000.0
BESS3_P_OPERACIONAL_2031_KW = 800.0
BESS3_FATOR_DEGRADACAO_2047 = 0.8666666667
BESS3_P_2047_KW = round(BESS3_P_OPERACIONAL_2031_KW * BESS3_FATOR_DEGRADACAO_2047)
BESS3_E_NOMINAL_KWH = 3000.0
BESS3_E_2047_KWH = BESS3_E_NOMINAL_KWH * BESS3_FATOR_DEGRADACAO_2047

BESS_P_TOTAL_KW = BESS1_P_2047_KW + BESS2_P_2047_KW + BESS3_P_2047_KW
BESS_E_TOTAL_KWH = BESS1_E_2047_KWH + BESS2_E_2047_KWH + BESS3_E_2047_KWH
BESS_E_NOMINAL_TOTAL_KWH = BESS1_E_NOMINAL_KWH + BESS2_E_NOMINAL_KWH + BESS3_E_NOMINAL_KWH

# Separacao operacional coerente com o despacho OpenDSS corrigido.
# FORA_PONTA:
#   BESS1 e BESS2 reservam 3000/5500 = 54,5455% para a ponta e usam o excedente fora-ponta.
#   BESS3 reserva 100% para a ponta.
# PONTA:
#   BESS1, BESS2 e BESS3 ficam liberados ate a reserva minima tecnica de 2%.
BESS1_RESERVA_PONTA_PCT = 100.0 * BESS1_E_BASE_PONTA_NOMINAL_KWH / BESS1_E_NOMINAL_KWH
BESS2_RESERVA_PONTA_PCT = 100.0 * 3000.0 / 5500.0  # 54.5454545%
BESS3_RESERVA_PONTA_PCT = 100.0
BESS_RESERVA_MIN_PONTA_PCT = 2.0

BESS1_E_RESERVA_PONTA_2047_KWH = BESS1_E_2047_KWH * BESS1_RESERVA_PONTA_PCT / 100.0
BESS2_E_RESERVA_PONTA_2047_KWH = BESS2_E_2047_KWH * BESS2_RESERVA_PONTA_PCT / 100.0
BESS3_E_RESERVA_PONTA_2047_KWH = BESS3_E_2047_KWH * BESS3_RESERVA_PONTA_PCT / 100.0
BESS_E_RESERVA_PONTA_KWH = BESS1_E_RESERVA_PONTA_2047_KWH + BESS2_E_RESERVA_PONTA_2047_KWH + BESS3_E_RESERVA_PONTA_2047_KWH
BESS_E_DISPONIVEL_FP_KWH = (BESS1_E_2047_KWH - BESS1_E_RESERVA_PONTA_2047_KWH) + (BESS2_E_2047_KWH - BESS2_E_RESERVA_PONTA_2047_KWH)

DCP_COM_BESS = max(0.0, DCP_SEM_BESS - BESS_P_TOTAL_KW)

CONTR_SIM22 = {"DCFP": DCFP_COM_BESS, "DCP": DCP_COM_BESS}

# -------------------------
# Tarifas
# -------------------------
TARIFAS = {
    "DCFP"    : 32.84,
    "DCP"     : 83.34,
    "DCFP_c"  : 27.26,
    "DCP_c"   : 69.17,
    "UFP"     : 65.68,
    "UP"      : 166.68,
    "CFP_TUSD": 0.15,
    "CP_TUSD" : 0.15,
    "CFP_TUE" : 0.37,
    "CP_TUE"  : 0.59,
}

# -------------------------
# Mapa de meses + ordem cronologica
# -------------------------
MES_MAP = {
    "JANEIRO": "JAN", "FEVEREIRO": "FEV", "MARCO": "MAR", "ABRIL": "ABR",
    "MAIO": "MAI", "JUNHO": "JUN", "JULHO": "JUL", "AGOSTO": "AGO",
    "SETEMBRO": "SET", "OUTUBRO": "OUT", "NOVEMBRO": "NOV", "DEZEMBRO": "DEZ",
}
MESES_ORD = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]

if not IN_FP.exists():
    curva_fp = SIM22_DIR / "Curva_de_Carga_GERAL_sim_22.csv"
    raise FileNotFoundError(
        f"Nao encontrei {IN_FP}. Execute a Celula 010 antes da Celula 011. "
        f"A Celula 010 padronizada gera este arquivo a partir de {curva_fp.name}; "
        "se a curva GERAL tambem nao existir, ela tenta reconstruir a curva a partir de Monitor_GERAL_anual.csv ou dos arquivos UFSM_Mon_GERAL_s*.csv."
    )

df = pd.read_csv(IN_FP, encoding="utf-8")
df.columns = (
    df.columns.astype(str)
    .str.replace("\ufeff", "", regex=False)
    .str.strip()
    .str.replace(r"\s+", " ", regex=True)
)

def tabela_custos(df_in: pd.DataFrame, fonte: str, DCFP: float, DCP: float) -> pd.DataFrame:
    """
    fonte = "SIM22"
    Usa:
      Consumo_P_{fonte}_kWh, DemandaMax_P_{fonte}_kW
    Aplica demandas contratadas especificas (DCFP/DCP).
    """
    colE = f"Consumo_P_{fonte}_kWh"
    colD = f"DemandaMax_P_{fonte}_kW"

    req = ["Mes", "Posto", colE, colD]
    miss = [c for c in req if c not in df_in.columns]
    if miss:
        raise ValueError(f"Colunas faltando para {fonte}: {miss}")

    d = df_in[["Mes", "Posto", colE, colD]].copy()
    d["Mes"] = d["Mes"].astype(str).str.strip().str.upper()
    d["Posto"] = d["Posto"].astype(str).str.strip().str.upper()

    d["MES"] = d["Mes"].map(MES_MAP)
    if d["MES"].isna().any():
        bad = d.loc[d["MES"].isna(), "Mes"].unique().tolist()
        raise ValueError(f"Meses nao mapeados: {bad}")

    fp = d[d["Posto"] == "FORA_PONTA"].set_index("MES")
    p = d[d["Posto"] == "PONTA"].set_index("MES")

    presentes = set(fp.index).intersection(set(p.index))
    meses = [m for m in MESES_ORD if m in presentes]

    if len(meses) != 12:
        print(f"[AVISO] meses em comum FP/P = {len(meses)} -> {meses}")

    out = pd.DataFrame({
        "MES": meses,
        "DMFP (kW)": pd.to_numeric(fp.loc[meses, colD], errors="coerce").round(0).astype("Int64"),
        "DMP (kW)": pd.to_numeric(p.loc[meses, colD], errors="coerce").round(0).astype("Int64"),
        "CFP (kWh)": pd.to_numeric(fp.loc[meses, colE], errors="coerce").round(0).astype("Int64"),
        "CP (kWh)": pd.to_numeric(p.loc[meses, colE], errors="coerce").round(0).astype("Int64"),
    })

    # Ultrapassagens com tolerancia de 5%.
    out["UFP (kW)"] = (out["DMFP (kW)"].astype(float) - DCFP).clip(lower=0)
    out.loc[out["DMFP (kW)"].astype(float) <= 1.05 * DCFP, "UFP (kW)"] = 0

    out["UP (kW)"] = (out["DMP (kW)"].astype(float) - DCP).clip(lower=0)
    out.loc[out["DMP (kW)"].astype(float) <= 1.05 * DCP, "UP (kW)"] = 0

    # Complemento ate a demanda contratada.
    out["DCFP_c (kW)"] = (DCFP - out["DMFP (kW)"].astype(float)).clip(lower=0)
    out["DCP_c (kW)"] = (DCP - out["DMP (kW)"].astype(float)).clip(lower=0)

    # Componentes de custo.
    out["DCFP (R$32,84)"] = (out["DMFP (kW)"].astype(float) * TARIFAS["DCFP"]).round(2)
    out["DCP  (R$83,34)"] = (out["DMP (kW)"].astype(float) * TARIFAS["DCP"]).round(2)
    out["DCFP_c (R$27,26)"] = (out["DCFP_c (kW)"] * TARIFAS["DCFP_c"]).round(2)
    out["DCP_c  (R$69,17)"] = (out["DCP_c (kW)"] * TARIFAS["DCP_c"]).round(2)
    out["UFP  (R$65,68)"] = (out["UFP (kW)"] * TARIFAS["UFP"]).round(2)
    out["UP   (R$166,68)"] = (out["UP (kW)"] * TARIFAS["UP"]).round(2)
    out["CFP (R$0,15) TUSD"] = (out["CFP (kWh)"].astype(float) * TARIFAS["CFP_TUSD"]).round(2)
    out["CP  (R$0,15) TUSD"] = (out["CP (kWh)"].astype(float) * TARIFAS["CP_TUSD"]).round(2)
    out["CFP (R$0,37) TUE"] = (out["CFP (kWh)"].astype(float) * TARIFAS["CFP_TUE"]).round(2)
    out["CP  (R$0,59) TUE"] = (out["CP (kWh)"].astype(float) * TARIFAS["CP_TUE"]).round(2)

    cols_rs = [
        "DCFP (R$32,84)", "DCP  (R$83,34)", "DCFP_c (R$27,26)", "DCP_c  (R$69,17)",
        "UFP  (R$65,68)", "UP   (R$166,68)", "CFP (R$0,15) TUSD", "CP  (R$0,15) TUSD",
        "CFP (R$0,37) TUE", "CP  (R$0,59) TUE",
    ]
    out["R$TOTAL_MES"] = out[cols_rs].sum(axis=1).round(2)

    totais = {
        "MES": "TOTAIS",
        "DMFP (kW)": int(pd.to_numeric(out["DMFP (kW)"], errors="coerce").max()),
        "DMP (kW)": int(pd.to_numeric(out["DMP (kW)"], errors="coerce").max()),
        "CFP (kWh)": int(pd.to_numeric(out["CFP (kWh)"], errors="coerce").sum()),
        "CP (kWh)": int(pd.to_numeric(out["CP (kWh)"], errors="coerce").sum()),
        "UFP (kW)": int(pd.to_numeric(out["UFP (kW)"], errors="coerce").max()),
        "UP (kW)": int(pd.to_numeric(out["UP (kW)"], errors="coerce").max()),
        "DCFP_c (kW)": int(pd.to_numeric(out["DCFP_c (kW)"], errors="coerce").max()),
        "DCP_c (kW)": int(pd.to_numeric(out["DCP_c (kW)"], errors="coerce").max()),
        "R$TOTAL_MES": float(out["R$TOTAL_MES"].sum()),
    }
    for c in cols_rs:
        totais[c] = float(out[c].sum())

    extras = [
        {"MES": "CTOTAL", "CFP (kWh)": int(totais["CFP (kWh)"] + totais["CP (kWh)"])},
        {"MES": "R$TOTAL", "R$TOTAL_MES": float(totais["R$TOTAL_MES"])},
        {"MES": "DCFP", "DMFP (kW)": int(DCFP)},
        {"MES": "DCP", "DMP (kW)": int(DCP)},
        {"MES": "KW_TARGET_FP", "DMFP (kW)": int(KW_TARGET_FP)},
        {"MES": "KW_TARGET_LOW_FP", "DMFP (kW)": int(KW_TARGET_LOW_FP)},
    ]

    return pd.concat([out, pd.DataFrame([totais]), pd.DataFrame(extras)], ignore_index=True)

tab22 = tabela_custos(
    df,
    SIM_TAG,
    DCFP=CONTR_SIM22["DCFP"],
    DCP=CONTR_SIM22["DCP"],
)

tab22.to_csv(OUT_SIM22, index=False, encoding="utf-8")

print("DONE. Saved (Simulacao 022 - BESS conjugado 4500 FP - 2047):")
print(" -", OUT_SIM22)
print("\nDemandas contratadas e alvos usados em 2047:")
print(f" - DCFP contratada = {DCFP_COM_BESS:.0f} kW")
print(f" - Alvo fora-ponta do despacho = {KW_TARGET_FP:.0f} kW")
print(f" - Permissao de recarga fora-ponta = {KW_TARGET_LOW_FP:.0f} kW")
print(f" - DCP sem BESS = {DCP_SEM_BESS:.0f} kW")
print(f" - DCP com BESS = {DCP_COM_BESS:.0f} kW")
print(f" - Potencia operacional total dos BESS = {BESS_P_TOTAL_KW:.0f} kW")
print(f" - Potencia BESS1 2047 = {BESS1_P_2047_KW:.0f} kW")
print(f" - Potencia BESS2 2047 = {BESS2_P_2047_KW:.0f} kW")
print(f" - Potencia BESS3 2047 = {BESS3_P_2047_KW:.0f} kW")
print(f" - Energia nominal total instalada = {BESS_E_NOMINAL_TOTAL_KWH:.0f} kWh")
print(f" - Energia disponivel em 2047 = {BESS_E_TOTAL_KWH:.0f} kWh")
print(f" - Energia BESS1 2047 = {BESS1_E_2047_KWH:.0f} kWh")
print(f" - Energia BESS2 2047 = {BESS2_E_2047_KWH:.0f} kWh")
print(f" - Energia BESS3 2047 = {BESS3_E_2047_KWH:.0f} kWh")
print(f" - Reserva BESS1 em fora-ponta = {BESS1_RESERVA_PONTA_PCT:.4f}%")
print(f" - Reserva BESS2 em fora-ponta = {BESS2_RESERVA_PONTA_PCT:.4f}%")
print(f" - Reserva BESS3 em fora-ponta = {BESS3_RESERVA_PONTA_PCT:.4f}%")
print(f" - Reserva minima tecnica em ponta = {BESS_RESERVA_MIN_PONTA_PCT:.1f}%")
print(f" - Excedente nominal por BESS1/BESS2 para fora-ponta = {BESS1_E_EXCEDENTE_FP_NOMINAL_KWH:.0f} kWh")
print(f" - Excedente degradado por BESS1/BESS2 para fora-ponta = {BESS1_E_EXCEDENTE_FP_2047_KWH:.0f} kWh")
print(f" - Energia reservada para ponta BESS1 = {BESS1_E_RESERVA_PONTA_2047_KWH:.0f} kWh")
print(f" - Energia reservada para ponta BESS2 = {BESS2_E_RESERVA_PONTA_2047_KWH:.0f} kWh")
print(f" - Energia reservada para ponta BESS3 = {BESS3_E_RESERVA_PONTA_2047_KWH:.0f} kWh")
print(f" - Energia reservada para ponta total = {BESS_E_RESERVA_PONTA_KWH:.0f} kWh")
print(f" - Energia disponivel para peak-shave fora-ponta = {BESS_E_DISPONIVEL_FP_KWH:.0f} kWh")
print("\nResumo anual:")
print(tab22[tab22["MES"].isin(["TOTAIS", "CTOTAL", "R$TOTAL", "DCFP", "DCP"])])

