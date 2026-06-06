import streamlit as st
import pandas as pd
import sqlite3
import re
import unicodedata
import os

# Configuration de la page Streamlit
st.set_page_config(
    page_title="IA Assistant Excel - SQL Autonome",
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
        color: #115e59;
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
        font-weight: bold;
    }
    .analysis-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-header'>📊 Assistant IA - Analyse SQL Intégrée et Autonome</h1>", unsafe_allow_html=True)

def normaliser_texte(texte):
    """Nettoie le texte (minuscules, sans accents, sans caractères spéciaux)."""
    if not isinstance(texte, str):
        return ""
    texte = "".join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')
    texte = texte.lower().strip()
    texte = re.sub(r'[^\w\s]', ' ', texte)
    return " ".join(texte.split())

class MoteurNLPLocal:
    """Moteur NLP heuristique pour traduire le français en SQL SQLite."""
    def __init__(self, df):
        self.df = df
        self.colonnes = list(df.columns)
        self.cols_normalisees = {normaliser_texte(c): c for c in self.colonnes}
        
    def generer_requete(self, requete_utilisateur):
        req_norm = normaliser_texte(requete_utilisateur)
        mots = req_norm.split()
        
        # Initialisation des composants SQL
        select_clause = "SELECT *"
        where_conditions = []
        order_by_clause = ""
        limit_clause = ""
        
        # 1. Détection des fonctions d'agrégation (Calculs)
        col_numeriques = [c for c in self.colonnes if pd.api.types.is_numeric_dtype(self.df[c])]
        col_cible_num = col_numeriques[0] if col_numeriques else None
        
        # Essayer de trouver la colonne numérique mentionnée dans la requête
        for col_norm, col_orig in self.cols_normalisees.items():
            if col_orig in col_numeriques and col_norm in req_norm:
                col_cible_num = col_orig
                break

        # Analyse des mots déclencheurs
        if any(w in req_norm for w in ["combien", "nombre", "quantite", "nb"]):
            select_clause = "SELECT COUNT(*) AS [Nombre total]"
        elif any(w in req_norm for w in ["somme", "total", "additionne"]):
            if col_cible_num:
                select_clause = f"SELECT SUM([{col_cible_num}]) AS [Total]"
        elif any(w in req_norm for w in ["moyenne", "moyen", "moyennement"]):
            if col_cible_num:
                select_clause = f"SELECT AVG([{col_cible_num}]) AS [Moyenne]"
        elif any(w in req_norm for w in ["maximum", "max", "plus grand", "plus haut", "plus cher"]):
            if col_cible_num:
                select_clause = f"SELECT MAX([{col_cible_num}]) AS [Maximum]"
        elif any(w in req_norm for w in ["minimum", "min", "plus petit", "plus bas", "moins cher"]):
            if col_cible_num:
                select_clause = f"SELECT MIN([{col_cible_num}]) AS [Minimum]"
        
        # 2. Détection dynamique des filtres de texte (Villes, Noms, etc.)
        # On parcourt les colonnes textuelles et on vérifie si une valeur de la colonne est dans la requête
        col_textuelles = [c for c in self.colonnes if not pd.api.types.is_numeric_dtype(self.df[c])]
        for col in col_textuelles:
            valeurs_uniques = self.df[col].dropna().unique()
            for val in valeurs_uniques:
                val_str = str(val)
                val_norm = normaliser_texte(val_str)
                # Si la valeur normalisée est un mot entier ou une expression dans la requête
                if val_norm and (val_norm in req_norm):
                    # Double protection pour éviter les correspondances partielles accidentelles sur des mots courts
                    if len(val_norm) > 2 or f" {val_norm} " in f" {req_norm} ":
                        where_conditions.append(f"[{col}] LIKE '{val_str}'")

        # 3. Détection des filtres numériques (Âge, Achats, etc.)
        nombres = re.findall(r'\b\d+\b', requete_utilisateur)
        if nombres and col_numeriques:
            valeur_num = int(nombres[0])
            # Choisir la colonne numérique appropriée
            col_filtre = col_numeriques[0]
            # Si l'utilisateur parle d'âge
            if "an" in req_norm or "age" in req_norm:
                cols_age = [c for c in col_numeriques if "age" in normaliser_texte(c) or "an" in normaliser_texte(c)]
                if cols_age:
                    col_filtre = cols_age[0]
            # Si l'utilisateur parle d'argent/montant
            elif any(w in req_norm for w in ["achat", "montant", "argent", "prix", "euro", "somme"]):
                cols_money = [c for c in col_numeriques if any(w in normaliser_texte(c) for w in ["achat", "montant", "prix", "solde"])]
                if cols_money:
                    col_filtre = cols_money[0]
            
            # Détection de l'opérateur de comparaison
            if any(w in req_norm for w in ["plus de", "superieur a", "plus grand que", "plus age que", "depasse", ">"]):
                where_conditions.append(f"[{col_filtre}] > {valeur_num}")
            elif any(w in req_norm for w in ["moins de", "inferieur a", "plus jeune que", "sous", "<"]):
                where_conditions.append(f"[{col_filtre}] < {valeur_num}")
            else:
                where_conditions.append(f"[{col_filtre}] = {valeur_num}")

        # 4. Détection des Tris et des Limites (Top, Classement)
        if "top" in req_norm or "premier" in req_norm:
            nb_limit = 5 # Valeur par défaut
            if nombres:
                nb_limit = int(nombres[0])
            limit_clause = f"LIMIT {nb_limit}"
            if col_cible_num:
                order_by_clause = f"ORDER BY [{col_cible_num}] DESC"
        elif "trier" in req_norm or "ordre" in req_norm or "classer" in req_norm:
            if col_cible_num:
                if "decroissant" in req_norm or "plus grand" in req_norm:
                    order_by_clause = f"ORDER BY [{col_cible_num}] DESC"
                else:
                    order_by_clause = f"ORDER BY [{col_cible_num}] ASC"

        # 5. Assemblage final de la requête SQL
        sql_final = select_clause + " FROM clients"
        if where_conditions:
            sql_final += " WHERE " + " AND ".join(where_conditions)
        if order_by_clause:
            sql_final += " " + order_by_clause
        if limit_clause:
            sql_final += " " + limit_clause
            
        return sql_final

with st.sidebar:
    st.header("⚙️ Fichier Source")
    file_name = st.text_input("Nom du fichier Excel attendu", "clients.xlsx")
    st.info("💡 Ce moteur NLP fonctionne de manière 100% autonome. Aucun logiciel tiers n'est requis !")

# Vérification et chargement du fichier Excel
df = None
if os.path.exists(file_name):
    try:
        df = pd.read_excel(file_name)
        st.success(f"✅ Fichier `{file_name}` chargé avec succès !")
    except Exception as e:
        st.error(f"Erreur de lecture : {e}")
else:
    st.warning(f"⚠️ Le fichier `{file_name}` est introuvable.")
    uploaded_file = st.file_uploader("Importez votre fichier Excel ici :", type=["xlsx", "xls"])
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            st.success("✅ Fichier chargé via l'importateur !")
        except Exception as e:
            st.error(f"Erreur : {e}")

if df is not None:
    # Aperçu des données
    with st.expander("👀 Aperçu de vos données Excel"):
        st.dataframe(df.head(10), use_container_width=True)
        st.caption(f"Le fichier contient {df.shape[0]} lignes et {df.shape[1]} colonnes.")

    # Création de la base SQLite en mémoire
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    df.to_sql("clients", conn, index=False, if_exists="replace")

    st.markdown("<div class='info-box'><b>Moteur IA Intégré :</b> Posez votre question en français simple. Vos phrases sont analysées localement et exécutées instantanément en SQL.</div>", unsafe_allow_html=True)

    # Zone de saisie utilisateur
    user_query = st.text_input(
        "Votre question en français :", 
        placeholder="Exemples : 'Donne moi le nombre de clients', 'Combien de clients habitent à Paris ?', 'Trier les clients par montant'"
    )

    if st.button("Lancer l'analyse 🚀"):
        if not user_query.strip():
            st.error("Veuillez saisir une question avant de lancer l'analyse.")
        else:
            with st.spinner("Analyse sémantique de la demande..."):
                try:
                    # Instanciation et exécution du moteur NLP local
                    nlp = MoteurNLPLocal(df)
                    sql_query = nlp.generer_requete(user_query)

                    # Diagnostic visuel de l'analyse pour l'utilisateur
                    st.subheader("🤖 Analyse sémantique de la phrase :")
                    
                    # Génération et exécution de la requête SQL
                    query_result = pd.read_sql_query(sql_query, conn)

                    # Affichage de la requête générée
                    st.markdown(f"<div class='sql-code'>{sql_query}</div>", unsafe_allow_html=True)
                    
                    st.subheader("📊 Résultats de la requête :")
                    if query_result.empty:
                        st.info("L'analyse a fonctionné, mais aucune ligne ne correspond à ces critères exacts.")
                    else:
                        st.dataframe(query_result, use_container_width=True)
                        
                        # Exportation des résultats
                        csv_data = query_result.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Télécharger ce résultat (CSV)",
                            data=csv_data,
                            file_name="resultat_ia_clients.csv",
                            mime="text/csv"
                        )
                except Exception as e:
                    st.error(f"Une erreur est survenue lors de l'exécution de la requête : {e}")
                    st.info("Astuce : Essayez de formuler votre question plus simplement en mentionnant clairement les noms de colonnes et les valeurs recherchées.")

    conn.close()




Dites-moi si l'application s'exécute maintenant correctement sur votre machine !
