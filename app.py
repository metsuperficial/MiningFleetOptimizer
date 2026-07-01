import math
import os
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Selección de Flota Minera", layout="wide")

st.markdown("""
<style>
.stApp {background:#080d18;}
.header {
    background:linear-gradient(135deg,#111827,#1f2937,#334155);
    padding:30px;
    border-radius:24px;
    text-align:center;
    color:white;
    margin-bottom:25px;
}
.box {
    background:#111827;
    border:1px solid #263244;
    border-radius:18px;
    padding:18px;
    color:white;
    margin-bottom:18px;
}
.name {
    background:#065f46;
    color:white;
    padding:10px;
    border-radius:10px;
    font-weight:bold;
    text-align:center;
    margin:10px 0;
}
.note {
    background:#111827;
    border-left:6px solid #22c55e;
    padding:16px;
    border-radius:12px;
    color:white;
    margin-bottom:20px;
}
</style>
""", unsafe_allow_html=True)


def n(x, default=0):
    try:
        if pd.isna(x):
            return default
        return float(x)
    except:
        return default


def costo_h(row, factor_hp):
    if "OPEX_USD_h" in row and not pd.isna(row["OPEX_USD_h"]):
        return n(row["OPEX_USD_h"])
    return n(row.get("Potencia_HP", 0)) * factor_hp


def imagen(row, icono):
    img = row.get("Imagen_URL", "")
    if isinstance(img, str) and img.strip():
        img = img.strip()
        try:
            if img.startswith("http"):
                st.image(img, use_container_width=True)
                return
            if os.path.exists(img):
                st.image(img, use_container_width=True)
                return
        except:
            pass
    st.markdown(f"<h1 style='text-align:center'>{icono}</h1>", unsafe_allow_html=True)


def validar_excel(archivo):
    hojas = pd.ExcelFile(archivo).sheet_names
    for hoja in ["Camiones", "Palas_Excavadoras", "Perforadoras"]:
        if hoja not in hojas:
            st.error(f"Falta la hoja obligatoria: {hoja}")
            st.stop()


def velocidades(vmax, pendiente, rr, tipo_via):
    factor_via = {
        "Excelente": 1.00,
        "Buena": 0.85,
        "Regular": 0.70,
        "Mala": 0.55
    }.get(tipo_via, 0.85)

    resistencia_total = pendiente + rr

    factor_cargado = max(0.40, 1 - resistencia_total / 100)
    factor_vacio = max(0.60, 1 - 0.5 * resistencia_total / 100)

    return vmax * factor_via * factor_cargado, vmax * factor_via * factor_vacio


def calcular_flotas(archivo, datos):
    camiones = pd.read_excel(archivo, sheet_name="Camiones")
    palas = pd.read_excel(archivo, sheet_name="Palas_Excavadoras")
    perforadoras = pd.read_excel(archivo, sheet_name="Perforadoras")

    planta = datos["planta"]
    sr = datos["sr"]
    horas = datos["horas"]
    densidad = datos["densidad"]
    esponjamiento = datos["esponjamiento"]

    altura_banco = datos["altura_banco"]
    burden = datos["burden"]
    espaciamiento = datos["espaciamiento"]
    sobreperf = datos["sobreperf"]
    diametro_req = datos["diametro_req"]

    ancho_rampa = datos["ancho_rampa"]
    altura_acceso = datos["altura_acceso"]

    d_planta = datos["d_planta"]
    d_botadero = datos["d_botadero"]
    pendiente = datos["pendiente"]
    rr = datos["rr"]
    tipo_via = datos["tipo_via"]

    mineral = planta
    desmonte = planta * sr
    total = mineral + desmonte

    distancia_prom = ((mineral * d_planta) + (desmonte * d_botadero)) / total

    longitud_barreno = altura_banco + sobreperf
    volumen_barreno = burden * espaciamiento * altura_banco
    toneladas_barreno = volumen_barreno * densidad
    toneladas_metro = toneladas_barreno / longitud_barreno
    metros_requeridos_dia = total / toneladas_metro

    resultados = []
    restricciones = []

    for _, perf in perforadoras.iterrows():
        modelo_perf = f"{perf.get('Marca')} {perf.get('Modelo')}"

        diam_min = n(perf.get("Diametro_min_mm", 0))
        diam_max = n(perf.get("Diametro_max_mm", 0))
        prof_max = n(perf.get("Profundidad_max_m", 0))
        ancho_perf = n(perf.get("Ancho_m", 0))
        alto_perf = n(perf.get("Alto_m", 0))

        if diam_min > 0 and diametro_req < diam_min:
            restricciones.append([modelo_perf, "Perforadora", "Diámetro requerido menor al rango"])
            continue
        if diam_max > 0 and diametro_req > diam_max:
            restricciones.append([modelo_perf, "Perforadora", "Diámetro requerido mayor al rango"])
            continue
        if prof_max > 0 and longitud_barreno > prof_max:
            restricciones.append([modelo_perf, "Perforadora", "Profundidad insuficiente"])
            continue
        if ancho_perf > 0 and ancho_perf > ancho_rampa:
            restricciones.append([modelo_perf, "Perforadora", "No cumple ancho de acceso"])
            continue
        if alto_perf > 0 and alto_perf > altura_acceso:
            restricciones.append([modelo_perf, "Perforadora", "No cumple altura de acceso"])
            continue

        vel_perf = n(perf.get("Velocidad_perforacion_m_h", 35), 35)
        dm_perf = n(perf.get("DM", 0.90), 0.90)
        ut_perf = n(perf.get("UT", 0.85), 0.85)

        metros_perf_dia = vel_perf * horas * dm_perf * ut_perf
        if metros_perf_dia <= 0:
            continue

        n_perf = math.ceil(metros_requeridos_dia / metros_perf_dia)
        prod_perf = n_perf * metros_perf_dia * toneladas_metro

        for _, pala in palas.iterrows():
            modelo_pala = f"{pala.get('Marca')} {pala.get('Modelo')}"

            ancho_pala = n(pala.get("Ancho_m", 0))
            alto_pala = n(pala.get("Alto_m", 0))

            if ancho_pala > 0 and ancho_pala > ancho_rampa:
                restricciones.append([modelo_pala, "Pala", "No cumple ancho de acceso"])
                continue
            if alto_pala > 0 and alto_pala > altura_acceso:
                restricciones.append([modelo_pala, "Pala", "No cumple altura de acceso"])
                continue

            cap_balde = n(pala.get("Capacidad_balde_m3", 0))
            factor_llenado = n(pala.get("Factor_llenado", 0.85), 0.85)
            tiempo_pala = n(pala.get("Tiempo_ciclo_pala_s", 30), 30)
            dm_pala = n(pala.get("DM", 0.90), 0.90)
            ut_pala = n(pala.get("UT", 0.85), 0.85)

            if cap_balde <= 0 or tiempo_pala <= 0:
                continue

            ton_pase = cap_balde * factor_llenado * densidad / esponjamiento
            prod_pala_h = ton_pase * (3600 / tiempo_pala) * dm_pala * ut_pala
            prod_pala_dia = prod_pala_h * horas
            n_palas = math.ceil(total / prod_pala_dia)
            prod_carguio = n_palas * prod_pala_dia

            for _, camion in camiones.iterrows():
                modelo_camion = f"{camion.get('Marca')} {camion.get('Modelo')}"

                ancho_camion = n(camion.get("Ancho_m", 0))
                alto_camion = n(camion.get("Alto_m", 0))

                if ancho_camion > 0 and ancho_camion > ancho_rampa:
                    restricciones.append([modelo_camion, "Camión", "No cumple ancho de acceso"])
                    continue
                if alto_camion > 0 and alto_camion > altura_acceso:
                    restricciones.append([modelo_camion, "Camión", "No cumple altura de acceso"])
                    continue

                altura_descarga = n(pala.get("Altura_max_descarga_m", 0))
                altura_carga = n(camion.get("Altura_carga_m", 0))

                if altura_descarga > 0 and altura_carga > 0 and altura_descarga < altura_carga:
                    restricciones.append([f"{modelo_pala} + {modelo_camion}", "Compatibilidad", "Altura de descarga insuficiente"])
                    continue

                carga = n(camion.get("Carga_util_t", 0))
                vmax = n(camion.get("Velocidad_kmh", 0))

                if carga <= 0 or vmax <= 0:
                    continue

                n_pases = math.ceil(carga / ton_pase)
                carga_real = min(carga, n_pases * ton_pase)

                v_cargado, v_vacio = velocidades(vmax, pendiente, rr, tipo_via)

                t_carga = (n_pases * tiempo_pala) / 60
                t_ida = (distancia_prom / v_cargado) * 60
                t_retorno = (distancia_prom / v_vacio) * 60
                t_descarga = n(camion.get("Tiempo_descarga_s", 90), 90) / 60
                t_maniobra = n(camion.get("Tiempo_maniobra_s", 90), 90) / 60

                ciclo = t_carga + t_ida + t_descarga + t_retorno + t_maniobra

                dm_camion = n(camion.get("DM", 0.90), 0.90)
                ut_camion = n(camion.get("UT", 0.85), 0.85)

                prod_camion_h = (60 / ciclo) * carga_real * dm_camion * ut_camion
                prod_camion_dia = prod_camion_h * horas
                n_camiones = math.ceil(total / prod_camion_dia)
                prod_transporte = n_camiones * prod_camion_dia

                prod_global = min(prod_perf, prod_carguio, prod_transporte)

                if prod_global < total:
                    continue

                costo_total_h = (
                    n_perf * costo_h(perf, 0.20)
                    + n_palas * costo_h(pala, 0.22)
                    + n_camiones * costo_h(camion, 0.18)
                )

                costo_dia = costo_total_h * horas
                costo_ton = costo_dia / total

                resultados.append({
                    "Perforadora": modelo_perf,
                    "Pala": modelo_pala,
                    "Camion": modelo_camion,
                    "N_perforadoras": n_perf,
                    "N_palas": n_palas,
                    "N_camiones": n_camiones,
                    "Produccion_t_dia": prod_global,
                    "Costo_USD_t": costo_ton,
                    "Costo_USD_dia": costo_dia,
                    "Ciclo_camion_min": ciclo,
                    "Vel_cargado_kmh": v_cargado,
                    "Vel_vacio_kmh": v_vacio,
                    "N_pases": n_pases,
                    "Ton_pase": ton_pase,
                    "Metros_req_dia": metros_requeridos_dia,
                    "Prod_perforacion": prod_perf,
                    "Prod_carguio": prod_carguio,
                    "Prod_transporte": prod_transporte,
                    "perf_row": perf,
                    "pala_row": pala,
                    "camion_row": camion,
                })

    df = pd.DataFrame(resultados)
    rest = pd.DataFrame(restricciones, columns=["Equipo", "Tipo", "Restricción aplicada"]).drop_duplicates()

    if df.empty:
        return df, rest

    df = df.sort_values("Costo_USD_t").reset_index(drop=True)
    return df, rest


st.markdown("""
<div class="header">
<h1>Sistema de Selección de Flota Minera</h1>
<p>Optimización técnico-económica por menor costo unitario US$/t</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.header("1. Base de datos")
archivo = st.sidebar.file_uploader("Sube el Excel de equipos", type=["xlsx"])

st.sidebar.header("2. Datos de entrada")

with st.sidebar.expander("Producción", expanded=True):
    planta = st.number_input("Capacidad de planta mineral (t/día)", value=50000.0)
    sr = st.number_input("Stripping ratio", value=2.0)
    turnos = st.number_input("Turnos por día", value=2, step=1)
    horas_turno = st.number_input("Horas por turno", value=10.0)
    horas = turnos * horas_turno
    st.info(f"Horas efectivas: {horas:.1f} h/día")

with st.sidebar.expander("Diseño del banco", expanded=True):
    densidad = st.number_input("Densidad del material (t/m³)", value=2.6)
    esponjamiento = st.number_input("Factor de esponjamiento", value=1.25)
    altura_banco = st.number_input("Altura de banco (m)", value=15.0)
    burden = st.number_input("Burden (m)", value=6.0)
    espaciamiento = st.number_input("Espaciamiento (m)", value=7.0)
    sobreperf = st.number_input("Sobreperforación (m)", value=1.5)
    diametro_req = st.number_input("Diámetro requerido (mm)", value=229.0)

with st.sidebar.expander("Acceso al tajo", expanded=True):
    ancho_rampa = st.number_input("Ancho disponible de vía/rampa (m)", value=35.0)
    altura_acceso = st.number_input("Altura máxima de acceso (m)", value=30.0)

with st.sidebar.expander("Transporte", expanded=True):
    d_planta = st.number_input("Distancia frente-planta (km)", value=2.5)
    d_botadero = st.number_input("Distancia frente-botadero (km)", value=1.8)
    pendiente = st.number_input("Pendiente de rampa (%)", value=8.0)
    rr = st.number_input("Resistencia a la rodadura (%)", value=2.0)
    tipo_via = st.selectbox("Tipo de vía", ["Excelente", "Buena", "Regular", "Mala"], index=1)

calcular = st.sidebar.button("CALCULAR FLOTA ÓPTIMA", use_container_width=True)

if archivo is None:
    st.info("Sube tu base de datos Excel para iniciar.")
    st.stop()

validar_excel(archivo)

if not calcular:
    st.success("Base cargada correctamente. Ingresa los datos y calcula la flota.")
    st.stop()

datos = {
    "planta": planta,
    "sr": sr,
    "horas": horas,
    "densidad": densidad,
    "esponjamiento": esponjamiento,
    "altura_banco": altura_banco,
    "burden": burden,
    "espaciamiento": espaciamiento,
    "sobreperf": sobreperf,
    "diametro_req": diametro_req,
    "ancho_rampa": ancho_rampa,
    "altura_acceso": altura_acceso,
    "d_planta": d_planta,
    "d_botadero": d_botadero,
    "pendiente": pendiente,
    "rr": rr,
    "tipo_via": tipo_via,
}

df, restricciones = calcular_flotas(archivo, datos)

if df.empty:
    st.error("No se encontró una flota viable.")
    if not restricciones.empty:
        st.dataframe(restricciones, use_container_width=True)
    st.stop()

mejor = df.iloc[0]
perf = mejor["perf_row"]
pala = mejor["pala_row"]
camion = mejor["camion_row"]
total = planta * (1 + sr)

st.subheader("🏆 Flota óptima seleccionada")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Material requerido", f"{total:,.0f} t/día")
k2.metric("Producción alcanzada", f"{mejor['Produccion_t_dia']:,.0f} t/día")
k3.metric("Costo unitario", f"US$ {mejor['Costo_USD_t']:.2f}/t")
k4.metric("Costo diario", f"US$ {mejor['Costo_USD_dia']:,.0f}")

st.markdown(f"""
<div class="note">
El sistema evaluó las combinaciones posibles de perforadora, pala/excavadora y camión.
Primero aplicó restricciones técnicas de acceso, perforación y compatibilidad pala-camión.
Luego eligió la alternativa que cumple <b>{total:,.0f} t/día</b> con menor costo unitario.
</div>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("## Perforadora")
    imagen(perf, "🛠️")
    st.markdown(f"<div class='name'>{mejor['Perforadora']}</div>", unsafe_allow_html=True)
    st.metric("Cantidad", int(mejor["N_perforadoras"]))
    st.write(f"Potencia: {perf.get('Potencia_HP','-')} HP")
    st.write(f"Diámetro: {perf.get('Diametro_min_mm','-')} - {perf.get('Diametro_max_mm','-')} mm")
    st.write(f"Profundidad máxima: {perf.get('Profundidad_max_m','-')} m")
    st.write(f"Velocidad perforación: {perf.get('Velocidad_perforacion_m_h','-')} m/h")
    st.write(f"Metros requeridos: {mejor['Metros_req_dia']:,.0f} m/día")

with c2:
    st.markdown("## Pala / Excavadora")
    imagen(pala, "⛏️")
    st.markdown(f"<div class='name'>{mejor['Pala']}</div>", unsafe_allow_html=True)
    st.metric("Cantidad", int(mejor["N_palas"]))
    st.write(f"Balde: {pala.get('Capacidad_balde_m3','-')} m³")
    st.write(f"Factor llenado: {pala.get('Factor_llenado','-')}")
    st.write(f"Tiempo ciclo: {pala.get('Tiempo_ciclo_pala_s','-')} s")
    st.write(f"Toneladas por pase: {mejor['Ton_pase']:.2f} t")
    st.write(f"Producción carguío: {mejor['Prod_carguio']:,.0f} t/día")

with c3:
    st.markdown("## Camión")
    imagen(camion, "🚚")
    st.markdown(f"<div class='name'>{mejor['Camion']}</div>", unsafe_allow_html=True)
    st.metric("Cantidad", int(mejor["N_camiones"]))
    st.write(f"Carga útil: {camion.get('Carga_util_t','-')} t")
    st.write(f"Velocidad cargado: {mejor['Vel_cargado_kmh']:.2f} km/h")
    st.write(f"Velocidad vacío: {mejor['Vel_vacio_kmh']:.2f} km/h")
    st.write(f"Tiempo ciclo: {mejor['Ciclo_camion_min']:.2f} min")
    st.write(f"N° pases: {int(mejor['N_pases'])}")

st.divider()

st.subheader("Combinaciones evaluadas")
vista = df.head(15)[[
    "Perforadora",
    "Pala",
    "Camion",
    "N_perforadoras",
    "N_palas",
    "N_camiones",
    "Produccion_t_dia",
    "Costo_USD_t",
    "Costo_USD_dia",
]]
st.dataframe(vista, use_container_width=True)

st.subheader("Restricciones técnicas aplicadas")
if restricciones.empty:
    st.success("No hubo equipos descartados por restricciones técnicas.")
else:
    st.dataframe(restricciones, use_container_width=True)

st.download_button(
    "Descargar combinaciones evaluadas CSV",
    vista.to_csv(index=False).encode("utf-8"),
    "combinaciones_evaluadas.csv",
    "text/csv",
    use_container_width=True
)