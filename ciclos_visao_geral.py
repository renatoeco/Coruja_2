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

col_projetos = db["projetos"]
df_projetos = pd.DataFrame(list(col_projetos.find()))

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

# Converter lista de fases operacionais para texto separado por vírgula
if "Fase operacional" in df_editais.columns:
    df_editais["Fase operacional"] = df_editais["Fase operacional"].apply(
        lambda x: ", ".join(x) if isinstance(x, list) else x
    )

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


def normalizar_valor(valor):
    """
    Converte valores monetários para float.
    """
    if pd.isna(valor):
        return 0.0

    try:
        return float(valor)
    except:
        return 0.0


def agregar_metricas_projetos(df_projetos, df_editais_original, df_ciclos_original):
    """
    Agrega número de iniciativas e valor investido por:
    - fase operacional
    - edital
    - doador
    """

    if df_projetos.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = df_projetos.copy()

    # Valor investido
    df["valor_investido_num"] = df["financeiro"].apply(
        lambda x: normalizar_valor(x.get("valor_total", 0))
        if isinstance(x, dict) else 0
    )
    
    # ==========================================================
    # MÉTRICAS POR EDITAL
    # ==========================================================
    metricas_editais = (
        df.groupby("edital")
        .agg(
            **{
                "Número de iniciativas apoiadas": ("_id", "count"),
                "Valor investido": ("valor_investido_num", "sum")
            }
        )
        .reset_index()
        .rename(columns={"edital": "Código"})
    )

    # ==========================================================
    # CRUZAMENTO COM EDITAIS PARA PEGAR CICLOS
    # ==========================================================
    df_editais_aux = df_editais_original[["codigo_edital", "ciclo_investimento"]].copy()

    df = df.merge(
        df_editais_aux,
        left_on="edital",
        right_on="codigo_edital",
        how="left"
    )

    # ==========================================================
    # MÉTRICAS POR FASE OPERACIONAL
    # ==========================================================
    df_fases = df.copy()

    df_fases["ciclo_investimento"] = df_fases["ciclo_investimento"].apply(
        lambda x: x if isinstance(x, list)
        else [x] if pd.notna(x)
        else []
    )

    df_fases = df_fases.explode("ciclo_investimento")

    metricas_fases = (
        df_fases.groupby("ciclo_investimento")
        .agg(
            **{
                "Número de iniciativas apoiadas": ("_id", "count"),
                "Valor investido": ("valor_investido_num", "sum")
            }
        )
        .reset_index()
        .rename(columns={"ciclo_investimento": "Código"})
    )

    # ==========================================================
    # CRUZAMENTO COM CICLOS PARA PEGAR DOADORES
    # ==========================================================
    df_ciclos_aux = df_ciclos_original[["codigo_ciclo", "doadores"]].copy()

    df_fases = df_fases.merge(
        df_ciclos_aux,
        left_on="ciclo_investimento",
        right_on="codigo_ciclo",
        how="left"
    )

    df_fases["doadores"] = df_fases["doadores"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    df_fases = df_fases.explode("doadores")

    metricas_doadores = (
        df_fases.groupby("doadores")
        .agg(
            **{
                "Número de iniciativas apoiadas": ("_id", "count"),
                "Valor investido": ("valor_investido_num", "sum")
            }
        )
        .reset_index()
        .rename(columns={"doadores": "Sigla"})
    )

    return metricas_fases, metricas_editais, metricas_doadores


###########################################################################################################
# INTERFACE PRINCIPAL DA PÁGINA
###########################################################################################################

# Logo do sidebar
st.logo("images/logo_fundo_ecos.png", size='large')

# Título da página
st.header("Visão geral")
st.write('')

metricas_fases, metricas_editais, metricas_doadores = agregar_metricas_projetos(
    df_projetos,
    pd.DataFrame(list(col_editais.find())),
    pd.DataFrame(list(col_ciclos.find()))
)

# Merge com fases
df_ciclos = df_ciclos.merge(
    metricas_fases,
    on="Código",
    how="left"
)

# Merge com editais
df_editais = df_editais.merge(
    metricas_editais,
    on="Código",
    how="left"
)

# Merge com doadores
df_doadores = df_doadores.merge(
    metricas_doadores,
    on="Sigla",
    how="left"
)

# Preencher vazios
for df_temp in [df_ciclos, df_editais, df_doadores]:
    if "Número de iniciativas apoiadas" in df_temp.columns:
        df_temp["Número de iniciativas apoiadas"] = (
            df_temp["Número de iniciativas apoiadas"]
            .fillna(0)
            .astype(int)
        )

    if "Valor investido" in df_temp.columns:
        df_temp["Valor investido"] = (
            df_temp["Valor investido"]
            .fillna(0)
            .astype(float)
        )
        
for df_temp in [df_ciclos, df_editais, df_doadores]:
    df_temp["Valor investido"] = df_temp["Valor investido"].map(
        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )

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
    df_editais_filtrado = df_editais[
        df_editais["Fase operacional"].apply(
            lambda x: filtro_ciclo in x if isinstance(x, str) else False
        )
    ]

    # Investidores e doadores relacionados
    #investidores_rel = df_ciclos_filtrado["Investidores"].explode().dropna().unique().tolist()
    doadores_rel = df_ciclos_filtrado["Doadores"].explode().dropna().unique().tolist()

    #df_investidores_filtrado = df_investidores[df_investidores["Sigla"].isin(investidores_rel)]
    df_doadores_filtrado = df_doadores[df_doadores["Sigla"].isin(doadores_rel)]


# --- FILTRO POR EDITAL ---
elif filtro_edital != "Todos" and "Código" in df_editais.columns:
    df_editais_filtrado = df_editais[df_editais["Código"] == filtro_edital]

    ciclos_rel = []

    if not df_editais_filtrado.empty and "Fase operacional" in df_editais_filtrado.columns:
        valor = df_editais_filtrado["Fase operacional"].iloc[0]

        if isinstance(valor, str):
            ciclos_rel = [v.strip() for v in valor.split(",") if v.strip()]

    df_ciclos_filtrado = df_ciclos[
        df_ciclos["Código"].isin(ciclos_rel)
    ]

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
    df_editais_filtrado = df_editais[
        df_editais["Fase operacional"].apply(
            lambda x: any(c in x for c in codigos_ciclos_rel) if isinstance(x, str) else False
        )
    ]

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
    column_order=[
        'Código',
        'Nome',
        'Data de Lançamento',
        'Doadores',
        'Número de iniciativas apoiadas',
        'Valor investido'
    ]
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
    column_order=[
        'Código',
        'Nome',
        'Data de Lançamento',
        'Fase operacional',
        'Número de iniciativas apoiadas',
        'Valor investido'
    ]
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
    column_order=[
        'Sigla',
        'Nome',
        'Número de iniciativas apoiadas',
        'Valor investido'
    ]
)









