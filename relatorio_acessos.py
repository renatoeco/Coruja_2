import streamlit as st
from funcoes_auxiliares import conectar_mongo_cepf_gestao  
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta



st.set_page_config(page_title="Relatório de acessos", page_icon=":material/bar_chart:")



###########################################################################################################
# CARREGAMENTO DO BANCO DE DADOS
###########################################################################################################


db = conectar_mongo_cepf_gestao()



###########################################################################################################
# INTERFACE
###########################################################################################################



# Logo do sidebar
st.logo("images/ieb_logo.svg", size='large')

st.header('Relatório de acessos')

st.write('')
st.write('')




# --------------------------------------------------------------------------------------------------
# FILTRO DE PERÍODO (COM LARGURA CONTROLADA)
# --------------------------------------------------------------------------------------------------


periodo = st.selectbox(
    "Selecione o período",
    ["Últimos 30 dias", "Últimos 12 meses", "Todo o período"],
    index=0,
    width=250
)

# --------------------------------------------------------------------------------------------------
# CARREGAMENTO DOS DADOS DO MONGODB
# --------------------------------------------------------------------------------------------------

colecao = db["estatistica"]
doc = colecao.find_one({"_id": "controle_acessos"})

if not doc or "total_sessoes" not in doc:
    st.warning("Nenhum dado de acesso encontrado.")
    st.stop()

df = pd.DataFrame(doc["total_sessoes"])

# --------------------------------------------------------------------------------------------------
# TRATAMENTO DE DATAS
# --------------------------------------------------------------------------------------------------

df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")

# --------------------------------------------------------------------------------------------------
# FILTRO DE PERÍODO
# --------------------------------------------------------------------------------------------------

hoje = datetime.now()

if periodo == "Últimos 30 dias":
    df = df[df["data"] >= hoje - timedelta(days=30)]

elif periodo == "Últimos 12 meses":
    df = df[df["data"] >= hoje - timedelta(days=365)]

df = df.sort_values("data")

# --------------------------------------------------------------------------------------------------
# PREPARAÇÃO DOS DADOS
# --------------------------------------------------------------------------------------------------

df = df.rename(columns={
    "equipe": "Equipe",
    "benef": "Beneficiários",
    "visit": "Visitantes"
})

df_melt = df.melt(
    id_vars="data",
    value_vars=["Equipe", "Beneficiários", "Visitantes"],
    var_name="Tipo",
    value_name="Sessões"
)

# --------------------------------------------------------------------------------------------------
# GRÁFICO
# --------------------------------------------------------------------------------------------------

fig = px.bar(
    df_melt,
    x="data",
    y="Sessões",
    color="Tipo",
    barmode="group",
    text="Sessões",
    color_discrete_map={
        "Equipe": "#007AD3",
        "Beneficiários": "#A0C256",
        "Visitantes": "orange"
    }
)

# --------------------------------------------------------------------------------------------------
# AJUSTES VISUAIS
# --------------------------------------------------------------------------------------------------

fig.update_traces(
    textposition="inside"
)


fig.update_layout(
    xaxis_title="",
    yaxis_title="Sessões",
    xaxis=dict(
        tickformat="%d/%m/%Y",
        tickangle=90
    ),
    yaxis=dict(
        dtick=1
    )
)


# --------------------------------------------------------------------------------------------------
# EXIBIÇÃO
# --------------------------------------------------------------------------------------------------

st.plotly_chart(fig, width='stretch', height=550)

