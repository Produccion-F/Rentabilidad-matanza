import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import unicodedata

# Intentamos importar AgGrid.
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode
    HAS_AGGRID = True
except ImportError:
    HAS_AGGRID = False

# --- CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(page_title="Matanza Óptima", layout="wide", page_icon="🐖")

# Inyectamos CSS para Estilos Ejecutivos (KPIs y Tablas)
st.markdown("""
    <style>
    /* Estilo para KPIs (Tarjetas Modernas) */
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        border-top: 4px solid #2e7d32; /* Verde corporativo */
        border-radius: 5px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        color: #333;
    }
    [data-testid="stMetricLabel"] {
        color: #2e7d32;
        font-weight: bold;
        font-size: 14px;
    }
    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #1a1a1a;
    }
    /* Estilos Generales */
    h1, h2, h3 {
        color: #1b5e20;
    }
    </style>
""", unsafe_allow_html=True)

# --- URLs ---
URL_ESCANDALLOS = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRtdfgZGMkk10_R_8pFbH2_qbRsFB1JyltIq3t-hJqfEGKJhXMCbjH3Xh0z12AkMgZkRXYt7rLclJ44/pub?gid=0&single=true&output=csv'
URL_VENTAS = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vTlJBcdE77BaiNke-06GxDH8nY7vQ0wm_XgtDaVlF9cDDlFIxIawsTNZHrEPlv3uoVecih6_HRo7gqH/pub?gid=1543847315&single=true&output=csv'
URL_EQUIVALENCIAS = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRtdfgZGMkk10_R_8pFbH2_qbRsFB1JyltIq3t-hJqfEGKJhXMCbjH3Xh0z12AkMgZkRXYt7rLclJ44/pub?gid=1911720872&single=true&output=csv'
URL_SUSTITUCIONES = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRtdfgZGMkk10_R_8pFbH2_qbRsFB1JyltIq3t-hJqfEGKJhXMCbjH3Xh0z12AkMgZkRXYt7rLclJ44/pub?gid=69264992&single=true&output=csv'

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

# --- FUNCIÓN AGRID CON ESTILO EXCEL ---
def mostrar_tabla_aggrid(df, height=400, currency_cols=[], kg_cols=[], pct_cols=[], num_cols=[], heatmap_cols=[], hidden_cols=[], key=None, selection_mode='single'):
    if not HAS_AGGRID:
        st.dataframe(df, use_container_width=True)
        return None

    gb = GridOptionsBuilder.from_dataframe(df)

    # Configuración base estilo Excel
    gb.configure_default_column(
        groupable=True,
        value=True,
        enableRowGroup=True,
        aggFunc='sum',
        editable=False,
        filterable=True,
        sortable=True,
        resizable=True
    )

    gb.configure_selection(selection_mode, use_checkbox=False, rowMultiSelectWithClick=False, suppressRowDeselection=False)

    js_currency = JsCode("""function(params) { if (params.value !== null) return params.value.toLocaleString('es-ES', {style: 'currency', currency: 'EUR'}); return null; }""")
    js_kg = JsCode("""function(params) { if (params.value !== null) return params.value.toLocaleString('es-ES', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' kg'; return null; }""")
    js_pct = JsCode("""function(params) { if (params.value !== null) return params.value.toLocaleString('es-ES', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + '%'; return null; }""")
    js_num = JsCode("""function(params) { if (params.value !== null) return params.value.toLocaleString('es-ES', {maximumFractionDigits: 0}); return null; }""")

    for col in currency_cols: gb.configure_column(col, valueFormatter=js_currency, type=["numericColumn"])
    for col in kg_cols: gb.configure_column(col, valueFormatter=js_kg, type=["numericColumn"])
    for col in pct_cols: gb.configure_column(col, valueFormatter=js_pct, type=["numericColumn"])
    for col in num_cols: gb.configure_column(col, valueFormatter=js_num, type=["numericColumn"])

    for col in hidden_cols: gb.configure_column(col, hide=True)

    for col in heatmap_cols:
        if col in df.columns:
            c_min, c_max = df[col].min(), df[col].max()
            if pd.isna(c_min): c_min = 0
            if pd.isna(c_max): c_max = 1
            if c_min == c_max: c_max = c_min + 1
            js_heatmap = JsCode(f"""function(params) {{
                if (params.value === null || params.value === undefined) return null;
                var val = params.value; var min = {c_min}; var max = {c_max};
                var ratio = (val - min) / (max - min);
                if (ratio < 0) ratio = 0; if (ratio > 1) ratio = 1;
                var color1 = [255, 200, 200]; var color2 = [255, 255, 200]; var color3 = [200, 255, 200];
                var r, g, b;
                if (ratio < 0.5) {{ var f = ratio * 2; r = color1[0] + f*(color2[0]-color1[0]); g = color1[1] + f*(color2[1]-color1[1]); b = color1[2] + f*(color2[2]-color1[2]); }}
                else {{ var f = (ratio - 0.5) * 2; r = color2[0] + f*(color3[0]-color2[0]); g = color2[1] + f*(color3[1]-color2[1]); b = color2[2] + f*(color3[2]-color2[2]); }}
                return {{'backgroundColor': 'rgb(' + Math.floor(r) + ',' + Math.floor(g) + ',' + Math.floor(b) + ')'}};
            }}""")
            gb.configure_column(col, cellStyle=js_heatmap)

    grid_options = gb.build()

    # CSS para parecer Excel (Verde y filas alternas)
    custom_css = {
        ".ag-header-cell": {"background-color": "#2e7d32 !important", "color": "white !important", "font-weight": "bold"},
        ".ag-row-odd": {"background-color": "#f1f8e9 !important"},
        ".ag-row-even": {"background-color": "#ffffff !important"},
        ".ag-header-cell-text": {"color": "white !important"}
    }

    # --- MODIFICACIÓN: Lógica de Pantalla Completa ---
    toggle_key = f"toggle_full_{key}" if key else f"toggle_full_{id(df)}"
    final_height = height
    if st.checkbox("⤢ Maximizar Tabla", key=toggle_key):
        final_height = 1200

    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        height=final_height,
        width='100%',
        data_return_mode=DataReturnMode.AS_INPUT,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        fit_columns_on_grid_load=True,
        allow_unsafe_jscode=True,
        theme='balham',
        custom_css=custom_css,
        key=key
    )
    return grid_response

# --- CARGA DATOS ---
def load_and_clean_data_raw():
    errores = []
    # 1. ESCANDALLOS
    try:
        try: df_e = pd.read_csv(URL_ESCANDALLOS, sep=None, engine='python')
        except: df_e = pd.read_csv(URL_ESCANDALLOS, sep=';')
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
    except Exception as e: return None, None, None, None, [f"Error Fatal Escandallos: {e}"]

    # 2. VENTAS
    try:
        try: df_v = pd.read_csv(URL_VENTAS, sep=None, engine='python')
        except: df_v = pd.read_csv(URL_VENTAS, sep=';')
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
    except Exception as e: return None, None, None, None, [f"Error Fatal Ventas: {e}"]

    # 3. EQUIVALENCIAS
    try:
        try: df_eq = pd.read_csv(URL_EQUIVALENCIAS, sep=None, engine='python')
        except: df_eq = pd.read_csv(URL_EQUIVALENCIAS, sep=';')
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

    # 4. SUSTITUCIONES
    try:
        try: df_raw = pd.read_csv(URL_SUSTITUCIONES, sep=None, engine='python')
        except: df_raw = pd.read_csv(URL_SUSTITUCIONES, sep=';')

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

# --- SIMULACIÓN ---
@st.cache_data(show_spinner="Recalculando simulación...", ttl=3600)
def run_simulation(df_esc, df_ven, df_eq, df_sust, target_config, forced_pigs_target=0, manual_overrides={}):
    log = []
    warnings_mapping = []
    simulated_parts_log = set()

    # 0. PREPARACIÓN DE DATOS (MERCADO, SUSTITUTOS, ETC.)
    df_ven_proc = df_ven.copy()

    # --- NUEVO: APLICAR PRECIOS MANUALES (SI EXISTEN) ---
    # Esto sobrescribe CUALQUIER otra lógica (Real, Congelado, Media)
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
    # ----------------------------------------------------

    # Pre-cálculo 1: Precios Medios Reales (Directos)
    ventas_reales = df_ven_proc[df_ven_proc['Cliente'].str.strip().str.upper() != "ENTRADAS A CONGELAR"].copy()
    ventas_reales = ventas_reales[ventas_reales['Precio'] > 0].copy() # Solo ventas con precio
    ventas_reales['Valor_Total'] = ventas_reales['Kilos'] * ventas_reales['Precio']

    agrupado_mercado = ventas_reales.groupby('Codigo').agg({'Valor_Total': 'sum', 'Kilos': 'sum'})
    agrupado_mercado['Precio_Medio'] = np.where(agrupado_mercado['Kilos'] > 0, agrupado_mercado['Valor_Total'] / agrupado_mercado['Kilos'], 0)
    mapa_precios_mercado = agrupado_mercado['Precio_Medio'].to_dict()

    # Pre-cálculo 2: Precios Mínimos de Sustitutos/Equivalencias (Indirectos)
    # Construimos mapa de Codigo -> Lista de Sustitutos/Equivalencias
    mapa_relaciones = {}

    # Añadimos sustituciones
    if not df_sust.empty and 'Codigo_Origen' in df_sust.columns and 'Codigo_Destino' in df_sust.columns:
        for _, row in df_sust.iterrows():
            o = str(row['Codigo_Origen']).strip()
            d = str(row['Codigo_Destino']).strip()
            if o and d:
                if o not in mapa_relaciones: mapa_relaciones[o] = []
                mapa_relaciones[o].append(d)

    # Añadimos equivalencias (Codigo Origen -> Codigo Principal Destino)
    if not df_eq.empty and 'Codigo_Origen' in df_eq.columns and 'Codigo_Principal' in df_eq.columns:
        for _, row in df_eq.iterrows():
            o = str(row['Codigo_Origen']).strip()
            d = str(row['Codigo_Principal']).strip()
            if o and d and d.lower() != 'nan':
                if o not in mapa_relaciones: mapa_relaciones[o] = []
                mapa_relaciones[o].append(d)

    # 1. BARRIDO DE SANIDAD (ENTRADAS A CONGELAR)
    # -----------------------------------------------------------
    count_arreglados_directo = 0
    count_arreglados_indirecto = 0
    indices_a_eliminar = []

    for idx, row in df_ven_proc.iterrows():
        cliente_limpio = str(row.get('Cliente', '')).strip().upper()
        # Si es simulación manual, no lo tocamos (se salta la eliminación de sobrantes)
        if cliente_limpio == '🔧 SIMULACIÓN MANUAL': continue

        precio_actual = float(row.get('Precio', 0))

        # Detectamos Congelado o Precio 0
        if cliente_limpio == "ENTRADAS A CONGELAR" or precio_actual <= 0.0001:
            cod = str(row.get('Codigo', '')).strip()
            nuevo_precio = 0
            motivo = ""

            # PASO 1: Búsqueda Directa (Media)
            if cod in mapa_precios_mercado and mapa_precios_mercado[cod] > 0:
                nuevo_precio = mapa_precios_mercado[cod]
                motivo = "Ref. Mercado Directo"
                count_arreglados_directo += 1

            # PASO 2: Búsqueda Indirecta (Sustitutos/Equiv -> PEOR PRECIO)
            elif cod in mapa_relaciones:
                precios_encontrados = []
                for rel_cod in mapa_relaciones[cod]:
                    # Buscamos en todas las ventas reales de ese código sustituto
                    ventas_sust = ventas_reales[ventas_reales['Codigo'] == rel_cod]
                    if not ventas_sust.empty:
                        min_p = ventas_sust['Precio'].min() # EL PEOR PRECIO
                        if min_p > 0: precios_encontrados.append(min_p)

                if precios_encontrados:
                    nuevo_precio = min(precios_encontrados) # El mínimo de los mínimos
                    motivo = "Ref. Indirecta (Mínimo)"
                    count_arreglados_indirecto += 1

            # APLICACIÓN O RECHAZO
            if nuevo_precio > 0:
                df_ven_proc.at[idx, 'Precio'] = nuevo_precio
                df_ven_proc.at[idx, 'Cliente'] = f"{cliente_limpio} [{motivo}]"
            else:
                # PASO 3: Sin referencias -> A la basura (Sobrantes)
                indices_a_eliminar.append(idx)

    # Separamos los rechazados
    df_rechazados = df_ven_proc.loc[indices_a_eliminar].copy()
    df_ven_proc = df_ven_proc.drop(indices_a_eliminar)

    log.append(f"Sanidad Stock: {count_arreglados_directo} directos, {count_arreglados_indirecto} indirectos (Peor Precio).")
    log.append(f"Sanidad Stock: {len(indices_a_eliminar)} partidas RECHAZADAS por falta de precio.")

    # -----------------------------------------------------------

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

            # --- PRE-CÁLCULO VALOR TEÓRICO SECUNDARIOS PARA CP ---
            valor_sec_teorico = 0
            for s in lista_secundarios:
                valor_sec_teorico += (s['Pct'] * s['PrecioTeorico'])

            recetas[cod] = {
                'Familia': fam,
                'Pct': p['Pct'],
                'Secundarios': lista_secundarios,
                'Escandallo_ID': eid,
                'Nombre_Principal': p['Nombre'],
                'Precio_Teorico_Principal': p['PrecioTeorico'],
                'Valor_Secundarios_Teorico': valor_sec_teorico
            }

    log.append(f"Recetas Activas: {len(recetas)}")

    mapa_equivalencias = {}
    if not df_eq.empty and 'Codigo_Origen' in df_eq.columns and 'Escandallo_Destino' in df_eq.columns and 'Codigo_Principal' in df_eq.columns:
        for _, row in df_eq.iterrows():
            orig = str(row['Codigo_Origen']).strip()
            dest_esc = str(row['Escandallo_Destino']).strip()
            dest_cod = str(row['Codigo_Principal']).strip()
            if (dest_esc, dest_cod) in pares_existentes:
                mapa_equivalencias[orig] = dest_cod
            else:
                warnings_mapping.append(f"❌ Error Mapeo: {orig} -> {dest_esc}/{dest_cod} no existe en Escandallos.")

    mapa_sustituciones = {}
    mapa_sustituciones_list = {}
    if not df_sust.empty and 'Codigo_Origen' in df_sust.columns and 'Codigo_Destino' in df_sust.columns:
        for _, row in df_sust.iterrows():
            orig = str(row['Codigo_Origen']).strip()
            dest = str(row['Codigo_Destino']).strip()
            if dest in recetas or dest in mapa_equivalencias:
                mapa_sustituciones[orig] = dest
            if orig not in mapa_sustituciones_list: mapa_sustituciones_list[orig] = []
            mapa_sustituciones_list[orig].append(dest)

    # 1. CLASIFICACIÓN
    cajones = {k: [] for k in target_config.keys()}
    last_known_item_meta = {}

    stock_secundarios = {}
    sobrantes_temp = []

    # Añadimos los rechazados a sobrantes directamente
    for _, row in df_rechazados.iterrows():
        sobrantes_temp.append({
            'Familia': 'Desconocido',
            'Codigo': str(row.get('Codigo')),
            'Nombre': str(row.get('Articulo')),
            'Tipo': 'RECHAZADO (Congelado 0€)',
            'Kg': row.get('Kilos'),
            'Motivo': 'Sin precio referencia (Directo/Indir)'
        })

    count_vinculados_mapeo = 0 # Inicialización corregida
    ventas_dict = df_ven_proc.to_dict('records')

    for venta in ventas_dict:
        cod = str(venta.get('Codigo', '')).strip()
        kg_venta = float(venta.get('Kilos', 0))
        pr = float(venta.get('Precio', 0))
        cliente = str(venta.get('Cliente', 'Varios'))
        articulo_nom = str(venta.get('Articulo', str(cod)))

        if not cod or cod == 'nan' or kg_venta <= 0: continue

        es_driver = False
        cod_para_receta = cod
        es_sustitucion = False

        if cod in recetas:
            es_driver = True
            info = recetas[cod]
        elif cod in mapa_equivalencias:
            es_driver = True
            cod_para_receta = mapa_equivalencias[cod]
            info = recetas.get(cod_para_receta)
            count_vinculados_mapeo += 1
        elif cod in mapa_sustituciones:
            es_driver = True
            cod_para_receta = mapa_sustituciones[cod]
            info = recetas.get(cod_para_receta)
            es_sustitucion = True

        if es_driver and info:
            fam_receta = info['Familia']
            match = False
            for target_key in cajones.keys():
                if target_key.lower() == fam_receta.lower():

                    # --- CÁLCULO DE CP PARA ORDENACIÓN (ESTRICTO) ---
                    pct_rendimiento = info['Pct']
                    valor_secundarios = info.get('Valor_Secundarios_Teorico', 0)

                    # Nota: pr ya viene "saneado" (no es 0), así que el CP será correcto.
                    if pct_rendimiento > 0:
                        cp_estimado = (pr * pct_rendimiento) + valor_secundarios
                    else:
                        cp_estimado = pr
                    # -----------------------------------------------

                    kg_anatomicos_reales = kg_venta / pct_rendimiento if pct_rendimiento > 0 else kg_venta
                    cajones[target_key].append({
                        'Kg': kg_anatomicos_reales,
                        'Val': 0,
                        'Codigo': cod,
                        'Codigo_Receta': cod_para_receta,
                        'Nombre': articulo_nom,
                        'Cliente': cliente,
                        'Precio_EXW': pr,
                        'CP_Estimado_Sort': cp_estimado, # Clave de ordenación
                        'Kg_Venta_Original': kg_venta,
                        'Familia': fam_receta,
                        'Es_Sustitucion': es_sustitucion
                    })
                    match = True; break
            if not match:
                sobrantes_temp.append({'Familia': fam_receta, 'Codigo': cod, 'Nombre': articulo_nom, 'Tipo': 'Familia no config', 'Kg': kg_venta, 'Motivo': f"Familia '{fam_receta}' no configurada"})
        else:
            if cod not in stock_secundarios: stock_secundarios[cod] = []
            stock_secundarios[cod].append({'Kg': kg_venta, 'Precio': pr, 'Cliente': cliente, 'Nombre': articulo_nom})

    for k in cajones:
        # --- ORDENACIÓN ESTRICTA POR CP ---
        cajones[k].sort(key=lambda x: -x['CP_Estimado_Sort'])

        if cajones[k]:
            last_item = cajones[k][-1] # Este será el peor CP real
            last_known_item_meta[k] = last_item

    # 2. FUNCIÓN DE CASACIÓN
    auditoria_secundarios = []

    def casar_secundario(cod_necesario, kg_necesarios, precio_teorico, nombre_teorico, escandallo_id):
        valor_recuperado = 0
        kg_pendientes = kg_necesarios
        clientes_involucrados = set()

        # Nivel 1: Búsqueda Directa
        if cod_necesario in stock_secundarios:
            for v in stock_secundarios[cod_necesario]:
                if kg_pendientes <= 0.0001: break
                if v['Kg'] > 0:
                    tomar = min(kg_pendientes, v['Kg'])

                    # El precio ya viene saneado (>0) o es venta real
                    precio_final = v['Precio']
                    cliente_ref = str(v['Cliente'])

                    valor_recuperado += tomar * precio_final
                    v['Kg'] -= tomar
                    kg_pendientes -= tomar
                    clientes_involucrados.add(cliente_ref)

        # Nivel 2: Sustitutos
        if kg_pendientes > 0.0001 and cod_necesario in mapa_sustituciones_list:
            candidatos = mapa_sustituciones_list[cod_necesario]
            pool_candidatos = []
            for cand in candidatos:
                if cand in stock_secundarios:
                    for v in stock_secundarios[cand]:
                        if v['Kg'] > 0:
                            pool_candidatos.append({'datos': v, 'cod_sust': cand})
            pool_candidatos.sort(key=lambda x: x['datos']['Precio'], reverse=True)
            for cand_obj in pool_candidatos:
                if kg_pendientes <= 0.0001: break
                v = cand_obj['datos']
                tomar = min(kg_pendientes, v['Kg'])

                precio_final = v['Precio']
                cliente_ref = f"{v['Cliente']} (Sust)"

                valor_recuperado += tomar * precio_final
                v['Kg'] -= tomar
                kg_pendientes -= tomar
                clientes_involucrados.add(cliente_ref)

        # Nivel 3: Invento (Teórico)
        if kg_pendientes > 0.0001:
            valor_inventado = kg_pendientes * precio_teorico
            valor_recuperado += valor_inventado
            auditoria_secundarios.append({
                'Escandallo_ID': escandallo_id,
                'Codigo': cod_necesario,
                'Nombre': nombre_teorico,
                'Tipo_Casacion': '3. Inventado (Teórico)',
                'Kg_Usados': kg_pendientes,
                'Precio_Aplicado': precio_teorico,
                'Valor': valor_inventado
            })
            kg_pendientes = 0
            clientes_involucrados.add("⚠️ ESTIMADO (Sin Venta)")

        cliente_str = ", ".join(list(clientes_involucrados))
        return valor_recuperado, cliente_str

    # 3. CONSTRUCCIÓN DE CERDOS
    cursors = {k: {'idx': 0, 'rem': cajones[k][0]['Kg'] if cajones[k] else 0} for k in cajones}
    cerdos = []
    causa_parada = "Límite seguridad alcanzado"
    prog = st.progress(0)

    LOOP_LIMIT = forced_pigs_target if forced_pigs_target > 0 else 1000000

    for i in range(LOOP_LIMIT):
        if i % 100 == 0: prog.progress(min(i/max(LOOP_LIMIT, 1000), 1.0))

        possible = True
        missing_part = ""

        for p, tgt in target_config.items():
            if tgt <= 0: continue
            has_stock = cursors[p]['idx'] < len(cajones[p])
            if not has_stock:
                if forced_pigs_target > 0:
                    if p not in simulated_parts_log:
                        simulated_parts_log.add(p)
                        log.append(f"⚠️ AVISO: A partir del cerdo {i+1} se agotó '{p}'. Iniciando SIMULACIÓN con el peor precio histórico.")
                else:
                    possible = False
                    missing_part = p
                    break

        if not possible:
            causa_parada = f"Se agotó: {missing_part}"
            break

        coste_cerdo = 0
        peso_referencia_cerdo = 0
        componentes_driver = []

        for p, tgt in target_config.items():
            if tgt <= 0: continue
            needed = tgt

            while needed > 0.001:
                item_data = None
                is_simulated = False

                if cursors[p]['idx'] < len(cajones[p]):
                    item_data = cajones[p][cursors[p]['idx']]
                    take = min(needed, cursors[p]['rem'])
                    cursors[p]['rem'] -= take
                    if cursors[p]['rem'] <= 0.001:
                        cursors[p]['idx'] += 1
                        if cursors[p]['idx'] < len(cajones[p]):
                            cursors[p]['rem'] = cajones[p][cursors[p]['idx']]['Kg']
                elif forced_pigs_target > 0:
                    is_simulated = True
                    plantilla = last_known_item_meta.get(p)
                    if plantilla:
                        take = needed
                        # --- SIMULACIÓN: USAR EL ÚLTIMO PRECIO REAL (Peor escenario) ---
                        # Como ordenamos por CP descendente, el último item tiene el PEOR CP.
                        precio_simulado = plantilla['Precio_EXW']

                        item_data = {
                            'Codigo': plantilla['Codigo'],
                            'Codigo_Receta': plantilla['Codigo_Receta'],
                            'Nombre': plantilla['Nombre'],
                            'Cliente': '🔮 SIMULADO (Peor Histórico)',
                            'Precio_EXW': precio_simulado,
                            'Familia': plantilla['Familia'],
                            'Simulado': True
                        }
                    else:
                        possible = False; causa_parada = f"Error crítico: No hay histórico para simular {p}"; break
                else:
                    possible = False; causa_parada = f"Se agotó: {p}"; break

                if not possible: break

                receta_usada = recetas[item_data['Codigo_Receta']]
                factor_principal = receta_usada['Pct']
                kg_venta_imputados = take * factor_principal
                precio_exw = item_data['Precio_EXW']
                valor_venta_principal = kg_venta_imputados * precio_exw

                breakdown_pig = []
                breakdown_pig.append({
                    'Escandallo': receta_usada['Escandallo_ID'],
                    'Tipo': '⭐ PRINCIPAL',
                    'Codigo': item_data['Codigo'],
                    'Articulo': item_data['Nombre'],
                    'Cliente': item_data['Cliente'],
                    '% Rendimiento': f"{factor_principal*100:.2f}%",
                    'Precio Aplicado (€)': precio_exw,
                    'Contribución (€)': factor_principal * precio_exw
                })

                valor_recuperado_secundarios = 0
                if factor_principal > 0:
                    base_calculo = take
                    for sec in receta_usada['Secundarios']:
                        kg_sec_generados = base_calculo * sec['Pct']
                        val_rec, cliente_sec_str = casar_secundario(sec['Codigo'], kg_sec_generados, sec['PrecioTeorico'], sec['Nombre'], receta_usada['Escandallo_ID'])
                        valor_recuperado_secundarios += val_rec

                        precio_real_medio = val_rec / kg_sec_generados if kg_sec_generados > 0 else 0
                        contribucion_al_cp = val_rec / take

                        breakdown_pig.append({
                            'Escandallo': receta_usada['Escandallo_ID'],
                            'Tipo': '🔹 SECUNDARIO',
                            'Codigo': sec['Codigo'],
                            'Articulo': sec['Nombre'],
                            'Cliente': cliente_sec_str,
                            '% Rendimiento': f"{sec['Pct']*100:.2f}%",
                            'Precio Aplicado (€)': precio_real_medio,
                            'Contribución (€)': contribucion_al_cp
                        })

                valor_total_operacion = valor_venta_principal + valor_recuperado_secundarios
                precio_cp = 0
                if take > 0: precio_cp = valor_total_operacion / take

                breakdown_pig.append({
                    'Escandallo': '', 'Tipo': '', 'Codigo': '', 'Articulo': 'TOTAL RECONSTITUIDO', 'Cliente': '',
                    '% Rendimiento': '100%', 'Precio Aplicado (€)': None,
                    'Contribución (€)': precio_cp
                })

                coste_cerdo += valor_total_operacion
                origen_str = "⚠️ SIMULADO" if is_simulated else "Real"

                componentes_driver.append({
                    'C': item_data['Cliente'],
                    'A': item_data['Nombre'],
                    'P': precio_exw,
                    'CP': precio_cp,
                    'K': kg_venta_imputados,
                    'F': item_data.get('Familia', 'Otros'),
                    'Cod': item_data['Codigo'],
                    'Origen': origen_str,
                    'Breakdown': breakdown_pig
                })

                needed -= take

            if not possible: break
            peso_referencia_cerdo += tgt

        if not possible: break
        if coste_cerdo == 0: break

        cerdos.append({'ID': i+1, 'Precio_Total': coste_cerdo, 'Precio_Medio': coste_cerdo/peso_referencia_cerdo, 'Detalles': componentes_driver})

    prog.empty()
    if forced_pigs_target > 0 and len(cerdos) >= forced_pigs_target:
        causa_parada = f"Objetivo de {forced_pigs_target} cerdos alcanzado (Simulación forzada)."

    log.append(f"🛑 Detenido. {causa_parada}")

    sobrantes_finales = sobrantes_temp.copy()
    for cod, lista_lotes in stock_secundarios.items():
        for lote in lista_lotes:
            if lote['Kg'] > 0.01:
                sobrantes_finales.append({'Familia': 'Secundario', 'Codigo': cod, 'Nombre': lote['Nombre'], 'Tipo': 'Resto Stock', 'Kg': lote['Kg'], 'Motivo': 'No hubo driver suficiente para consumirlo'})

    return pd.DataFrame(cerdos), pd.DataFrame(sobrantes_finales), log, cajones, warnings_mapping, count_vinculados_mapeo, pd.DataFrame(auditoria_secundarios), recetas

# --- UI ---
st.title("🐖 Rentabilidad Matanza")
if 'raw_data' not in st.session_state: st.session_state.raw_data = None
if 'desgloses_db' not in st.session_state: st.session_state.desgloses_db = {}
if 'manual_prices' not in st.session_state: st.session_state.manual_prices = {}

with st.sidebar:
    st.header("⚙️ Configuración")

    # --- NUEVO: SIMULADOR MANUAL DE PRECIOS ---
    with st.expander("🛠️ Simulador de Precios (Lab)", expanded=False):
        st.caption("Sobrescribe precios reales para simular escenarios.")
        col_s1, col_s2 = st.columns([1, 1])
        with col_s1:
            code_sim = st.text_input("Código Artículo").strip()
        with col_s2:
            price_sim = st.number_input("Nuevo Precio (€)", min_value=0.0, step=0.01)

        if st.button("➕ Añadir Regla Manual"):
            if code_sim:
                st.session_state.manual_prices[code_sim] = price_sim
                st.success(f"Regla: {code_sim} -> {price_sim}€")

        if st.session_state.manual_prices:
            st.divider()
            st.caption("Reglas Activas:")
            claves_borrar = []
            for k, v in st.session_state.manual_prices.items():
                col_d1, col_d2 = st.columns([3, 1])
                col_d1.text(f"{k}: {v:.2f} €")
                if col_d2.button("❌", key=f"del_{k}"):
                    claves_borrar.append(k)

            for k in claves_borrar:
                del st.session_state.manual_prices[k]
                st.rerun()

            if st.button("🗑️ Borrar Todo"):
                st.session_state.manual_prices = {}
                st.rerun()
    # ------------------------------------------

    if st.button("🔄 Cargar/Actualizar Datos (Google)", type="secondary"):
        with st.spinner("Descargando datos..."):
            datos = load_and_clean_data_raw()
            if datos[4]:
                for e in datos[4]: st.error(e)
            else:
                st.session_state.raw_data = datos
                st.success("Datos actualizados.")

    st.divider()
    precio_compra = st.number_input("Precio Canal (€/kg)", value=2.10, step=0.01, min_value=0.0)
    coste_ind = st.number_input("Coste Ind. (€/kg)", value=0.35, step=0.01, min_value=0.0)

    st.divider()
    modo_forzado = st.checkbox("🔮 Simular hasta N Cerdos (Forzar producción)", value=False, help="Si se activa, cuando se acabe el stock de una pieza, el programa 'inventará' más stock usando el PEOR precio histórico para completar los cerdos.")
    target_pigs = 0
    if modo_forzado:
        target_pigs = st.number_input("Objetivo de Cerdos a Simular:", min_value=1, value=5000, step=100)
        st.caption(f"⚠️ El sistema forzará la venta de piezas agotadas al precio más bajo registrado.")

    st.divider()
    peso = st.number_input("Peso Canal (Kg)", value=93.00, min_value=0.1)
    c1, c2 = st.columns(2)
    p_jamon = c1.number_input("% Jamón", value=33.00, step=0.01, min_value=0.0, max_value=100.0)
    p_paleta = c2.number_input("% Paleta", value=17.30, step=0.01, min_value=0.0, max_value=100.0)
    p_chuleta = c1.number_input("% Chuleta", value=26.00, step=0.01, min_value=0.0, max_value=100.0)
    p_panceta = c2.number_input("% Panceta", value=15.8, step=0.01, min_value=0.0, max_value=100.0)
    p_cabeza = c1.number_input("% Cabeza", value=5.20, step=0.01, min_value=0.0, max_value=100.0)
    p_papada = c2.number_input("% Papada", value=2.70, step=0.01, min_value=0.0, max_value=100.0)
    config = {'Jamon': (p_jamon/100)*peso, 'Paleta': (p_paleta/100)*peso, 'Chuleta': (p_chuleta/100)*peso, 'Panceta': (p_panceta/100)*peso, 'Cabeza': (p_cabeza/100)*peso, 'Papada': (p_papada/100)*peso}
    st.info(f"Total Kg: {sum(config.values()):.2f}")

if st.session_state.raw_data is None:
    st.info("👋 Para empezar, pulsa el botón 'Cargar/Actualizar Datos' en el menú de la izquierda.")
else:
    esc, ven, eq, sus, err = st.session_state.raw_data
    # Pasamos los precios manuales a la simulación
    df, df_s, logs, cajones_res, warnings_map, total_mapeados, df_audit_sec, recetas_db = run_simulation(esc, ven, eq, sus, config, target_pigs, st.session_state.manual_prices)

    if not df.empty:
         df['Precio_Medio'] = df['Precio_Total'] / peso

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

        # --- NUEVO: BUSCADOR Y FILTROS DE TRAZABILIDAD (POST-PROCESADO) ---
        with st.expander("🔍 Buscador y Filtros de Trazabilidad (Resultados)", expanded=False):
            c_fil1, c_fil2 = st.columns(2)
            filtro_art = c_fil1.text_input("Filtrar por Artículo (Código/Nombre):", help="Muestra solo cerdos que contengan este artículo.").strip().lower()
            filtro_cli = c_fil2.text_input("Filtrar por Cliente:", help="Muestra solo cerdos vendidos a este cliente.").strip().lower()

            df_filtered = df.copy()
            if filtro_art or filtro_cli:
                def cumple_filtro(detalles_lista):
                    if not isinstance(detalles_lista, list): return False # Safety check for robustness
                    # Detalles es una lista de dicts. Buscamos en cada componente.
                    for d in detalles_lista:
                        if not isinstance(d, dict): continue # Safety check

                        # Usamos normalizar_texto para búsqueda aproximada (tildes, mayúsculas)
                        txt_art = normalizar_texto(str(d.get('A','')) + " " + str(d.get('Cod','')))
                        txt_cli = normalizar_texto(str(d.get('C','')))

                        term_art = normalizar_texto(filtro_art)
                        term_cli = normalizar_texto(filtro_cli)

                        match_art = True if not term_art else (term_art in txt_art)
                        match_cli = True if not term_cli else (term_cli in txt_cli)

                        # Si encontramos UN componente que cumpla, el cerdo cumple (si buscamos trazabilidad positiva)
                        if match_art and match_cli: return True
                    return False

                mask = df_filtered['Detalles'].apply(cumple_filtro)
                df_filtered = df_filtered[mask]
                st.info(f"🔎 Resultados encontrados: {len(df_filtered)} cerdos (de {total_cerdos})")
            else:
                st.caption("Mostrando todos los cerdos.")
        # ------------------------------------------------------------------

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
            if "Se agotó" in l: parte = l.split("Se agotó:")[1].strip(); st.error(f"🛑 **ATENCIÓN:** La producción se detuvo en el cerdo {total_cerdos} porque **FALTAN KG DE {parte.upper()}**."); found_stop = True
        if not found_stop: st.info(f"ℹ️ Estado final: {logs[-1]}")

        with st.expander("📊 Detalle de lote (Gráficos e Inspector)", expanded=True):
            st.subheader("Evolución de Rentabilidad por Grupos")

            # Usamos el DF Filtrado para los gráficos y tablas si hay filtro activo
            df_viz = df_filtered if (filtro_art or filtro_cli) else df

            # Si el DF está vacío, mostramos aviso y no pintamos nada para evitar error
            if df_viz.empty:
                st.warning("No hay datos para mostrar con los filtros actuales.")
            else:
                lote_size = st.number_input("Tamaño Grupo", min_value=1, value=100, step=1)

                # Recalculamos grupos dinámicamente sobre la selección
                df_viz = df_viz.copy() # Evitar warning
                # Reiniciamos índice para agrupar visualmente la selección de 0 a N
                df_viz = df_viz.reset_index(drop=True)
                df_viz['Grupo_ID'] = df_viz.index // lote_size
                df_viz['Grupo_Label'] = df_viz['Grupo_ID'].apply(lambda x: f"Grupo {x+1}")

                grp_stats = df_viz.groupby('Grupo_Label').agg({'Precio_Medio': 'mean'}).reset_index()
                grp_stats['Coste'] = coste_total_kg; grp_stats['Rentabilidad'] = grp_stats['Precio_Medio'] - coste_total_kg

                # Robustez en la extracción del número de grupo
                grp_stats['Num_Grupo'] = pd.to_numeric(grp_stats['Grupo_Label'].str.extract('(\d+)')[0], errors='coerce').fillna(0).astype(int)

                base = alt.Chart(grp_stats).encode(
                    x=alt.X('Grupo_Label', sort=alt.EncodingSortField(field="Num_Grupo", order="ascending"), title="Grupos", axis=alt.Axis(labelAngle=-90)),
                    y=alt.Y('Precio_Medio', title="Precio Medio"),
                    tooltip=['Grupo_Label', 'Precio_Medio']
                ).properties(height=400)

                bars = base.mark_bar().encode(color=alt.Color('Rentabilidad', scale=alt.Scale(scheme='greens')))
                linea = alt.Chart(pd.DataFrame({'y': [coste_total_kg]})).mark_rule(color='red', strokeDash=[5,5]).encode(y='y')

                st.altair_chart((bars + linea).interactive(), use_container_width=True)

                st.divider()
                st.markdown("### 🔬 Detalle de Grupos (AgGrid)")
                st.caption("👇 **Haz CLIC en cualquier fila** para ver el **desglose REAL** de su coste.")
                grupos_disponibles = df_viz['Grupo_Label'].unique(); grupo_selec = st.selectbox("Selecciona Grupo:", grupos_disponibles); cerdos_grupo = df_viz[df_viz['Grupo_Label'] == grupo_selec]

                if not cerdos_grupo.empty:
                    g_cerdos = len(cerdos_grupo); g_ventas = cerdos_grupo['Precio_Total'].sum(); g_coste = g_cerdos * peso * coste_total_kg; g_ben = g_ventas - g_coste; g_pm = cerdos_grupo['Precio_Medio'].mean()
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Cerdos", g_cerdos)
                    c2.metric("Precio Venta", f"{g_pm:.2f} €/kg")
                    c3.metric("Beneficio Grupo", f"{g_ben:,.2f} €")
                    c4.metric("Rentabilidad/Kg", f"{(g_pm - coste_total_kg):.2f} €")

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
                            if row_key not in st.session_state.desgloses_db:
                                st.session_state.desgloses_db[row_key] = d['Breakdown']

                            detalles_flat.append({
                                'Familia': d.get('F', 'Otros'),
                                'Cliente': d['C'],
                                'Articulo': d['A'],
                                'Codigo': d.get('Cod', ''),
                                'Origen': d.get('Origen', 'Real'),
                                'Precio_EXW': d['P'],
                                'Precio_CP': d.get('CP', 0),
                                'Kg_Usados': d['K'],
                                'Row_Key': row_key
                            })

                    if detalles_flat:
                        df_detalles = pd.DataFrame(detalles_flat)
                        resumen = df_detalles.groupby(['Familia', 'Articulo', 'Codigo', 'Cliente', 'Origen', 'Precio_EXW', 'Precio_CP', 'Row_Key']).agg({'Kg_Usados': 'sum'}).reset_index()

                        grid_resp = mostrar_tabla_aggrid(resumen, currency_cols=['Precio_EXW', 'Precio_CP'], kg_cols=['Kg_Usados'], hidden_cols=['Row_Key'], key='grid_inspector_v2')

                        # BOTÓN DE DESCARGA PARA EL DETALLE
                        csv_detalle = convert_df_to_excel_csv(df_detalles.drop(columns=['Row_Key']))
                        st.download_button("📥 Descargar Detalle Grupo (CSV)", data=csv_detalle, file_name=f"detalle_{grupo_selec.replace(' ','_')}.csv", mime="text/csv")

                        selected_rows = grid_resp.get('selected_rows', [])
                        sel = None
                        if isinstance(selected_rows, pd.DataFrame):
                            if not selected_rows.empty: sel = selected_rows.iloc[0].to_dict()
                        elif isinstance(selected_rows, list):
                            if len(selected_rows) > 0: sel = selected_rows[0]

                        if sel:
                            r_key = sel['Row_Key']
                            breakdown_data = st.session_state.desgloses_db.get(r_key, [])

                            if breakdown_data:
                                esc_id = breakdown_data[0].get('Escandallo', 'Desconocido') if len(breakdown_data)>0 else ""
                                st.divider()
                                st.markdown(f"#### Escandallo: **{sel['Articulo']}** (Ref: {esc_id})")
                                st.caption(f"Desglose REAL de costes (Origen: {sel['Origen']})")

                                df_bd = pd.DataFrame(breakdown_data)
                                st.dataframe(df_bd.style.format({
                                    'Precio Aplicado (€)': '{:.2f} €',
                                    'Contribución (€)': '{:.4f} €'
                                }, na_rep=""), use_container_width=True)
                            else:
                                st.warning("⚠️ No se pudieron recuperar los detalles de coste para esta selección.")

                except Exception as e: st.error(f"Error detalles: {e}")

        with st.expander("🏁 Auditoría: Comprobación de Cantidades (Drivers)", expanded=True):
            audit_data = []
            for familia, kg_necesarios_cerdo in config.items():
                if kg_necesarios_cerdo <= 0: continue
                items = cajones_res.get(familia, []); total_anatomico = sum(x['Kg'] for x in items); total_ventas = sum(x['Kg_Venta_Original'] for x in items)
                pct_medio = (total_ventas / total_anatomico * 100) if total_anatomico > 0 else 0; max_cerdos = total_anatomico / kg_necesarios_cerdo if kg_necesarios_cerdo > 0 else 0
                audit_data.append({"Familia": familia, "Kg Venta (Neto)": total_ventas, "Rendimiento Medio": pct_medio, "Kg Reconstruidos (Anatómico)": total_anatomico, "Necesidad/Cerdo (Kg)": kg_necesarios_cerdo, "Cerdos Máximos": int(max_cerdos)})
            if audit_data:
                df_audit = pd.DataFrame(audit_data).sort_values("Cerdos Máximos")
                mostrar_tabla_aggrid(df_audit, height=300, kg_cols=["Kg Venta (Neto)", "Kg Reconstruidos (Anatómico)", "Necesidad/Cerdo (Kg)"], pct_cols=["Rendimiento Medio"], num_cols=["Cerdos Máximos"], heatmap_cols=["Cerdos Máximos"], key='grid_audit_v2')

                # BOTÓN DESCARGA AUDITORÍA
                csv_audit = convert_df_to_excel_csv(df_audit)
                st.download_button("📥 Descargar Auditoría (CSV)", data=csv_audit, file_name="auditoria_drivers.csv", mime="text/csv")

        with st.expander("🗑️ Auditoría de Secundarios: Inventados (No vendidos)", expanded=True):
            if not df_audit_sec.empty:
                df_inv = df_audit_sec[df_audit_sec['Tipo_Casacion'].str.contains("Inventado", case=False, na=False)]
                if not df_inv.empty:
                    resumen = df_inv.groupby(['Escandallo_ID', 'Codigo', 'Nombre']).agg({'Kg_Usados': 'sum'}).reset_index()
                    mostrar_tabla_aggrid(resumen, kg_cols=['Kg_Usados'], key='grid_secundarios_audit')
                    # BOTÓN DESCARGA INVENTADOS
                    csv_inv = convert_df_to_excel_csv(resumen)
                    st.download_button("📥 Descargar Inventados (CSV)", data=csv_inv, file_name="secundarios_inventados.csv", mime="text/csv")
                else: st.success("¡Perfecto! Todo se ha vendido o sustituido. No hay inventados.")
            else: st.info("No hay datos de auditoría disponibles.")

        if not df_s.empty:
            with st.expander("📦 Sobrantes Reales (Stock no utilizado)", expanded=True):
                cols = ['Familia', 'Codigo', 'Nombre', 'Tipo', 'Kg', 'Motivo']
                mostrar_tabla_aggrid(df_s[cols], height=500, kg_cols=['Kg'], key='grid_sobrantes_final')
                # BOTÓN DESCARGA SOBRANTES
                csv_sob = convert_df_to_excel_csv(df_s[cols])
                st.download_button("📥 Descargar Sobrantes (CSV)", data=csv_sob, file_name="sobrantes_stock.csv", mime="text/csv")
