import streamlit as st
import itertools
import requests
import random
from datetime import datetime, timezone, timedelta
from google import genai

# --- CONFIGURAZIONE PAGINA MOBILE ---
st.set_page_config(
    page_title="Football System Analyst AI Pro",
    page_icon="⚽",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ESTETICA MOBILE AVANZATA
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        font-weight: bold;
    }
    .green-box {
        background-color: #e6f4ea;
        border-left: 5px solid #137333;
        padding: 12px;
        border-radius: 6px;
        color: #137333;
        font-weight: bold;
        margin-bottom: 12px;
    }
    .warning-box {
        background-color: #fef7e0;
        border-left: 5px solid #b06000;
        padding: 12px;
        border-radius: 6px;
        color: #b06000;
        font-weight: bold;
        margin-bottom: 12px;
    }
    .stats-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 8px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚽ System Analyst AI — Pro")
st.caption("Piattaforma analitica avanzata con supporto Serie B, Serie C / Lega Pro e leghe minori europee.")

# --- GESTIONE CHIAVI API ---
with st.sidebar:
    st.header("⚙️ Configurazione API")
    gemini_key = st.text_input(
        "Gemini API Key", 
        value=st.secrets.get("GEMINI_API_KEY", ""), 
        type="password"
    )
    odds_api_key = st.text_input(
        "The Odds API Key (Quote Live)", 
        value=st.secrets.get("ODDS_API_KEY", "1fc996cb834a1af51b71c5eb9979dd53"), 
        type="password"
    )

if "partite" not in st.session_state:
    st.session_state.partite = []

# --- RECUPERO PALINSESTO ESTESO CON LEGHE MINORI ED ITALIANE ---
@st.cache_data(ttl=300)
def recupera_palinsesto_stabile(api_key):
    if not api_key:
        return []
    
    tutte = []
    
    # 1. Chiamata generica per catturare eventi generici
    url_gen = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
    try:
        res = requests.get(url_gen, timeout=6)
        if res.status_code == 200:
            tutte.extend(res.json())
    except Exception:
        pass

    # 2. Elenco completo comprendente Serie B, Serie C, League One, League Two ecc.
    leghe_estese = [
        # Italia
        "soccer_italy_serie_a",
        "soccer_italy_serie_b",
        "soccer_italy_serie_c",
        # Inghilterra
        "soccer_epl",
        "soccer_efl_champ",
        "soccer_england_league1",
        "soccer_england_league2",
        "soccer_england_national_league",
        # Spagna
        "soccer_spain_la_liga",
        "soccer_spain_segunda_division",
        # Germania
        "soccer_germany_bundesliga",
        "soccer_germany_bundesliga2",
        # Francia
        "soccer_france_ligue_1",
        "soccer_france_ligue_2",
        # Coppe e Nazionali
        "soccer_uefa_champs_league",
        "soccer_uefa_europa_league",
        "soccer_intl_specials",
        "soccer_fifa_world_cup"
    ]
    
    for lega in leghe_estese:
        url_l = f"https://api.the-odds-api.com/v4/sports/{lega}/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
        try:
            r = requests.get(url_l, timeout=3)
            if r.status_code == 200:
                tutte.extend(r.json())
        except Exception:
            continue
            
    visti = set()
    risultato_unico = []
    for m in tutte:
        m_id = m.get('id')
        if m_id and m_id not in visti:
            visti.add(m_id)
            risultato_unico.append(m)
        elif not m_id:
            risultato_unico.append(m)
            
    return risultato_unico

# --- FILTRO TEMPORALE MATCH ---
def filtra_per_orizzonte_temporale(palinsesto, opzione_tempo):
    ora_attuale = datetime.now(timezone.utc)
    palinsesto_filtrato = []

    for m in palinsesto:
        commence_str = m.get('commence_time')
        if not commence_str:
            palinsesto_filtrato.append(m)
            continue
            
        try:
            commence_time = datetime.fromisoformat(commence_str.replace('Z', '+00:00'))
        except Exception:
            palinsesto_filtrato.append(m)
            continue

        differenza = commence_time - ora_attuale

        if opzione_tempo == "Solo oggi":
            if commence_time.date() == ora_attuale.date():
                palinsesto_filtrato.append(m)
        elif opzione_tempo == "Oggi e domani":
            if commence_time.date() <= (ora_attuale + timedelta(days=1)).date():
                palinsesto_filtrato.append(m)
        elif opzione_tempo == "Entro 3 giorni":
            if differenza <= timedelta(days=3):
                palinsesto_filtrato.append(m)
        elif opzione_tempo == "Lungo termine (entro 12-14 giorni)":
            if differenza <= timedelta(days=14):
                palinsesto_filtrato.append(m)
        else:
            palinsesto_filtrato.append(m)

    return palinsesto_filtrato

# --- MOTORE ANALITICO ED ESTRAZIONE MERCATI ---
def estrai_mercati_completi(match_data):
    opzioni = {}
    home_team = match_data.get('home_team')
    away_team = match_data.get('away_team')
    
    q1, qx, q2 = None, None, None
    q_over25, q_under25 = None, None

    for bookmaker in match_data.get('bookmakers', []):
        for market in bookmaker.get('markets', []):
            key = market['key']
            if key == 'h2h':
                for outcome in market['outcomes']:
                    name = outcome['name']
                    price = float(outcome['price'])
                    if name == home_team:
                        q1 = price
                        opzioni["Esito 1"] = price
                    elif name == away_team:
                        q2 = price
                        opzioni["Esito 2"] = price
                    else:
                        qx = price
                        opzioni["Esito X"] = price
            elif key == 'totals':
                for outcome in market['outcomes']:
                    name = outcome['name']
                    point = outcome.get('point', 2.5)
                    price = float(outcome['price'])
                    if point == 2.5:
                        if name == "Over":
                            q_over25 = price
                            opzioni["Over 2.5"] = price
                        elif name == "Under":
                            q_under25 = price
                            opzioni["Under 2.5"] = price

    if q1 and qx:
        opzioni["Doppia Chance 1X"] = round(1 / ((1/q1) + (1/qx)), 2)
    if qx and q2:
        opzioni["Doppia Chance X2"] = round(1 / ((1/qx) + (1/q2)), 2)
    if q1 and q2:
        opzioni["Doppia Chance 12"] = round(1 / ((1/q1) + (1/q2)), 2)

    if q_over25 and q_under25:
        opzioni["Goal"] = round(max(1.30, q_over25 * 0.92), 2)
        opzioni["No Goal"] = round(max(1.30, q_under25 * 0.94), 2)
        opzioni["Over 3.5"] = round(max(1.80, q_over25 * 1.55), 2)

    return opzioni

def analizza_valore_e_probabilita(opzioni_esiti, tipo_mercato="Esiti Misti"):
    if not opzioni_esiti:
        return None, {}
    
    mercati_1x2 = {k: v for k, v in opzioni_esiti.items() if k in ["Esito 1", "Esito X", "Esito 2"]}
    if mercati_1x2:
        lavagna = sum([1.0 / v for v in mercati_1x2.values()])
        prob_reali = {k: round(((1.0 / v) / lavagna) * 100, 1) for k, v in opzioni_esiti.items()}
    else:
        lavagna = sum([1.0 / v for v in opzioni_esiti.values()])
        prob_reali = {k: round(((1.0 / v) / lavagna) * 100, 1) for k, v in opzioni_esiti.items()}

    if tipo_mercato == "Solo Esiti Fissi (1, X, 2)":
        filtrati = {k: v for k, v in prob_reali.items() if k in ["Esito 1", "Esito X", "Esito 2"]}
        scelta = max(filtrati, key=filtrati.get) if filtrati else max(prob_reali, key=prob_reali.get)
    elif tipo_mercato == "Solo Over 2.5 / Over 3.5":
        filtrati = {k: v for k, v in prob_reali.items() if k in ["Over 2.5", "Over 3.5"]}
        scelta = max(filtrati, key=filtrati.get) if filtrati else ("Over 2.5" if "Over 2.5" in opzioni_esiti else max(prob_reali, key=prob_reali.get))
    else:
        p_1 = prob_reali.get("Esito 1", 0)
        p_2 = prob_reali.get("Esito 2", 0)
        if abs(p_1 - p_2) < 15 and "Doppia Chance 1X" in opzioni_esiti:
            if opzioni_esiti.get("Goal", 0) >= 1.60 and prob_reali.get("Goal", 0) > 52:
                scelta = "Goal"
            elif p_1 >= p_2:
                scelta = "Doppia Chance 1X"
            else:
                scelta = "Doppia Chance X2"
        else:
            scelta = max(prob_reali, key=prob_reali.get)

    return scelta, prob_reali

# --- SELEZIONE DINAMICA PER TARGET QUOTA TOTALE ---
def genera_schedina_per_target_quota(palinsesto, target_quota, tipo_mercato, forza_generazione, modalita="multipla"):
    candidati = []
    for m in palinsesto:
        match_str = f"{m['home_team']} vs {m['away_team']}"
        opzioni = estrai_mercati_completi(m)
        if opzioni:
            esito_opt, prob_dict = analizza_valore_e_probabilita(opzioni, tipo_mercato)
            if esito_opt in opzioni:
                quota_opt = opzioni[esito_opt]
                prob_opt = prob_dict.get(esito_opt, 0)

                valido_strict = (1.25 <= quota_opt <= 2.50 and prob_opt >= 40.0)
                if valido_strict or forza_generazione:
                    candidati.append({
                        "match": match_str,
                        "esito": esito_opt,
                        "quota": quota_opt,
                        "prob": prob_opt,
                        "is_low_value": not valido_strict
                    })

    if not candidati:
        return [], 1.0

    # Ordiniamo per valore di probabilità
    candidati.sort(key=lambda x: x['prob'], reverse=True)
    
    usati = set()
    selezionati = []
    quota_accumulata = 1.0
    
    # Continua ad aggiungere finché non raggiunge la quota target
    for c in candidati:
        if c['match'] not in usati:
            usati.add(c['match'])
            selezionati.append(c)
            quota_accumulata *= c['quota']
            
            if quota_accumulata >= target_quota * 0.95:
                break
                
            if len(selezionati) >= 15:
                break

    if modalita == "sistema":
        for idx, item in enumerate(selezionati):
            item['base'] = True if idx < 2 else False

    return selezionati, quota_accumulata

# --- TABS NAVIGAZIONE ---
tab_input, tab_multipla, tab_auto, tab_ai, tab_math = st.tabs([
    "➕ Eventi", "🎯 Multipla Pro", "⚡ Sistema Value", "🤖 Analisi IA", "📊 Matrice"
])

# ----------------------------------------------------
# TAB 1: RICERCA E SELEZIONE
# ----------------------------------------------------
with tab_input:
    st.subheader("Ricerca Partite e Selezione Guidata")
    
    palinsesto = recupera_palinsesto_stabile(odds_api_key)
    
    if odds_api_key and palinsesto:
        search_query = st.text_input("🔍 Cerca squadra o partita (es. Lecce, Catania, Wrexham, Real):")
        
        elenco_partite_totale = list(dict.fromkeys([f"{m['home_team']} vs {m['away_team']}" for m in palinsesto]))
        
        if search_query.strip():
            elenco_filtrato = [p for p in elenco_partite_totale if search_query.lower() in p.lower()]
        else:
            elenco_filtrato = elenco_partite_totale

        if elenco_filtrato:
            partita_selezionata = st.selectbox("Seleziona partita dal palinsesto:", ["-- Scegli partita --"] + elenco_filtrato)
            
            if partita_selezionata != "-- Scegli partita --":
                match_data = next((m for m in palinsesto if f"{m['home_team']} vs {m['away_team']}" == partita_selezionata), None)
                if match_data:
                    opzioni_esiti = estrai_mercati_completi(match_data)
                    miglior_esito, percentuali = analizza_valore_e_probabilita(opzioni_esiti)
                    
                    st.markdown(f"""
                    <div class="green-box">
                        🟢 <b>SUGGERIMENTO ANALITICO:</b> {miglior_esito} @ <b>{opzioni_esiti[miglior_esito]}</b><br>
                        <small>Probabilità stimata de-aggiata: {percentuali.get(miglior_esito, 0)}%</small>
                    </div>
                    """, unsafe_allow_html=True)

                    lista_menu_esiti = [f"{k} @ {v} (Prob: {percentuali.get(k, 0)}%)" for k, v in opzioni_esiti.items()]
                    esito_scelto_str = st.selectbox("Seleziona Mercato:", lista_menu_esiti)
                    
                    esito_pulito = esito_scelto_str.split(" @ ")[0]
                    quota_scelta = opzioni_esiti[esito_pulito]
                    is_base_live = st.checkbox("Imposta come BASE (Fissa)")
                    
                    if st.button("Aggiungi al Schedario"):
                        st.session_state.partite.append({
                            "match": partita_selezionata,
                            "esito": esito_pulito,
                            "quota": float(quota_scelta),
                            "base": is_base_live
                        })
                        st.success("Partita aggiunta con successo!")
                        st.rerun()
        else:
            st.warning("Nessuna partita trovata con questo nome nel palinsesto esteso.")
    else:
        st.info("💡 Inserisci 'The Odds API Key' nel menu laterale per accedere al palinsesto live.")
            
    st.markdown("---")
    st.markdown("#### Inserimento Manuale Personalizzato")
    
    with st.form("form_manuale"):
        squadra_input = st.text_input("Nome partita/squadra (manuale):", placeholder="Es. Barcellona vs Real Madrid")
        esito_sel = st.selectbox("Seleziona Esito", [
            "Esito 1", "Esito X", "Esito 2", 
            "1X", "X2", "12",
            "Goal", "No Goal",
            "Over 1.5", "Over 2.5", "Under 2.5", "Under 3.5"
        ])
        quota_input = st.number_input("Quota", min_value=1.01, value=1.90, step=0.05)
        is_base = st.checkbox("Imposta come BASE (Fissa)")
        btn_manuale = st.form_submit_button("Aggiungi Manualmente")
        
        if btn_manuale:
            if squadra_input.strip():
                st.session_state.partite.append({"match": squadra_input, "esito": esito_sel, "quota": float(quota_input), "base": is_base})
                st.success("Evento manuale aggiunto!")
                st.rerun()
            else:
                st.error("Inserisci il nome della partita.")

    st.markdown("---")
    st.subheader(f"Eventi Selezionati ({len(st.session_state.partite)})")
    for idx, item in enumerate(st.session_state.partite):
        tipo = "📌 BASE" if item['base'] else "🔄 VARIABILE"
        st.write(f"**{idx+1}. {item['match']}** | {item['esito']} @ **{item['quota']}** ({tipo})")
        if st.button(f"Rimuovi #{idx+1}", key=f"del_{idx}"):
            st.session_state.partite.pop(idx)
            st.rerun()

# ----------------------------------------------------
# TAB 2: MULTIPLA PRO CON TARGET QUOTA
# ----------------------------------------------------
with tab_multipla:
    st.subheader("🎯 Multipla con Target Quota Personalizzato")
    
    orizzonte_mult = st.selectbox(
        "📅 Lasso di tempo match:",
        ["Solo oggi", "Oggi e domani", "Entro 3 giorni", "Lungo termine (entro 12-14 giorni)"],
        index=0,
        key="time_mult"
    )
    
    tipo_mercato_mult = st.selectbox(
        "⚽ Tipologia Scommessa Multipla:",
        ["Esiti Misti", "Solo Over 2.5 / Over 3.5", "Solo Esiti Fissi (1, X, 2)"],
        index=0,
        key="mercato_mult"
    )
    
    col_q1, col_q2 = st.columns(2)
    with col_q1:
        target_quota_mult = st.number_input("🎯 Quota Totale Target (da 3 a 100)", min_value=3.0, max_value=100.0, value=30.0, step=1.0)
    with col_q2:
        importo_mult = st.number_input("💶 Importo Giocata (€)", min_value=1.0, value=3.0, step=1.0)
        
    forza_mult = st.checkbox("⚠️ Forza generazione anche con partite a quota/valore basso", value=True, key="forza_mult")
    
    if st.button("🚀 Genera Multipla per Quota Target"):
        if not odds_api_key:
            st.error("Inserisci la chiave The Odds API.")
        else:
            with st.spinner("Ricerca nel palinsesto esteso (Serie A, B, C, League One, ecc.)..."):
                palinsesto_realtime = recupera_palinsesto_stabile(odds_api_key)
                palinsesto_filtrato = filtra_per_orizzonte_temporale(palinsesto_realtime, orizzonte_mult)
                multipla_finale, quota_effettiva = genera_schedina_per_target_quota(
                    palinsesto_filtrato, target_quota_mult, tipo_mercato_mult, forza_mult, modalita="multipla"
                )
            
            if not multipla_finale:
                st.warning("Nessuna combinazione trovata per i criteri impostati.")
            else:
                has_low_val = any(ev.get('is_low_value', False) for ev in multipla_finale)
                if has_low_val or target_quota_mult >= 30.0:
                    st.markdown("""
                    <div class="warning-box">
                        ⚠️ <b>AVVISO RISCHIO ELEVATO:</b> Quota target elevata. Giocare con prudenza.
                    </div>
                    """, unsafe_allow_html=True)

                vincita_potenziale = quota_effettiva * importo_mult
                
                st.markdown(f"### 📋 Multipla Generata ({len(multipla_finale)} Eventi):")
                for i, ev in enumerate(multipla_finale, 1):
                    tag_risk = " ⚠️ *(Quota/Valore Basso)*" if ev.get('is_low_value') else ""
                    st.markdown(f"""
                    <div class="stats-card">
                        <b>{i}. {ev['match']}</b>{tag_risk}<br>
                        Esito: <b>{ev['esito']}</b> @ <b>{ev['quota']}</b> | Probabilità Reale: <b>{ev['prob']}%</b>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                st.metric("Quota Totale Reale", f"{quota_effettiva:.2f}")
                st.metric("Vincita Potenziale", f"{vincita_potenziale:.2f} €")

# ----------------------------------------------------
# TAB 3: GENERATORE SISTEMI CON TARGET QUOTA
# ----------------------------------------------------
with tab_auto:
    st.subheader("⚡ Sistema Value Bet con Target Quota")
    
    orizzonte_sis = st.selectbox(
        "📅 Lasso di tempo match:",
        ["Solo oggi", "Oggi e domani", "Entro 3 giorni", "Lungo termine (entro 12-14 giorni)"],
        index=0,
        key="time_sis"
    )
    
    tipo_mercato_sis = st.selectbox(
        "⚽ Tipologia Scommessa Sistema:",
        ["Esiti Misti", "Solo Over 2.5 / Over 3.5", "Solo Esiti Fissi (1, X, 2)"],
        index=0,
        key="mercato_sis"
    )
    
    target_quota_sis = st.number_input("🎯 Quota Totale Target Sistema (da 3 a 100)", min_value=3.0, max_value=100.0, value=30.0, step=1.0)
    forza_sis = st.checkbox("⚠️ Forza generazione anche con partite a quota/valore basso", value=True, key="forza_sis")
    
    if st.button("⚡ Genera Sistema per Quota Target Ora"):
        if not odds_api_key:
            st.error("Inserisci la chiave The Odds API.")
        else:
            with st.spinner("Calcolo combinazioni su palinsesto esteso..."):
                palinsesto_realtime = recupera_palinsesto_stabile(odds_api_key)
                palinsesto_filtrato = filtra_per_orizzonte_temporale(palinsesto_realtime, orizzonte_sis)
                sistema_generato, quota_effettiva_sis = genera_schedina_per_target_quota(
                    palinsesto_filtrato, target_quota_sis, tipo_mercato_sis, forza_sis, modalita="sistema"
                )
            
            if not sistema_generato:
                st.error("Nessun evento individuato per costruire il sistema richiesto.")
            else:
                st.session_state.partite = sistema_generato
                st.success(f"✅ Sistema Generato ({len(sistema_generato)} eventi) e caricato nel Schedario! Quota accumulata: {quota_effettiva_sis:.2f}")
                for item in st.session_state.partite:
                    tipo = "📌 BASE" if item['base'] else "🔄 VARIABILE"
                    st.write(f"- **{item['match']}** | {item['esito']} @ **{item['quota']}** ({tipo})")

# ----------------------------------------------------
# TAB 4: ANALISI IA AVANZATA
# ----------------------------------------------------
with tab_ai:
    st.subheader("🤖 Analisi Critica & Audit IA")
    st.caption("Valutazione dei rischi e dei fattori esterni (infortuni, forma, motivazioni, turnover).")
    
    if st.button("🚀 Avvia Audit Analitico IA"):
        if not gemini_key:
            st.error("Inserisci la Gemini API Key.")
        elif not st.session_state.partite:
            st.warning("Nessun evento presente nel tuo schedario.")
        else:
            try:
                client = genai.Client(api_key=gemini_key)
                elenco = "\n".join([f"- {p['match']} | Esito: {p['esito']} @ {p['quota']} ({'BASE (Fissa)' if p['base'] else 'VARIABILE'})" for p in st.session_state.partite])
                
                prompt_rigido = f"""
                Sei un analista quantitativo e tattico di scommesse sportive professionale ed estremamente severo.
                Analizza in modo approfondito e senza accondiscendenza queste selezioni:
                {elenco}

                Svolgi una ricerca mentale approfondita incrociando i seguenti fattori chiave per ogni match:
                1. **Stato di Forma recente e Rendimento Casa/Trasferta**.
                2. **Impegni ravvicinati, impegni di Coppe/Nazionali e probabile Turnover**.
                3. **Infortuni chiave, squalifiche e forze complessive delle squadre**.
                4. **Condizioni o fattori esterni che incidono sulla partita**.

                Fornisci un report chiaro suddiviso in:
                - **Analisi Singole Partite & Insidie Nascoste**: Evidenzia eventuali trappole nelle quote.
                - **Valutazione del Rischio Globale**: Rispondi chiaramente se la giocata ha un valore atteso positivo (+EV).
                - **Verdetto Severo**: Indica quali eventi eliminare o sostituire.
                """
                
                with st.spinner("Audit approfondito IA con Gemini 2.5..."):
                    res = client.models.generate_content(
                        model='gemini-2.5-flash', 
                        contents=prompt_rigido
                    )
                st.markdown(res.text)
            except Exception as e:
                st.error(f"Errore durante l'elaborazione IA: {e}")

# ----------------------------------------------------
# TAB 5: MATRICE E CALCOLO SISTEMA
# ----------------------------------------------------
with tab_math:
    st.subheader("📊 Validatore Matematico e Calcolo Rendimento")
    errori = st.selectbox("Tolleranza Errori", [1, 2, 3], index=0)
    stake_colonna = st.number_input("Puntata per colonna (€)", min_value=0.5, value=1.0, step=0.5)
    
    basi = [p for p in st.session_state.partite if p['base']]
    variabili = [p for p in st.session_state.partite if not p['base']]
    k = len(variabili) - errori
    
    if len(variabili) <= errori:
        st.warning(f"Servono almeno {errori + 1} eventi 'Variabili' per sviluppare la matrice ad errore.")
    else:
        quote_var = [p['quota'] for p in variabili]
        combinazioni = list(itertools.combinations(quote_var, k))
        num_colonne = len(combinazioni)
        spesa_totale = num_colonne * stake_colonna
        
        quota_basi = 1.0
        for b in basi:
            quota_basi *= b['quota']
            
        peggiori_var = sorted(quote_var)[:k]
        quota_minima = quota_basi
        for q in peggiori_var:
            quota_minima *= q
            
        incasso_minimo = quota_minima * stake_colonna
        profitto_minimo = incasso_minimo - spesa_totale
        
        st.metric("Sviluppo Bollette (Colonne)", num_colonne)
        st.metric("Spesa Totale", f"{spesa_totale:.2f} €")
        st.metric("Incasso Minimo Garantito", f"{incasso_minimo:.2f} €")
        
        if profitto_minimo >= 0:
            st.success(f"🟢 **SISTEMA A VALORE POSITIVO**: Profitto minimo netto: +{profitto_minimo:.2f} €")
        else:
            st.error(f"🔴 **ATTENZIONE — RESA NEGATIVA**: Perdita nello scenario con {errori} errori: {profitto_minimo:.2f} € (Aumenta le quote o riduci le variabili).")
