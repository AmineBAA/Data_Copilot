import streamlit as st
import pandas as pd
import sqlite3
import ollama
import os

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

# Sidebar - Configuration & Diagnostic de connexion
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Saisie du nom du fichier Excel
    file_name = st.text_input("Nom du fichier Excel source", "info_clients.xlsx")
    
    # Choix du modèle Ollama disponible (Modèle 1.5b par défaut car très rapide)
    st.subheader("🤖 Modèle NLP Local")
    model_name = st.text_input("Modèle Ollama à utiliser", "qwen2.5-coder:1.5b")
    
    st.subheader("🌐 Connexion Ollama")
    # Adresse de connexion personnalisable (IP directe ou localhost)
    ollama_host = st.text_input("Adresse d'Ollama", "http://127.0.0.1:11434")
    
    # Bouton de diagnostic en temps réel
    if st.button("🔌 Tester la connexion à Ollama"):
        try:
            test_client = ollama.Client(host=ollama_host)
            # Tente de lister les modèles pour vérifier la bonne communication
            test_client.list()
            st.success("✅ Connecté avec succès à Ollama !")
        except Exception as e:
            st.error(f"❌ Échec de la connexion à l'adresse fournie.\n\nDétails : {e}")

# Vérification de l'existence du fichier Excel
df = None
if os.path.exists(file_name):
    try:
        df = pd.read_excel(file_name)
        st.success(f"✅ Fichier `{file_name}` chargé avec succès depuis le dossier local !")
    except Exception as e:
        st.error(f"Erreur lors du chargement de l'Excel : {e}")
else:
    st.warning(f"⚠️ Le fichier `{file_name}` est introuvable dans le dossier de l'application.")
    uploaded_file = st.file_uploader("Ou importez un fichier Excel temporaire ici :", type=["xlsx", "xls"])
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            st.success("✅ Fichier chargé avec succès via l'importateur !")
        except Exception as e:
            st.error(f"Erreur : {e}")

# Si les données sont chargées et prêtes
if df is not None:
    # Aperçu des données pour l'utilisateur
    with st.expander("👀 Aperçu du fichier client importé"):
        st.dataframe(df.head(10), use_container_width=True)
        st.caption(f"Le fichier contient {df.shape[0]} lignes et {df.shape[1]} colonnes.")

    # Création de la base de données SQL en mémoire temporaire (SQLite)
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    # Injecte les données dans une table appelée "clients"
    df.to_sql("clients", conn, index=False, if_exists="replace")

    # Message d'instructions
    st.markdown("<div class='info-box'>Posez n'importe quelle question sur vos clients. L'IA locale va générer la requête SQL appropriée, l'exécuter sur vos données et afficher le résultat instantanément.</div>", unsafe_allow_html=True)
    
    user_query = st.text_input(
        "Votre question en français :", 
        placeholder="Exemple : Donne-moi le nombre de clients"
    )

    if st.button("Lancer l'analyse 🚀"):
        if not user_query.strip():
            st.error("Veuillez saisir une question avant de lancer l'analyse.")
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
                    # Utilisation de l'hôte sélectionné par l'utilisateur dans l'interface
                    client = ollama.Client(host=ollama_host)
                    response = client.generate(model=model_name, prompt=prompt)
                    sql_query = response['response'].strip()
                    
                    # Nettoyage de sécurité si le modèle n'a pas respecté l'exclusion de balises Markdown
                    if sql_query.startswith("```"):
                        lines = sql_query.split("\n")
                        sql_query = "\n".join([line for line in lines if not line.startswith("```")])
                    
                    sql_query = sql_query.replace("`", "").strip()

                    # Affichage de la requête générée
                    st.subheader("🤖 Requête SQL générée par l'IA :")
                    st.markdown(f"<div class='sql-code'>{sql_query}</div>", unsafe_allow_html=True)
                    
                    # Exécution de la requête SQL sur la base de données en mémoire
                    with st.spinner("Exécution du SQL sur le fichier Excel..."):
                        query_result = pd.read_sql_query(sql_query, conn)
                        
                    # Affichage des résultats
                    st.subheader("📊 Résultats de la requête :")
                    if query_result.empty:
                        st.info("La requête s'est exécutée correctement, mais aucun client ne correspond à ces critères.")
                    else:
                        st.dataframe(query_result, use_container_width=True)
                        
                        # Bouton pour exporter les résultats en CSV
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
                    st.info("Astuce : Assurez-vous qu'Ollama est bien démarré sur votre machine et que le modèle de la barre latérale a bien été téléchargé.")
                    
    # Fermeture de la connexion à SQLite
    conn.close()

Dites-moi si le bouton de test passe au vert !
