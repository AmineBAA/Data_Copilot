import streamlit as st
import pandas as pd
import sqlite3
import ollama
import os

# Force l'utilisation de l'IP de bouclage locale pour éviter les bugs de résolution de Windows
os.environ["OLLAMA_HOST"] = "http://127.0.0.1:11434"

# Configuration de la page Streamlit
st.set_page_config(
    page_title="IA Assistant Excel - SQL Local",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style CSS personnalisé pour l'interface
st.markdown("""
<style>
    .main-header {
        font-family: 'Poppins', sans-serif;
        color: #0f766e;
        text-align: center;
        margin-bottom: 20px;
    }
    .info-box {
        background-color: #f0fdfa;
        border-left: 5px solid #0d9488;
        padding: 15px;
        border-radius: 4px;
        margin-bottom: 25px;
    }
    .stButton>button {
        background-color: #0d9488 !important;
        color: white !important;
        border-radius: 6px !important;
        border: none !important;
        padding: 10px 24px !important;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #0f766e !important;
    }
    .sql-code {
        background-color: #1e293b;
        color: #38bdf8;
        padding: 15px;
        border-radius: 6px;
        font-family: 'Courier New', Courier, monospace;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-header'>📊 Assistant IA - Analyse SQL sur Fichier Client</h1>", unsafe_allow_html=True)

# Sidebar - Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Saisie du nom du fichier Excel
    file_name = st.text_input("Nom du fichier Excel source", "info_clients.xlsx")
    
    # Choix du modèle Ollama disponible
    st.subheader("🤖 Modèle NLP Local")
    model_name = st.text_input("Modèle Ollama à utiliser", "qwen2.5-coder:7b")

# Vérification de l'existence du fichier Excel
df = None
if os.path.exists(file_name):
    try:
        df = pd.read_excel(file_name)
        st.success(f"✅ Fichier `{file_name}` chargé avec succès depuis le dossier local !")
    except Exception as e:
        st.error(f"Erreur lors du chargement de l'Excel : {e}")
else:
    st.warning(f"⚠️ Le fichier `{file_name}` est introuvable dans le dossier actuel.")
    uploaded_file = st.file_uploader("Ou importez un fichier Excel temporaire ici :", type=["xlsx", "xls"])
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            st.success("✅ Fichier chargé avec succès via l'importateur !")
        except Exception as e:
            st.error(f"Erreur : {e}")

# Si les données sont prêtes
if df is not None:
    # Affichage d'un aperçu des données
    with st.expander("👀 Aperçu du fichier client importé"):
        st.dataframe(df.head(10), use_container_width=True)
        st.caption(f"Le fichier contient {df.shape[0]} lignes et {df.shape[1]} colonnes.")

    # Création de la base de données SQL en mémoire temporaire
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    df.to_sql("clients", conn, index=False, if_exists="replace")

    # Zone de saisie utilisateur
    st.markdown("<div class='info-box'>Posez n'importe quelle question sur vos clients. L'intelligence artificielle locale va convertir votre phrase en requête SQL, l'exécuter sur vos données, puis afficher le résultat instantanément.</div>", unsafe_allow_html=True)
    
    user_query = st.text_input(
        "Votre question en français :", 
        placeholder="Exemple : Donne-moi le top 5 des clients qui ont le plus gros montant d'achat, avec leur ville"
    )

    if st.button("Lancer l'analyse 🚀"):
        if not user_query.strip():
            st.error("Veuillez saisir une question avant de valider.")
        else:
            with st.spinner("L'IA locale génère la requête SQL..."):
                columns_list = list(df.columns)
                prompt = f"""
                You are an expert SQL generator. 
                Database system: SQLite.
                Table name: 'clients'
                Columns in table 'clients': {columns_list}

                Translate the user's natural language request into a single, syntactically correct SQLite query.
                Rule 1: Output ONLY the raw SQL query. Do not wrap it in markdown code blocks like ```sql ... ```.
                Rule 2: Do not write any explanations, preambles, or markdown formatting. Just the raw SQL string.
                Rule 3: Use case-insensitive matching where appropriate (e.g. using LIKE) to make the search robust.
                Rule 4: Do not use non-existent columns. Only select from: {columns_list}

                User request: {user_query}
                """

                try:
                    # Utilisation du client Ollama configuré sur l'IP locale directe sous Windows
                    client = ollama.Client(host="http://127.0.0.1:11434")
                    response = client.generate(model=model_name, prompt=prompt)
                    sql_query = response['response'].strip()
                    
                    # Nettoyage de sécurité si le modèle a ignoré l'instruction d'exclusion de markdown
                    if sql_query.startswith("```"):
                        lines = sql_query.split("\n")
                        sql_query = "\n".join([line for line in lines if not line.startswith("```")])
                    
                    sql_query = sql_query.replace("`", "").strip()

                    # Affichage de la requête générée
                    st.subheader("🤖 Requête SQL générée par l'IA :")
                    st.markdown(f"<div class='sql-code'>{sql_query}</div>", unsafe_allow_html=True)
                    
                    # Exécution de la requête SQL sur SQLite
                    with st.spinner("Exécution du SQL sur le fichier Excel..."):
                        query_result = pd.read_sql_query(sql_query, conn)
                        
                    # Affichage des résultats
                    st.subheader("📊 Résultats de la requête :")
                    if query_result.empty:
                        st.info("La requête s'est exécutée correctement, mais aucun client ne correspond à ces critères.")
                    else:
                        st.dataframe(query_result, use_container_width=True)
                        
                        # Bouton de téléchargement
                        csv_data = query_result.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Télécharger ce résultat au format CSV",
                            data=csv_data,
                            file_name="resultat_ia_clients.csv",
                            mime="text/csv"
                        )
                        
                except Exception as e:
                    st.error("❌ Une erreur est survenue lors de la génération ou de l'exécution.")
                    st.write(f"Détails de l'erreur : `{e}`")
                    st.info("Astuce : Assurez-vous qu'Ollama est bien démarré sur votre PC et que le modèle choisi est téléchargé.")
                    
    # Fermeture de la connexion
    conn.close()
```
eof

### Ce qu'il vous reste à faire :

1. Enregistrez ce code propre à la place de l'ancien contenu dans votre fichier `data_copilot.py`.
2. Assurez-vous d'avoir démarré l'application **Ollama** (l'icône de la tête de lama doit être visible en bas à droite de votre écran Windows, près de l'horloge).
3. Relancez votre application dans votre terminal de commande Windows :
   ```cmd
   streamlit run data_copilot.py
   ```

Tout devrait fonctionner parfaitement maintenant ! Dites-moi si vous parvenez à générer vos premières requêtes SQL.
