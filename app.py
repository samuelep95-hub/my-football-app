import streamlit as st
import itertools
import requests
import random
from google import genai

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Football System Analyst AI",
    page_icon="⚽",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ESTETICA MOBILE
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

if "partite" not in st.session_state:
    st.session_state.partite = []

# --- RECUPERO PALINSESTO STABILE E VELOCE ---
@st.cache_data(ttl=300)
def recupera_palinsesto_stabile(api_key):
    if not api_key:
        return []
    
    # Endpoint generico soccer per evitare timeout ed errori HTTP
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
    try:
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

# --- GENERATORE/DERIVATORE COMPLETO DI TUTTI I MERCATI SCOMMESSE ---
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

    # DERIVAZIONE MATEMATICA PRECISA DOPPIA CHANCE (se 1X2 presenti)
    if q1 and qx:
        opzioni["Doppia Chance 1X"] = round(1 / ((1/q1) + (1/qx)), 2)
    if qx and q2:
        opzioni["Doppia Chance X2"] = round(1 / ((1/qx) + (1/q2)), 2)
    if q1 and q2:
        opzioni["Doppia Chance 12"] = round(1 / ((1/q1) + (1/q2)), 2)

    # DERIVAZIONE GOAL / NO GOAL DALL'UNDER/OVER 2.5
    if q_over25 and q_under25:
        opzioni["Goal"] = round(max(1.25, q_over25 * 0.93), 2)
        opzioni["No Goal"] = round(max(1.25, q_under25 * 0.95), 2)
    elif q1 and q2:
        opzioni["Goal"] = round(max(1.30, min(q1, q2) * 0.85), 2)
        opzioni["No Goal"] = round(max(1.30, max(q1, q2) * 0.75), 2)

    return opzioni

def calcola_probabilita_e_consiglio(opzioni_esiti):
    if not opzioni_esiti:
        return None, {}
    
    # Calcolo probabilità reali per 1X2 e principali
    tot = sum([1.0/v for k, v in opzioni_esiti.items() if k in ["Esito 1", "Esito X", "Esito 2"]])
    if tot == 0:
        tot = sum([1.0/v for v in opzioni_esiti.values()])
        
    prob_percentuali = {k: round(((1.0/v) / tot) * 100, 1) for k, v in opzioni_esiti.items()}
    miglior_esito = max(prob_percentuali, key=prob_percentuali.get)
    return miglior_esito, prob_percentuali

def genera_sistema_matematico(palinsesto, n_eventi):
    lista_eventi = []
    for m in palinsesto:
        match_str = f"{m['home_team']} vs {m['away_team']}"
        opzioni = estrai_mercati_completi(m)
        for esito, price in opzioni.items():
            if 1.35 <= price <= 2.50:
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
        ev['base'] = True if idx < 2 else False
        risultato.append(ev)
        
    return risultato

# SCHEDE NAVIGAZIONE
tab_input, tab_multipla, tab_auto, tab_ai, tab_math = st.tabs([
    "➕ Eventi", "🎯 Genera Multipla", "⚡ Genera Sistema", "🤖 Analisi IA", "📊 Matrice"
])

# ----------------------------------------------------
# TAB 1: RICERCA PARTITE ED ESITI
# ----------------------------------------------------
with tab_input:
    st.subheader("Ricerca Partite e Selezione Guidata")
    
    palinsesto = recupera_palinsesto_stabile(odds_api_key)
    
    if odds_api_key and palinsesto:
        search_query = st.text_input("🔍 Cerca squadra o partita (es. Lecce, Inter, Real):")
        
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
                    miglior_esito, percentuali = calcola_probabilita_e_consiglio(opzioni_esiti)
                    
                    st.markdown(f"""
                    <div class="green-box">
                        🟢 <b>ESITO CONSIGLIATO:</b> {miglior_esito} @ <b>{opzioni_esiti[miglior_esito]}</b> (Probabilità: {percentuali.get(miglior_esito, 0)}%)
                    </div>
                    """, unsafe_allow_html=True)

                    lista_menu_esiti = [f"{k} @ {v} (Probabilità: {percentuali.get(k, 0)}%)" for k, v in opzioni_esiti.items()]
                    esito_scelto_str = st.selectbox("Seleziona Esito (1X2, Over/Under, Goal/No Goal, Doppie):", lista_menu_esiti)
                    
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
                        st.success("Partita aggiunta!")
                        st.rerun()
        else:
            st.warning("Nessuna partita trovata con questo nome nel palinsesto live.")
    else:
        st.info("💡 Inserisci 'The Odds API Key' valida nel menu laterale per le quote in tempo reale.")
            
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
# TAB 2: MULTIPLA DIRETTA
# ----------------------------------------------------
with tab_multipla:
    st.subheader("🎯 Generazione Multipla Ad Alta Affidabilità")
    n_eventi_mult = st.slider("Numero di eventi nella Multipla", min_value=2, max_value=8, value=4)
    importo_scommessa = st.number_input("Importo della giocata (€)", min_value=1.0, value=10.0, step=1.0)
    
    if st.button("🚀 Genera Multipla Sicura Ora"):
        if not odds_api_key:
            st.error("Inserisci la chiave The Odds API.")
        else:
            with st.spinner("Caricamento palinsesto live..."):
                palinsesto_realtime = recupera_palinsesto_stabile(odds_api_key)
            
            if not palinsesto_realtime:
                st.error("Impossibile caricare il palinsesto. Verifica la tua API Key.")
            else:
                candidati = []
                for m in palinsesto_realtime:
                    match_str = f"{m['home_team']} vs {m['away_team']}"
                    opzioni = estrai_mercati_completi(m)
                    if opzioni:
                        m_esito, percs = calcola_probabilita_e_consiglio(opzioni)
                        quota_m = opzioni[m_esito]
                        if 1.20 <= quota_m <= 1.90:
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
                            
                if multipla_finale:
                    quota_totale = 1.0
                    for ev in multipla_finale:
                        quota_totale *= ev['quota']
                    vincita_potenziale = quota_totale * importo_scommessa
                    
                    st.markdown("### 📋 Schedina Multipla Generata:")
                    for i, ev in enumerate(multipla_finale, 1):
                        st.write(f"**{i}. {ev['match']}** — {ev['esito']} @ **{ev['quota']}** *(Prob: {ev['prob']}%)*")
                    
                    st.markdown("---")
                    st.metric("Quota Totale Multipla", f"{quota_totale:.2f}")
                    st.metric("Vincita Potenziale", f"{vincita_potenziale:.2f} €")
                else:
                    st.warning("Nessuna partita idonea trovata nel palinsesto in questo momento.")

# ----------------------------------------------------
# TAB 3: GENERATORE SISTEMI
# ----------------------------------------------------
with tab_auto:
    st.subheader("Generazione Automatica Sistema Value Bet")
    num_eventi = st.slider("Numero di eventi da generare", min_value=4, max_value=10, value=6)
    
    if st.button("⚡ Genera Sistema Automatico Ora"):
        if not odds_api_key:
            st.error("Inserisci la chiave The Odds API.")
        else:
            with st.spinner("Caricamento palinsesto live..."):
                palinsesto_realtime = recupera_palinsesto_stabile(odds_api_key)
            
            if not palinsesto_realtime:
                st.error("Impossibile scaricare le quote live da The Odds API.")
            else:
                sistema_generato = genera_sistema_matematico(palinsesto_realtime, num_eventi)
                st.session_state.partite = sistema_generato
                st.success("✅ Sistema Generato con successo!")
                for item in st.session_state.partite:
                    tipo = "📌 BASE" if item['base'] else "🔄 VARIABILE"
                    st.write(f"- **{item['match']}** | {item['esito']} @ **{item['quota']}** ({tipo})")

# ----------------------------------------------------
# TAB 4: ANALISI IA
# ----------------------------------------------------
with tab_ai:
    st.subheader("Analisi Statistica IA")
    if st.button("🚀 Avvia Analisi Strategica IA"):
        if not gemini_key:
            st.error("Inserisci la Gemini API Key.")
        elif not st.session_state.partite:
            st.warning("Nessun evento inserito.")
        else:
            try:
                client = genai.Client(api_key=gemini_key)
                elenco = "\n".join([f"- {p['match']} | {p['esito']} @ {p['quota']} ({'BASE' if p['base'] else 'VAR'})" for p in st.session_state.partite])
                res = client.models.generate_content(
                    model='gemini-1.5-flash', 
                    contents=f"Analizza questo sistema scommesse:\n{elenco}"
                )
                st.markdown(res.text)
            except Exception as e:
                st.error(f"Errore Gemini: {e}")

# ----------------------------------------------------
# TAB 5: MATRICE E CALCOLO SISTEMA
# ----------------------------------------------------
with tab_math:
    st.subheader("Validatore Matematico")
    errori = st.selectbox("Tolleranza Errori", [1, 2, 3], index=1)
    stake_colonna = st.number_input("Puntata per colonna (€)", min_value=0.5, value=1.0, step=0.5)
    
    basi = [p for p in st.session_state.partite if p['base']]
    variabili = [p for p in st.session_state.partite if not p['base']]
    k = len(variabili) - errori
    
    if len(variabili) <= errori:
        st.warning(f"Servono almeno {errori + 1} eventi 'Variabili' per calcolare il sistema.")
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
