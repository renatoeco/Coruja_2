import streamlit as st
from funcoes_auxiliares import conectar_mongo_coruja, calcular_status_projetos, registrar_estatistica_sessao
import plotly.express as px
import pandas as pd
import datetime
# import locale


st.set_page_config(page_title="Visão Geral", page_icon=":material/analytics:")




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





# ###########################################################################################################
# # REGISTRO DE ESTATÍSTICA -  CONTABILIZAÇÃO DE VISITA
# ###########################################################################################################

registrar_estatistica_sessao(db)





###########################################################################################################
# FUNÇÕES
###########################################################################################################





# ============================================
# ÁREA DE NOTIFICAÇÕES
# ============================================


if "notificacoes" not in st.session_state:
    st.session_state.notificacoes = []




###########################################################################################################
# TRATAMENTO DE DADOS
###########################################################################################################

if not df_projetos.empty:

    # ------------------------------------------------------------------------------
    # 1. Limpa notificações anteriores
    # ------------------------------------------------------------------------------
    st.session_state.notificacoes = []


    # ------------------------------------------------------------------------------
    # 2. Calcula status dos projetos (status, dias_atraso, próximo evento, etc.)
    # ------------------------------------------------------------------------------
    df_projetos = calcular_status_projetos(df_projetos)


    # ------------------------------------------------------------------------------
    # 3. Filtra usuários relevantes (admin e equipe)
    # ------------------------------------------------------------------------------
    df_pessoas = df_pessoas[
        df_pessoas["tipo_usuario"].isin(["admin", "equipe"])
    ]


    # ------------------------------------------------------------------------------
    # 4. Relaciona projetos aos padrinhos
    # ------------------------------------------------------------------------------

    # Seleciona apenas colunas necessárias
    df_pessoas_proj = df_pessoas[["nome_completo", "projetos"]].copy()

    # Garante que "projetos" seja sempre uma lista
    df_pessoas_proj["projetos"] = df_pessoas_proj["projetos"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    # Cria uma linha por projeto (explode)
    df_pessoas_proj = df_pessoas_proj.explode("projetos")

    # Remove registros sem código de projeto
    df_pessoas_proj = df_pessoas_proj.dropna(subset=["projetos"])

    # Renomeia colunas para facilitar o merge
    df_pessoas_proj = df_pessoas_proj.rename(columns={
        "projetos": "codigo",
        "nome_completo": "padrinho"
    })

    # Agrupa padrinhos por projeto (caso haja mais de um)
    df_padrinhos = (
        df_pessoas_proj
        .groupby("codigo")["padrinho"]
        .apply(lambda nomes: ", ".join(sorted(set(nomes))))
        .reset_index()
    )


    # ------------------------------------------------------------------------------
    # 4.1 Validação antes do merge (evita KeyError quando não há projetos)
    # ------------------------------------------------------------------------------

    # Verifica se o dataframe de projetos não está vazio e possui a coluna "codigo"
    if not df_projetos.empty and "codigo" in df_projetos.columns:

        # Realiza o merge com padrinhos
        df_projetos = df_projetos.merge(
            df_padrinhos,
            on="codigo",
            how="left"
        )

    else:
        # Garante que a coluna "padrinho" exista mesmo sem merge
        # Isso evita erros posteriores na interface e nos filtros
        df_projetos["padrinho"] = None


    # Garante que colunas essenciais existam mesmo se o dataframe vier vazio
    colunas_essenciais = ["codigo", "sigla", "edital"]

    for col in colunas_essenciais:
        if col not in df_projetos.columns:
            df_projetos[col] = None




    # ------------------------------------------------------------------------------
    # 5. Ajustes de tipos (IDs e datas) - versão resiliente
    # ------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------
    # 5.1 Garante que a coluna "_id" exista antes da conversão
    # ------------------------------------------------------------------------------

    # DataFrame de pessoas
    if "_id" in df_pessoas.columns:
        df_pessoas["_id"] = df_pessoas["_id"].astype(str)

    # DataFrame de projetos
    if "_id" in df_projetos.columns:
        df_projetos["_id"] = df_projetos["_id"].astype(str)


    # ------------------------------------------------------------------------------
    # 5.2 Conversão de datas com validação de existência das colunas
    # ------------------------------------------------------------------------------

    # Data início do contrato
    if "data_inicio_contrato" in df_projetos.columns:
        df_projetos["data_inicio_contrato_dtime"] = pd.to_datetime(
            df_projetos["data_inicio_contrato"],
            format="%d/%m/%Y",
            dayfirst=True,
            errors="coerce"
        )
    else:
        # Cria a coluna vazia para manter consistência do dataframe
        df_projetos["data_inicio_contrato_dtime"] = pd.NaT


    # Data fim do contrato
    if "data_fim_contrato" in df_projetos.columns:
        df_projetos["data_fim_contrato_dtime"] = pd.to_datetime(
            df_projetos["data_fim_contrato"],
            format="%d/%m/%Y",
            dayfirst=True,
            errors="coerce"
        )
    else:
        # Cria a coluna vazia para manter consistência do dataframe
        df_projetos["data_fim_contrato_dtime"] = pd.NaT









###########################################################################################################
# INTERFACE PRINCIPAL DA PÁGINA
###########################################################################################################


# Logo do sidebar
st.logo("images/logo_fundo_ecos.png", size='large')

# Título da página
st.header("Projetos")


st.write('')


# Área de notificações

if st.session_state.notificacoes:
    with st.expander("Notificações", expanded=False, icon=":material/warning:"):
        for msg in st.session_state.notificacoes:
            st.warning(msg)

st.write('')
st.write('')



# ============================================
# SELEÇÃO DO EDITAL
# ============================================



# ------------------------------------------------------------------------------
# SELEÇÃO DO EDITAL - versão resiliente
# ------------------------------------------------------------------------------

# Verifica se o dataframe de editais possui dados e a coluna necessária
if not df_editais.empty and "codigo_edital" in df_editais.columns:

    lista_editais = ["Todos"] + df_editais["codigo_edital"].dropna().tolist()

else:
    # Garante que o selectbox funcione mesmo sem editais cadastrados
    lista_editais = ["Todos"]


# Criação do selectbox
edital_selecionado = st.selectbox(
    "Selecione o edital",
    lista_editais,
    width=300
)






# ============================================
# TÍTULO + TOGGLE NO MESMO CONTAINER
# ============================================


with st.container(horizontal=True):

    col_titulo, col_toggle = st.columns([4, 1])

    with col_titulo:
        if edital_selecionado == "Todos":
            st.subheader("Todos os editais")
        else:
            nome_edital = df_editais.loc[
                df_editais["codigo_edital"] == edital_selecionado,
                "nome_edital"
            ].values[0]

            st.subheader(f"{edital_selecionado} - {nome_edital}")

    with col_toggle:
        st.write("")
        ver_meus_projetos = st.toggle(
            "Ver somente os meus projetos",
            False
        )




# ============================================
# APLICAÇÃO DOS FILTROS
# ============================================


# -------------------------------------------------
# FILTRO POR EDITAL
# -------------------------------------------------

df_filtrado = df_projetos.copy()


if edital_selecionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado["edital"] == edital_selecionado]

# Se não há projetos no edital
if df_filtrado.empty:
    st.divider()
    st.warning("Nenhum projeto encontrado.")
    st.stop()


# -------------------------------------------------
# FILTRO POR PADRINHO LOGADO
# -------------------------------------------------
if ver_meus_projetos:

    # Se a coluna padrinho não existir
    if "padrinho" not in df_filtrado.columns:
        st.divider()
        st.caption("Nenhum projeto associado a você.")
        st.stop()


    df_meus = df_filtrado[
        df_filtrado["padrinho"]
            .fillna("")  # evita erro se houver NaN
            .str.contains(st.session_state.nome, case=False)
    ]




    if df_meus.empty:
        st.divider()
        st.caption("Nenhum projeto associado a você.")
        st.stop()

    # Se encontrou projetos do usuário
    df_filtrado = df_meus


# Caso não existam projetos após os filtros
if df_filtrado.empty:
    st.divider()
    st.warning("Nenhum projeto encontrado.")
    st.stop()



else:

    # ============================================
    # INTERFACE
    # ============================================

    st.divider()

    sobre_col1, sobre_col2 = st.columns([7, 3])

    sobre_col1.write("**Projetos atrasados**")
    sobre_col2.write("**Status dos projetos**")

    # -------------------------------------------------
    # FILTRO DE PROJETOS ATRASADOS (ÚNICO PONTO)
    # -------------------------------------------------
    if edital_selecionado == "Todos":
        projetos_atrasados = df_filtrado[df_filtrado["status"] == "Atrasado"]
    else:
        projetos_atrasados = df_filtrado[
            (df_filtrado["edital"] == edital_selecionado) &
            (df_filtrado["status"] == "Atrasado")
        ]

    # -------------------------------------------------
    # COLUNAS
    # -------------------------------------------------
    col1, col2, col3 = st.columns([1, 6, 3], gap="large")

    # -------------------------------------------------
    # COLUNA 1 — MÉTRICA
    # -------------------------------------------------
    with col1:
        total_atrasados = len(projetos_atrasados)
        st.metric("", total_atrasados)
        st.write("")

    # -------------------------------------------------
    # COLUNA 2 — LISTA DE PROJETOS ATRASADOS
    # -------------------------------------------------
    with col2:
        st.write("")

        if not projetos_atrasados.empty:
            df_exibir = projetos_atrasados.copy()

            df_exibir = df_exibir[
                ["codigo", "sigla", "padrinho", "edital", "dias_atraso"]
            ]

            df_exibir = df_exibir.rename(columns={
                "codigo": "Código",
                "sigla": "Sigla",
                "padrinho": "Padrinho/Madrinha",
                "dias_atraso": "Dias de atraso",
                "edital": "Edital"
            })

            df_exibir = df_exibir.sort_values(
                by="Dias de atraso",
                ascending=False
            )

            st.dataframe(df_exibir, hide_index=True)

        else:
            st.write("Não há projetos atrasados.")






    # Gráfico de pizza do status
    with col3:

        mapa_cores_status = {
            'Concluído': 'rgba(0, 122, 211, 0.4)',   # Azul 50%
            'Em dia': 'rgba(160, 194, 86, 0.4)',     # Verde 50%
            'Atrasado': 'rgba(226, 101, 12, 0.4)',   # Laranja 50%
            'Cancelado': '#bbb',
            'Sem cronograma': '#fff099'
        }



        contagens = df_filtrado['status'].value_counts(dropna=True)
        status = contagens.index.tolist()
        contagem_status = contagens.values.tolist()

        fig = px.pie(
            names=status,
            values=contagem_status,
            color=status,
            color_discrete_map=mapa_cores_status,
            height=300
        )
        st.plotly_chart(fig)









    # Cronograma de contratos
    st.write("**Cronograma de contratos**")

    # Criando uma nova coluna com a data de fim no formato datetime, pra poder usar o sort por data
    df_filtrado['data_fim_contrato_dt'] = pd.to_datetime(
        df_filtrado['data_fim_contrato'],
        format='%d/%m/%Y',
        errors='coerce'
    )

    # Sort pela data de fim
    df_filtrado_sorted = df_filtrado.sort_values(
        by='data_fim_contrato_dt',
        ascending=False
    )

    altura_base = 400
    altura_extra = sum([10 / (1 + i * 0.01) for i in range(len(df_filtrado_sorted))])
    altura = int(altura_base + altura_extra)


    fig = px.timeline(
        df_filtrado_sorted.assign(
            _texto_barra=(
                df_filtrado_sorted['codigo'].astype(str)
                + ' - '
                + df_filtrado_sorted['sigla'].astype(str)
            )
        ),
        x_start='data_inicio_contrato_dtime',
        x_end='data_fim_contrato_dtime',
        y='codigo',
        text='_texto_barra',  # 👈 inline: codigo - sigla
        color='status',
        color_discrete_map=mapa_cores_status,
        height=altura,
    )



    fig.update_traces(
        hovertemplate=(
            '<b>Projeto:</b> %{y}<br>' +
            '<b>Início:</b> %{customdata[0]}<br>' +
            '<b>Fim:</b> %{customdata[1]}<br>' +
            '<extra></extra>'
        ),
        textposition='inside',
        insidetextanchor='middle',
        textfont=dict(size=14),
        cliponaxis=False,
        customdata=df_filtrado_sorted[['data_inicio_contrato', 'data_fim_contrato']].values
    )

    fig.update_yaxes(
        visible=False,
        showticklabels=False
    )


    fig.add_vline(
        x=datetime.datetime.today(),
        line_width=2,
        line_dash="dash",
        line_color="red",
    )

    fig.update_layout(
        
        showlegend=False,
        yaxis=dict(title=None, side="right"),
        xaxis=dict(
            showgrid=True,
            gridcolor='lightgray',
            tickmode='linear',
            dtick="M1",
            tickformat="%m/%Y"
        )
    )

    st.plotly_chart(fig)


