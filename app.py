import streamlit as st
import itertools
import requests
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
    </style>
""", unsafe_allow_html=True)

st.title("⚽ System Analyst AI")
st.caption("Piattaforma mobile per la gestione, generazione automatica e validazione di sistemi.")

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

# --- FUNZIONE CHIAMATA GEMINI (CON RETRY E FALLBACK) ---
def genera_con_gemini(client, prompt):
    modelli = ['gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.5-flash']
    ultimo_errore = None
    
    for modello in modelli:
        for tentativo in range(2):
            try:
                res = client.models.generate_content(
                    model=modello,
                    contents=prompt
                )
                return res.text
            except Exception as e:
                ultimo_errore = e
                time.sleep(1)
                
    raise ultimo_errore

# --- FUNZIONE RECUPERO PALINSESTO COMPLETO ---
@st.cache_data(ttl=300)
def recupera_palinsesto_live(api_key):
    if not api_key:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
    try:
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

# SCHEDE PER SMARTPHONE
tab_input, tab_auto, tab_ai, tab_math = st.tabs(["➕ Eventi", "⚡ Genera Sistema", "🤖 Analisi IA", "📊 Matrice"])

# ----------------------------------------------------
# TAB 1: RICERCA PARTITE E SELEZIONE QUOTE
# ----------------------------------------------------
with tab_input:
    st.subheader("Ricerca Partite e Selezione Quote")
    
    palinsesto = recupera_palinsesto_live(odds_api_key)
    
    if odds_api_key and palinsesto:
        # Campo di ricerca testuale per filtrare le squadre
        search_query = st.text_input("🔍 Cerca squadra o partita (es. Barcellona, Inter, Real):", placeholder="Digita per filtrare...")
        
        elenco_partite_totale = [f"{m['home_team']} vs {m['away_team']}" for m in palinsesto]
        
        if search_query.strip():
            elenco_filtrato = [p for p in elenco_partite_totale if search_query.lower() in p.lower()]
        else:
            elenco_filtrato = elenco_partite_totale

        partita_selezionata = st.selectbox(
            "Seleziona partita:", 
            ["-- Scegli partita --"] + elenco_filtrato
        )
        
        if partita_selezionata != "-- Scegli partita --":
            match_data = next((m for m in palinsesto if f"{m['home_team']} vs {m['away_team']}" == partita_selezionata), None)
            
            if match_data:
                opzioni_esiti = {}
                home_team = match_data.get('home_team')
                away_team = match_data.get('away_team')

                for bookmaker in match_data.get('bookmakers', []):
                    for market in bookmaker.get('markets', []):
                        if market['key'] == 'h2h':
                            for outcome in market['outcomes']:
                                name = outcome['name']
                                if name == home_team:
                                    lbl = "1"
                                elif name == away_team:
                                    lbl = "2"
                                else:
                                    lbl = "X"
                                opzioni_esiti[f"Esito {lbl}"] = outcome['price']

                        elif market['key'] == 'totals':
                            for outcome in market['outcomes']:
                                name = outcome['name'] # Over / Under
                                point = outcome.get('point', '')
                                opzioni_esiti[f"{name} {point}"] = outcome['price']
                
                if opzioni_esiti:
                    esito_scelto = st.selectbox("Seleziona Esito e Quota:", list(opzioni_esiti.keys()))
                    quota_scelta = opzioni_esiti[esito_scelto]
                    st.write(f"Quota selezionata: **{quota_scelta}**")
                    is_base_live = st.checkbox("Imposta come BASE (Fissa)")
                    
                    if st.button("Aggiungi al Sistema"):
                        st.session_state.partite.append({
                            "match": partita_selezionata,
                            "esito": esito_scelto,
                            "quota": float(quota_scelta),
                            "base": is_base_live
                        })
                        st.success("Partita aggiunta al sistema!")
                        st.rerun()
    else:
        if not odds_api_key:
            st.info("💡 Inserisci 'The Odds API Key' nel menu laterale per accedere al palinsesto con ricerca automatica.")
        elif not palinsesto:
            st.warning("Impossibile caricare il palinsesto live. Inserisci i dati manualmente.")
        
        squadra_input = st.text_input("Inserisci nome partita/squadra (manuale):", placeholder="Es. Barcellona vs Real Madrid")
        esito_sel = st.selectbox("Seleziona Esito", ["1", "X", "2", "Over 1.5", "Over 2.5", "Under 2.5", "Goal", "No Goal"])
        quota_input = st.number_input("Quota", min_value=1.01, value=1.90, step=0.05)
        is_base = st.checkbox("Imposta come BASE (Fissa)")
        
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
# TAB 2: GENERATORE AUTOMATICO SISTEMI CON ESITI STANDARD ITALIANI
# ----------------------------------------------------
with tab_auto:
    st.subheader("Generazione Automatica Sistema Value Bet")
    st.write("L'algoritmo seleziona gli eventi imminenti calcolando le quote di valore.")
    
    num_eventi = st.slider("Numero di eventi da generare", min_value=4, max_value=10, value=6)
    
    if st.button("⚡ Genera Sistema Automatico Ora"):
        if not gemini_key:
            st.error("Inserisci la Gemini API Key nel menu laterale per la generazione automatica.")
        elif not odds_api_key:
            st.error("Serve la chiave The Odds API per scaricare le partite reali.")
        else:
            with st.spinner("Recupero partite e quote in tempo reale..."):
                palinsesto_realtime = recupera_palinsesto_live(odds_api_key)
            
            if not palinsesto_realtime:
                st.error("Impossibile scaricare le partite. Verifica la tua API Key di The Odds API.")
            else:
                sintesi_palinsesto = []
                for m in palinsesto_realtime[:30]:
                    match_str = f"{m['home_team']} vs {m['away_team']}"
                    quote_str = []
                    for b in m.get('bookmakers', [])[:1]:
                        for mk in b.get('markets', []):
                            if mk['key'] == 'h2h':
                                for out in mk['outcomes']:
                                    name = "1" if out['name'] == m['home_team'] else ("2" if out['name'] == m['away_team'] else "X")
                                    quote_str.append(f"{name}: {out['price']}")
                            elif mk['key'] == 'totals':
                                for out in mk['outcomes']:
                                    quote_str.append(f"{out['name']} {out.get('point','')}: {out['price']}")
                    if quote_str:
                        sintesi_palinsesto.append(f"- {match_str} -> {', '.join(quote_str)}")
                
                testo_palinsesto = "\n".join(sintesi_palinsesto)
                
                prompt_gen = f"""
                Sei un analista quantitativo di scommesse sportive. 
                Di seguito trovi il palinsesto reale delle prossime partite con le relative quote di mercato:

                {testo_palinsesto}

                Seleziona esattamente {num_eventi} partite TRA QUELLE IN ELENCO SOPRA che offrono il maggior valore (Value Bet).
                
                REGOLE STRITTE PER L'ESITO (NOTAZIONE ITALIANA):
                - Per la vittoria della squadra di casa usa esclusivamente: "1"
                - Per il pareggio usa esclusivamente: "X" (NON usare mai "Draw" o nomi squadra)
                - Per la vittoria della squadra in trasferta usa esclusivamente: "2"
                - Per i gol usa notazioni standard: "Over 1.5", "Over 2.5", "Under 2.5", "Goal", "No Goal".

                Designa 1 o 2 eventi come "BASE" e i restanti come "VARIABILE".

                Rispondi ESCLUSIVAMENTE con questo formato per ogni riga (senza introduzione né spiegazioni):
                SquadraA vs SquadraB | Esito | Quota | BASE/VARIABILE
                """
                
                try:
                    with st.spinner("Analisi Value Bet in corso con IA..."):
                        client = genai.Client(api_key=gemini_key)
                        testo_risposta = genera_con_gemini(client, prompt_gen)
                        st.markdown("### 🎯 Sistema Reale Generato:")
                        st.text(testo_risposta)
                except Exception as e:
                    st.error(f"Errore generazione IA: {e}")

# ----------------------------------------------------
# TAB 3: ANALISI IA
# ----------------------------------------------------
with tab_ai:
    st.subheader("Analisi Statistica e Notizie")
    
    if st.button("🚀 Avvia Analisi Strategica IA"):
        if not gemini_key:
            st.error("Inserisci la tua Gemini API Key nella barra laterale per usare l'analisi.")
        elif not st.session_state.partite:
            st.warning("Inserisci almeno una partita prima di avviare l'analisi.")
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
                3. Eventuali trappole o fattori di rischio da considerare (forma, infortuni noti).
                """
                with st.spinner("Analisi in corso..."):
                    testo_risposta = genera_con_gemini(client, prompt_analysis)
                    st.markdown(testo_risposta)
            except Exception as e:
                st.error(f"Server occupati, riprova tra qualche secondo: {e}")

# ----------------------------------------------------
# TAB 4: CALCOLO MATEMATICO DEL SISTEMA
# ----------------------------------------------------
with tab_math:
    st.subheader("Validatore Matematico")
    errori = st.selectbox("Tolleranza Errori", [1, 2, 3], index=1)
    stake_colonna = st.number_input("Puntata per colonna (€)", min_value=0.5, value=1.0, step=0.5)
    
    basi = [p for p in st.session_state.partite if p['base']]
    variabili = [p for p in st.session_state.partite if not p['base']]
    
    k = len(variabili) - errori
    
    if len(variabili) <= errori:
        st.warning(f"Servono almeno {errori + 1} eventi 'Variabili' per questo sistema.")
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
