# ==============================================================================
# 1. IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================
import streamlit as st
import pandas as pd
import os
import altair as alt
import re 

# ==============================================================================
# 2. CONFIGURACIÓN E INTERFAZ
# ==============================================================================
st.set_page_config(
    page_title="NBA Analyzer V14 (Full Classification)",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🏀"
)

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    div[data-testid="metric-container"] {
        background-color: #1e2130;
        border: 1px solid #2b3144;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .metric-ml { color: #f1c40f !important; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. PROCESAMIENTO DE DATOS
# ==============================================================================
ARCHIVO = 'datos.xlsx'

def parse_teams(row):
    try:
        p = str(row['Partido (Local vs Visitante)']).strip()
        parts = p.split(' vs ')
        if len(parts) != 2: return None, None
        h_match = re.match(r'^([A-Z]+)', parts[0].strip())
        a_match = re.match(r'^([A-Z]+)', parts[1].strip())
        if h_match and a_match:
            return h_match.group(1), a_match.group(1)
        return None, None
    except:
        return None, None

def invertir_clasificacion(texto):
    """
    Invierte la clasificación del Excel para el equipo contrario.
    Ej: "Favorito Pesado" -> "Underdog Pesado"
    """
    if pd.isna(texto): return "N/A"
    texto = str(texto)
    
    if "Favorito" in texto:
        return texto.replace("Favorito", "Underdog")
    elif "Underdog" in texto:
        return texto.replace("Underdog", "Favorito")
    # Si dice Pick'em o algo neutro, se queda igual (o ajusta según tu excel)
    return texto

@st.cache_data
def cargar_datos_v14():
    if not os.path.exists(ARCHIVO): return None
    try:
        try: df = pd.read_excel(ARCHIVO)
        except: df = pd.read_csv(ARCHIVO)
        df.columns = df.columns.str.strip()
        
        if 'Fecha' in df.columns: df['Fecha'] = pd.to_datetime(df['Fecha'])
        df = df.sort_values('Fecha').reset_index(drop=True)
        if 'HomeTeam' not in df.columns:
            df[['HomeTeam', 'AwayTeam']] = df.apply(parse_teams, axis=1, result_type='expand')

        team_history = {} 
        team_streaks = {} 
        
        new_cols = {
            # Rachas
            'Calc_Home_Streak': [], 'Calc_Away_Streak': [],
            # Rest y Viaje
            'Calc_Home_Rest': [], 'Calc_Away_Rest': [],
            'Calc_Home_Travel': [], 'Calc_Away_Travel': [],
            'Calc_Pick_Travel': [], 'Calc_Opp_Travel': [],
            # Previos Generales
            'Calc_Home_Prev_ATS': [], 'Calc_Away_Prev_ATS': [],
            'Calc_Home_Prev_ML': [], 'Calc_Away_Prev_ML': [], 
            'Calc_Home_Prev_OU': [], 'Calc_Away_Prev_OU': [],
            # Previos Relativos al Pick
            'Calc_Pick_Prev_ATS': [], 'Calc_Opp_Prev_ATS': [],
            'Calc_Pick_Prev_ML': [], 'Calc_Opp_Prev_ML': [],
            'Calc_Pick_Prev_OU': [], 'Calc_Opp_Prev_OU': [],
            # CLASIFICACIÓN REAL (NUEVO)
            'Real_Home_Class': [], 'Real_Away_Class': [],
            # Flags
            'Real_Home_Covered': [], 'Real_Away_Covered': [],
            'Real_Home_Won': [], 'Real_Away_Won': []
        }

        for idx, row in df.iterrows():
            home, away = row['HomeTeam'], row['AwayTeam']
            pick = row['Selección Modelo']
            game_date = row['Fecha']
            
            # --- LÓGICA DE CLASIFICACIÓN (ESPEJO) ---
            # Obtenemos la clasificación del Pick desde el Excel
            class_pick = row.get('Tipo de Momio', 'N/A')
            class_opp = invertir_clasificacion(class_pick)
            
            if pick == home:
                new_cols['Real_Home_Class'].append(class_pick)
                new_cols['Real_Away_Class'].append(class_opp)
            else: # Pick is Away
                new_cols['Real_Away_Class'].append(class_pick)
                new_cols['Real_Home_Class'].append(class_opp)

            # --- RACHAS & HISTORIA (Standard) ---
            h_streak = team_streaks.get(home, 0)
            a_streak = team_streaks.get(away, 0)
            new_cols['Calc_Home_Streak'].append(h_streak)
            new_cols['Calc_Away_Streak'].append(a_streak)

            h_last = team_history.get(home)
            a_last = team_history.get(away)
            
            def get_rest(last):
                if not last: return "N/A"
                delta = (game_date - last['date']).days - 1
                return "0" if delta < 0 else "3+" if delta >= 3 else str(delta)
            
            def get_travel(last, is_home_now):
                if not last: return "N/A"
                if last['was_home']: return "L-L (Homestand)" if is_home_now else "L-V (Sale)"
                else: return "V-L (Regresa)" if is_home_now else "V-V (Gira)"
            
            def get_prev_ats(last): return "SI" if last and last['covered'] else ("NO" if last else "N/A")
            def get_prev_ml(last): return "SI" if last and last['won'] else ("NO" if last else "N/A")
            def get_prev_ou(last): return last['ou'] if last else "N/A"

            # Generales
            h_trav = get_travel(h_last, True)
            a_trav = get_travel(a_last, False)
            new_cols['Calc_Home_Travel'].append(h_trav)
            new_cols['Calc_Away_Travel'].append(a_trav)
            new_cols['Calc_Home_Rest'].append(get_rest(h_last))
            new_cols['Calc_Away_Rest'].append(get_rest(a_last))
            
            new_cols['Calc_Home_Prev_ATS'].append(get_prev_ats(h_last))
            new_cols['Calc_Away_Prev_ATS'].append(get_prev_ats(a_last))
            new_cols['Calc_Home_Prev_ML'].append(get_prev_ml(h_last))
            new_cols['Calc_Away_Prev_ML'].append(get_prev_ml(a_last))
            new_cols['Calc_Home_Prev_OU'].append(get_prev_ou(h_last))
            new_cols['Calc_Away_Prev_OU'].append(get_prev_ou(a_last))

            # Relativos al Pick
            if pick == home:
                pick_last, opp_last = h_last, a_last
                pick_trav, opp_trav = h_trav, a_trav
            else:
                pick_last, opp_last = a_last, h_last
                pick_trav, opp_trav = a_trav, h_trav
            
            new_cols['Calc_Pick_Travel'].append(pick_trav)
            new_cols['Calc_Opp_Travel'].append(opp_trav)
            new_cols['Calc_Pick_Prev_ATS'].append(get_prev_ats(pick_last))
            new_cols['Calc_Opp_Prev_ATS'].append(get_prev_ats(opp_last))
            new_cols['Calc_Pick_Prev_ML'].append(get_prev_ml(pick_last))
            new_cols['Calc_Opp_Prev_ML'].append(get_prev_ml(opp_last))
            new_cols['Calc_Pick_Prev_OU'].append(get_prev_ou(pick_last))
            new_cols['Calc_Opp_Prev_OU'].append(get_prev_ou(opp_last))

            # RESULTADOS
            is_pick_home = (pick == home)
            ats_hit = (row['Resultado ATS'] == 'SI')
            ml_hit = (row['Resultado ML'] == 'SI')
            
            if is_pick_home:
                home_covered = ats_hit
                away_covered = not ats_hit
            else:
                away_covered = ats_hit
                home_covered = not ats_hit
            
            if ml_hit: winner_team = pick
            else: winner_team = away if is_pick_home else home
                
            home_won = (winner_team == home)
            away_won = (winner_team == away)
            
            new_cols['Real_Home_Covered'].append(home_covered)
            new_cols['Real_Away_Covered'].append(away_covered)
            new_cols['Real_Home_Won'].append(home_won)
            new_cols['Real_Away_Won'].append(away_won)
            
            if home_won:
                team_streaks[home] = h_streak + 1 if h_streak > 0 else 1
                team_streaks[away] = a_streak - 1 if a_streak < 0 else -1
            else:
                team_streaks[away] = a_streak + 1 if a_streak > 0 else 1
                team_streaks[home] = h_streak - 1 if h_streak < 0 else -1

            team_history[home] = {'date': game_date, 'covered': home_covered, 'won': home_won, 'ou': row['Resultado O/U'], 'was_home': True}
            team_history[away] = {'date': game_date, 'covered': away_covered, 'won': away_won, 'ou': row['Resultado O/U'], 'was_home': False}

        for k, v in new_cols.items(): df[k] = v
        df['Fecha_Str'] = df['Fecha'].dt.strftime('%Y-%m-%d')
        return df 
    except Exception as e:
        st.error(f"Error V14: {e}")
        return None

df = cargar_datos_v14()

if df is None:
    st.error(f"❌ Error crítico. Verifica '{ARCHIVO}'")
    st.stop()

# ==============================================================================
# 4. INTERFAZ Y FILTROS
# ==============================================================================
st.sidebar.markdown("### 🎛️ MODO DE ANÁLISIS")
modo_analisis = st.sidebar.radio("Enfoque:", ["🤖 Rendimiento del Modelo", "🌍 Tendencias de Equipo (Mercado)"], index=1)
st.sidebar.markdown("---")

def crear_filtro(etiqueta, columna, key_id):
    if columna not in df.columns: return 'Todos'
    valores = df[columna].fillna("N/A").astype(str).unique()
    valores = [v for v in valores if v != "" and v != "nan"]
    return st.sidebar.selectbox(etiqueta, ['Todos'] + sorted(valores), key=key_id)

def crear_filtro_racha_rango(etiqueta, key_id):
    opciones = ["Todos", "3+ Victorias (🔥)", "4+ Victorias (🔥🔥)", "5+ Victorias (🔥🔥🔥)", "6+ Victorias (🚀)",
                "3+ Derrotas (❄️)", "4+ Derrotas (❄️❄️)", "5+ Derrotas (🧊)", "6+ Derrotas (💀)"]
    return st.sidebar.selectbox(etiqueta, opciones, key=key_id)

# Variables globales filtro
f_equipo, f_condicion, f_confianza, f_h2h = 'Todos', 'Todos', 'Todos', 'Todos'
f_target_team, f_role, f_status_team_class = 'Todos', 'Todos', 'Todos'
f_prev_pick_ats, f_prev_opp_ats = 'Todos', 'Todos'
f_prev_pick_ml, f_prev_opp_ml = 'Todos', 'Todos'
f_prev_pick_ou, f_prev_opp_ou = 'Todos', 'Todos'
f_travel_pick, f_travel_opp = 'Todos', 'Todos'

# --- MENU DINÁMICO ---
if modo_analisis == "🤖 Rendimiento del Modelo":
    with st.sidebar.expander("📂 Filtros Modelo", expanded=True):
        f_equipo = crear_filtro("Equipo (Pick)", "Selección Modelo", "m_eq")
        f_condicion = crear_filtro("Condición (Pick)", "EsLocal", "m_loc")
        f_confianza = crear_filtro("Confianza", "Confianza", "m_conf")
        f_h2h = crear_filtro("H2H Season", "H2H_Season", "m_h2h")

    with st.sidebar.expander("🔄 Situacional (Pick vs Rival)"):
        # VIAJES
        t1, t2 = st.columns(2)
        with t1: f_travel_pick = crear_filtro("Viaje Pick", "Calc_Pick_Travel", "p_tr")
        with t2: f_travel_opp = crear_filtro("Viaje Rival", "Calc_Opp_Travel", "o_tr")
        st.markdown("---")
        # ATS & ML (GANÓ)
        c1, c2 = st.columns(2)
        with c1: f_prev_pick_ats = crear_filtro("Pick Cubrió?", "Calc_Pick_Prev_ATS", "p_ats")
        with c2: f_prev_opp_ats = crear_filtro("Rival Cubrió?", "Calc_Opp_Prev_ATS", "o_ats")
        
        c3, c4 = st.columns(2)
        with c3: f_prev_pick_ml = crear_filtro("Pick Ganó (ML)?", "Calc_Pick_Prev_ML", "p_ml") 
        with c4: f_prev_opp_ml = crear_filtro("Rival Ganó (ML)?", "Calc_Opp_Prev_ML", "o_ml")
        
        st.markdown("---")
        c5, c6 = st.columns(2)
        with c5: f_prev_pick_ou = crear_filtro("Pick O/U", "Calc_Pick_Prev_OU", "p_ou")
        with c6: f_prev_opp_ou = crear_filtro("Rival O/U", "Calc_Opp_Prev_OU", "o_ou")

elif modo_analisis == "🌍 Tendencias de Equipo (Mercado)":
    with st.sidebar.expander("🌍 Filtros de Equipo", expanded=True):
        all_teams = sorted(list(set(df['HomeTeam'].unique()) | set(df['AwayTeam'].unique())))
        f_target_team = st.sidebar.selectbox("Equipo Objetivo", ['Todos'] + all_teams, key="t_team")
        f_role = st.sidebar.selectbox("Rol", ["Todos", "Local (Home)", "Visita (Away)"], key="t_role")
        
        # FILTRO MEJORADO: Clasificación Específica (Pesado, Moderado, etc.)
        # Unificamos todas las clases posibles (Home y Away) para llenar el combo
        all_classes = sorted(list(set(df['Real_Home_Class'].unique()) | set(df['Real_Away_Class'].unique())))
        all_classes = [c for c in all_classes if c != "N/A"]
        f_status_team_class = st.sidebar.selectbox("Clasificación Mercado (Odds Type)", ['Todos'] + all_classes, key="t_stat_class")
        
        f_h2h = crear_filtro("H2H Season", "H2H_Season", "mer_h2h")

    with st.sidebar.expander("🔄 Situacional (Local vs Visita)"):
        t1, t2 = st.columns(2)
        with t1: f_travel_pick = crear_filtro("Viaje Local", "Calc_Home_Travel", "h_tr")
        with t2: f_travel_opp = crear_filtro("Viaje Visita", "Calc_Away_Travel", "a_tr")
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1: f_prev_pick_ats = crear_filtro("Local Cubrió?", "Calc_Home_Prev_ATS", "h_ats")
        with c2: f_prev_opp_ats = crear_filtro("Visita Cubrió?", "Calc_Away_Prev_ATS", "a_ats")
        c3, c4 = st.columns(2)
        with c3: f_prev_pick_ml = crear_filtro("Local Ganó?", "Calc_Home_Prev_ML", "h_ml")
        with c4: f_prev_opp_ml = crear_filtro("Visita Ganó?", "Calc_Away_Prev_ML", "a_ml")

# --- COMUNES ---
with st.sidebar.expander("🔥 Rachas (Streaks)"):
    c1, c2 = st.columns(2)
    with c1: f_streak_h_lbl = crear_filtro_racha_rango("Racha Local", "s_h_rng")
    with c2: f_streak_a_lbl = crear_filtro_racha_rango("Racha Visita", "s_a_rng")

with st.sidebar.expander("⏳ Descanso (Rest)"):
    c3, c4 = st.columns(2)
    with c3: f_rest_h = crear_filtro("Rest Local", "Calc_Home_Rest", "r_h")
    with c4: f_rest_a = crear_filtro("Rest Visita", "Calc_Away_Rest", "r_a")

with st.sidebar.expander("📊 Mercado"):
    f_tipo = crear_filtro("Tipo Partido", "Tipo de Partido", "gen_tipo")
    f_linea = crear_filtro("Línea O/U", "Nivel de Línea", "gen_linea")
    if modo_analisis == "🤖 Rendimiento del Modelo":
        f_ml = crear_filtro("Momio (Del Pick)", "Tipo de Momio", "gen_ml")
    else:
        f_ml = 'Todos' 

# ==============================================================================
# 5. FILTRADO
# ==============================================================================
df_f = df.copy()

if f_h2h != 'Todos': df_f = df_f[df_f['H2H_Season'].fillna("").astype(str) == f_h2h]

if modo_analisis == "🤖 Rendimiento del Modelo":
    if f_equipo != 'Todos': df_f = df_f[df_f['Selección Modelo'] == f_equipo]
    if f_condicion != 'Todos': df_f = df_f[df_f['EsLocal'] == f_condicion]
    if f_confianza != 'Todos': df_f = df_f[df_f['Confianza'] == f_confianza]
    if f_ml != 'Todos': df_f = df_f[df_f['Tipo de Momio'] == f_ml]

    # Situacional (Pick/Opp)
    if f_travel_pick != 'Todos': df_f = df_f[df_f['Calc_Pick_Travel'] == f_travel_pick]
    if f_travel_opp != 'Todos': df_f = df_f[df_f['Calc_Opp_Travel'] == f_travel_opp]
    if f_prev_pick_ats != 'Todos': df_f = df_f[df_f['Calc_Pick_Prev_ATS'] == f_prev_pick_ats]
    if f_prev_opp_ats != 'Todos': df_f = df_f[df_f['Calc_Opp_Prev_ATS'] == f_prev_opp_ats]
    if f_prev_pick_ml != 'Todos': df_f = df_f[df_f['Calc_Pick_Prev_ML'] == f_prev_pick_ml]
    if f_prev_opp_ml != 'Todos': df_f = df_f[df_f['Calc_Opp_Prev_ML'] == f_prev_opp_ml]
    if f_prev_pick_ou != 'Todos': df_f = df_f[df_f['Calc_Pick_Prev_OU'] == f_prev_pick_ou]
    if f_prev_opp_ou != 'Todos': df_f = df_f[df_f['Calc_Opp_Prev_OU'] == f_prev_opp_ou]

    df_f['WIN_FLAG'] = df_f['Resultado ATS'] == 'SI'
    df_f['ML_FLAG'] = df_f['Resultado ML'] == 'SI'

elif modo_analisis == "🌍 Tendencias de Equipo (Mercado)":
    # 1. Filtro Equipo
    if f_target_team != 'Todos':
        df_f = df_f[(df_f['HomeTeam'] == f_target_team) | (df_f['AwayTeam'] == f_target_team)]
    
    # 2. Filtro Rol y Clasificación Específica
    if f_role == "Local (Home)":
        if f_target_team != 'Todos': df_f = df_f[df_f['HomeTeam'] == f_target_team]
        if f_status_team_class != 'Todos': df_f = df_f[df_f['Real_Home_Class'] == f_status_team_class] # Filtra por "Favorito Pesado", etc.
            
    elif f_role == "Visita (Away)":
        if f_target_team != 'Todos': df_f = df_f[df_f['AwayTeam'] == f_target_team]
        if f_status_team_class != 'Todos': df_f = df_f[df_f['Real_Away_Class'] == f_status_team_class]
    
    else: # Rol = Todos
        if f_target_team != 'Todos' and f_status_team_class != 'Todos':
            df_f = df_f[
                ((df_f['HomeTeam']==f_target_team) & (df_f['Real_Home_Class']==f_status_team_class)) |
                ((df_f['AwayTeam']==f_target_team) & (df_f['Real_Away_Class']==f_status_team_class))
            ]

    # Situacional (Home/Away)
    if f_travel_pick != 'Todos': df_f = df_f[df_f['Calc_Home_Travel'] == f_travel_pick]
    if f_travel_opp != 'Todos': df_f = df_f[df_f['Calc_Away_Travel'] == f_travel_opp]
    if f_prev_pick_ats != 'Todos': df_f = df_f[df_f['Calc_Home_Prev_ATS'] == f_prev_pick_ats]
    if f_prev_opp_ats != 'Todos': df_f = df_f[df_f['Calc_Away_Prev_ATS'] == f_prev_opp_ats]
    if f_prev_pick_ml != 'Todos': df_f = df_f[df_f['Calc_Home_Prev_ML'] == f_prev_pick_ml]
    if f_prev_opp_ml != 'Todos': df_f = df_f[df_f['Calc_Away_Prev_ML'] == f_prev_opp_ml]

    # Flags Ganador
    if f_target_team != 'Todos':
        df_f['WIN_FLAG'] = df_f.apply(lambda r: r['Real_Home_Covered'] if r['HomeTeam']==f_target_team else r['Real_Away_Covered'], axis=1)
        df_f['ML_FLAG'] = df_f.apply(lambda r: r['Real_Home_Won'] if r['HomeTeam']==f_target_team else r['Real_Away_Won'], axis=1)
    else:
        df_f['WIN_FLAG'] = df_f['Real_Home_Covered'] # Default Home
        df_f['ML_FLAG'] = df_f['Real_Home_Won']

# Comunes
def aplicar_filtro_racha(dframe, col_name, label_filtro):
    if label_filtro == 'Todos': return dframe
    try: num = int(label_filtro.split('+')[0]) 
    except: return dframe
    if "Victorias" in label_filtro: return dframe[dframe[col_name] >= num]
    elif "Derrotas" in label_filtro: return dframe[dframe[col_name] <= -num]
    return dframe

df_f = aplicar_filtro_racha(df_f, 'Calc_Home_Streak', f_streak_h_lbl)
df_f = aplicar_filtro_racha(df_f, 'Calc_Away_Streak', f_streak_a_lbl)

if f_rest_h != 'Todos': df_f = df_f[df_f['Calc_Home_Rest'] == f_rest_h]
if f_rest_a != 'Todos': df_f = df_f[df_f['Calc_Away_Rest'] == f_rest_a]
if f_tipo != 'Todos': df_f = df_f[df_f['Tipo de Partido'] == f_tipo]
if f_linea != 'Todos': df_f = df_f[df_f['Nivel de Línea'] == f_linea]
if f_ml != 'Todos': df_f = df_f[df_f['Tipo de Momio'] == f_ml]

# ==============================================================================
# 6. DASHBOARD
# ==============================================================================
st.markdown(f"### 📊 Resultados ({len(df_f)} Partidos)")

total = len(df_f)
if total > 0:
    ats_wins = df_f['WIN_FLAG'].sum()
    ats_rate = (ats_wins / total * 100)
    roi = ((ats_wins * 90.91 - (total - ats_wins) * 100) / (total * 100) * 100)
    ml_wins = df_f['ML_FLAG'].sum()
    ml_rate = (ml_wins / total * 100)
    over_rate = (len(df_f[df_f['Resultado O/U']=='Over']) / total * 100)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Partidos", total)
    c2.metric("Win Rate ATS", f"{ats_rate:.1f}%", delta=f"{ats_rate-52.4:.1f}%", delta_color="normal" if ats_rate>52.4 else "inverse")
    c3.metric("Moneyline (ML)", f"{ml_rate:.1f}%", delta="Ganador")
    c4.metric("ROI (ATS)", f"{roi:.1f}%", delta="Positivo" if roi>0 else "Negativo")
    c5.metric("O/U Tendencia", "OVER" if over_rate > 50 else "UNDER", f"{max(over_rate, 100-over_rate):.1f}%")

    if ats_rate >= 60 and total >= 5: st.success(f"🔥 **ALERTA ATS:** {ats_rate:.1f}% Win Rate")

    tab1, tab2 = st.tabs(["📉 Gráficos", "📋 Tabla Completa (Excel)"])
    
    with tab1:
        g1, g2 = st.columns(2)
        with g1:
            df_chart = pd.DataFrame({'R': ['Cubrió', 'Falló'], 'V': [ats_wins, total-ats_wins]})
            st.altair_chart(alt.Chart(df_chart).mark_arc(innerRadius=60).encode(
                theta=alt.Theta("V", stack=True), color=alt.Color("R", scale=alt.Scale(range=['#00c853', '#ff5252']))
            ), use_container_width=True)
        with g2:
            st.altair_chart(alt.Chart(df_f).mark_bar().encode(
                x="count()", y=alt.Y("Resultado O/U", sort="-x"), color="Resultado O/U"
            ), use_container_width=True)

    with tab2:
        def style_ats(val): return f'background-color: {"rgba(46, 204, 113, 0.2)" if val=="SI" else "rgba(231, 76, 60, 0.2)"}'
        def style_streak(val):
            try:
                v = int(val)
                if v >= 3: return 'color: #2ecc71; font-weight: bold' 
                if v <= -3: return 'color: #e74c3c; font-weight: bold'
            except: pass
            return ''

        st.dataframe(
            df_f.style
            .applymap(style_streak, subset=['Calc_Home_Streak', 'Calc_Away_Streak'])
            .applymap(style_ats, subset=['Resultado ATS']),
            use_container_width=True
        )
else:

    st.warning("⚠️ No hay datos.")
