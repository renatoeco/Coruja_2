import streamlit as st
from funcoes_auxiliares import conectar_mongo_coruja  # Função personalizada para conectar ao MongoDB
import pandas as pd
from bson import ObjectId
import time


st.set_page_config(page_title="Visitantes", page_icon=":material/visibility:")




###########################################################################################################
# CONEXÃO COM O BANCO DE DADOS MONGODB
###########################################################################################################

# Conecta-se ao banco de dados MongoDB (usa cache automático para melhorar performance)
db = conectar_mongo_coruja()

# Importa coleções e cria dataframes

# Pessoas
col_pessoas = db["pessoas"]



###########################################################################################################
# TRATAMENTO DOS DADOS
###########################################################################################################

# Busca todos os documentos, mas exclui o campo "senha"
df_pessoas = pd.DataFrame(list(col_pessoas.find({}, {"senha": 0})))

# Converte ObjectId para string
df_pessoas["_id"] = df_pessoas["_id"].astype(str)

# Renomeia as colunas
df_pessoas = df_pessoas.rename(columns={
    "nome_completo": "Nome",
    "tipo_usuario": "Tipo de usuário",
    "tipo_beneficiario": "Tipo de beneficiário",
    "e_mail": "E-mail",
    "telefone": "Telefone",
    "status": "Status",
    "projetos": "Projetos"
})

# Ordena por Nome
df_pessoas = df_pessoas.sort_values(by="Nome")

# Projetos
col_projetos = db["projetos"]
df_projetos = pd.DataFrame(list(col_projetos.find()))
# Converte objectId para string
df_projetos['_id'] = df_projetos['_id'].astype(str)





###########################################################################################################
# Funções
###########################################################################################################


# Diálogo para editar uma pessoa
@st.dialog("Editar Pessoa", width="medium")
def editar_pessoa(_id: str):
    """Abre o diálogo para editar uma pessoa"""
    
    pessoa = col_pessoas.find_one({"_id": ObjectId(_id)})
    if not pessoa:
        st.error("Pessoa não encontrada.")
        return

    # Inputs básicos
    nome = st.text_input("Nome", value=pessoa.get("nome_completo", ""))
    email = st.text_input("E-mail", value=pessoa.get("e_mail", ""))
    telefone = st.text_input("Telefone", value=pessoa.get("telefone", ""))

    # Tipo de usuário
    tipo_usuario_raw = pessoa.get("tipo_usuario", "")
    tipo_usuario_default = tipo_usuario_raw.strip() if isinstance(tipo_usuario_raw, str) else ""

    tipo_usuario = st.selectbox(
        "Tipo de usuário",
        options=["admin", "equipe", "beneficiario", "visitante"],
        index=["admin", "equipe", "beneficiario", "visitante"].index(tipo_usuario_default)
        if tipo_usuario_default in ["admin", "equipe", "beneficiario", "visitante"]
        else 0
    )

    # Tipo de beneficiário — só aparece se tipo_usuario == beneficiario
    tipo_beneficiario = None
    if tipo_usuario == "beneficiario":
        tipo_beneficiario = st.selectbox(
            "Tipo de beneficiário",
            options=["técnico", "financeiro"],
            index=["técnico", "financeiro"].index(pessoa.get("tipo_beneficiario", "técnico"))
            if pessoa.get("tipo_beneficiario") in ["técnico", "financeiro"]
            else 0
        )

    # Status
    status = st.selectbox(
        "Status",
        options=["ativo", "inativo"],
        index=0 if pessoa.get("status", "ativo") == "ativo" else 1
    )

    # Projetos
    projetos = st.multiselect(
        "Projetos",
        options=df_projetos["codigo"].tolist(),
        default=pessoa.get("projetos", []),
    )

    st.write("")

    # Botão de salvar
    if st.button("Salvar alterações", icon=":material/save:"):
        # Documento base
        update_data = {
            "nome_completo": nome,
            "e_mail": email,
            "telefone": telefone,
            "tipo_usuario": tipo_usuario,
            "status": status,
            "projetos": projetos
        }

        # Adiciona tipo_beneficiario apenas se aplicável
        if tipo_beneficiario:
            update_data["tipo_beneficiario"] = tipo_beneficiario
        else:
            # Remove o campo se existir no documento anterior
            col_pessoas.update_one({"_id": ObjectId(_id)}, {"$unset": {"tipo_beneficiario": ""}})

        # Atualiza o registro
        col_pessoas.update_one({"_id": ObjectId(_id)}, {"$set": update_data})

        st.success("Pessoa atualizada com sucesso!")
        time.sleep(2)
        st.rerun()





###########################################################################################################
# INTERFACE
###########################################################################################################


# Logo do sidebar
st.logo("images/logo_fundo_ecos.png", size='large')

st.header('Visitantes')

st.divider()

# Separando só os visitantes
df_visitantes = df_pessoas[
    df_pessoas["Tipo de usuário"] == "visitante"
]

st.write('')

dist_colunas = [3, 4, 3, 2, 3, 2, 1]

# Colunas
col1, col2, col3, col4, col5, col6, col7 = st.columns(dist_colunas)

# Cabeçalho da lista
col1.write('**Nome**')
col2.write('**Projetos**')
col3.write('**E-mail**')
col4.write('**Telefone**')
col5.write('**Tipo de usuário**')
col6.write('**Status**')
col7.write('')

st.write('')

# Pra cada linha, criar colunas para os dados
for _, row in df_visitantes.iterrows():
    col1, col2, col3, col4, col5, col6, col7 = st.columns(dist_colunas)

    # NOME -----------------
    col1.write(row["Nome"])

    # PROJETOS -----------------

    # Tratando a coluna projetos, que pode ter múltiplos valores------
    projetos = row.get("Projetos", [])
    # Garante que 'projetos' seja uma lista
    if isinstance(projetos, str):
        projetos = [projetos]
    elif not isinstance(projetos, list):
        projetos = []
    # Exibe de forma amigável
    if len(projetos) == 0:
        col2.write("")
    elif len(projetos) == 1:
        col2.write(projetos[0])
    else:
        col2.write(", ".join(projetos))
    

    # E-MAIL -----------------

    col3.write(row["E-mail"])

    # TELEFONE -----------------
    col4.write(row["Telefone"])


    # TIPO DE USUÁRIO -----------------
    tipo_usuario = str(row.get("Tipo de usuário", "")).strip()

    # Exibição
    col5.write(tipo_usuario)


    # STATUS -----------------       
    col6.write(row["Status"])

    # BOTÃO DE EDITAR -----------------
    col7.button(":material/edit:", key=row["_id"], on_click=editar_pessoa, args=(row["_id"],))
