import streamlit as st
import pandas as pd
import re

from funcoes_auxiliares import (
    conectar_mongo_cepf_gestao,
    sidebar_projeto,
)


st.set_page_config(page_title="Fotos", page_icon=":material/image:")





###########################################################################################################
# CONEXÃO COM O BANCO DE DADOS
###########################################################################################################

db = conectar_mongo_cepf_gestao()
col_projetos = db["projetos"]

###########################################################################################################
# FUNÇÕES AUXILIARES
###########################################################################################################

def extrair_id_drive(valor):
    if not valor:
        return None

    # Se já for apenas o ID
    if "/" not in valor and len(valor) > 20:
        return valor

    if "/d/" in valor:
        return valor.split("/d/")[1].split("/")[0]

    if "id=" in valor:
        m = re.search(r"id=([a-zA-Z0-9_-]+)", valor)
        if m:
            return m.group(1)

    return None


def gerar_urls_drive(file_id):
    return {
        "preview": f"https://drive.google.com/file/d/{file_id}/preview",
        "drive": f"https://drive.google.com/file/d/{file_id}/view",
    }

def coletar_fotos_projeto(projeto):
    fotos = []

    plano = projeto.get("plano_trabalho", {})
    componentes = plano.get("componentes", [])

    for componente in componentes:
        for entrega in componente.get("entregas", []):
            for atividade in entrega.get("atividades", []):
                nome_atividade = atividade.get("atividade")

                for relato in atividade.get("relatos", []):
                    id_relato = relato.get("id_relato")
                    texto_relato = relato.get("relato")
                    quando = relato.get("quando")
                    onde = relato.get("onde")

                    for foto in relato.get("fotos", []):
                        fotos.append({
                            # atividade
                            "atividade": nome_atividade,

                            # relato
                            "id_relato": id_relato,
                            "relato": texto_relato,
                            "quando": quando,
                            "onde": onde,

                            # foto
                            "nome_arquivo": foto.get("nome_arquivo"),
                            "descricao": foto.get("descricao"),
                            "fotografo": foto.get("fotografo"),
                            "id_arquivo": foto.get("id_arquivo"),
                        })

    return fotos


###########################################################################################################
# CARREGAMENTO DO PROJETO
###########################################################################################################

codigo_projeto_atual = st.session_state.get("projeto_atual")

if not codigo_projeto_atual:
    st.error("Nenhum projeto selecionado.")
    st.stop()

df_projeto = pd.DataFrame(
    list(col_projetos.find({"codigo": codigo_projeto_atual}))
)

if df_projeto.empty:
    st.error("Projeto não encontrado.")
    st.stop()

projeto = df_projeto.iloc[0].to_dict()

###########################################################################################################
# INTERFACE
###########################################################################################################

st.logo("images/ieb_logo.svg", size="large")

col_titulo, col_identificacao = st.columns([3, 2])

with col_titulo:
    st.header("Galeria de Fotos")

with col_identificacao:
    st.markdown(
        f"<div style='text-align:right; margin-top:30px;'>"
        f"{projeto.get('codigo')} - {projeto.get('sigla')}"
        f"</div>",
        unsafe_allow_html=True
    )

sidebar_projeto()

###########################################################################################################
# GALERIA DE FOTOS
###########################################################################################################

fotos = coletar_fotos_projeto(projeto)

st.markdown(
    f"#### {len(fotos)} foto" if len(fotos) == 1 else f"#### {len(fotos)} fotos"
)

if not fotos:
    st.caption("Nenhuma foto cadastrada neste projeto.")
    st.stop()

with st.container(border=False, horizontal=True, width="stretch"):

    for i, foto in enumerate(fotos):

        with st.container(
            border=True,
            width=280,
            height=520,
            key=f"foto_{i}"
        ):

            file_id = extrair_id_drive(foto.get("id_arquivo"))

            if file_id:
                urls = gerar_urls_drive(file_id)


                st.markdown(
                    f"""
                    <div style="
                        background-color: white;
                        padding: 4px;
                        border-radius: 8px;
                    ">
                        <iframe
                            src="{urls['preview']}"
                            width="100%"
                            height="200"
                            style="
                                border: none;
                                background-color: white;
                                border-radius: 6px;
                            "
                            loading="lazy"
                        ></iframe>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            else:
                st.warning("Imagem sem ID válido")

            # Texto do card
            # --- METADADOS ---

            st.markdown(
                f"<strong>Atividade:</strong> {foto.get('atividade', '')}",
                unsafe_allow_html=True
            )

            st.markdown(
                f"<strong>{foto.get('id_relato', '')}:</strong>"
                " "
                f"{foto.get('relato', '')}",
                unsafe_allow_html=True
            )

            if foto.get("quando"):
                st.write(f"**Quando:** {foto.get('quando')}")

            if foto.get("onde"):
                st.write(f"**Onde:** {foto.get('onde')}")

            st.divider()

            st.write(f"**Descrição:** {foto.get('descricao', '')}")
            st.write(f"**Fotógrafo:** {foto.get('fotografo', '')}")
            st.write(f"**Arquivo:** {foto.get('nome_arquivo', '')}")


            if file_id:
                st.link_button(
                    "Ver foto",
                    urls["drive"],
                    type="primary",
                    icon=":material/open_in_new:"
                )




