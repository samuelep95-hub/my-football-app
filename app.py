import streamlit as st
import itertools
import requests
import random
from datetime import datetime, timezone, timedelta
from google import genai

# --- CONFIGURAZIONE PAGINA MOBILE ---
st.set_page_config(
    page_title="Football System Analyst AI",
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
st.caption("Piattaforma avanzata basata su modelli statistici, analisi del valore e IA.")

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

# --- RECUPERO PALINSESTO ESTESO ---
@st.cache_data(ttl=300)
def recupera_palinsesto_stabile(api_key):
    if not api_key:
        return []
    
    tutte = []
    
    # 1. Scarico generico soccer
    url_gen = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
    try:
        res = requests.get(url_gen, timeout=6)
        if res.status_code == 200:
            tutte.extend(res.json())
    except Exception:
        pass

    # 2. Scarico specifico per i principali campionati europei
    leghe = [
        "soccer_italy_serie_a",
        "soccer_epl",
        "soccer_spain_la_liga",
        "soccer_germany_bundesliga",
        "soccer_uefa_champs_league"
    ]
    
    for lega in leghe:
        url_l = f"https://api.the-odds-api.com/v4/sports/{lega}/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
        try:
            r = requests.get(url_l, timeout=4)
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

    # Derivazione Matematica con rimozione aggio bookmaker
    if q1 and qx:
        opzioni["Doppia Chance 1X"] = round(1 / ((1/q1) + (1/qx)), 2)
    if qx and q2:
        opzioni["Doppia Chance X2"] = round(1 / ((1/qx) + (1/q2)), 2)
    if q1 and q2:
        opzioni["Doppia Chance 12"] = round(1 / ((1/q1) + (1/q2)), 2)

    if q_over25 and q_under25:
        opzioni["Goal"] = round(max(1.30, q_over25 * 0.92), 2)
        opzioni["No Goal"] = round(max(1.30, q_under25 * 0.94), 2)
    elif q1 and q2:
        opzioni["Goal"] = round(max(1.35, min(q1, q2) * 0.85), 2)
        opzioni["No Goal"] = round(max(1.35, max(q1, q2) * 0.75), 2)

    return opzioni

def analizza_valore_e_probabilita(opzioni_esiti):
    """
    Calcola la probabilità reale de-aggiata e seleziona la scommessa a maggior valore (Value Bet).
    """
    if not opzioni_esiti:
        return None, {}
    
    # 1. Calcolo lavagna e rimozione aggio sui mercati principali
    mercati_1x2 = {k: v for k, v in opzioni_esiti.items() if k in ["Esito 1", "Esito X", "Esito 2"]}
    if mercati_1x2:
        lavagna = sum([1.0 / v for v in mercati_1x2.values()])
        prob_reali = {k: round(((1.0 / v) / lavagna) * 100, 1) for k, v in opzioni_esiti.items()}
    else:
        lavagna = sum([1.0 / v for v in opzioni_esiti.values()])
        prob_reali = {k: round(((1.0 / v) / lavagna) * 100, 1) for k, v in opzioni_esiti.values()}

    # 2. Selezione intelligente dell'esito più sicuro vs a maggior valore
    # Privilegiamo Doppie Chance o Over se le probabilità 1X2 sono troppo bilanciate (partita trappola)
    p_1 = prob_reali.get("Esito 1", 0)
    p_2 = prob_reali.get("Esito 2", 0)
    
    if abs(p_1 - p_2) < 15 and "Doppia Chance 1X" in opzioni_esiti:
        # Partita equilibrata: meglio evitare 1X2 secco e scegliere la copertura o i gol
        if opzioni_esiti.get("Goal", 0) >= 1.60 and prob_reali.get("Goal", 0) > 52:
            scelta = "Goal"
        elif p_1 >= p_2:
            scelta = "Doppia Chance 1X"
        else:
            scelta = "Doppia Chance X2"
    else:
        scelta = max(prob_reali, key=prob_reali.get)

    return scelta, prob_reali

def seleziona_eventi_multipla_avanzata(palinsesto, n_eventi):
    candidati = []
    for m in palinsesto:
        match_str = f"{m['home_team']} vs {m['away_team']}"
        opzioni = estrai_mercati_completi(m)
        if opzioni:
            esito_opt, prob_dict = analizza_valore_e_probabilita(opzioni)
            quota_opt = opzioni[esito_opt]
            prob_opt = prob_dict.get(esito_opt, 0)

            # Filtro severo Multipla: Quota tra 1.35 e 1.75 con probabilità reale > 58%
            if 1.35 <= quota_opt <= 1.75 and prob_opt >= 58.0:
                candidati.append({
                    "match": match_str,
                    "esito": esito_opt,
                    "quota": quota_opt,
                    "prob": prob_opt
                })

    candidati.sort(key=lambda x: x['prob'], reverse=True)
    
    usati = set()
    risultato = []
    for c in candidati:
        if c['match'] not in usati:
            usati.add(c['match'])
            risultato.append(c)
            if len(risultato) == n_eventi:
                break
    return risultato

def seleziona_eventi_sistema_avanzato(palinsesto, n_eventi):
    candidati = []
    for m in palinsesto:
        match_str = f"{m['home_team']} vs {m['away_team']}"
        opzioni = estrai_mercati_completi(m)
        if opzioni:
            esito_opt, prob_dict = analizza_valore_e_probabilita(opzioni)
            quota_opt = opzioni[esito_opt]
            prob_opt = prob_dict.get(esito_opt, 0)

            # Per il sistema cerchiamo valore reale: quote tra 1.60 e 2.30 ma con probabilità solide (> 45%)
            if 1.60 <= quota_opt <= 2.30 and prob_opt >= 45.0:
                candidati.append({
                    "match": match_str,
                    "esito": esito_opt,
                    "quota": quota_opt,
                    "prob": prob_opt
                })

    random.shuffle(candidati)
    usati = set()
    risultato_raw = []
    for c in candidati:
        if c['match'] not in usati:
            usati.add(c['match'])
            risultato_raw.append(c)
            if len(risultato_raw) == n_eventi:
                break

    # Assegnazione BASI (le 2 partite a probabilità più alta) e VARIABILI
    risultato_raw.sort(key=lambda x: x['prob'], reverse=True)
    risultato_finale = []
    for idx, item in enumerate(risultato_raw):
        item['base'] = True if idx < 2 else False
        risultato_finale.append(item)

    return risultato_finale

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
# TAB 2: MULTIPLA PRO (FILTRO SEVERO)
# ----------------------------------------------------
with tab_multipla:
    st.subheader("🎯 Generazione Multipla Ad Alta Probabilità")
    
    orizzonte_mult = st.selectbox(
        "📅 Lasso di tempo match:",
        ["Solo oggi", "Oggi e domani", "Entro 3 giorni", "Lungo termine (entro 12-14 giorni)"],
        index=1,
        key="time_mult"
    )
    
    n_eventi_mult = st.slider("Numero di eventi nella Multipla", min_value=2, max_value=6, value=3)
    importo_scommessa = st.number_input("Importo della giocata (€)", min_value=1.0, value=10.0, step=1.0)
    
    if st.button("🚀 Genera Multipla Analitica Ora"):
        if not odds_api_key:
            st.error("Inserisci la chiave The Odds API.")
        else:
            with st.spinner("Analisi statistica delle quote in corso..."):
                palinsesto_realtime = recupera_palinsesto_stabile(odds_api_key)
                palinsesto_filtrato = filtra_per_orizzonte_temporale(palinsesto_realtime, orizzonte_mult)
                multipla_finale = seleziona_eventi_multipla_avanzata(palinsesto_filtrato, n_eventi_mult)
            
            if len(multipla_finale) < n_eventi_mult:
                st.warning(f"Trovati solo {len(multipla_finale)} eventi che rispettano i rigidi criteri di stabilità e valore statistico nell'intervallo selezionato.")
            
            if multipla_finale:
                quota_totale = 1.0
                for ev in multipla_finale:
                    quota_totale *= ev['quota']
                vincita_potenziale = quota_totale * importo_scommessa
                
                st.markdown("### 📋 Multipla Selezionata:")
                for i, ev in enumerate(multipla_finale, 1):
                    st.markdown(f"""
                    <div class="stats-card">
                        <b>{i}. {ev['match']}</b><br>
                        Esito: <b>{ev['esito']}</b> @ <b>{ev['quota']}</b> | Probabilità Reale: <b>{ev['prob']}%</b>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                st.metric("Quota Totale", f"{quota_totale:.2f}")
                st.metric("Vincita Potenziale", f"{vincita_potenziale:.2f} €")

# ----------------------------------------------------
# TAB 3: GENERATORE SISTEMI VALUE BET
# ----------------------------------------------------
with tab_auto:
    st.subheader("⚡ Generazione Sistema Value Bet (Con Copertura)")
    
    orizzonte_sis = st.selectbox(
        "📅 Lasso di tempo match:",
        ["Solo oggi", "Oggi e domani", "Entro 3 giorni", "Lungo termine (entro 12-14 giorni)"],
        index=2,
        key="time_sis"
    )
    
    num_eventi = st.slider("Numero di eventi da generare", min_value=4, max_value=8, value=5)
    
    if st.button("⚡ Genera Sistema Value Bet Ora"):
        if not odds_api_key:
            st.error("Inserisci la chiave The Odds API.")
        else:
            with st.spinner("Calcolo Value Bets e bilanciamento errori..."):
                palinsesto_realtime = recupera_palinsesto_stabile(odds_api_key)
                palinsesto_filtrato = filtra_per_orizzonte_temporale(palinsesto_realtime, orizzonte_sis)
                sistema_generato = seleziona_eventi_sistema_avanzato(palinsesto_filtrato, num_eventi)
            
            if not sistema_generato:
                st.error("Nessun evento ad alto valore (Value Bet) individuato nell'intervallo temporale scelto.")
            else:
                st.session_state.partite = sistema_generato
                st.success("✅ Sistema Generato e caricato nel Schedario!")
                for item in st.session_state.partite:
                    tipo = "📌 BASE" if item['base'] else "🔄 VARIABILE"
                    st.write(f"- **{item['match']}** | {item['esito']} @ **{item['quota']}** ({tipo})")

# ----------------------------------------------------
# TAB 4: ANALISI IA AVANZATA (GEMINI 2.5)
# ----------------------------------------------------
with tab_ai:
    st.subheader("🤖 Analisi Critica & Audit IA")
    st.caption("Valutazione dei rischi e dei fattori esterni (infortuni, forma, motivazioni).")
    
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
                Sei un analista quantitativo di scommesse sportive professionale ed estremamente severo.
                Analizza questo sistema/multipla:
                {elenco}

                Fornisci un report strutturato con:
                1. **Punti Critici e Partite Trappola**: Identifica quali eventi sono estremamente rischiosi e perché.
                2. **Consistenza Statistica**: Valuta se le quote rispecchiano il valore o se sono trappole dei bookmaker.
                3. **Raccomandazione Finale**: Indica chiaramente quali partite eliminare o sostituire per aumentare l'aspettativa di vincita (Expected Value +EV).
                
                Sii schietto, realista e non condiscendente.
                """
                
                with st.spinner("Audit IA in corso con Gemini 2.5..."):
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
