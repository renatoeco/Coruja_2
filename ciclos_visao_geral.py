import streamlit as st
from funcoes_auxiliares import conectar_mongo_coruja, safe_col, safe_get, validar_df
import pandas as pd
import time
import datetime


st.set_page_config(page_title="Fases Operacionais", page_icon=":material/analytics:")



###########################################################################################################
# CONEXÃO COM O BANCO DE DADOS MONGODB
###########################################################################################################

# Conecta-se ao banco de dados MongoDB (usa cache automático para melhorar performance)
db = conectar_mongo_coruja()


col_ciclos = db["ciclos_investimento"]
df_ciclos = pd.DataFrame(list(col_ciclos.find()))

col_editais = db["editais"]
df_editais = pd.DataFrame(list(col_editais.find()))

# col_investidores = db["investidores"]
# df_investidores = pd.DataFrame(list(col_investidores.find()))

col_doadores = db["doadores"]
df_doadores = pd.DataFrame(list(col_doadores.find()))

# Define as coleções específicas que serão utilizadas a partir do banco
# col_pessoas = db["pessoas"]


###########################################################################################################
# TRATAMENTO DOS DADOS
###########################################################################################################

# Renomear as colunas de df_ciclos
df_ciclos = df_ciclos.rename(columns={
    col: novo for col, novo in {
        "codigo_ciclo": "Código",
        "nome_ciclo": "Nome",
        "data_lancamento": "Data de Lançamento",
        #"investidores": "Investidores",
        "doadores": "Doadores"
    }.items() if col in df_ciclos.columns
})

# Renomear as colunas de df_editais
df_editais = df_editais.rename(columns={
    col: novo for col, novo in {
        "codigo_edital": "Código",
        "nome_edital": "Nome",
        "data_lancamento": "Data de Lançamento",
        "ciclo_investimento": "Fase operacional",
    }.items() if col in df_editais.columns
})

# Renomear as colunas de df_investidores
# df_investidores = df_investidores.rename(columns={
#     col: novo for col, novo in {
#         "sigla_investidor": "Sigla",
#         "nome_investidor": "Nome",
#     }.items() if col in df_investidores.columns
# })

# Renomear as colunas de df_doadores
df_doadores = df_doadores.rename(columns={
    col: novo for col, novo in {
        "sigla_doador": "Sigla",
        "nome_doador": "Nome",
    }.items() if col in df_doadores.columns
})

# Converte o ObjectId para string (evita erro do PyArrow)
if "_id" in df_ciclos.columns:
    df_ciclos["_id"] = df_ciclos["_id"].astype(str)

if "_id" in df_editais.columns:
    df_editais["_id"] = df_editais["_id"].astype(str)

# if "_id" in df_investidores.columns:
#     df_investidores["_id"] = df_investidores["_id"].astype(str)

if "_id" in df_doadores.columns:
    df_doadores["_id"] = df_doadores["_id"].astype(str)


###########################################################################################################
# VALIDAÇÃO DOS DADOS
###########################################################################################################


erros_gerais = []

valido_ciclos, erros = validar_df(df_ciclos, "Ciclos", ["Código"])
erros_gerais += erros

valido_editais, erros = validar_df(df_editais, "Editais", ["Código"])
erros_gerais += erros

# valido_investidores, erros = validar_df(df_investidores, "Investidores", ["Sigla"])
# erros_gerais += erros

valido_doadores, erros = validar_df(df_doadores, "Doadores", ["Sigla"])
erros_gerais += erros


###########################################################################################################
# FUNÇÕES
###########################################################################################################




###########################################################################################################
# INTERFACE PRINCIPAL DA PÁGINA
###########################################################################################################

# Logo do sidebar
st.logo("images/logo_fundo_ecos.png", size='large')

# Título da página
st.header("Visão geral")
st.write('')

if erros_gerais:
    st.warning(
        "Dados incompletos detectados:\n\n- " +
        "\n- ".join(erros_gerais)
    )
    
    st.write("")
    st.write("")


# --- Função auxiliar para pluralização ---
def pluralizar(qtd, singular, plural):
    return f"{qtd} {singular if qtd == 1 else plural}"


# --- FILTROS ---
with st.expander("**Filtros**"):

    col_filtros = st.columns(3)

    with col_filtros[0]:
        filtro_ciclo = st.selectbox(
            "Fase operacional:",
                options=["Todos"] + (
                sorted(df_ciclos["Código"].dropna().unique().tolist())
                if "Código" in df_ciclos.columns else []
            )
        )

    with col_filtros[1]:
        filtro_edital = st.selectbox(
            "Edital:",
            options=["Todos"] + (
                sorted(df_editais["Código"].dropna().unique().tolist())
                if "Código" in df_editais.columns else []
            )
        )

    # with col_filtros[2]:
    #     filtro_investidor = st.selectbox(
    #         "Investidor:",
    #             options=["Todos"] + (
    #                 sorted(df_investidores["Sigla"].dropna().unique().tolist())
    #                 if "Sigla" in df_investidores.columns else []
    #         )
    #     )

    with col_filtros[2]:
        filtro_doador = st.selectbox(
            "Doador:",
                options=["Todos"] + (
                    sorted(df_doadores["Sigla"].dropna().unique().tolist())
                    if "Sigla" in df_doadores.columns else []
            )
        )


# --- Inicializa dataframes filtrados ---
df_ciclos_filtrado = df_ciclos.copy()
df_editais_filtrado = df_editais.copy()
#df_investidores_filtrado = df_investidores.copy()
df_doadores_filtrado = df_doadores.copy()


# --- FILTRO POR FASE OPERACIONAL ---
if filtro_ciclo != "Todos" and "Código" in df_ciclos.columns:
    # Fase operacional selecionada
    df_ciclos_filtrado = df_ciclos[df_ciclos["Código"] == filtro_ciclo]

    # Editais relacionados
    df_editais_filtrado = df_editais[df_editais["Fase operacional"] == filtro_ciclo]

    # Investidores e doadores relacionados
    #investidores_rel = df_ciclos_filtrado["Investidores"].explode().dropna().unique().tolist()
    doadores_rel = df_ciclos_filtrado["Doadores"].explode().dropna().unique().tolist()

    #df_investidores_filtrado = df_investidores[df_investidores["Sigla"].isin(investidores_rel)]
    df_doadores_filtrado = df_doadores[df_doadores["Sigla"].isin(doadores_rel)]


# --- FILTRO POR EDITAL ---
elif filtro_edital != "Todos" and "Código" in df_editais.columns:
    df_editais_filtrado = df_editais[df_editais["Código"] == filtro_edital]

    ciclo_rel = None
    if not df_editais_filtrado.empty and "Fase operacional" in df_editais_filtrado.columns:
        ciclo_rel = df_editais_filtrado["Fase operacional"].iloc[0]
        
    df_ciclos_filtrado = df_ciclos[df_ciclos["Código"] == ciclo_rel]

    #investidores_rel = df_ciclos_filtrado["Investidores"].explode().dropna().unique().tolist()
    doadores_rel = df_ciclos_filtrado["Doadores"].explode().dropna().unique().tolist()

    #df_investidores_filtrado = df_investidores[df_investidores["Sigla"].isin(investidores_rel)]
    df_doadores_filtrado = df_doadores[df_doadores["Sigla"].isin(doadores_rel)]


# --- FILTRO POR INVESTIDOR ---
# elif filtro_investidor != "Todos" and "Investidores" in df_ciclos.columns:
#     df_ciclos_filtrado = df_ciclos[
#         df_ciclos["Investidores"].apply(lambda x: filtro_investidor in x if isinstance(x, list) else False)
#     ]

#     codigos_ciclos_rel = df_ciclos_filtrado["Código"].unique().tolist()
#     df_editais_filtrado = df_editais[df_editais["Fase operacional"].isin(codigos_ciclos_rel)]

#     df_investidores_filtrado = df_investidores[df_investidores["Sigla"] == filtro_investidor]

#     doadores_rel = df_ciclos_filtrado["Doadores"].explode().dropna().unique().tolist()
#     df_doadores_filtrado = df_doadores[df_doadores["Sigla"].isin(doadores_rel)]


# --- FILTRO POR DOADOR ---
elif filtro_doador != "Todos" and "Doadores" in df_ciclos.columns:
    df_ciclos_filtrado = df_ciclos[
        df_ciclos["Doadores"].apply(lambda x: filtro_doador in x if isinstance(x, list) else False)
    ]

    codigos_ciclos_rel = df_ciclos_filtrado["Código"].unique().tolist()
    df_editais_filtrado = df_editais[df_editais["Fase operacional"].isin(codigos_ciclos_rel)]

    #investidores_rel = df_ciclos_filtrado["Investidores"].explode().dropna().unique().tolist()
    #df_investidores_filtrado = df_investidores[df_investidores["Sigla"].isin(investidores_rel)]

    df_doadores_filtrado = df_doadores[df_doadores["Sigla"] == filtro_doador]








# --- EXIBIÇÃO DOS DATAFRAMES ---

st.write('')

# Fases Operacionais ------------------------------------------------------
st.subheader(pluralizar(len(df_ciclos_filtrado), "Fase Operacional", "Fases Operacionais"))
st.dataframe(
    df_ciclos_filtrado,
    hide_index=True,
    column_order=['Código', 'Nome', 'Data de Lançamento', 'Doadores']
)
st.write('')

# EDITAIS ------------------------------------------------------
st.subheader(pluralizar(len(df_editais_filtrado), "Edital", "Editais"))

# Formata a coluna para dd/mm/yyyy
if "Data de Lançamento" in df_editais_filtrado.columns:
            df_editais_filtrado["Data de Lançamento"] = (
            pd.to_datetime(
                df_editais_filtrado["Data de Lançamento"],
                dayfirst=True  
            )
            .dt.strftime("%d/%m/%Y")
        )

st.dataframe(
    df_editais_filtrado,
    hide_index=True,
    column_order=['Código', 'Nome', 'Data de Lançamento', 'Fase operacional']
)
st.write('')

# INVESTIDORES ------------------------------------------------------
# st.subheader(pluralizar(len(df_investidores_filtrado), "investidor", "investidores"))
# st.dataframe(
#     df_investidores_filtrado,
#     hide_index=True,
#     column_order=['Sigla', 'Nome']
# )
# st.write('')

# DOADORES ------------------------------------------------------
st.subheader(pluralizar(len(df_doadores_filtrado), "Doador", "Doadores"))
st.dataframe(
    df_doadores_filtrado,
    hide_index=True,
    column_order=['Sigla', 'Nome']
)









