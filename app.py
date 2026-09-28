import streamlit as st
import itertools
from google import genai
from google.genai import types

# --- CONFIGURAZIONE PAGINA PER SMARTPHONE ---
st.set_page_config(
    page_title="Football System Strategy AI",
    page_icon="⚽",
    layout="centered", # 'centered' è l'ideale per il display verticale degli smartphone
    initial_sidebar_state="collapsed"
)

# STILE CSS PERSONALIZZATO PER SCHERMI MOBILE
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        font-weight: bold;
    }
    .stMetric {
        background-color: #1e222a;
        padding: 10px;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚽ System Analyst AI")
st.caption("Piattaforma mobile per la gestione e validazione di sistemi ad errore e value bets.")

# --- BARRA LATERALE PER CHIAVE API ---
with st.sidebar:
    st.header("⚙️ Impostazioni")
    gemini_key = st.text_input("Inserisci la tua Gemini API Key", type="password", help="Ottieni una chiave gratuita da Google AI Studio")
    st.markdown("---")
    st.markdown("### Guida Rapida")
    st.write("1. Aggiungi gli eventi con la relativa quota.\n2. Seleziona fino a 2 Basi (fisse).\n3. Lancia l'analisi IA o calcola l'efficienza del sistema.")

# --- INIZIALIZZAZIONE STATO ---
if "partite" not in st.session_state:
    st.session_state.partite = []

# --- SCHEDE NAVIGABILI DA MOBILE ---
tab_input, tab_ai, tab_math = st.tabs(["➕ Eventi", "🤖 Analisi IA", "📊 Matrice Sistema"])

# ----------------------------------------------------
# TAB 1: INSERIMENTO EVENTI
# ----------------------------------------------------
with tab_input:
    st.subheader("Inserisci Partita nel Sistema")
    
    with st.form("form_evento", clear_on_submit=True):
        squadre = st.text_input("Partita / Campionato", placeholder="Es. Brescia vs Palermo (Serie B)")
        esito = st.text_input("Esito / Mercato", placeholder="Es. Over 2.5 / Gol / 1X")
        quota = st.number_input("Quota proposta dal Bookmaker", min_value=1.01, value=1.95, step=0.05)
        is_base = st.checkbox("📌 Imposta come BASE (Fissa - zero errori)")
        
        btn_add = st.form_submit_button("Aggiungi al Sistema")
        
        if btn_add:
            if squadre and esito:
                st.session_state.partite.append({
                    "match": squadre,
                    "esito": esito,
                    "quota": float(quota),
                    "base": is_base
                })
                st.success("Evento aggiunto!")
            else:
                st.warning("Compila tutti i campi prima di aggiungere.")

    st.markdown("---")
    st.subheader(f"Eventi Inseriti ({len(st.session_state.partite)})")
    
    if st.session_state.partite:
        for idx, item in enumerate(st.session_state.partite):
            tipo = "📌 BASE (FISSA)" if item['base'] else "🔄 VARIABILE"
            st.markdown(f"**{idx+1}. {item['match']}**")
            st.caption(f"Mercato: `{item['esito']}` | Quota: **{item['quota']}** | Tipo: {tipo}")
            
            if st.button("Rimuovi", key=f"del_{idx}"):
                st.session_state.partite.pop(idx)
                st.rerun()
            st.markdown("---")
    else:
        st.info("Nessuna partita presente. Aggiungi gli eventi per iniziare.")

# ----------------------------------------------------
# TAB 2: ANALISI APPROFONDITA TRAMITE IA
# ----------------------------------------------------
with tab_ai:
    st.subheader("Analisi Statistica e Notizie (IA)")
    st.write("L'IA analizzerà le partite inserite per identificare anomalie nelle quote o rischi nascosti.")
    
    if st.button("🚀 Avvia Analisi Strategica IA"):
        if not gemini_key:
            st.error("Devi inserire la tua Gemini API Key nella barra laterale per usare l'analisi!")
        elif not st.session_state.partite:
            st.warning("Inserisci almeno una partita prima di avviare l'analisi.")
        else:
            try:
                # Inizializzazione SDK ufficiale google-genai
                client = genai.Client(api_key=gemini_key)
                
                # Costruzione del prompt analitico
                elenco_partite = ""
                for p in st.session_state.partite:
                    elenco_partite += f"- Partita: {p['match']} | Esito: {p['esito']} | Quota: {p['quota']} | Ruolo: {'BASE' if p['base'] else 'VARIABILE'}\n"
                
                prompt_sistema = f"""
                Sei un analista quantitativo esperto in betting sportivo e Value Betting.
                Analizza con estremo rigore e obiettività i seguenti eventi che l'utente vuole inserire in un sistema a correzione d'errore:

                {elenco_partite}

                Per ogni evento fornisci un feedback sintetico ma profondo focalizzato su:
                1. RAGIONEVOLEZZA DELLA QUOTA: La quota proposta è sostenibile o nasconde rischi?
                2. FATTORI DI RISCHIO: Rendimento casa/trasferta, probabili assenze, motivazioni.
                3. IDONEITÀ AL SISTEMA: Se l'evento è impostato come "BASE", confermi che è affidabile? Se è una "VARIABILE", la quota giustifica il rischio?

                Sii realista, severo ed evita qualsiasi toni accondiscendente. Se una giocata non ha senso matematico o strategico, segnalalo chiaramente.
                """
                
                with st.spinner("Analisi in corso sui server IA..."):
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt_sistema,
                    )
                    st.markdown("### Risultato Analisi IA:")
                    st.markdown(response.text)
                    
            except Exception as e:
                st.error(f"Errore durante l'elaborazione IA: {e}")

# ----------------------------------------------------
# TAB 3: CALCOLO MATEMATICO DEL SISTEMA
# ----------------------------------------------------
with tab_math:
    st.subheader("Validatore Matematico del Sistema")
    
    errori = st.selectbox("Tolleranza Errori", [1, 2, 3], index=1)
    stake_colonna = st.number_input("Puntata per colonna (€)", min_value=0.5, value=1.0, step=0.5)
    
    basi = [p for p in st.session_state.partite if p['base']]
    variabili = [p for p in st.session_state.partite if not p['base']]
    
    k = len(variabili) - errori
    
    if len(variabili) <= errori:
        st.warning(f"Devi inserire almeno {errori + 1} eventi 'Variabili' per applicare {errori} errori.")
    else:
        # Calcolo combinazioni
        quote_var = [p['quota'] for p in variabili]
        combinazioni = list(itertools.combinations(quote_var, k))
        num_colonne = len(combinazioni)
        spesa_totale = num_colonne * stake_colonna
        
        # Quota Basi
        quota_basi = 1.0
        for b in basi:
            quota_basi *= b['quota']
            
        st.metric("Totale Bollette Sviluppate", num_colonne)
        st.metric("Spesa Totale", f"{spesa_totale:.2f} €")
        
        st.markdown("---")
        st.subheader("Scenario Minimo Garantito")
        st.caption(f"Cosa succede se commetti esattamente {errori} errori e azzecchi solo le quote variabili più basse:")
        
        peggiori_var = sorted(quote_var)[:k]
        quota_minima_vincente = quota_basi
        for q in peggiori_var:
            quota_minima_vincente *= q
            
        incasso_minimo = quota_minima_vincente * stake_colonna
        profitto_minimo = incasso_minimo - spesa_totale
        
        st.metric("Quota Colonna Minima", f"{quota_minima_vincente:.2f}")
        st.metric("Incasso Minimo Lordo", f"{incasso_minimo:.2f} €")
        
        if profitto_minimo >= 0:
            st.success(f"🟢 **SISTEMA EFFICIENTE**: Profitto netto minimo garantito: +{profitto_minimo:.2f} €")
        else:
            st.error(f"🔴 **SISTEMA NON CONVENIENTE**: Perdita netta nello scenario minimo: {profitto_minimo:.2f} €. Alza le quote o inserisci Basi più solide.")
