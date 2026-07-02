import streamlit as st
from funcoes_auxiliares import conectar_mongo_coruja  # Função personalizada para conectar ao MongoDB
import pandas as pd
from bson import ObjectId
import time



st.set_page_config(page_title="Convites pendentes", page_icon=":material/mail:")




###########################################################################################################
# CONEXÃO COM O BANCO DE DADOS MONGODB
###########################################################################################################

# Conecta-se ao banco de dados MongoDB (usa cache automático para melhorar performance)
db = conectar_mongo_coruja()

# Importa coleções e cria dataframes

# Pessoas
col_pessoas = db["pessoas"]


# Projetos
col_projetos = db["projetos"]


###########################################################################################################
# TRATAMENTO DOS DADOS
###########################################################################################################

# PROJETOS
# Converte objectId para string
df_projetos = pd.DataFrame(list(col_projetos.find()))

# Converte ObjectId para string (somente se existir)
if "_id" in df_projetos.columns:
    df_projetos["_id"] = df_projetos["_id"].astype(str)
else:
    st.warning("Projetos sem campo '_id'.")

# =============================================================================
# MAPAS DE COMPATIBILIDADE ENTRE CÓDIGO E OBJECTID
# =============================================================================

mapa_codigo_para_id = dict(
    zip(df_projetos["codigo"], df_projetos["_id"])
)

mapa_id_para_codigo = dict(
    zip(df_projetos["_id"], df_projetos["codigo"])
)

codigos_validos = set(df_projetos["codigo"].astype(str))

# PESSOAS

# 1) Busca todos os documentos, mas já exclui a coluna 'senha'
df_pessoas = pd.DataFrame(list(col_pessoas.find({}, {"senha": 0})))

if "_id" in df_pessoas.columns:
    df_pessoas["_id"] = df_pessoas["_id"].astype(str)
else:
    st.warning("Pessoas sem campo '_id'.")
    df_pessoas["_id"] = ""

# 2) Filtra apenas os registros com status 'convidado'
if "status" in df_pessoas.columns:
    df_pendentes = df_pessoas[df_pessoas["status"] == "convidado"]
else:
    df_pendentes = pd.DataFrame()
    st.warning("Coluna 'status' não encontrada.")





# Renomeia as colunas
df_pendentes = df_pendentes.rename(columns={
    "nome_completo": "Nome",
    "tipo_usuario": "Tipo de usuário",
    "e_mail": "E-mail",
    "telefone": "Telefone",
    "status": "Status",
    "projetos": "Projetos",
    "data_convite": "Data do convite"
})

# Ordena por Nome
df_pendentes = df_pendentes.sort_values(by="Nome")





###########################################################################################################
# Funções
###########################################################################################################


def converter_para_codigo(valor):

    valor = str(valor)

    # Nova estrutura (ObjectId)
    if valor in mapa_id_para_codigo:
        return mapa_id_para_codigo[valor]

    # Estrutura antiga (código)
    if valor in codigos_validos:
        return valor

    return None

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

    if "codigo" in df_projetos.columns:
        opcoes_projetos = df_projetos["codigo"].dropna().astype(str).tolist()
    else:
        opcoes_projetos = []
        st.warning("Projetos sem coluna 'codigo'.")

    # Projetos
    projetos_salvos = pessoa.get("projetos", [])

    if not isinstance(projetos_salvos, list):
        projetos_salvos = []

    projetos_default = [
        codigo
        for codigo in (
            converter_para_codigo(p)
            for p in projetos_salvos
        )
        if codigo is not None
    ]

    projetos = st.multiselect(
        "Projetos",
        options=opcoes_projetos,
        default=projetos_default,
    )

    st.write("")

    # Botão de salvar
    if st.button("Salvar alterações", icon=":material/save:"):
        # Documento base
        projetos_ids = [
            ObjectId(mapa_codigo_para_id[codigo])
            for codigo in projetos
            if codigo in mapa_codigo_para_id
        ]

        update_data = {
            "nome_completo": nome,
            "e_mail": email,
            "telefone": telefone,
            "tipo_usuario": tipo_usuario,
            "projetos": projetos_ids
        }

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

st.header('Convites pendentes')

st.divider()


dist_colunas = [3, 4, 3, 2, 3, 2, 1]

# Colunas
col1, col2, col3, col4, col5, col6, col7 = st.columns(dist_colunas)

# Cabeçalho da lista
col1.write('**Nome**')
col2.write('**Projetos**')
col3.write('**E-mail**')
col4.write('**Telefone**')
col5.write('**Tipo de usuário**')
col6.write('**Data do convite**')
col7.write('')

st.write('')

# Pra cada linha, criar colunas para os dados
for _, row in df_pendentes.iterrows():
    col1, col2, col3, col4, col5, col6, col7 = st.columns(dist_colunas)

    # NOME -----------------
    col1.write(row["Nome"])

    # PROJETOS -----------------

    # Tratando a coluna projetos, que pode ter múltiplos valores------
    projetos = row.get("Projetos", [])

    if not isinstance(projetos, list):
        projetos = []

    codigos = [
        codigo
        for codigo in (
            converter_para_codigo(p)
            for p in projetos
        )
        if codigo is not None
    ]

    col2.write(", ".join(codigos))
    

    # E-MAIL -----------------

    col3.write(row["E-mail"])

    # TELEFONE -----------------
    col4.write(row["Telefone"])


    # TIPO DE USUÁRIO -----------------
    tipo_usuario = str(row.get("Tipo de usuário", "") or "").strip()

    if tipo_usuario.lower() == "beneficiario":
        tipo_exibido = f"{tipo_usuario}"

    col5.write(tipo_exibido)

    # STATUS -----------------       
    col6.write(row["Data do convite"])

    # BOTÃO DE EDITAR -----------------
    col7.button(":material/edit:", key=row["_id"], on_click=editar_pessoa, args=(row["_id"],))
