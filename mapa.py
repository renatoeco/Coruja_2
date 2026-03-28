import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from funcoes_auxiliares import conectar_mongo_cepf_gestao



st.set_page_config(page_title="Mapa", page_icon=":material/map:")




###########################################################################################################
# CONEXÃO COM O BANCO
###########################################################################################################

db = conectar_mongo_cepf_gestao()

col_projetos = db["projetos"]
df_projetos = pd.DataFrame(list(col_projetos.find()))

col_editais = db["editais"]
df_editais = pd.DataFrame(list(col_editais.find()))



###########################################################################################################
# FUNÇÕES
###########################################################################################################

if "notificacoes_mapa" not in st.session_state:
    st.session_state.notificacoes_mapa = []

# Envia mensagem para a área de notificação
def notificar_mapa(mensagem: str):
    st.session_state.notificacoes_mapa.append(mensagem)







###########################################################################################################
# TRATAMENTO DOS DADOS
###########################################################################################################



###########################################################################################################
# INTERFACE
###########################################################################################################

st.logo("images/ieb_logo.svg", size="large")
st.header("Mapa de projetos")

st.write('')

# Área de notificações
if st.session_state.notificacoes_mapa:
    with st.expander("Notificações", expanded=False, icon=":material/warning:"):
        for msg in st.session_state.notificacoes_mapa:
            st.warning(msg)

# Limpar as notificações, para preencher novamente.
st.session_state.notificacoes_mapa = []



# ============================================
# FILTRO DE EDITAL
# ============================================

lista_editais = ["Todos"] + df_editais["codigo_edital"].tolist()
edital_selecionado = st.selectbox("Selecione o edital", lista_editais, width=300)

st.write("")

if edital_selecionado == "Todos":
    st.markdown("##### Todos os editais")
else:
    nome_edital = df_editais.loc[
        df_editais["codigo_edital"] == edital_selecionado,
        "nome_edital"
    ].values[0]

    st.markdown(f"##### {edital_selecionado} - {nome_edital}")

# ============================================
# FILTRAGEM DE PROJETOS
# ============================================

df_filtrado = df_projetos.copy()

if edital_selecionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado["edital"] == edital_selecionado]

if df_filtrado.empty:
    st.divider()
    st.warning("Nenhum projeto encontrado.")
    st.stop()



# ============================================
# COLETA DE PONTOS PARA O MAPA
# ============================================

pontos_mapa = []

for _, projeto in df_filtrado.iterrows():

    encontrou_localidade = False  # <- controle por projeto

    locais = projeto.get("locais")

    # Garante que seja um dicionário
    if not isinstance(locais, dict):
        notificar_mapa(
            f"O projeto {projeto.get('codigo')} - {projeto.get('sigla')} não tem localidades cadastradas."
        )
        continue

    localidades = locais.get("localidades")

    # Garante lista válida
    if not isinstance(localidades, list) or not localidades:
        notificar_mapa(
            f"O projeto {projeto.get('codigo')} - {projeto.get('sigla')} não tem localidades cadastradas."
        )
        continue

    for local in localidades:
        if not isinstance(local, dict):
            continue

        lat = local.get("latitude")
        lon = local.get("longitude")

        # Ignora coordenadas inválidas
        if lat is None or lon is None:
            continue

        encontrou_localidade = True

        pontos_mapa.append({
            "codigo": projeto.get("codigo"),
            "sigla": projeto.get("sigla"),
            "nome_projeto": projeto.get("nome_do_projeto"),
            "organizacao": projeto.get("organizacao"),
            "municipio": local.get("municipio"),
            "localidade": local.get("nome_localidade"),
            "latitude": lat,
            "longitude": lon
        })

    # Se passou pelo projeto inteiro e não achou nenhuma localidade válida
    if not encontrou_localidade:
        notificar_mapa(
            f"O projeto {projeto.get('codigo')} - {projeto.get('sigla')} não tem localidades cadastradas."
        )



# ============================================
# RENDERIZAÇÃO DO MAPA
# ============================================

if not pontos_mapa:
    st.info("Nenhuma localidade com coordenadas válidas foi encontrada.")
else:
    df_mapa = pd.DataFrame(pontos_mapa)

    centro_lat = df_mapa["latitude"].mean()
    centro_lon = df_mapa["longitude"].mean()

    mapa = folium.Map(
        location=[centro_lat, centro_lon],
        zoom_start=4,
        tiles="OpenStreetMap"
    )

    for _, row in df_mapa.iterrows():

        popup_html = f"""
        <div style="width:300px">
            <b>{row.get('localidade', '')}</b><br><br>
            <b>{row.get('codigo', '')} - {row.get('sigla', '')}</b><br><br>
            
            <b>Organização:</b> {row.get('organizacao', '')}<br>
            <b>Projeto:</b> {row.get('nome_projeto', '')}<br>
            <b>Município:</b> {row.get('municipio', '')}<br>
        </div>
        """

        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=folium.Popup(popup_html, max_width=500),
            icon=folium.Icon(color="red", prefix="fa"),
        ).add_to(mapa)

    st_folium(mapa, width="100%", height=600)




