# %% Celula 001
# INMET 2025 -> UFV_poa_2025.csv (15 min, POA pu (kW/m2), sem cabecalho)
# Cabecalho novo INMET:
#   Data_Hora_UTC,Temp_Med_C,Radiacao_kJ/m2,Radiacao_W/m2,Vel_Vento_m/s
# Usa obrigatoriamente Radiacao_W/m2 como GHI.

import pandas as pd
from pathlib import Path
import pvlib

# ---- Parametros (mesmos do seu script) ----
LATITUDE = -29.7127348
LONGITUDE = -53.7201994
FUSO = "America/Sao_Paulo"
INCLINACAO_GRAU = 23
AZIMUTE_GRAU = 350

# ---- Arquivos ----
ARQ_INMET = Path(r"C:\Users\afole\OneDrive\Dissertacao2025\00_dados_de_entrada_inmet_ufsm_2025.csv")
ARQ_SAIDA = Path(r"C:\Users\afole\OneDrive\Dissertacao2025\UFV_poa_2025.csv")

# ---- Periodo alvo (hora local) ----
idx = pd.date_range("2025-01-01 00:00", "2025-12-31 23:45", freq="15min", tz=FUSO)

# ---- Leitura e parsing (Data_Hora_UTC no formato EUA) ----
df = pd.read_csv(ARQ_INMET, sep=",", decimal=".", encoding="latin1")
df.columns = [str(c).strip() for c in df.columns]

COL_DT = "Data_Hora_UTC"
COL_GHI = "Radiacao_W/m2"

if COL_DT not in df.columns:
    raise ValueError(f"Coluna ausente: {COL_DT}. Colunas: {list(df.columns)}")
if COL_GHI not in df.columns:
    raise ValueError(f"Coluna ausente: {COL_GHI}. Colunas: {list(df.columns)}")

df["datahora_utc"] = pd.to_datetime(
    df[COL_DT],
    format="%m/%d/%Y %H:%M:%S",
    errors="coerce",
    utc=True,
)

df = (
    df.set_index("datahora_utc")
      .tz_convert(FUSO)[[COL_GHI]]
      .rename(columns={COL_GHI: "GHI"})
      .sort_index()
)

df["GHI"] = pd.to_numeric(df["GHI"], errors="coerce")

# ---- Reindex para 15 min no ano todo ----
df = df.reindex(idx)

# ---- Interpola so de dia e zera a noite ----
loc = pvlib.location.Location(LATITUDE, LONGITUDE, FUSO)
pos = loc.get_solarposition(idx)
dia = pos["zenith"] < 90

df.loc[~dia, "GHI"] = pd.NA
df["GHI"] = df["GHI"].interpolate(limit_direction="both")
df.loc[~dia, "GHI"] = 0.0
df["GHI"] = df["GHI"].clip(lower=0)

# ---- GHI -> POA (Erbs + HayDavies) ----
diss = pvlib.irradiance.erbs(df["GHI"], pos["zenith"], idx)
dni_extra = pvlib.irradiance.get_extra_radiation(idx)

poa_raw = pvlib.irradiance.get_total_irradiance(
    surface_tilt=INCLINACAO_GRAU,
    surface_azimuth=AZIMUTE_GRAU,
    ghi=df["GHI"],
    dhi=diss["dhi"],
    dni=diss["dni"],
    dni_extra=dni_extra,
    solar_zenith=pos["zenith"],
    solar_azimuth=pos["azimuth"],
    model="haydavies",
)["poa_global"]

# ---- Corte crepuscular + normalizacao (pu = kW/m2) ----
mascara_noite = (pos["zenith"] >= 84) | (df["GHI"] < 50)
poa_pu = poa_raw.mask(mascara_noite, 0.0).clip(lower=0) / 1000.0

# ---- Exporta no formato OpenDSS: hora_decimal, POA_pu ----
n = len(poa_pu)  # deve dar 35040
hora_decimal = pd.Series([i * 0.25 for i in range(n)])

saida = pd.concat([hora_decimal, poa_pu.reset_index(drop=True)], axis=1)
saida.iloc[-1, 1] = 0.0  # garante ultimo ponto 0
saida.to_csv(ARQ_SAIDA, header=False, index=False, float_format="%.4f")

print("OK:", ARQ_SAIDA)
print(f"Pontos: {n} (esperado 35040)")

# %% Celula 002 (PV apenas) - UFV_tmod_2025.csv (15 min, sem cabecalho)
# INMET 2025 (Temp + Vento) + UFV_poa_2025.csv (POA kW/m2) -> T_mod (SAPM)
# Ajuste PV: quando POA=0, forca T_mod = T_ar (noite/sem sol)
# Cabecalho novo INMET:
#   Data_Hora_UTC,Temp_Med_C,Radiacao_kJ/m2,Radiacao_W/m2,Vel_Vento_m/s

import pandas as pd
from pathlib import Path
import pvlib

# ----------------------- PARAMETROS DO LOCAL --------------------------------
LATITUDE  = -29.7127348
LONGITUDE = -53.7201994
FUSO      = "America/Sao_Paulo"

# Coeficientes SAPM padrao
A_SAPM      = -3.47
B_SAPM      = -0.0594
DELTAT_SAPM = 3.0

# --------------------------- ARQUIVOS ----------------------------------------
ARQ_INMET = Path(r"C:\Users\afole\OneDrive\Dissertacao2025\00_dados_de_entrada_inmet_ufsm_2025.csv")
ARQ_POA   = Path(r"C:\Users\afole\OneDrive\Dissertacao2025\UFV_poa_2025.csv")
ARQ_SAIDA = Path(r"C:\Users\afole\OneDrive\Dissertacao2025\UFV_tmod_2025.csv")

# ------------------------- GRADE 15 MIN (2025) ------------------------------
idx = pd.date_range("2025-01-01 00:00", "2025-12-31 23:45", freq="15min", tz=FUSO)

# -------------------------- LEITURA INMET 2025 ------------------------------
df = pd.read_csv(ARQ_INMET, sep=",", decimal=".", encoding="latin1")
df.columns = [str(c).strip() for c in df.columns]

COL_DT = "Data_Hora_UTC"
COL_T  = "Temp_Med_C"
COL_V  = "Vel_Vento_m/s"

for c in [COL_DT, COL_T, COL_V]:
    if c not in df.columns:
        raise ValueError(f"Coluna obrigatoria ausente: '{c}'. Colunas: {list(df.columns)}")

df["datahora_utc"] = pd.to_datetime(
    df[COL_DT],
    format="%m/%d/%Y %H:%M:%S",
    errors="coerce",
    utc=True,
)

df = (
    df.set_index("datahora_utc")
      .tz_convert(FUSO)[[COL_T, COL_V]]
      .rename(columns={COL_T: "T_ar", COL_V: "V_vento"})
      .apply(pd.to_numeric, errors="coerce")
      .sort_index()
)

# copia original (para manter noite como veio do INMET)
df_original = df.copy()

# reindex 15 min
df = df.reindex(idx)
df_original = df_original.reindex(idx)

# ------------------- ZENITE E INTERPOLACAO APENAS DE DIA --------------------
loc = pvlib.location.Location(LATITUDE, LONGITUDE, FUSO)
zenite = loc.get_solarposition(idx)["zenith"]
dia = zenite < 90.0

df_dia = df.copy()

# bloqueia interpolacao na noite
df_dia.loc[~dia, ["T_ar", "V_vento"]] = pd.NA

# interpola apenas durante o dia
df_dia[["T_ar", "V_vento"]] = df_dia[["T_ar", "V_vento"]].interpolate(limit_direction="both")

# a noite: volta ao valor original (se existir); se nao existir, permanece NaN
df_dia.loc[~dia, ["T_ar", "V_vento"]] = df_original.loc[~dia, ["T_ar", "V_vento"]]

# seguranca
df_dia["V_vento"] = df_dia["V_vento"].clip(lower=0)

# -------------------------- LEITURA DO POA (2025) ---------------------------
# UFV_poa_2025.csv: hora_decimal, POA_kWm2 (kW/m2)
poa = pd.read_csv(ARQ_POA, header=None, names=["hora_dec", "POA_kWm2"])
poa.index = idx
poa_kWm2 = pd.to_numeric(poa["POA_kWm2"], errors="coerce").fillna(0.0)

# SAPM espera W/m2
poa_Wm2 = poa_kWm2 * 1000.0

# --------------------- CALCULO TEMPERATURA DO MODULO ------------------------
t_mod = pvlib.temperature.sapm_cell(
    poa_global=poa_Wm2,
    temp_air=df_dia["T_ar"],
    wind_speed=df_dia["V_vento"],
    a=A_SAPM,
    b=B_SAPM,
    deltaT=DELTAT_SAPM,
)

# PV apenas: sem sol => T_mod = T_ar (evita artefatos noturnos)
mask_sem_sol = (poa_Wm2 <= 1.0)  # tolerancia numerica
t_mod = t_mod.where(~mask_sem_sol, df_dia["T_ar"])

# ---------------------------- EXPORTA OpenDSS -------------------------------
n = len(idx)  # 35040
hora_decimal = pd.Series([i * 0.25 for i in range(n)])

saida = pd.concat([hora_decimal, t_mod.reset_index(drop=True)], axis=1)

# garante que nao fique NaN residual (ex.: T_ar noturno faltante no INMET)
saida.iloc[:, 1] = saida.iloc[:, 1].interpolate(limit_direction="both")

saida.to_csv(ARQ_SAIDA, header=False, index=False, float_format="%.2f")

print("OK:", ARQ_SAIDA)
print(f"Pontos: {n} (esperado 35040)")

# %% Celula 003 - HVAC externo: salva P_env_kW e PU para LoadShape do OpenDSS (base 1 MW)
# Entrada INMET (UTC):
#   Data_Hora_UTC,Temp_Med_C,Radiacao_W/m2,Vel_Vento_m/s
# Saidas:
#   1) BESS_HVAC_ENV_PkW_2025.csv        (header): hora_decimal, P_env_kW
#   2) BESS_HVAC_ENV_LoadShape_2025.csv  (sem header): hora_decimal, pu_env  (pu_env = P_env_kW / P_BASE_KW)
#   3) BESS_HVAC_ENV_AUD_2025.csv        (auditoria)

import pandas as pd
import numpy as np
from pathlib import Path
import pytz

# ----------------------- Arquivos -------------------------------------------
WORK_DIR = Path(r"C:\Users\afole\OneDrive\Dissertacao2025")

ARQ_INMET = WORK_DIR / "00_dados_de_entrada_inmet_ufsm_2025.csv"

ARQ_OUT_PKW = WORK_DIR / "BESS_HVAC_ENV_PkW_2025.csv"
ARQ_OUT_PU  = WORK_DIR / "BESS_HVAC_ENV_LoadShape_2025.csv"   # sem header (hora_decimal, pu)
ARQ_AUD     = WORK_DIR / "BESS_HVAC_ENV_AUD_2025.csv"

TZ_LOCAL = "America/Sao_Paulo"
INTERVALO_MIN = 15
NPTS_ESPERADO = 365 * 24 * (60 // INTERVALO_MIN)

# ----------------------- Base para PU ---------------------------------------
P_BASE_KW = 1000.0  # <<< base fixa (kW) = 1 MW para o LoadShape do OpenDSS

# ----------------------- Parametros fisicos ---------------------------------
T_IN_C = 25.0

# Cor: cinza medio (envelhecido). Ajuste se quiser.
ALFA_ROOF = 0.55

U_ROOF  = 0.45
U_WALLS = 0.55
COP = 3.0

# Geometria (m)
L = 12.19
W = 2.44
H = 2.90
A_ROOF  = L * W
A_WALLS = 2.0 * (L * H) + 2.0 * (W * H)

def h_out(v_ms: float) -> float:
    v = max(0.0, float(v_ms))
    return 5.7 + 3.8 * v

# ------------------- Leitura INMET ------------------------------------------
df = pd.read_csv(ARQ_INMET, sep=",", decimal=".", encoding="latin1")
df.columns = [str(c).strip() for c in df.columns]

COL_DT = "Data_Hora_UTC"
COL_T  = "Temp_Med_C"
COL_G  = "Radiacao_W/m2"
COL_V  = "Vel_Vento_m/s"

for c in [COL_DT, COL_T, COL_G, COL_V]:
    if c not in df.columns:
        raise ValueError(f"Coluna obrigatoria ausente: '{c}'. Colunas: {list(df.columns)}")

df["dt_utc"] = pd.to_datetime(
    df[COL_DT],
    format="%m/%d/%Y %H:%M:%S",
    errors="coerce",
    utc=True,
)

df = df.dropna(subset=["dt_utc"]).copy()
df["temp_c"]  = pd.to_numeric(df[COL_T], errors="coerce")
df["ghi_wm2"] = pd.to_numeric(df[COL_G], errors="coerce").fillna(0.0)
df["wind_ms"] = pd.to_numeric(df[COL_V], errors="coerce")

tz_local = pytz.timezone(TZ_LOCAL)
df["dt_local"] = df["dt_utc"].dt.tz_convert(tz_local)
df = df.set_index("dt_local").sort_index()[["temp_c", "ghi_wm2", "wind_ms"]]

# ------------------- Grade alvo 15 min (2025 local) --------------------------
start_local = tz_local.localize(pd.Timestamp("2025-01-01 00:00:00"))
end_local   = tz_local.localize(pd.Timestamp("2025-12-31 23:45:00"))
idx_15 = pd.date_range(start=start_local, end=end_local, freq=f"{INTERVALO_MIN}min", tz=tz_local)

# ------------------- Reamostragem e interpolacao -----------------------------
df_hourly = df.resample("60min").mean(numeric_only=True)

idx_15_full = pd.date_range(
    start=df_hourly.index.min(),
    end=df_hourly.index.max(),
    freq=f"{INTERVALO_MIN}min",
    tz=tz_local,
)

x15 = df_hourly.reindex(idx_15_full).interpolate(method="time", limit_direction="both")
x15 = x15.reindex(idx_15).interpolate(method="time", limit_direction="both")

if len(x15) != NPTS_ESPERADO:
    raise RuntimeError(f"Tamanho inesperado: {len(x15)} (esperado {NPTS_ESPERADO}).")

x15["temp_c"]  = x15["temp_c"].ffill().bfill()
x15["ghi_wm2"] = x15["ghi_wm2"].fillna(0.0)
x15["wind_ms"] = x15["wind_ms"].fillna(0.0)

# ------------------- Modelo externo: sol-air no teto -------------------------
ho = x15["wind_ms"].apply(h_out).replace(0.0, np.nan)

T_sa_roof = x15["temp_c"] + (ALFA_ROOF * x15["ghi_wm2"]) / ho
T_sa_roof = T_sa_roof.fillna(x15["temp_c"])

Q_roof_W  = U_ROOF  * A_ROOF  * (T_sa_roof - T_IN_C)
Q_walls_W = U_WALLS * A_WALLS * (x15["temp_c"] - T_IN_C)

Q_env_W = Q_roof_W + Q_walls_W
Q_env_cool_W = np.maximum(Q_env_W, 0.0)

P_env_kW = (Q_env_cool_W / max(1e-9, COP)) / 1000.0

# ------------------- hora_decimal e PU --------------------------------------
hora_decimal = (x15.index - start_local) / pd.Timedelta(hours=1)

pu_env = P_env_kW / max(1e-9, P_BASE_KW)

# ------------------- Salva saidas -------------------------------------------
out_pkw = pd.DataFrame({"hora_decimal": hora_decimal.astype(float), "P_env_kW": P_env_kW.astype(float)})
out_pkw.to_csv(ARQ_OUT_PKW, index=False, encoding="utf-8-sig", float_format="%.6f")

out_pu = pd.DataFrame({0: hora_decimal.astype(float), 1: pu_env.astype(float)})
out_pu.to_csv(ARQ_OUT_PU, index=False, header=False, float_format="%.6f")

aud = pd.DataFrame(
    {
        "hora_decimal": hora_decimal.astype(float),
        "temp_c": x15["temp_c"].astype(float),
        "ghi_wm2": x15["ghi_wm2"].astype(float),
        "wind_ms": x15["wind_ms"].astype(float),
        "ho_wm2k": ho.fillna(0.0).astype(float),
        "T_sa_roof": T_sa_roof.astype(float),
        "Q_roof_W": Q_roof_W.astype(float),
        "Q_walls_W": Q_walls_W.astype(float),
        "Q_env_W": Q_env_W.astype(float),
        "P_env_kW": P_env_kW.astype(float),
        "P_BASE_KW": float(P_BASE_KW),
        "pu_env": pu_env.astype(float),
    }
)
aud.to_csv(ARQ_AUD, index=False, encoding="utf-8-sig", float_format="%.6f")

print("Celula 003 - HVAC externo: P_env_kW e LoadShape PU (base 1 MW)")
print(f"Base PU (kW): {P_BASE_KW:.3f}")
print(f"Saida P_env_kW: {ARQ_OUT_PKW.resolve()}")
print(f"Saida PU      : {ARQ_OUT_PU.resolve()}")
print(f"Auditoria     : {ARQ_AUD.resolve()}")
print(f"pu_env min/max: {float(pu_env.min()):.6f} .. {float(pu_env.max()):.6f}")
print(f"P_env_kW min/mean/max: {float(np.nanmin(P_env_kW)):.6f} / {float(np.nanmean(P_env_kW)):.6f} / {float(np.nanmax(P_env_kW)):.6f}")