import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from funcoes_auxiliares import conectar_mongo_coruja, safe_col, safe_get, validar_df


st.set_page_config(page_title="Mapa", page_icon=":material/map:")


###########################################################################################################
# CONEXÃO COM O BANCO
###########################################################################################################


db = conectar_mongo_coruja()

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
# VALIDAÇÃO DOS DADOS
###########################################################################################################


erros_gerais = []

valido_editais, erros = validar_df(
    df_editais,
    "Editais",
    ["codigo_edital", "nome_edital"]
)
erros_gerais += erros

valido_projetos, erros = validar_df(
    df_projetos,
    "Projetos",
    ["codigo", "sigla", "edital"]
)


###########################################################################################################
# INTERFACE
###########################################################################################################

st.logo("images/logo_fundo_ecos.png", size="large")
st.header("Mapa de projetos")

st.write('')

if erros_gerais:
    st.warning(
        "Dados incompletos detectados:\n\n- " +
        "\n- ".join(erros_gerais)
    )
    
    st.write('')
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

if valido_editais:
    lista_editais = ["Todos"] + sorted(
        safe_col(df_editais, "codigo_edital", pd.Series()).dropna().unique().tolist()
    )
else:
    lista_editais = ["Todos"]
    
edital_selecionado = st.selectbox("Selecione o edital", lista_editais, width=300)

st.write("")

if edital_selecionado == "Todos":
    st.markdown("##### Todos os editais")
else:
    nome_edital = "Nome não disponível"

    if valido_editais and edital_selecionado != "Todos":
        resultado = df_editais.loc[
            df_editais["codigo_edital"] == edital_selecionado,
            "nome_edital"
        ]
        if not resultado.empty:
            nome_edital = resultado.values[0]

    st.markdown(f"##### {edital_selecionado} - {nome_edital}")

# ============================================
# FILTRAGEM DE PROJETOS
# ============================================

df_filtrado = df_projetos.copy()

if edital_selecionado != "Todos" and "edital" in df_filtrado.columns:
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

    locais = safe_get(projeto, "locais")

    # Garante que seja um dicionário
    if not isinstance(locais, dict):
        notificar_mapa(
            f"O projeto {safe_get(projeto,'codigo','-')} - {safe_get(projeto,'sigla','-')} não tem localidades cadastradas."
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

        lat = local.get("latitude") if isinstance(local, dict) else None
        lon = local.get("longitude") if isinstance(local, dict) else None

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




