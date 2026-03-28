import streamlit as st
from funcoes_auxiliares import conectar_mongo_coruja, calcular_status_projetos
# import plotly.express as px
import pandas as pd


st.set_page_config(page_title="Projetos", page_icon=":material/list:")




###########################################################################################################
# CONEXÃO COM O BANCO DE DADOS MONGODB
###########################################################################################################

# Conecta-se ao banco de dados MongoDB (usa cache automático para melhorar performance)
db = conectar_mongo_coruja()

# Importa coleções e cria dataframes

# Pessoas
col_pessoas = db["pessoas"]
df_pessoas = pd.DataFrame(list(col_pessoas.find()))

# Projetos
col_projetos = db["projetos"]
df_projetos = pd.DataFrame(list(col_projetos.find()))

# Editais
col_editais = db["editais"]
df_editais = pd.DataFrame(list(col_editais.find()))

# Organizações
col_organizacoes = db["organizacoes"]
df_organizacoes = pd.DataFrame(list(col_organizacoes.find()))


###########################################################################################################
# FUNÇÕES
###########################################################################################################


###########################################################################################################
# MAPA ID -> NOME DA ORGANIZAÇÃO
###########################################################################################################

# cria um dicionário para acessar rapidamente o nome da organização pelo _id
mapa_org_id_nome = {
    row["_id"]: row["nome_organizacao"]
    for _, row in df_organizacoes.iterrows()
}




###########################################################################################################
# TRATAMENTO DE DADOS   
###########################################################################################################

if not df_projetos.empty:
    
    # Inclulir o status no dataframe de projetos
    df_projetos = calcular_status_projetos(df_projetos)


    # Converter object_id para string
    df_pessoas['_id'] = df_pessoas['_id'].astype(str)
    df_projetos['_id'] = df_projetos['_id'].astype(str)

    # Convertendo datas de string para datetime
    df_projetos['data_inicio_contrato_dtime'] = pd.to_datetime(
        df_projetos['data_inicio_contrato'], 
        format="%d/%m/%Y", 
        dayfirst=True, 
        errors="coerce"
    )

    df_projetos['data_fim_contrato_dtime'] = pd.to_datetime(
        df_projetos['data_fim_contrato'], 
        format="%d/%m/%Y", 
        dayfirst=True, 
        errors="coerce"
    )

    # Filtar somente tipos de usuário admin e equipe em df_pessoas
    df_pessoas = df_pessoas[(df_pessoas["tipo_usuario"] == "admin") | (df_pessoas["tipo_usuario"] == "equipe")]

    # Incluir padrinho no dataframe de projetos
    # Fazendo um dataframe auxiliar de relacionamento
    # Seleciona apenas colunas necessárias
    df_pessoas_proj = df_pessoas[["nome_completo", "projetos"]].copy()

    # Garante que "projetos" seja sempre lista
    df_pessoas_proj["projetos"] = df_pessoas_proj["projetos"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    # Explode: uma linha por projeto
    df_pessoas_proj = df_pessoas_proj.explode("projetos")

    # Remove linhas sem código de projeto
    df_pessoas_proj = df_pessoas_proj.dropna(subset=["projetos"])

    # Renomeia para facilitar o merge
    df_pessoas_proj = df_pessoas_proj.rename(columns={
        "projetos": "codigo",
        "nome_completo": "padrinho"
    })

    # Agrupar (caso haja mais de um padrinho por projeto)
    df_padrinhos = (
        df_pessoas_proj
        .groupby("codigo")["padrinho"]
        .apply(lambda nomes: ", ".join(sorted(set(nomes))))
        .reset_index()
    )

    # Fazer o merge
    df_projetos = df_projetos.merge(
        df_padrinhos,
        on="codigo",
        how="left"
    )

###########################################################################################################
# INTERFACE PRINCIPAL DA PÁGINA
###########################################################################################################


# Logo do sidebar
st.logo("images/logo_fundo_ecos.png", size='large')

# Título da página
st.header("Projetos")


st.write('')


col1, col2, col3, col4 = st.columns(4)


with col1:

    # ============================================
    # SELEÇÃO DO EDITAL
    # ============================================

    # Lista de editais disponíveis
    lista_editais = sorted(df_editais['codigo_edital'].unique().tolist())

    # Adiciona "Todos" no início
    lista_editais = ["Todos"] + lista_editais

    # Selectbox de edital
    edital_selecionado = st.selectbox("Selecione o edital", lista_editais, width=300)






with col2:

    # ============================================
    # SELEÇÃO DA ORGANIZAÇÃO
    # ============================================

    # Cria coluna concatenada "SIGLA - Nome"
    df_organizacoes["org_label"] = (
        df_organizacoes["sigla_organizacao"] + " - " + df_organizacoes["nome_organizacao"]
    )

    # Ordena para melhor visualização
    df_organizacoes = df_organizacoes.sort_values("org_label")

    # Cria lista de opções
    lista_orgs = df_organizacoes["org_label"].tolist()

    # Adiciona opção "Todas"
    lista_orgs = ["Todas"] + lista_orgs

    # Cria mapa label -> id da organização
    mapa_org_label_id = {
        row["org_label"]: row["_id"]
        for _, row in df_organizacoes.iterrows()
    }

    # Selectbox de organização
    org_selecionada = st.selectbox(
        "Selecione a organização",
        lista_orgs,
        width=300
    )

st.write('')








st.write('')

# TÍTULO + TOGGLE 
# Colunas lado a lado dentro do container
col_titulo, col_toggle = st.columns([4, 1])


# --- TÍTULO ---
with col_titulo:
    if edital_selecionado == "Todos":
        st.subheader("Todos")

        # Contagem de projetos
        total_projetos = len(df_projetos)
        st.markdown(f"##### {total_projetos} projetos")


    else:
        nome_edital = df_editais.loc[
            df_editais["codigo_edital"] == edital_selecionado,
            "nome_edital"
        ].values[0]

        st.subheader(f"{edital_selecionado} — {nome_edital}")

        # Contagem de projetos
        total_projetos = len(df_projetos[df_projetos['edital'] == edital_selecionado])
        st.markdown(f"##### {total_projetos} projetos")
        

# --- TOGGLE ---
with col_toggle:
    st.write('')
    ver_meus_projetos = st.toggle(
        "Ver somente os meus projetos",
        False,
    )



# ============================================
# FILTROS
# ============================================


df_filtrado = df_projetos.copy()

col1, col2, col3, col4 = st.columns(4, gap="large")

# ###########################################################################################################
# Filtrar pelo EDITAL
# ###########################################################################################################

if edital_selecionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado["edital"] == edital_selecionado]


# Filtrar somente os projetos da pessoa logada
if ver_meus_projetos:

    nome_usuario = st.session_state.nome

    # Busca a pessoa logada no df_pessoas (nome CONTÉM o nome do usuário)
    pessoa = df_pessoas.loc[
        df_pessoas["nome_completo"]
            .fillna("")
            .str.contains(st.session_state.nome, case=False)
    ]

    # Busca a pessoa logada no df_pessoas
    if pessoa.empty:
        st.warning("Usuário não encontrado no cadastro de pessoas.")
        st.stop()

    # Pega a lista de projetos da primeira linha encontrada
    codigos_projetos = pessoa.iloc[0].get("projetos", [])

    # Garante que seja uma lista
    if not isinstance(codigos_projetos, list) or len(codigos_projetos) == 0:
        st.divider()
        st.caption("Nenhum projeto associado a você.")
        st.stop()

    df_meus = df_filtrado[
        df_filtrado["codigo"].isin(codigos_projetos)
    ]

    if df_meus.empty:
        st.divider()
        st.caption("Nenhum projeto associado a você.")
        st.stop()

    df_filtrado = df_meus



# ###############################################################################
# Filtrar pela ORGANIZAÇÃO
# ###############################################################################


if org_selecionada != "Todas":

    # Recupera o id da organização selecionada
    id_org = mapa_org_label_id.get(org_selecionada)

    # Aplica filtro
    df_filtrado = df_filtrado[
        df_filtrado["id_organizacao"] == id_org
    ]
















# Se nenhum projeto encontrado
if df_filtrado.empty:
    st.divider()
    st.warning("Nenhum projeto encontrado.")
    st.stop()

# Ordenar ascendente pela sigla
df_filtrado = df_filtrado.sort_values(by="sigla", ignore_index=True)


# ============================================
# INTERFACE - LISTAGEM DE PROJETOS
# ============================================

st.divider()

larguras_colunas = [2, 2, 5, 2, 2, 2]
col_labels = ["Código", "Sigla", "Organização", "Padrinho/Madrinha", "Status", "Abrir"]

# Cabeçalhos
cols = st.columns(larguras_colunas)
for i, label in enumerate(col_labels):
    cols[i].markdown(f"**{label}**")
st.write('')


# --------------------------------------------
# Listagem linha por linha
# --------------------------------------------

for index, projeto in df_filtrado.iterrows():
    
    cols = st.columns(larguras_colunas)

    cols[0].write(projeto['codigo'])
    cols[1].write(projeto['sigla'])

    # NOME DA ORGANIZAÇÃO
    # recupera o nome da organização usando o id armazenado no projeto
    nome_org = mapa_org_id_nome.get(projeto["id_organizacao"], "")

    cols[2].write(nome_org)



    # cols[2].write(projeto['organizacao'])

    # Padrinho
    valor = projeto.get("padrinho")

    if not valor or (isinstance(valor, float) and pd.isna(valor)):
        cols[3].markdown(
            "<span style='color:#d97706; font-style:italic;'>não definido</span>",
            unsafe_allow_html=True
        )
    else:
        cols[3].write(valor)



    mapa_cores_status = {
        'Concluído': 'rgba(0, 122, 211)',   # Azul 50%
        'Em dia': 'rgba(160, 194, 86)',     # Verde 50%
        'Atrasado': 'rgba(226, 101, 12)',   # Laranja 50%
        'Cancelado': '#bbb',
        'Sem cronograma': '#fff099'
    }

    status = projeto.get("status", "")

    cor = mapa_cores_status.get(status, "#ccc")

    # define o estilo especial
    estilo = ""
    texto_status = status

    if status == "Sem cronograma":
        estilo = "color:#d97706; font-style:italic;"
        texto_status = status.lower()

    html = f"""
    <span style="display:flex; align-items:center; gap:6px;">
        <span style="width:10px;height:10px;background-color:{cor};border-radius:50%;display:inline-block;"></span>
        <span style="{estilo}">{texto_status}</span>
    </span>
    """

    cols[4].markdown(html, unsafe_allow_html=True)


    # Botão “Ver projeto”
    if cols[5].button("Ver projeto", key=f"ver_{projeto['codigo']}"):
        st.session_state.pagina_atual = "ver_projeto"
        st.session_state.projeto_atual = projeto["codigo"]
        st.rerun()


