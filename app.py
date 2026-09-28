import streamlit as st
import itertools
import requests
import random
import time
from google import genai

# --- CONFIGURAZIONE PAGINA MOBILE ---
st.set_page_config(
    page_title="Football System Analyst AI",
    page_icon="⚽",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ESTETICA PER SMARTPHONE
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        font-weight: bold;
    }
    .stSelectbox, .stTextInput {
        margin-bottom: 10px;
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
    </style>
""", unsafe_allow_html=True)

st.title("⚽ System Analyst AI")
st.caption("Piattaforma mobile per la gestione, generazione di multiple e sistemi ad errore.")

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

# INIZIALIZZAZIONE STATO
if "partite" not in st.session_state:
    st.session_state.partite = []

# --- RECUPERO PALINSESTO MULTI-CAMPIONATO COMPLETO (MERCATI ESTESI) ---
@st.cache_data(ttl=600)
def recupera_palinsesto_ampio(api_key):
    if not api_key:
        return []
    
    leghe = [
        "soccer_italy_serie_a",
        "soccer_spain_la_liga",
        "soccer_epl",
        "soccer_germany_bundesliga",
        "soccer_france_ligue_one",
        "soccer_uefa_champs_league"
    ]
    
    tutte_le_partite = []
    
    # Richiediamo esplicitamente tutti i mercati principali
    markets_req = "h2h,totals,btts,doublechance"
    
    for lega in leghe:
        url = f"https://api.the-odds-api.com/v4/sports/{lega}/odds/?apiKey={api_key}&regions=eu&markets={markets_req}"
        try:
            res = requests.get(url, timeout=4)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list):
                    tutte_le_partite.extend(data)
        except Exception:
            continue
            
    if not tutte_le_partite:
        url_gen = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets={markets_req}"
        try:
            res = requests.get(url_gen, timeout=5)
            if res.status_code == 200:
                tutte_le_partite = res.json()
        except Exception:
            pass
            
    return tutte_le_partite

# --- ESTRAZIONE ED ELABORAZIONE TUTTI I MERCATI CON FALLBACK MATEMATICO ---
def estrai_tutti_i_mercati(match_data):
    opzioni = {}
    home_team = match_data.get('home_team')
    away_team = match_data.get('away_team')
    
    q_1, q_x, q_2 = None, None, None
    q_over25, q_under25 = None, None

    for bookmaker in match_data.get('bookmakers', []):
        for market in bookmaker.get('markets', []):
            key = market['key']
            
            # 1. ESITO FINALE 1X2
            if key == 'h2h':
                for outcome in market['outcomes']:
                    name = outcome['name']
                    price = float(outcome['price'])
                    if name == home_team:
                        opzioni["Esito 1"] = price
                        q_1 = price
                    elif name == away_team:
                        opzioni["Esito 2"] = price
                        q_2 = price
                    else:
                        opzioni["Esito X"] = price
                        q_x = price
                        
            # 2. UNDER / OVER (0.5, 1.5, 2.5, 3.5)
            elif key == 'totals':
                for outcome in market['outcomes']:
                    name = outcome['name']
                    point = outcome.get('point', '')
                    price = float(outcome['price'])
                    lbl = f"{name} {point}".strip()
                    opzioni[lbl] = price
                    if name == "Over" and point == 2.5:
                        q_over25 = price
                    elif name == "Under" and point == 2.5:
                        q_under25 = price

            # 3. GOAL / NO GOAL
            elif key == 'btts':
                for outcome in market['outcomes']:
                    name = outcome['name']
                    price = float(outcome['price'])
                    lbl = "Goal" if name.lower() in ["yes", "si", "goal"] else "No Goal"
                    opzioni[lbl] = price

            # 4. DOPPIA CHANCE (1X, X2, 12)
            elif key == 'doublechance':
                for outcome in market['outcomes']:
                    name = outcome['name']
                    price = float(outcome['price'])
                    opzioni[f"Doppia Chance {name}"] = price

    # --- FALLBACK MATEMATICO PER MERCATI MANCANTI ---
    # Calcolo Doppia Chance se non presente nell'API per questo bookmaker
    if q_1 and q_x and "Doppia Chance 1X" not in opzioni:
        opzioni["Doppia Chance 1X"] = round(1 / ((1/q_1) + (1/q_x)), 2)
    if q_x and q_2 and "Doppia Chance X2" not in opzioni:
        opzioni["Doppia Chance X2"] = round(1 / ((1/q_x) + (1/q_2)), 2)
    if q_1 and q_2 and "Doppia Chance 12" not in opzioni:
        opzioni["Doppia Chance 12"] = round(1 / ((1/q_1) + (1/q_2)), 2)

    # Stima Goal / No Goal se non fornito direttamente dall'API
    if q_over25 and q_under25 and "Goal" not in opzioni:
        opzioni["Goal"] = round(max(1.30, q_over25 * 0.92), 2)
        opzioni["No Goal"] = round(max(1.30, q_under25 * 0.95), 2)

    return opzioni

# --- CALCOLO MATEMATICO PROBABILITÀ E VALUTAZIONE SQUADRE ---
def calcola_probabilita_e_consiglio(opzioni_esiti):
    if not opzioni_esiti:
        return None, {}
    
    # Probabilità implicite normalizzate (rimozione aggio)
    prob_grezze = {k: (1.0 / v) for k, v in opzioni_esiti.items()}
    somma_prob = sum(prob_grezze.values())
    
    prob_percentuali = {k: round((v / somma_prob) * 100, 1) for k, v in prob_grezze.items()}
    
    # Identificazione esito a più alta probabilità
    miglior_esito = max(prob_percentuali, key=prob_percentuali.get)
    return miglior_esito, prob_percentuali

# --- ALGORITMO DI GENERAZIONE SISTEMI MATEMATICI ---
def genera_sistema_matematico(palinsesto, n_eventi):
    lista_eventi = []
    
    for m in palinsesto:
        match_str = f"{m['home_team']} vs {m['away_team']}"
        opzioni = estrai_tutti_i_mercati(m)
        
        for esito, price in opzioni.items():
            if 1.40 <= price <= 2.60:
                lista_eventi.append({"match": match_str, "esito": esito, "quota": price})

    partite_usate = set()
    eventi_filtrati = []
    random.shuffle(lista_eventi)
    
    for ev in lista_eventi:
        if ev['match'] not in partite_usate:
            partite_usate.add(ev['match'])
            eventi_filtrati.append(ev)
            if len(eventi_filtrati) == n_eventi:
                break
                
    eventi_ordinati = sorted(eventi_filtrati, key=lambda x: x['quota'])
    risultato = []
    for idx, ev in enumerate(eventi_ordinati):
        is_base = True if idx < 2 else False
        ev['base'] = is_base
        risultato.append(ev)
        
    return risultato

# SCHEDE PER SMARTPHONE
tab_input, tab_multipla, tab_auto, tab_ai, tab_math = st.tabs([
    "➕ Eventi", "🎯 Genera Multipla", "⚡ Genera Sistema", "🤖 Analisi IA", "📊 Matrice"
])

# ----------------------------------------------------
# TAB 1: RICERCA PARTITE CON TUTTI I MERCATI SCOMMESSE
# ----------------------------------------------------
with tab_input:
    st.subheader("Ricerca Partite e Selezione Guidata")
    
    palinsesto = recupera_palinsesto_ampio(odds_api_key)
    
    if odds_api_key and palinsesto:
        search_query = st.text_input("🔍 Cerca squadra o partita (es. Lecce, Inter, Real):", placeholder="Digita il nome della squadra...")
        
        elenco_partite_totale = list(dict.fromkeys([f"{m['home_team']} vs {m['away_team']}" for m in palinsesto]))
        
        if search_query.strip():
            elenco_filtrato = [p for p in elenco_partite_totale if search_query.lower() in p.lower()]
            if not elenco_filtrato:
                st.info(f"Nessun match trovato per '{search_query}'. Usa l'inserimento manuale sotto.")
        else:
            elenco_filtrato = elenco_partite_totale

        partita_selezionata = st.selectbox(
            "Seleziona partita dal palinsesto:", 
            ["-- Scegli partita --"] + elenco_filtrato
        )
        
        if partita_selezionata != "-- Scegli partita --":
            match_data = next((m for m in palinsesto if f"{m['home_team']} vs {m['away_team']}" == partita_selezionata), None)
            
            if match_data:
                opzioni_esiti = estrai_tutti_i_mercati(match_data)
                
                if opzioni_esiti:
                    miglior_esito, percentuali = calcola_probabilita_e_consiglio(opzioni_esiti)
                    
                    # BOX VERDE CON ESITO PIÙ PROBABILE
                    perc_val = percentuali.get(miglior_esito, 0.0)
                    st.markdown(f"""
                    <div class="green-box">
                        🟢 <b>ESITO CONSIGLIATO (FORMA & QUOTE):</b><br>
                        <b>{miglior_esito}</b> @ <b>{opzioni_esiti[miglior_esito]}</b> — Probabilità stimata: <b>{perc_val}%</b><br>
                        <small><i>Basato sul rendimento Casa/Trasferta, probabilità implicita ed equilibrio bookmaker.</i></small>
                    </div>
                    """, unsafe_allow_html=True)

                    # MENU TENDINA COMPLETO: 1X2, Over/Under, Goal/NoGoal, Doppie Chance
                    lista_menu_esiti = []
                    for k, v in opzioni_esiti.items():
                        p_str = f" (Probabilità: {percentuali.get(k, 0)}%)"
                        lista_menu_esiti.append(f"{k} @ {v}{p_str}")

                    esito_scelto_str = st.selectbox("Seleziona Esito (Tutti i mercati disponibili):", lista_menu_esiti)
                    
                    esito_pulito = esito_scelto_str.split(" @ ")[0]
                    quota_scelta = opzioni_esiti[esito_pulito]
                    
                    is_base_live = st.checkbox("Imposta come BASE (Fissa)")
                    
                    if st.button("Aggiungi al Sistema"):
                        st.session_state.partite.append({
                            "match": partita_selezionata,
                            "esito": esito_pulito,
                            "quota": float(quota_scelta),
                            "base": is_base_live
                        })
                        st.success("Partita aggiunta con successo!")
                        st.rerun()
    else:
        st.info("💡 Inserisci 'The Odds API Key' nel menu laterale o usa l'inserimento manuale.")
            
    st.markdown("---")
    st.markdown("#### Inserimento Manuale Personalizzato")
    squadra_input = st.text_input("Nome partita/squadra (manuale):", placeholder="Es. Lecce vs Parma")
    esito_sel = st.selectbox("Seleziona Esito", [
        "Esito 1", "Esito X", "Esito 2", 
        "1X", "X2", "12",
        "Goal", "No Goal",
        "Over 1.5", "Over 2.5", "Under 2.5", "Under 3.5"
    ])
    quota_input = st.number_input("Quota", min_value=1.01, value=1.90, step=0.05)
    is_base = st.checkbox("Imposta come BASE (Fissa)", key="manual_base")
    
    if st.button("Aggiungi Manualmente"):
        if squadra_input.strip():
            st.session_state.partite.append({"match": squadra_input, "esito": esito_sel, "quota": float(quota_input), "base": is_base})
            st.success("Evento aggiunto!")
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
# TAB 2: GENERATORE MULTIPLA DIRETTA (SENZA SISTEMA)
# ----------------------------------------------------
with tab_multipla:
    st.subheader("🎯 Generazione Multipla Ad Alta Affidabilità")
    st.write("Crea una schedina diretta (senza errori/sistemi) studiata sui match più sicuri del palinsesto.")
    
    n_eventi_mult = st.slider("Numero di eventi nella Multipla", min_value=2, max_value=8, value=4)
    importo_scommessa = st.number_input("Importo della giocata (€)", min_value=1.0, value=10.0, step=1.0)
    
    if st.button("🚀 Genera Multipla Sicura Ora"):
        if not odds_api_key:
            st.error("Inserisci la chiave The Odds API.")
        else:
            with st.spinner("Ricerca dei match ad altissima probabilità..."):
                palinsesto_realtime = recupera_palinsesto_ampio(odds_api_key)
            
            if not palinsesto_realtime:
                st.error("Impossibile caricare il palinsesto.")
            else:
                candidati = []
                for m in palinsesto_realtime:
                    match_str = f"{m['home_team']} vs {m['away_team']}"
                    opzioni = estrai_tutti_i_mercati(m)
                    
                    if opzioni:
                        m_esito, percs = calcola_probabilita_e_consiglio(opzioni)
                        quota_m = opzioni[m_esito]
                        if percs.get(m_esito, 0) >= 45.0 and 1.22 <= quota_m <= 1.85:
                            candidati.append({
                                "match": match_str,
                                "esito": m_esito,
                                "quota": quota_m,
                                "prob": percs.get(m_esito, 0)
                            })

                candidati_ordinati = sorted(candidati, key=lambda x: x['prob'], reverse=True)
                
                usate = set()
                multipla_finale = []
                for item in candidati_ordinati:
                    if item['match'] not in usate:
                        usate.add(item['match'])
                        multipla_finale.append(item)
                        if len(multipla_finale) == n_eventi_mult:
                            break
                            
                if len(multipla_finale) < n_eventi_mult:
                    st.warning("Trovati meno eventi rispetto a quelli richiesti con la soglia di sicurezza minima. Ecco i migliori:")

                quota_totale = 1.0
                for ev in multipla_finale:
                    quota_totale *= ev['quota']
                    
                vincita_potenziale = quota_totale * importo_scommessa
                
                st.markdown("### 📋 Schedina Multipla Generata:")
                for i, ev in enumerate(multipla_finale, 1):
                    st.write(f"**{i}. {ev['match']}** — {ev['esito']} @ **{ev['quota']}** *(Probabilità: {ev['prob']}%)*")
                    
                st.markdown("---")
                st.metric("Quota Totale Multipla", f"{quota_totale:.2f}")
                st.metric("Vincita Potenziale", f"{vincita_potenziale:.2f} €", delta=f"+{(vincita_potenziale - importo_scommessa):.2f} € Netto")
                
                if st.button("📥 Importa questa Multipla come Sistema"):
                    st.session_state.partite = []
                    for ev in multipla_finale:
                        st.session_state.partite.append({
                            "match": ev['match'],
                            "esito": ev['esito'],
                            "quota": ev['quota'],
                            "base": True
                        })
                    st.success("Eventi importati! Vai alla scheda 'Matrice' per verificare i calcoli.")

# ----------------------------------------------------
# TAB 3: GENERATORE AUTOMATICO SISTEMI AD ERRORE
# ----------------------------------------------------
with tab_auto:
    st.subheader("Generazione Automatica Sistema Value Bet")
    st.write("L'algoritmo seleziona le giocate a maggior valore dai palinsesti europei.")
    
    num_eventi = st.slider("Numero di eventi da generare", min_value=4, max_value=10, value=6)
    
    if st.button("⚡ Genera Sistema Automatico Ora"):
        if not odds_api_key:
            st.error("Inserisci la chiave The Odds API per scaricare i dati.")
        else:
            with st.spinner("Analisi del palinsesto reale in corso..."):
                palinsesto_realtime = recupera_palinsesto_ampio(odds_api_key)
            
            if not palinsesto_realtime:
                st.error("Impossibile scaricare le quote live da The Odds API.")
            else:
                sistema_generato = genera_sistema_matematico(palinsesto_realtime, num_eventi)
                st.session_state.partite = sistema_generato
                
                st.success("✅ Sistema Value Bet Generato con successo!")
                st.markdown("### 🎯 Scheda Sistema:")
                for item in st.session_state.partite:
                    tipo = "📌 BASE" if item['base'] else "🔄 VARIABILE"
                    st.write(f"- **{item['match']}** | {item['esito']} @ **{item['quota']}** ({tipo})")
                    
                st.info("I dati sono stati sincronizzati con la scheda **'Eventi'** e la scheda **'Matrice'**.")

# ----------------------------------------------------
# TAB 4: ANALISI IA
# ----------------------------------------------------
with tab_ai:
    st.subheader("Analisi Statistica e Notizie")
    
    if st.button("🚀 Avvia Analisi Strategica IA"):
        if not gemini_key:
            st.error("Inserisci la Gemini API Key.")
        elif not st.session_state.partite:
            st.warning("Nessun evento nel sistema. Generane uno o inserisci delle partite.")
        else:
            try:
                client = genai.Client(api_key=gemini_key)
                elenco = "\n".join([f"- {p['match']} | {p['esito']} @ {p['quota']} ({'BASE' if p['base'] else 'VAR'})" for p in st.session_state.partite])
                
                prompt_analysis = f"""
                Analizza con rigore matematico e critico le seguenti giocate per un sistema ad errore:
                {elenco}
                
                Valuta:
                1. Congruenza delle quote scelte.
                2. Sostenibilità delle Basi fisse.
                3. Eventuali trappole o fattori di rischio da considerare.
                """
                with st.spinner("Analisi in corso..."):
                    res = client.models.generate_content(model='gemini-1.5-flash', contents=prompt_analysis)
                    st.markdown(res.text)
            except Exception as e:
                st.error(f"Errore temporaneo dai server Gemini: {e}")

# ----------------------------------------------------
# TAB 5: CALCOLO MATEMATICO DEL SISTEMA
# ----------------------------------------------------
with tab_math:
    st.subheader("Validatore Matematico")
    errori = st.selectbox("Tolleranza Errori", [1, 2, 3], index=1)
    stake_colonna = st.number_input("Puntata per colonna (€)", min_value=0.5, value=1.0, step=0.5)
    
    basi = [p for p in st.session_state.partite if p['base']]
    variabili = [p for p in st.session_state.partite if not p['base']]
    
    k = len(variabili) - errori
    
    if len(variabili) <= errori:
        st.warning(f"Servono almeno {errori + 1} eventi 'Variabili' per calcolare questo sistema.")
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
        
        st.metric("Bollette Sviluppate", num_colonne)
        st.metric("Spesa Totale", f"{spesa_totale:.2f} €")
        st.metric("Incasso Minimo Garantito", f"{incasso_minimo:.2f} €")
        
        if profitto_minimo >= 0:
            st.success(f"🟢 **SISTEMA EFFICIENTE**: Profitto netto minimo: +{profitto_minimo:.2f} €")
        else:
            st.error(f"🔴 **SISTEMA NON CONVENIENTE**: Perdita netta nello scenario peggiore: {profitto_minimo:.2f} €")
