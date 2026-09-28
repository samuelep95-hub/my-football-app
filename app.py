import streamlit as st
import itertools
import requests
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
        value=st.secrets.get("ODDS_API_KEY", ""), 
        type="password"
    )

# INIZIALIZZAZIONE STATO
if "partite" not in st.session_state:
    st.session_state.partite = []

# --- FUNZIONI PER RECUPERO QUOTE LIVE ---
def cerca_partite_live(query_squadra, api_key):
    if not api_key:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            risultati = []
            for match in data:
                home = match.get('home_team', '')
                away = match.get('away_team', '')
                if query_squadra.lower() in home.lower() or query_squadra.lower() in away.lower():
                    risultati.append(match)
            return risultati
    except Exception:
        pass
    return []

def genera_con_fallback(client, prompt):
    # Prova prima il modello primario, se fallisce usa il secondario
    modelli = ['gemini-2.5-flash', 'gemini-1.5-flash']
    ultimo_errore = None
    for mod in modelli:
        try:
            res = client.models.generate_content(model=mod, contents=prompt)
            return res.text
        except Exception as e:
            ultimo_errore = e
            continue
    raise ultimo_errore

# SCHEDE PER SMARTPHONE
tab_input, tab_auto, tab_ai, tab_math = st.tabs(["➕ Eventi", "⚡ Genera Sistema", "🤖 Analisi IA", "📊 Matrice"])

# ----------------------------------------------------
# TAB 1: RICERCA PARTITE CON QUOTE REALI
# ----------------------------------------------------
with tab_input:
    st.subheader("Cerca Partita e Selezione Quote")
    
    query = st.text_input("Scrivi il nome della squadra (es. Lecce, Parma, Arsenal)", placeholder="Cerca squadra...")
    
    if query:
        if not odds_api_key:
            st.info("💡 Per vedere le partite live e le quote aggiornate dei bookmaker, inserisci la 'The Odds API Key' (gratuita) nel menu laterale.")
            squadra_input = query
            esito_sel = st.selectbox("Seleziona Esito", ["1 (Vittoria Casa)", "X (Pareggio)", "2 (Vittoria Trasferta)", "Over 2.5", "Under 2.5", "Gol", "No Gol"])
            quota_input = st.number_input("Quota", min_value=1.01, value=1.90, step=0.05)
            is_base = st.checkbox("Imposta come BASE (Fissa)")
            if st.button("Aggiungi Manualmente"):
                st.session_state.partite.append({"match": squadra_input, "esito": esito_sel, "quota": float(quota_input), "base": is_base})
                st.success("Evento aggiunto!")
                st.rerun()
        else:
            matches = cerca_partite_live(query, odds_api_key)
            if matches:
                st.write(f"Partite trovate ({len(matches)}):")
                for m in matches:
                    match_name = f"{m['home_team']} vs {m['away_team']}"
                    st.markdown(f"**{match_name}**")
                    
                    opzioni_esiti = {}
                    for bookmaker in m.get('bookmakers', []):
                        for market in bookmaker.get('markets', []):
                            if market['key'] == 'h2h':
                                for outcome in market['outcomes']:
                                    opzioni_esiti[f"Esito 1X2: {outcome['name']}"] = outcome['price']
                            elif market['key'] == 'totals':
                                for outcome in market['outcomes']:
                                    opzioni_esiti[f"Totale {outcome['name']} {outcome.get('point','')}"] = outcome['price']
                    
                    if opzioni_esiti:
                        esito_scelto = st.selectbox("Seleziona il mercato/quota live:", list(opzioni_esiti.keys()), key=f"sel_{m['id']}")
                        quota_scelta = opzioni_esiti[esito_scelto]
                        st.write(f"Quota selezionata: **{quota_scelta}**")
                        is_base_live = st.checkbox("Imposta come BASE", key=f"chk_{m['id']}")
                        
                        if st.button("Aggiungi al Sistema", key=f"btn_{m['id']}"):
                            st.session_state.partite.append({
                                "match": match_name,
                                "esito": esito_scelto,
                                "quota": float(quota_scelta),
                                "base": is_base_live
                            })
                            st.success("Partita aggiunta al sistema!")
                            st.rerun()
            else:
                st.warning("Nessuna partita trovata con questo nome nel palinsesto aggiornato.")

    st.markdown("---")
    st.subheader(f"Eventi Selezionati ({len(st.session_state.partite)})")
    for idx, item in enumerate(st.session_state.partite):
        tipo = "📌 BASE" if item['base'] else "🔄 VARIABILE"
        st.write(f"**{idx+1}. {item['match']}** | {item['esito']} @ **{item['quota']}** ({tipo})")
        if st.button("Rimuovi", key=f"del_{idx}"):
            st.session_state.partite.pop(idx)
            st.rerun()

# ----------------------------------------------------
# TAB 2: GENERATORE AUTOMATICO DI SISTEMI CON IA
# ----------------------------------------------------
with tab_auto:
    st.subheader("Generazione Automatica Sistema Value Bet")
    st.write("L'algoritmo cercherà automaticamente i migliori eventi europei del giorno bilanciando quote ed errore.")
    
    num_eventi = st.slider("Numero di eventi da generare", min_value=4, max_value=10, value=6)
    
    if st.button("⚡ Genera Sistema Automatico Ora"):
        if not gemini_key:
            st.error("Devi inserire la Gemini API Key per generare il sistema automatico!")
        else:
            try:
                client = genai.Client(api_key=gemini_key)
                prompt_gen = f"""
                Sei un tipster quantitativo. Genera una lista di esattamente {num_eventi} partite di calcio reali programmate per i prossimi giorni nei campionati europei.
                
                Per ciascuna partita seleziona un esito a quota medio-alta (tra 1.70 e 2.50) che presenti valore (Value Bet).
                Designa 1 o 2 di questi eventi come "BASE" e le restanti come "VARIABILI".
                
                Rispondi ESCLUSIVAMENTE in formato testo pulito con questo schema per ogni riga:
                SquadraA vs SquadraB | Esito | Quota | BASE/VARIABILE
                """
                
                with st.spinner("Ricerca Value Bet nei campionati europei..."):
                    testo_risposta = genera_con_fallback(client, prompt_gen)
                    st.markdown("### Sistema Suggerito dall'IA:")
                    st.text(testo_risposta)
            except Exception as e:
                st.error(f"Errore generazione: {e}")

# ----------------------------------------------------
# TAB 3: ANALISI IA
# ----------------------------------------------------
with tab_ai:
    st.subheader("Analisi Statistica e Notizie")
    
    if st.button("🚀 Avvia Analisi Strategica IA"):
        if not gemini_key:
            st.error("Devi inserire la tua Gemini API Key nella barra laterale per usare l'analisi!")
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
                    testo_analisi = genera_con_fallback(client, prompt_analysis)
                    st.markdown(testo_analisi)
            except Exception as e:
                st.error(f"Errore IA: {e}")

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
