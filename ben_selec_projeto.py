import streamlit as st
from funcoes_auxiliares import conectar_mongo_cepf_gestao, registrar_estatistica_sessao


st.set_page_config(page_title="Lista de projetos", page_icon=":material/list")




###########################################################################################################
# CONEXÃO COM O BANCO DE DADOS MONGODB
###########################################################################################################

# Conecta-se ao banco de dados MongoDB (usa cache automático para melhorar performance)
db = conectar_mongo_cepf_gestao()

# Define as coleções específicas que serão utilizadas a partir do banco

# # Pessoas
# col_pessoas = db["pessoas"]
# df_pessoas = col_pessoas.find()

# Projetos
col_projetos = db["projetos"]
df_projetos = col_projetos.find()




# ###########################################################################################################
# # REGISTRO DE ESTATÍSTICA -  CONTABILIZAÇÃO DE VISITA
# ###########################################################################################################

registrar_estatistica_sessao(db)




###########################################################################################################
# FUNÇÕES
###########################################################################################################




###########################################################################################################
# INTERFACE PRINCIPAL DA PÁGINA
###########################################################################################################

# Define o layout da página como largura total
# st.set_page_config(layout="centered")

# Exibe o logo
container_logo = st.container(horizontal=True, horizontal_alignment="center")
container_logo.image("images/ieb_logo.svg", width=300)

st.write('')
st.write('')
st.write('')




# =====================================================================
# OBTÉM OS PROJETOS DO BENEFICIÁRIO LOGADO
# =====================================================================
projetos_raw = st.session_state.get("projetos")
projetos_usuario = projetos_raw if isinstance(projetos_raw, list) else []

nome_usuario = st.session_state.get("nome", "Usuário")
nome_usuario_split = nome_usuario.split(" ")
nome_usuario_primeiro_nome = nome_usuario_split[0]


col1, col2, col3 = st.columns([1, 3, 1])

with col2:
    st.header(f"Olá {nome_usuario_primeiro_nome}")
    st.write('')

    # =====================================================================
    # FILTRA OS PROJETOS DO BANCO DE DADOS
    # =====================================================================

    if projetos_usuario:
        st.subheader("Selecione o projeto que deseja acessar:")

        st.markdown("""
            <style>
            div.stButton > button {
                text-align: left !important;
                justify-content: flex-start !important;
            }
            </style>
        """, unsafe_allow_html=True)

        projetos_cursor = col_projetos.find({"codigo": {"$in": projetos_usuario}})
        projetos = list(projetos_cursor)

        if projetos:
            for i, projeto in enumerate(projetos):
                codigo = str(projeto.get("codigo", "")).strip()
                sigla = projeto.get("sigla", "")
                nome_proj = projeto.get("nome_do_projeto", "")
                texto_botao = f"**{codigo} - {sigla} - {nome_proj}**"

                key = f"btn_proj_{i}_{codigo}"

                if st.button(texto_botao, key=key, type="tertiary"):
                    st.session_state.projeto_atual = codigo
                    st.session_state.pagina_atual = "ver_projeto"
                    st.rerun()

        else:
            st.warning("Nenhum projeto encontrado para este usuário.")
    else:
        st.write("Não há projetos associados a este usuário.")
        st.write("Entre em contato com os administradores do sistema.")

