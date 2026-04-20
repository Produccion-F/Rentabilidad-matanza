import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import unicodedata
import gspread
from google.oauth2.service_account import Credentials
import re
import json

# --- CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(page_title="Matanza Óptima", layout="wide", page_icon="🐖")

# ==========================================
# 🔒 SISTEMA DE SEGURIDAD (CONTRASEÑA)
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h1 style='text-align: center; color: #1b5e20;'>🔒 Acceso Restringido</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Por favor, introduce la clave para acceder al simulador.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("Contraseña:", type="password")
        if st.button("Entrar", use_container_width=True):
            if pwd == "comerprod26":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta")
    st.stop()
# ==========================================

st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: #f8f9fa; border-top: 4px solid #2e7d32; border-radius: 5px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); color: #333; }
    [data-testid="stMetricLabel"] { color: #2e7d32; font-weight: bold; font-size: 14px; }
    [data-testid="stMetricValue"] { font-size: 24px; color: #1a1a1a; }
    h1, h2, h3 { color: #1b5e20; }
    </style>
""", unsafe_allow_html=True)

# =====================================================================
# ⚠️ PON AQUÍ LAS URLs DE TUS EXCELS PRIVADOS (Desde la barra del navegador)
# =====================================================================
URL_ESCANDALLOS = 'https://docs.google.com/spreadsheets/d/1nGSUQGspPnvkkSD0qmlYqhhfXAEAqbN1vm5DTPhaDkM/edit?gid=0#gid=0'
URL_VENTAS = 'https://docs.google.com/spreadsheets/d/1kyiTFjTl-XxkwhYQlm6FjMbnZWhNR4-AtW3iFj2qXzs/edit?gid=1543847315#gid=1543847315'
URL_EQUIVALENCIAS = 'https://docs.google.com/spreadsheets/d/1nGSUQGspPnvkkSD0qmlYqhhfXAEAqbN1vm5DTPhaDkM/edit?gid=1911720872#gid=1911720872'
URL_SUSTITUCIONES = 'https://docs.google.com/spreadsheets/d/1nGSUQGspPnvkkSD0qmlYqhhfXAEAqbN1vm5DTPhaDkM/edit?gid=69264992#gid=69264992'

# --- CONEXIÓN SEGURA A GOOGLE SHEETS ---
@st.cache_resource(show_spinner=False)
def init_gcp_connection():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = json.loads(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Error de Conexión a Google Cloud: Revisa los Secrets. Detalle: {e}")
        return None

def get_df_from_gspread(url):
    if "PEGAR_AQUI" in url:
        raise ValueError("URL no configurada. Por favor, pon tu enlace privado en el código.")
        
    gc = init_gcp_connection()
    if not gc: 
        raise ValueError("No se pudo conectar a Google Cloud.")
        
    base_url = url.split('#')[0]
    match = re.search(r'gid=([0-9]+)', url)
    gid = int(match.group(1)) if match else 0
    try:
        sh = gc.open_by_url(base_url)
        ws = next((w for w in sh.worksheets() if w.id == gid), sh.sheet1)
        data = ws.get_all_values()
        if not data: 
            raise ValueError("El archivo Excel devuelto está completamente vacío.")
        headers = data.pop(0)
        return pd.DataFrame(data, columns=headers)
    except Exception as e:
        raise Exception(f"No se pudo leer la pestaña (Asegúrate de que el Robot tiene acceso). Detalle: {e}")

# --- FUNCIONES AUXILIARES ---
def clean_float(x):
    if pd.isna(x): return 0.0
    s = str(x).strip().replace('%', '')
    if not s: return 0.0
    try: return float(s)
    except:
        try: return float(s.replace('.', '').replace(',', '.'))
        except: return 0.0

def normalizar_texto(texto):
    if not isinstance(texto, str): return str(texto)
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')

def convert_df_to_excel_csv(df):
    return df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')

# --- FUNCIÓN DE TABLAS NATIVAS DE STREAMLIT (SIN AGGRID) ---
def mostrar_tabla_aggrid(df, height=400, currency_cols=[], kg_cols=[], pct_cols=[], num_cols=[], heatmap_cols=[], hidden_cols=[], key=None, selection_mode='single'):
    display_df = df.copy()
    
    # Configuración nativa de columnas para que se vean muy visuales
    col_config = {}
    
    # Ocultar columnas nativamente
    for col in hidden_cols:
        if col in display_df.columns:
            col_config[col] = None 
            
    # Formatos de número personalizados
    for col in currency_cols:
        if col in display_df.columns: 
            col_config[col] = st.column_config.NumberColumn(format="%.2f €")
    for col in kg_cols:
        if col in display_df.columns: 
            col_config[col] = st.column_config.NumberColumn(format="%.2f kg")
    for col in pct_cols:
        if col in display_df.columns: 
            col_config[col] = st.column_config.NumberColumn(format="%.2f %%")
    for col in num_cols:
        if col in display_df.columns: 
            col_config[col] = st.column_config.NumberColumn(format="%d")
            
    # Sustituimos el heatmap de AgGrid por unas Barras de Progreso visuales nativas de Streamlit
    for col in heatmap_cols:
        if col in display_df.columns:
            max_val = float(display_df[col].max()) if not display_df.empty else 1.0
            if pd.isna(max_val) or max_val <= 0: max_val = 1.0
            col_config[col] = st.column_config.ProgressColumn(
                format="%d",
                min_value=0,
                max_value=max_val
            )

    toggle_key = f"toggle_full_{key}" if key else f"toggle_full_{id(df)}"
    final_height = height
    if st.checkbox("⤢ Maximizar Tabla", key=toggle_key): final_height = 800

    # Intentamos cargar la tabla interactiva de las nuevas versiones de Streamlit
    try:
        event = st.dataframe(
            display_df,
            height=final_height,
            use_container_width=True,
            column_config=col_config,
            on_select="rerun",
            selection_mode="single-row",
            key=key
        )
        
        selected_rows = []
        if event and hasattr(event, 'selection') and event.selection.rows:
            idx = event.selection.rows[0]
            selected_rows = [df.iloc[idx].to_dict()]
            
        # Devolvemos la estructura exacta que esperaba tu código original para no romper NADA
        return {'selected_rows': selected_rows}
        
    except TypeError:
        # Fallback de seguridad si el servidor de Streamlit usa una versión antigua
        st.dataframe(
            display_df,
            height=final_height,
            use_container_width=True,
            column_config=col_config,
            key=key
        )
        return {'selected_rows': []}

# --- CARGA DATOS (VERSIÓN PRIVADA GSPREAD) ---
def load_and_clean_data_raw():
    errores = []
    
    try:
        df_e = get_df_from_gspread(URL_ESCANDALLOS)
        rename_map = {}
        for col in df_e.columns:
            limpio = normalizar_texto(col)
            if limpio == 'escandallo' or limpio == 'id': rename_map[col] = 'Escandallo_ID'
            elif 'codigo' in limpio and 'escandallo' not in limpio: rename_map[col] = 'Codigo'
            elif 'exw' in limpio or ('precio' in limpio and 'escandallo' not in limpio): rename_map[col] = 'Precio'
            elif 'cantidad' in limpio or 'peso' in limpio: rename_map[col] = 'Peso'
            elif 'familia' in limpio: rename_map[col] = 'Familia'
            elif 'nombre' in limpio: rename_map[col] = 'Nombre'
            elif 'tipo' in limpio: rename_map[col] = 'Tipo'
        df_e.rename(columns=rename_map, inplace=True)
        df_e = df_e.loc[:, ~df_e.columns.duplicated()]
        if 'Peso' in df_e.columns: df_e['Peso'] = df_e['Peso'].apply(clean_float)
        if 'Precio' in df_e.columns: df_e['Precio'] = df_e['Precio'].apply(clean_float)
        if 'Escandallo_ID' in df_e.columns and 'Peso' in df_e.columns:
            df_e['Total_Grupo'] = df_e.groupby('Escandallo_ID')['Peso'].transform('sum')
            df_e['Pct_Rendimiento'] = np.where(df_e['Total_Grupo']>0, df_e['Peso']/df_e['Total_Grupo'], 0)
    except Exception as e: return None, None, None, None, [f"Error en Escandallos: {e}"]

    try:
        df_v = get_df_from_gspread(URL_VENTAS)
        rename_map_v = {}
        for col in df_v.columns:
            limpio = normalizar_texto(col)
            if limpio == 'codigo': rename_map_v[col] = 'Codigo'
            elif 'cliente' in limpio: rename_map_v[col] = 'Cliente'
            elif limpio == 'nombre' or 'articulo' in limpio: rename_map_v[col] = 'Articulo'
            elif 'kilos' in limpio: rename_map_v[col] = 'Kilos'
            elif 'precio' in limpio: rename_map_v[col] = 'Precio'
        df_v.rename(columns=rename_map_v, inplace=True)
        df_v = df_v.loc[:, ~df_v.columns.duplicated()]
        if 'Codigo' in df_v.columns: df_v['Codigo'] = df_v['Codigo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        for c in ['Kilos', 'Precio']:
            if c in df_v.columns: df_v[c] = df_v[c].apply(clean_float)
    except Exception as e: return None, None, None, None, [f"Error en Ventas: {e}"]

    try:
        df_eq = get_df_from_gspread(URL_EQUIVALENCIAS)
        rename_map_eq = {}
        for col in df_eq.columns:
            limpio = normalizar_texto(col)
            if limpio == 'codigo' and 'principal' not in limpio: rename_map_eq[col] = 'Codigo_Origen'
            elif 'escandallo' in limpio: rename_map_eq[col] = 'Escandallo_Destino'
            elif 'principal' in limpio: rename_map_eq[col] = 'Codigo_Principal'
        df_eq.rename(columns=rename_map_eq, inplace=True)
        if 'Codigo_Origen' in df_eq.columns: df_eq['Codigo_Origen'] = df_eq['Codigo_Origen'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        if 'Codigo_Principal' in df_eq.columns: df_eq['Codigo_Principal'] = df_eq['Codigo_Principal'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    except Exception as e:
        df_eq = pd.DataFrame()
        errores.append(f"Aviso Equivalencias: {e}")

    try:
        df_raw = get_df_from_gspread(URL_SUSTITUCIONES)
        col_origen = None
        cols_destino = []
        for col in df_raw.columns:
            limpio = normalizar_texto(col)
            if 'original' in limpio or 'origen' in limpio: col_origen = col
            elif 'alt' in limpio or 'sust' in limpio: cols_destino.append(col)

        pairs = []
        if col_origen:
            for _, row in df_raw.iterrows():
                orig = str(row[col_origen]).replace('.0', '').strip()
                if not orig or orig.lower() == 'nan': continue
                for c_dest in cols_destino:
                    dest = str(row[c_dest]).replace('.0', '').strip()
                    if dest and dest.lower() != 'nan':
                        pairs.append({'Codigo_Origen': orig, 'Codigo_Destino': dest})
            df_sust = pd.DataFrame(pairs)
        else:
            df_sust = df_raw.copy()
            rename_sust = {}
            for col in df_sust.columns:
                limpio = normalizar_texto(col)
                if 'origen' in limpio: rename_sust[col] = 'Codigo_Origen'
                elif 'destino' in limpio: rename_sust[col] = 'Codigo_Destino'
            df_sust.rename(columns=rename_sust, inplace=True)

        if 'Codigo_Origen' in df_sust.columns: df_sust['Codigo_Origen'] = df_sust['Codigo_Origen'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        if 'Codigo_Destino' in df_sust.columns: df_sust['Codigo_Destino'] = df_sust['Codigo_Destino'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    except Exception as e:
        df_sust = pd.DataFrame()
        errores.append(f"Aviso Sustituciones: {e}")

    return df_e, df_v, df_eq, df_sust, errores

# --- SIMULACIÓN (LÓGICA INTACTA) ---
@st.cache_data(show_spinner="Recalculando simulación...", ttl=3600)
def run_simulation(df_esc, df_ven, df_eq, df_sust, target_config, forced_pigs_target=0, manual_overrides={}):
    log = []
    warnings_mapping = []
    simulated_parts_log = set()

    df_ven_proc = df_ven.copy()

    if manual_overrides:
        count_manual = 0
        for cod_man, precio_man in manual_overrides.items():
            mask = df_ven_proc['Codigo'] == str(cod_man).strip()
            if mask.any():
                df_ven_proc.loc[mask, 'Precio'] = float(precio_man)
                df_ven_proc.loc[mask, 'Cliente'] = '🔧 SIMULACIÓN MANUAL'
                count_manual += 1
        if count_manual > 0:
            log.append(f"🛠️ Se han aplicado precios manuales a {count_manual} artículos.")
    
    ventas_reales = df_ven_proc[df_ven_proc['Cliente'].str.strip().str.upper() != "ENTRADAS A CONGELAR"].copy()
    ventas_reales = ventas_reales[ventas_reales['Precio'] > 0].copy()
    ventas_reales['Valor_Total'] = ventas_reales['Kilos'] * ventas_reales['Precio']
    agrupado_mercado = ventas_reales.groupby('Codigo').agg({'Valor_Total': 'sum', 'Kilos': 'sum'})
    agrupado_mercado['Precio_Medio'] = np.where(agrupado_mercado['Kilos'] > 0, agrupado_mercado['Valor_Total'] / agrupado_mercado['Kilos'], 0)
    mapa_precios_mercado = agrupado_mercado['Precio_Medio'].to_dict()

    mapa_relaciones = {}
    if not df_sust.empty and 'Codigo_Origen' in df_sust.columns and 'Codigo_Destino' in df_sust.columns:
        for _, row in df_sust.iterrows():
            o, d = str(row['Codigo_Origen']).strip(), str(row['Codigo_Destino']).strip()
            if o and d:
                if o not in mapa_relaciones: mapa_relaciones[o] = []
                mapa_relaciones[o].append(d)
    
    if not df_eq.empty and 'Codigo_Origen' in df_eq.columns and 'Codigo_Principal' in df_eq.columns:
        for _, row in df_eq.iterrows():
            o, d = str(row['Codigo_Origen']).strip(), str(row['Codigo_Principal']).strip()
            if o and d and d.lower() != 'nan':
                if o not in mapa_relaciones: mapa_relaciones[o] = []
                mapa_relaciones[o].append(d)

    count_arreglados_directo, count_arreglados_indirecto = 0, 0
    indices_a_eliminar = []

    for idx, row in df_ven_proc.iterrows():
        cliente_limpio = str(row.get('Cliente', '')).strip().upper()
        if cliente_limpio == '🔧 SIMULACIÓN MANUAL': continue

        precio_actual = float(row.get('Precio', 0))
        if cliente_limpio == "ENTRADAS A CONGELAR" or precio_actual <= 0.0001:
            cod = str(row.get('Codigo', '')).strip()
            nuevo_precio, motivo = 0, ""

            if cod in mapa_precios_mercado and mapa_precios_mercado[cod] > 0:
                nuevo_precio = mapa_precios_mercado[cod]
                motivo = "Ref. Mercado Directo"
                count_arreglados_directo += 1
            elif cod in mapa_relaciones:
                precios_encontrados = []
                for rel_cod in mapa_relaciones[cod]:
                    ventas_sust = ventas_reales[ventas_reales['Codigo'] == rel_cod]
                    if not ventas_sust.empty:
                        min_p = ventas_sust['Precio'].min()
                        if min_p > 0: precios_encontrados.append(min_p)
                if precios_encontrados:
                    nuevo_precio = min(precios_encontrados)
                    motivo = "Ref. Indirecta (Mínimo)"
                    count_arreglados_indirecto += 1
            
            if nuevo_precio > 0:
                df_ven_proc.at[idx, 'Precio'] = nuevo_precio
                df_ven_proc.at[idx, 'Cliente'] = f"{cliente_limpio} [{motivo}]"
            else:
                indices_a_eliminar.append(idx)

    df_rechazados = df_ven_proc.loc[indices_a_eliminar].copy()
    df_ven_proc = df_ven_proc.drop(indices_a_eliminar)
    log.append(f"Sanidad Stock: {count_arreglados_directo} directos, {count_arreglados_indirecto} indirectos (Peor Precio).")
    log.append(f"Sanidad Stock: {len(indices_a_eliminar)} partidas RECHAZADAS por falta de precio.")

    catalogo_info = {}
    if 'Codigo' in df_esc.columns:
        for _, row in df_esc.iterrows():
            c = str(row['Codigo']).replace('.0', '').strip()
            if c: catalogo_info[c] = {'Nombre': row.get('Nombre', 'Desconocido'), 'Tipo': row.get('Tipo', 'Desconocido')}

    df_esc['Esc_Key'] = df_esc['Escandallo_ID'].astype(str)
    df_esc['Cod_Key'] = df_esc['Codigo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    pares_existentes = set(zip(df_esc['Esc_Key'], df_esc['Cod_Key']))

    recetas = {}
    if 'Escandallo_ID' not in df_esc.columns: return pd.DataFrame(), pd.DataFrame(), [f"Fallo columnas Escandallo"], {}, [], 0, pd.DataFrame(), {}
    grupos = df_esc.groupby('Escandallo_ID')

    for eid, grp in grupos:
        fam_raw = " ".join(grp['Familia'].astype(str).unique()).lower() if 'Familia' in grp.columns else "otros"
        fam = "Otros"
        if 'jamon' in fam_raw: fam = 'Jamon'
        elif 'paleta' in fam_raw: fam = 'Paleta'
        elif 'chuleta' in fam_raw or 'lomo' in fam_raw: fam = 'Chuleta'
        elif 'panceta' in fam_raw: fam = 'Panceta'
        elif 'cabeza' in fam_raw: fam = 'Cabeza'
        elif 'papada' in fam_raw: fam = 'Papada'

        lista_secundarios = []
        lista_principales = []

        for _, row in grp.iterrows():
            es_principal = False
            raw_tipo = str(row.get('Tipo', '')).lower()
            if 'principal' in raw_tipo: es_principal = True
            elif 'secundario' in raw_tipo: es_principal = False
            elif row.get('Pct_Rendimiento', 0) > 0.4: es_principal = True

            datos_item = {
                'Codigo': str(row.get('Codigo', '')).replace('.0', '').strip(),
                'Pct': row['Pct_Rendimiento'],
                'PrecioTeorico': row['Precio'],
                'Nombre': row.get('Nombre', '')
            }
            if es_principal: lista_principales.append(datos_item)
            else: lista_secundarios.append(datos_item)

        for p in lista_principales:
            cod = p['Codigo']
            if not cod: continue
            valor_sec_teorico = sum([s['Pct'] * s['PrecioTeorico'] for s in lista_secundarios])
            recetas[cod] = {
                'Familia': fam, 'Pct': p['Pct'], 'Secundarios': lista_secundarios, 'Escandallo_ID': eid,
                'Nombre_Principal': p['Nombre'], 'Precio_Teorico_Principal': p['PrecioTeorico'], 'Valor_Secundarios_Teorico': valor_sec_teorico 
            }
    log.append(f"Recetas Activas: {len(recetas)}")

    mapa_equivalencias = {}
    if not df_eq.empty and 'Codigo_Origen' in df_eq.columns and 'Escandallo_Destino' in df_eq.columns and 'Codigo_Principal' in df_eq.columns:
        for _, row in df_eq.iterrows():
            orig, dest_esc, dest_cod = str(row['Codigo_Origen']).strip(), str(row['Escandallo_Destino']).strip(), str(row['Codigo_Principal']).strip()
            if (dest_esc, dest_cod) in pares_existentes: mapa_equivalencias[orig] = dest_cod
            else: warnings_mapping.append(f"❌ Error Mapeo: {orig} -> {dest_esc}/{dest_cod} no existe en Escandallos.")

    mapa_sustituciones = {}
    mapa_sustituciones_list = {}
    if not df_sust.empty and 'Codigo_Origen' in df_sust.columns and 'Codigo_Destino' in df_sust.columns:
        for _, row in df_sust.iterrows():
            orig, dest = str(row['Codigo_Origen']).strip(), str(row['Codigo_Destino']).strip()
            if dest in recetas or dest in mapa_equivalencias: mapa_sustituciones[orig] = dest
            if orig not in mapa_sustituciones_list: mapa_sustituciones_list[orig] = []
            mapa_sustituciones_list[orig].append(dest)

    cajones = {k: [] for k in target_config.keys()}
    last_known_item_meta = {}
    stock_secundarios = {}
    sobrantes_temp = []
    
    for _, row in df_rechazados.iterrows():
        sobrantes_temp.append({'Familia': 'Desconocido', 'Codigo': str(row.get('Codigo')), 'Nombre': str(row.get('Articulo')), 'Tipo': 'RECHAZADO (Congelado 0€)', 'Kg': row.get('Kilos'), 'Motivo': 'Sin precio referencia (Directo/Indir)'})

    count_vinculados_mapeo = 0 
    ventas_dict = df_ven_proc.to_dict('records')

    for venta in ventas_dict:
        cod, kg_venta, pr = str(venta.get('Codigo', '')).strip(), float(venta.get('Kilos', 0)), float(venta.get('Precio', 0))
        cliente, articulo_nom = str(venta.get('Cliente', 'Varios')), str(venta.get('Articulo', str(cod)))
        if not cod or cod == 'nan' or kg_venta <= 0: continue

        es_driver, cod_para_receta, es_sustitucion = False, cod, False

        if cod in recetas: es_driver = True; info = recetas[cod]
        elif cod in mapa_equivalencias: es_driver = True; cod_para_receta = mapa_equivalencias[cod]; info = recetas.get(cod_para_receta); count_vinculados_mapeo += 1
        elif cod in mapa_sustituciones: es_driver = True; cod_para_receta = mapa_sustituciones[cod]; info = recetas.get(cod_para_receta); es_sustitucion = True

        if es_driver and info:
            fam_receta = info['Familia']
            match = False
            for target_key in cajones.keys():
                if target_key.lower() == fam_receta.lower():
                    pct_rendimiento = info['Pct']
                    cp_estimado = (pr * pct_rendimiento) + info.get('Valor_Secundarios_Teorico', 0) if pct_rendimiento > 0 else pr 
                    kg_anatomicos_reales = kg_venta / pct_rendimiento if pct_rendimiento > 0 else kg_venta
                    cajones[target_key].append({'Kg': kg_anatomicos_reales, 'Val': 0, 'Codigo': cod, 'Codigo_Receta': cod_para_receta, 'Nombre': articulo_nom, 'Cliente': cliente, 'Precio_EXW': pr, 'CP_Estimado_Sort': cp_estimado, 'Kg_Venta_Original': kg_venta, 'Familia': fam_receta, 'Es_Sustitucion': es_sustitucion})
                    match = True; break
            if not match: sobrantes_temp.append({'Familia': fam_receta, 'Codigo': cod, 'Nombre': articulo_nom, 'Tipo': 'Familia no config', 'Kg': kg_venta, 'Motivo': f"Familia '{fam_receta}' no configurada"})
        else:
            if cod not in stock_secundarios: stock_secundarios[cod] = []
            stock_secundarios[cod].append({'Kg': kg_venta, 'Precio': pr, 'Cliente': cliente, 'Nombre': articulo_nom})

    for k in cajones:
        cajones[k].sort(key=lambda x: -x['CP_Estimado_Sort'])
        if cajones[k]: last_known_item_meta[k] = cajones[k][-1]

    auditoria_secundarios = []
    def casar_secundario(cod_necesario, kg_necesarios, precio_teorico, nombre_teorico, escandallo_id):
        valor_recuperado, kg_pendientes, clientes_involucrados = 0, kg_necesarios, set()

        if cod_necesario in stock_secundarios:
            for v in stock_secundarios[cod_necesario]:
                if kg_pendientes <= 0.0001: break
                if v['Kg'] > 0:
                    tomar = min(kg_pendientes, v['Kg'])
                    valor_recuperado += tomar * v['Precio']
                    v['Kg'] -= tomar
                    kg_pendientes -= tomar
                    clientes_involucrados.add(str(v['Cliente']))

        if kg_pendientes > 0.0001 and cod_necesario in mapa_sustituciones_list:
            candidatos = mapa_sustituciones_list[cod_necesario]
            pool_candidatos = []
            for cand in candidatos:
                if cand in stock_secundarios:
                    for v in stock_secundarios[cand]:
                        if v['Kg'] > 0: pool_candidatos.append({'datos': v, 'cod_sust': cand})
            pool_candidatos.sort(key=lambda x: x['datos']['Precio'], reverse=True)
            for cand_obj in pool_candidatos:
                if kg_pendientes <= 0.0001: break
                v = cand_obj['datos']
                tomar = min(kg_pendientes, v['Kg'])
                valor_recuperado += tomar * v['Precio']
                v['Kg'] -= tomar
                kg_pendientes -= tomar
                clientes_involucrados.add(f"{v['Cliente']} (Sust)")

        if kg_pendientes > 0.0001:
            valor_inventado = kg_pendientes * precio_teorico
            valor_recuperado += valor_inventado
            auditoria_secundarios.append({'Escandallo_ID': escandallo_id, 'Codigo': cod_necesario, 'Nombre': nombre_teorico, 'Tipo_Casacion': '3. Inventado (Teórico)', 'Kg_Usados': kg_pendientes, 'Precio_Aplicado': precio_teorico, 'Valor': valor_inventado})
            kg_pendientes = 0
            clientes_involucrados.add("⚠️ ESTIMADO (Sin Venta)")

        return valor_recuperado, ", ".join(list(clientes_involucrados))

    cursors = {k: {'idx': 0, 'rem': cajones[k][0]['Kg'] if cajones[k] else 0} for k in cajones}
    cerdos, causa_parada = [], "Límite seguridad alcanzado"
    prog = st.progress(0)
    LOOP_LIMIT = forced_pigs_target if forced_pigs_target > 0 else 1000000

    for i in range(LOOP_LIMIT):
        if i % 100 == 0: prog.progress(min(i/max(LOOP_LIMIT, 1000), 1.0))

        possible, missing_part = True, ""
        for p, tgt in target_config.items():
            if tgt <= 0: continue
            has_stock = cursors[p]['idx'] < len(cajones[p])
            if not has_stock:
                if forced_pigs_target > 0:
                    if p not in simulated_parts_log:
                        simulated_parts_log.add(p)
                        log.append(f"⚠️ AVISO: A partir del cerdo {i+1} se agotó '{p}'. Iniciando SIMULACIÓN con el peor precio histórico.")
                else: possible = False; missing_part = p; break

        if not possible: causa_parada = f"Se agotó: {missing_part}"; break

        coste_cerdo, peso_referencia_cerdo, componentes_driver = 0, 0, []

        for p, tgt in target_config.items():
            if tgt <= 0: continue
            needed = tgt

            while needed > 0.001:
                item_data, is_simulated = None, False

                if cursors[p]['idx'] < len(cajones[p]):
                    item_data = cajones[p][cursors[p]['idx']]
                    take = min(needed, cursors[p]['rem'])
                    cursors[p]['rem'] -= take
                    if cursors[p]['rem'] <= 0.001:
                        cursors[p]['idx'] += 1
                        if cursors[p]['idx'] < len(cajones[p]): cursors[p]['rem'] = cajones[p][cursors[p]['idx']]['Kg']
                elif forced_pigs_target > 0:
                    is_simulated = True
                    plantilla = last_known_item_meta.get(p)
                    if plantilla:
                        take = needed
                        item_data = {'Codigo': plantilla['Codigo'], 'Codigo_Receta': plantilla['Codigo_Receta'], 'Nombre': plantilla['Nombre'], 'Cliente': '🔮 SIMULADO (Peor Histórico)', 'Precio_EXW': plantilla['Precio_EXW'], 'Familia': plantilla['Familia'], 'Simulado': True}
                    else: possible = False; causa_parada = f"Error crítico: No hay histórico para simular {p}"; break
                else: possible = False; causa_parada = f"Se agotó: {p}"; break

                if not possible: break

                receta_usada = recetas[item_data['Codigo_Receta']]
                factor_principal = receta_usada['Pct']
                kg_venta_imputados = take * factor_principal
                precio_exw = item_data['Precio_EXW']
                valor_venta_principal = kg_venta_imputados * precio_exw

                breakdown_pig = [{'Escandallo': receta_usada['Escandallo_ID'], 'Tipo': '⭐ PRINCIPAL', 'Codigo': item_data['Codigo'], 'Articulo': item_data['Nombre'], 'Cliente': item_data['Cliente'], '% Rendimiento': f"{factor_principal*100:.2f}%", 'Precio Aplicado (€)': precio_exw, 'Contribución (€)': factor_principal * precio_exw}]

                valor_recuperado_secundarios = 0
                if factor_principal > 0:
                    base_calculo = take
                    for sec in receta_usada['Secundarios']:
                        kg_sec_generados = base_calculo * sec['Pct']
                        val_rec, cliente_sec_str = casar_secundario(sec['Codigo'], kg_sec_generados, sec['PrecioTeorico'], sec['Nombre'], receta_usada['Escandallo_ID'])
                        valor_recuperado_secundarios += val_rec
                        precio_real_medio = val_rec / kg_sec_generados if kg_sec_generados > 0 else 0
                        breakdown_pig.append({'Escandallo': receta_usada['Escandallo_ID'], 'Tipo': '🔹 SECUNDARIO', 'Codigo': sec['Codigo'], 'Articulo': sec['Nombre'], 'Cliente': cliente_sec_str, '% Rendimiento': f"{sec['Pct']*100:.2f}%", 'Precio Aplicado (€)': precio_real_medio, 'Contribución (€)': val_rec / take})

                valor_total_operacion = valor_venta_principal + valor_recuperado_secundarios
                precio_cp = valor_total_operacion / take if take > 0 else 0
                breakdown_pig.append({'Escandallo': '', 'Tipo': '', 'Codigo': '', 'Articulo': 'TOTAL RECONSTITUIDO', 'Cliente': '', '% Rendimiento': '100%', 'Precio Aplicado (€)': None, 'Contribución (€)': precio_cp})

                coste_cerdo += valor_total_operacion
                componentes_driver.append({'C': item_data['Cliente'], 'A': item_data['Nombre'], 'P': precio_exw, 'CP': precio_cp, 'K': kg_venta_imputados, 'F': item_data.get('Familia', 'Otros'), 'Cod': item_data['Codigo'], 'Origen': "⚠️ SIMULADO" if is_simulated else "Real", 'Breakdown': breakdown_pig})
                needed -= take

            if not possible: break
            peso_referencia_cerdo += tgt

        if not possible or coste_cerdo == 0: break
        cerdos.append({'ID': i+1, 'Precio_Total': coste_cerdo, 'Precio_Medio': coste_cerdo/peso_referencia_cerdo, 'Detalles': componentes_driver})

    prog.empty()
    if forced_pigs_target > 0 and len(cerdos) >= forced_pigs_target: causa_parada = f"Objetivo de {forced_pigs_target} cerdos alcanzado (Simulación forzada)."
    log.append(f"🛑 Detenido. {causa_parada}")

    sobrantes_finales = sobrantes_temp.copy()
    for cod, lista_lotes in stock_secundarios.items():
        for lote in lista_lotes:
            if lote['Kg'] > 0.01: sobrantes_finales.append({'Familia': 'Secundario', 'Codigo': cod, 'Nombre': lote['Nombre'], 'Tipo': 'Resto Stock', 'Kg': lote['Kg'], 'Motivo': 'No hubo driver suficiente para consumirlo'})

    return pd.DataFrame(cerdos), pd.DataFrame(sobrantes_finales), log, cajones, warnings_mapping, count_vinculados_mapeo, pd.DataFrame(auditoria_secundarios), recetas

# --- UI PRINCIPAL ---
st.title("🐖 Rentabilidad Matanza")
if 'raw_data' not in st.session_state: st.session_state.raw_data = None
if 'desgloses_db' not in st.session_state: st.session_state.desgloses_db = {}
if 'manual_prices' not in st.session_state: st.session_state.manual_prices = {}

with st.sidebar:
    st.header("⚙️ Configuración Global")
    
    with st.expander("🛠️ Simulador de Precios (Lab)", expanded=False):
        st.caption("Sobrescribe precios reales para simular escenarios.")
        col_s1, col_s2 = st.columns([1, 1])
        with col_s1: code_sim = st.text_input("Código Artículo").strip()
        with col_s2: price_sim = st.number_input("Nuevo Precio (€)", min_value=0.0, step=0.01)
        
        if st.button("➕ Añadir Regla Manual") and code_sim:
            st.session_state.manual_prices[code_sim] = price_sim
            st.success(f"Regla: {code_sim} -> {price_sim}€")
        
        if st.session_state.manual_prices:
            st.divider()
            st.caption("Reglas Activas:")
            claves_borrar = []
            for k, v in st.session_state.manual_prices.items():
                col_d1, col_d2 = st.columns([3, 1])
                col_d1.text(f"{k}: {v:.2f} €")
                if col_d2.button("❌", key=f"del_{k}"): claves_borrar.append(k)
            
            for k in claves_borrar: del st.session_state.manual_prices[k]; st.rerun()
            if st.button("🗑️ Borrar Todo"): st.session_state.manual_prices = {}; st.rerun()

    if st.button("🔄 Cargar/Actualizar Datos (Google)", type="secondary"):
        with st.spinner("Descargando datos de Google Sheets Privados..."):
            datos = load_and_clean_data_raw()
            if datos[4]:
                for e in datos[4]: st.error(e)
            else:
                st.session_state.raw_data = datos
                st.success("Datos actualizados correctamente.")

    st.divider()
    precio_compra = st.number_input("Precio Canal (€/kg) [Pestaña 1]", value=2.10, step=0.01, min_value=0.0)
    coste_ind = st.number_input("Coste Ind. (€/kg) [Pestaña 1]", value=0.35, step=0.01, min_value=0.0)

    st.divider()
    modo_forzado = st.checkbox("🔮 Simular N Cerdos (Forzar)", value=False)
    target_pigs = 0
    if modo_forzado:
        target_pigs = st.number_input("Objetivo de Cerdos a Simular:", min_value=1, value=5000, step=100)

    st.divider()
    peso = st.number_input("Peso Canal Neto (Kg)", value=93.00, min_value=0.1)
    c1, c2 = st.columns(2)
    p_jamon = c1.number_input("% Jamón", value=33.00, step=0.01, min_value=0.0)
    p_paleta = c2.number_input("% Paleta", value=17.30, step=0.01, min_value=0.0)
    p_chuleta = c1.number_input("% Chuleta", value=26.00, step=0.01, min_value=0.0)
    p_panceta = c2.number_input("% Panceta", value=15.8, step=0.01, min_value=0.0)
    p_cabeza = c1.number_input("% Cabeza", value=5.20, step=0.01, min_value=0.0)
    p_papada = c2.number_input("% Papada", value=2.70, step=0.01, min_value=0.0)
    config = {'Jamon': (p_jamon/100)*peso, 'Paleta': (p_paleta/100)*peso, 'Chuleta': (p_chuleta/100)*peso, 'Panceta': (p_panceta/100)*peso, 'Cabeza': (p_cabeza/100)*peso, 'Papada': (p_papada/100)*peso}
    st.info(f"Total Kg: {sum(config.values()):.2f}")

if st.session_state.raw_data is None:
    st.info("👋 Para empezar, pulsa 'Cargar Datos' en el panel lateral.")
else:
    esc, ven, eq, sus, err = st.session_state.raw_data

    # --- CREACIÓN DE LAS DOS PESTAÑAS (RECUPERADAS Y BLINDADAS) ---
    tab_main, tab_sim = st.tabs(["🔬 Análisis Detallado", "📊 Comparador de Escenarios (What-If)"])

    # =========================================================
    # PESTAÑA 1: EL PROGRAMA ORIGINAL INTACTO
    # =========================================================
    with tab_main:
        df, df_s, logs, cajones_res, warnings_map, total_mapeados, df_audit_sec, recetas_db = run_simulation(esc, ven, eq, sus, config, target_pigs, st.session_state.manual_prices)

        if not df.empty: df['Precio_Medio'] = df['Precio_Total'] / peso

        if total_mapeados > 0: st.success(f"✅ Vinculaciones por equivalencia: {total_mapeados}")
        if warnings_map:
            with st.expander("⚠️ Avisos de Equivalencias", expanded=False):
                for w in warnings_map: st.warning(w)

        coste_total_kg = precio_compra + coste_ind
        if not df.empty:
            total_cerdos = len(df); total_ventas = df['Precio_Total'].sum(); total_costes = total_cerdos * peso * coste_total_kg; beneficio_total = total_ventas - total_costes
            total_kg_canal = total_cerdos * peso
            precio_medio_global = total_ventas / total_kg_canal if total_kg_canal > 0 else 0
            margen_pct = (beneficio_total / total_ventas) * 100 if total_ventas > 0 else 0
            rentabilidad_kg_global = precio_medio_global - coste_total_kg

            with st.expander("🔍 Buscador y Filtros de Trazabilidad (Resultados)", expanded=False):
                c_fil1, c_fil2 = st.columns(2)
                filtro_art = c_fil1.text_input("Filtrar por Artículo (Código/Nombre):").strip().lower()
                filtro_cli = c_fil2.text_input("Filtrar por Cliente:").strip().lower()
                
                df_filtered = df.copy()
                if filtro_art or filtro_cli:
                    def cumple_filtro(detalles_lista):
                        if not isinstance(detalles_lista, list): return False
                        for d in detalles_lista:
                            if not isinstance(d, dict): continue
                            txt_art = normalizar_texto(str(d.get('A','')) + " " + str(d.get('Cod','')))
                            txt_cli = normalizar_texto(str(d.get('C','')))
                            match_art = True if not normalizar_texto(filtro_art) else (normalizar_texto(filtro_art) in txt_art)
                            match_cli = True if not normalizar_texto(filtro_cli) else (normalizar_texto(filtro_cli) in txt_cli)
                            if match_art and match_cli: return True
                        return False

                    mask = df_filtered['Detalles'].apply(cumple_filtro)
                    df_filtered = df_filtered[mask]
                    st.info(f"🔎 Resultados: {len(df_filtered)} cerdos (de {total_cerdos})")

            st.markdown("### 📈 Balance General")
            k1, k2, k3, k4, k5, k6 = st.columns(6)
            k1.metric("🐷 Cerdos", f"{total_cerdos:,.0f}")
            k2.metric("💰 Precio Venta", f"{precio_medio_global:.2f} €/kg")
            k3.metric("📉 Coste Total", f"{coste_total_kg:.2f} €/kg", delta="Coste fijo", delta_color="inverse")
            k4.metric("💵 Beneficio", f"{beneficio_total:,.2f} €")
            k5.metric("📈 Rentabilidad", f"{rentabilidad_kg_global:.2f} €/kg")
            k6.metric("📊 Margen", f"{margen_pct:.2f}%")

            st.markdown("#### 🍖 Precio Medio por Corte Primario (€/kg)")
            cp_globales = {}
            for dets in df['Detalles']:
                if isinstance(dets, list):
                    for d in dets:
                        if isinstance(d, dict):
                            f = d.get('F', 'Otros')
                            if f not in cp_globales: cp_globales[f] = []
                            cp_globales[f].append(d.get('CP', 0))
            
            cp_medios_glob = {k: (sum(v)/len(v) if v else 0) for k, v in cp_globales.items()}
            familias_orden = ['Jamon', 'Paleta', 'Chuleta', 'Panceta', 'Cabeza', 'Papada']
            cp_cols = st.columns(6)
            for idx, fam_name in enumerate(familias_orden):
                val = cp_medios_glob.get(fam_name, 0)
                label = "Chuleta/Lomo" if fam_name == "Chuleta" else fam_name
                cp_cols[idx].metric(label, f"{val:.2f} €")

            found_stop = False
            for l in logs:
                if "A partir del cerdo" in l: st.warning(l)
                if "Se agotó" in l: parte = l.split("Se agotó:")[1].strip(); st.error(f"🛑 **ATENCIÓN:** Producción detenida en cerdo {total_cerdos} (FALTAN KG DE {parte.upper()})."); found_stop = True
            if not found_stop: st.info(f"ℹ️ Estado final: {logs[-1]}")

            with st.expander("📊 Detalle de lote (Gráficos e Inspector)", expanded=True):
                st.subheader("Evolución de Rentabilidad por Grupos")
                df_viz = df_filtered if (filtro_art or filtro_cli) else df
                
                if df_viz.empty: st.warning("No hay datos para mostrar.")
                else:
                    lote_size = st.number_input("Tamaño Grupo", min_value=1, value=100, step=1)
                    df_viz = df_viz.reset_index(drop=True)
                    df_viz['Grupo_ID'] = df_viz.index // lote_size
                    df_viz['Grupo_Label'] = df_viz['Grupo_ID'].apply(lambda x: f"Grupo {x+1}")
                    
                    grp_stats = df_viz.groupby('Grupo_Label').agg({'Precio_Medio': 'mean'}).reset_index()
                    grp_stats['Coste'] = coste_total_kg; grp_stats['Rentabilidad'] = grp_stats['Precio_Medio'] - coste_total_kg
                    grp_stats['Num_Grupo'] = pd.to_numeric(grp_stats['Grupo_Label'].astype(str).str.extract(r'(\d+)')[0], errors='coerce').fillna(0).astype(int)

                    base = alt.Chart(grp_stats).encode(x=alt.X('Grupo_Label', sort=alt.EncodingSortField(field="Num_Grupo", order="ascending"), title="Grupos"), y=alt.Y('Precio_Medio', title="Precio Medio"), tooltip=['Grupo_Label', 'Precio_Medio']).properties(height=400) 
                    bars = base.mark_bar().encode(color=alt.Color('Rentabilidad', scale=alt.Scale(scheme='greens')))
                    linea = alt.Chart(pd.DataFrame({'y': [coste_total_kg]})).mark_rule(color='red', strokeDash=[5,5]).encode(y='y')
                    st.altair_chart((bars + linea).interactive(), use_container_width=True)

                    st.divider()
                    st.markdown("### 🔬 Detalle de Grupos")
                    grupos_disponibles = df_viz['Grupo_Label'].unique(); grupo_selec = st.selectbox("Selecciona Grupo:", grupos_disponibles); cerdos_grupo = df_viz[df_viz['Grupo_Label'] == grupo_selec]

                    if not cerdos_grupo.empty:
                        g_cerdos = len(cerdos_grupo); g_ventas = cerdos_grupo['Precio_Total'].sum(); g_coste = g_cerdos * peso * coste_total_kg; g_ben = g_ventas - g_coste; g_pm = cerdos_grupo['Precio_Medio'].mean()
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Cerdos", g_cerdos); c2.metric("Precio Venta", f"{g_pm:.2f} €/kg"); c3.metric("Beneficio Grupo", f"{g_ben:,.2f} €"); c4.metric("Rentabilidad/Kg", f"{(g_pm - coste_total_kg):.2f} €")

                        st.markdown("##### 🍖 Precio Medio por Corte Primario en este Grupo (€/kg)")
                        cp_grupo = {}
                        for dets in cerdos_grupo['Detalles']:
                            if isinstance(dets, list):
                                for d in dets:
                                    if isinstance(d, dict):
                                        f = d.get('F', 'Otros')
                                        if f not in cp_grupo: cp_grupo[f] = []
                                        cp_grupo[f].append(d.get('CP', 0))
                        
                        cp_medios_grup = {k: (sum(v)/len(v) if v else 0) for k, v in cp_grupo.items()}
                        gcp_cols = st.columns(6)
                        for idx, fam_name in enumerate(familias_orden):
                            val = cp_medios_grup.get(fam_name, 0)
                            label = "Chuleta/Lomo" if fam_name == "Chuleta" else fam_name
                            gcp_cols[idx].metric(label, f"{val:.2f} €")

                    try:
                        detalles_flat = []
                        st.session_state.desgloses_db = {}
                        for _, row in cerdos_grupo.iterrows():
                            for d in row['Detalles']:
                                row_key = f"{d.get('Cod','X')}_{d['P']}_{d['CP']}_{d.get('Origen', 'Real')}"
                                st.session_state.desgloses_db[row_key] = d['Breakdown']
                                detalles_flat.append({'Familia': d.get('F', 'Otros'), 'Cliente': d['C'], 'Articulo': d['A'], 'Codigo': d.get('Cod', ''), 'Origen': d.get('Origen', 'Real'), 'Precio_EXW': d['P'], 'Precio_CP': d.get('CP', 0), 'Kg_Usados': d['K'], 'Row_Key': row_key})

                        if detalles_flat:
                            df_detalles = pd.DataFrame(detalles_flat)
                            resumen = df_detalles.groupby(['Familia', 'Articulo', 'Codigo', 'Cliente', 'Origen', 'Precio_EXW', 'Precio_CP', 'Row_Key']).agg({'Kg_Usados': 'sum'}).reset_index()
                            grid_resp = mostrar_tabla_aggrid(resumen, currency_cols=['Precio_EXW', 'Precio_CP'], kg_cols=['Kg_Usados'], hidden_cols=['Row_Key'], key='grid_inspector_v2')
                            csv_detalle = convert_df_to_excel_csv(df_detalles.drop(columns=['Row_Key']))
                            st.download_button("📥 Descargar Detalle Grupo (CSV)", data=csv_detalle, file_name=f"detalle_{grupo_selec.replace(' ','_')}.csv", mime="text/csv")

                            sel = grid_resp.get('selected_rows', [])
                            if isinstance(sel, pd.DataFrame) and not sel.empty: sel = sel.iloc[0].to_dict()
                            elif isinstance(sel, list) and len(sel) > 0: sel = sel[0]

                            if sel and isinstance(sel, dict):
                                breakdown_data = st.session_state.desgloses_db.get(sel.get('Row_Key'), [])
                                if breakdown_data:
                                    st.divider()
                                    st.markdown(f"#### Escandallo: **{sel['Articulo']}** (Ref: {breakdown_data[0].get('Escandallo', '')})")
                                    st.caption(f"Desglose REAL de costes (Origen: {sel['Origen']})")
                                    st.dataframe(pd.DataFrame(breakdown_data).style.format({'Precio Aplicado (€)': '{:.2f} €', 'Contribución (€)': '{:.4f} €'}, na_rep=""), use_container_width=True)

                    except Exception as e: st.error(f"Error detalles: {e}")

            with st.expander("🏁 Auditoría: Comprobación de Cantidades (Drivers)", expanded=True):
                audit_data = []
                for familia, kg_necesarios_cerdo in config.items():
                    if kg_necesarios_cerdo <= 0: continue
                    items = cajones_res.get(familia, [])
                    total_anatomico = sum(x['Kg'] for x in items)
                    total_ventas = sum(x['Kg_Venta_Original'] for x in items)
                    pct_medio = (total_ventas / total_anatomico * 100) if total_anatomico > 0 else 0
                    max_cerdos = total_anatomico / kg_necesarios_cerdo if kg_necesarios_cerdo > 0 else 0
                    audit_data.append({"Familia": familia, "Kg Venta (Neto)": total_ventas, "Rendimiento Medio": pct_medio, "Kg Reconstruidos (Anatómico)": total_anatomico, "Necesidad/Cerdo (Kg)": kg_necesarios_cerdo, "Cerdos Máximos": int(max_cerdos)})
                if audit_data:
                    df_audit = pd.DataFrame(audit_data).sort_values("Cerdos Máximos")
                    mostrar_tabla_aggrid(df_audit, height=300, kg_cols=["Kg Venta (Neto)", "Kg Reconstruidos (Anatómico)", "Necesidad/Cerdo (Kg)"], pct_cols=["Rendimiento Medio"], num_cols=["Cerdos Máximos"], heatmap_cols=["Cerdos Máximos"], key='grid_audit_v2')
                    st.download_button("📥 Descargar Auditoría", data=convert_df_to_excel_csv(df_audit), file_name="auditoria.csv", mime="text/csv")

            with st.expander("🗑️ Auditoría de Secundarios: Inventados (No vendidos)", expanded=True):
                if not df_audit_sec.empty:
                    df_inv = df_audit_sec[df_audit_sec['Tipo_Casacion'].str.contains("Inventado", case=False, na=False)]
                    if not df_inv.empty:
                        resumen = df_inv.groupby(['Escandallo_ID', 'Codigo', 'Nombre']).agg({'Kg_Usados': 'sum'}).reset_index()
                        mostrar_tabla_aggrid(resumen, kg_cols=['Kg_Usados'], key='grid_secundarios_audit')
                        st.download_button("📥 Descargar Inventados", data=convert_df_to_excel_csv(resumen), file_name="inventados.csv", mime="text/csv")
                    else: st.success("¡Perfecto! Todo se ha vendido o sustituido.")
                else: st.info("No hay datos disponibles.")

            if not df_s.empty:
                with st.expander("📦 Sobrantes Reales (Stock no utilizado)", expanded=True):
                    cols = ['Familia', 'Codigo', 'Nombre', 'Tipo', 'Kg', 'Motivo']
                    mostrar_tabla_aggrid(df_s[cols], height=500, kg_cols=['Kg'], key='grid_sobrantes_final')
                    st.download_button("📥 Descargar Sobrantes", data=convert_df_to_excel_csv(df_s[cols]), file_name="sobrantes.csv", mime="text/csv")


    # =========================================================
    # PESTAÑA 2: NUEVO COMPARADOR MULTIESCENARIO (NO TOCA LO ANTERIOR)
    # =========================================================
    with tab_sim:
        st.markdown("### 📊 Comparador de 5 Escenarios")
        st.caption("Introduce variables para 5 casos distintos y compara sus KPIs globales al instante. (Utiliza el Peso Canal Neto y los Rendimientos definidos en la barra lateral).")

        with st.form("form_multisim"):
            cols_sim = st.columns(5)
            sim_params = []
            
            for i in range(5):
                with cols_sim[i]:
                    st.markdown(f"**Escenario {i+1}**")
                    ms_pigs = st.number_input("Cerdos a simular", min_value=1, value=1000 + (i*500), step=100, key=f"ms_p_{i}")
                    ms_price = st.number_input("Precio Canal (€)", min_value=0.0, value=2.10, step=0.01, key=f"ms_pr_{i}")
                    ms_cost = st.number_input("Coste Ind. (€)", min_value=0.0, value=0.35, step=0.01, key=f"ms_c_{i}")
                    sim_params.append({'pigs': ms_pigs, 'price': ms_price, 'cost': ms_cost})

            btn_lanzar = st.form_submit_button("🚀 Lanzar 5 Simulaciones", use_container_width=True)

        if btn_lanzar:
            with st.spinner("Procesando 5 simulaciones en paralelo usando el motor principal. Un momento..."):
                resultados_ms = []
                for i, param in enumerate(sim_params):
                    df_sim, _, _, _, _, _, _, _ = run_simulation(esc, ven, eq, sus, config, forced_pigs_target=param['pigs'], manual_overrides=st.session_state.manual_prices)

                    if not df_sim.empty:
                        t_cerdos = len(df_sim)
                        t_ventas = df_sim['Precio_Total'].sum()
                        t_coste_kg = param['price'] + param['cost']
                        t_costes = t_cerdos * peso * t_coste_kg
                        ben = t_ventas - t_costes
                        t_kg_canal = t_cerdos * peso
                        pm_global = t_ventas / t_kg_canal if t_kg_canal > 0 else 0
                        margen = (ben / t_ventas) * 100 if t_ventas > 0 else 0
                        rentabilidad = pm_global - t_coste_kg

                        resultados_ms.append({
                            'Métrica': [
                                '🐷 Cerdos Reales Logrados',
                                '💰 Precio Medio Venta',
                                '📉 Coste Total Base',
                                '💵 Beneficio Total',
                                '📈 Rentabilidad por Kg',
                                '📊 Margen'
                            ],
                            f'Escenario {i+1}': [
                                f"{t_cerdos:,.0f}",
                                f"{pm_global:.3f} €/kg",
                                f"{t_coste_kg:.3f} €/kg",
                                f"{ben:,.2f} €",
                                f"{rentabilidad:.3f} €/kg",
                                f"{margen:.2f} %"
                            ]
                        })

                if resultados_ms:
                    df_comparativa = pd.DataFrame({'Métrica': resultados_ms[0]['Métrica']})
                    for res in resultados_ms:
                        esc_name = list(res.keys())[1]
                        df_comparativa[esc_name] = res[esc_name]

                    st.markdown("#### 🏆 Resultados de la Comparativa")
                    
                    # --- FUNCIÓN PARA COLOREAR EN VERDE/ROJO ---
                    def colorear_metricas(row):
                        estilos = [''] * len(row)
                        if 'Beneficio Total' in str(row['Métrica']) or 'Rentabilidad por Kg' in str(row['Métrica']) or 'Margen' in str(row['Métrica']):
                            for i, col_name in enumerate(row.index):
                                if 'Escenario' in str(col_name):
                                    val_str = str(row[col_name])
                                    val_limpio = val_str.replace('€', '').replace('/kg', '').replace('%', '').replace(',', '').strip()
                                    try:
                                        val_num = float(val_limpio)
                                        if val_num > 0.0001:
                                            estilos[i] = 'color: #2e7d32; font-weight: bold;'
                                        elif val_num < -0.0001:
                                            estilos[i] = 'color: #d32f2f; font-weight: bold;'
                                    except:
                                        pass
                        return estilos
                    # -------------------------------------------
                    
                    df_estilizado = df_comparativa.style.apply(colorear_metricas, axis=1)
                    st.dataframe(df_estilizado, use_container_width=True, hide_index=True)
                    st.success("¡Simulaciones completadas con éxito!")
