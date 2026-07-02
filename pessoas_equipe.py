import streamlit as st
from funcoes_auxiliares import conectar_mongo_coruja  # Função personalizada para conectar ao MongoDB
import pandas as pd
from bson import ObjectId
import time



st.set_page_config(page_title="Equipe", page_icon=":material/badge:")




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
if "_id" in df_pessoas.columns:
    df_pessoas["_id"] = df_pessoas["_id"].astype(str)
else:
    st.warning("Pessoas sem campo '_id'.")
    df_pessoas["_id"] = ""

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
if "Nome" in df_pessoas.columns:
    df_pessoas = df_pessoas.sort_values(by="Nome")

# Projetos
col_projetos = db["projetos"]
df_projetos = pd.DataFrame(list(col_projetos.find()))

# Mapeamentos para conversão entre id e código
mapa_id_para_codigo = dict(zip(df_projetos["_id"], df_projetos["codigo"]))
mapa_codigo_para_id = dict(zip(df_projetos["codigo"], df_projetos["_id"]))

# Permite identificar quando o valor antigo já era o código do projeto
codigos_validos = set(df_projetos["codigo"].astype(str))

# Converte ObjectId para string (somente se existir)
if "_id" in df_projetos.columns:
    df_projetos["_id"] = df_projetos["_id"].astype(str)
else:
    st.warning("Projetos sem campo '_id'.")





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

    # ===============================
    # Campos básicos
    # ===============================
    nome = st.text_input("Nome", value=pessoa.get("nome_completo", ""))
    email = st.text_input("E-mail", value=pessoa.get("e_mail", ""))
    telefone = st.text_input("Telefone", value=pessoa.get("telefone", ""))

    # ===============================
    # Tipo de usuário
    # ===============================
    tipos_usuario_validos = ["admin", "equipe", "beneficiario", "visitante"]

    tipo_usuario_raw = pessoa.get("tipo_usuario", "")
    tipo_usuario_default = (
        tipo_usuario_raw.strip()
        if isinstance(tipo_usuario_raw, str) and tipo_usuario_raw in tipos_usuario_validos
        else tipos_usuario_validos[0]
    )

    tipo_usuario = st.selectbox(
        "Tipo de usuário",
        options=tipos_usuario_validos,
        index=tipos_usuario_validos.index(tipo_usuario_default),
    )

    # ===============================
    # Tipo de beneficiário (condicional)
    # ===============================
    tipo_beneficiario = None
    tipos_beneficiario_validos = ["técnico", "financeiro"]

    if tipo_usuario == "beneficiario":
        tipo_beneficiario_raw = pessoa.get("tipo_beneficiario", tipos_beneficiario_validos[0])
        tipo_beneficiario_default = (
            tipo_beneficiario_raw
            if tipo_beneficiario_raw in tipos_beneficiario_validos
            else tipos_beneficiario_validos[0]
        )

        tipo_beneficiario = st.selectbox(
            "Tipo de beneficiário",
            options=tipos_beneficiario_validos,
            index=tipos_beneficiario_validos.index(tipo_beneficiario_default),
        )

    # ===============================
    # Status
    # ===============================
    status_validos = ["ativo", "inativo"]
    status_raw = pessoa.get("status", "ativo")
    status_default = status_raw if status_raw in status_validos else "ativo"

    status = st.selectbox(
        "Status",
        options=status_validos,
        index=status_validos.index(status_default),
    )

    # ===============================
    # Projetos
    # ===============================
    # Opções existentes no banco
    if "codigo" in df_projetos.columns:
        opcoes_projetos = (
            df_projetos["codigo"]
            .dropna()
            .astype(str)
            .sort_values()
            .tolist()
        )
    else:
        opcoes_projetos = []
        st.warning("Projetos sem coluna 'codigo'.")

    # Projetos salvos na pessoa (agora são IDs)
    projetos_pessoa = pessoa.get("projetos", [])
    if not isinstance(projetos_pessoa, list):
        projetos_pessoa = []

    # Converte IDs em códigos para exibição
    projetos_default_validos = []

    for projeto in projetos_pessoa:

        # Formato novo: ID
        if projeto in mapa_id_para_codigo:
            projetos_default_validos.append(mapa_id_para_codigo[projeto])

        # Formato antigo: já era o código do projeto
        elif projeto in codigos_validos:
            projetos_default_validos.append(projeto)

    # Detecta IDs inexistentes
    # projetos_invalidos = [
    #     p for p in projetos_pessoa
    #     if p not in mapa_id_para_codigo
    # ]

    # if projetos_invalidos:
    #     st.warning(
    #         "Alguns projetos associados não existem mais e serão removidos."
    #     )

    # Usuário continua vendo apenas os códigos
    projetos = st.multiselect(
        "Projetos",
        options=opcoes_projetos,
        default=projetos_default_validos,
    )

    st.divider()

    # ===============================
    # Salvar alterações
    # ===============================
    if st.button("Salvar alterações", icon=":material/save:"):
        
        # Converte os códigos selecionados para IDs
        projetos_ids = [
            mapa_codigo_para_id[codigo]
            for codigo in projetos
            if codigo in mapa_codigo_para_id
        ]
        
        update_data = {
            "nome_completo": nome,
            "e_mail": email,
            "telefone": telefone,
            "tipo_usuario": tipo_usuario,
            "status": status,
            "projetos": projetos_ids,
        }

        # Tipo beneficiário (somente se for beneficiário)
        if tipo_usuario == "beneficiario" and tipo_beneficiario:
            update_data["tipo_beneficiario"] = tipo_beneficiario
        else:
            # Remove se existir no banco
            col_pessoas.update_one(
                {"_id": ObjectId(_id)},
                {"$unset": {"tipo_beneficiario": ""}},
            )

        # Atualiza documento
        col_pessoas.update_one(
            {"_id": ObjectId(_id)},
            {"$set": update_data},
        )

        st.success("Pessoa atualizada com sucesso!")
        time.sleep(2)
        st.rerun()











###########################################################################################################
# INTERFACE
###########################################################################################################


# Logo do sidebar
st.logo("images/logo_fundo_ecos.png", size='large')

st.header('Equipe')

# st.write('')
#st.divider()

aba_ativos, aba_inativos = st.tabs([":material/person: Ativos", ":material/block: Inativos"])

with aba_ativos:

    # Filtra apenas usuários da equipe e administradores
    # com status igual a "ativo"
    df_equipe = df_pessoas[
        (
            df_pessoas["Tipo de usuário"].isin(["admin", "equipe"])
        )
        &
        (
            df_pessoas["Status"] == "ativo"
        )
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
    for _, row in df_equipe.iterrows():
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
            
        # Converte IDs em códigos
        projetos_convertidos = []

        for projeto in projetos:

            # Formato novo (ID)
            if projeto in mapa_id_para_codigo:
                projetos_convertidos.append(mapa_id_para_codigo[projeto])

            # Formato antigo (código)
            else:
                projetos_convertidos.append(projeto)

        projetos = projetos_convertidos    
        
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
        tipo_usuario = row.get("Tipo de usuário", "").strip()

        col5.write(tipo_usuario)

        # STATUS -----------------       
        col6.write(row["Status"])

        # BOTÃO DE EDITAR -----------------
        col7.button(":material/edit:", key=row["_id"], on_click=editar_pessoa, args=(row["_id"],))
        

with aba_inativos:

    st.write('')

    st.markdown(
        "<span style='color:red;'>Usuários inativos estão impedidos de acessar o sistema.</span>",
        unsafe_allow_html=True
    )

    st.write('')

    # Filtra apenas usuários da equipe e administradores
    # com status igual a "inativo"
    df_equipe_inativos = df_pessoas[
        (
            df_pessoas["Tipo de usuário"].isin(["admin", "equipe"])
        )
        &
        (
            df_pessoas["Status"] == "inativo"
        )
    ]

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
    for _, row in df_equipe_inativos.iterrows():
        col1, col2, col3, col4, col5, col6, col7 = st.columns(dist_colunas)
        
        # NOME -----------------
        col1.write(row["Nome"])
        
        # PROJETOS -----------------
        
        # Tratando a coluna projetos, que pode ter múltiplos valores
        projetos = row.get("Projetos", [])

        # Garante que 'projetos' seja uma lista
        if isinstance(projetos, str):
            projetos = [projetos]
        elif not isinstance(projetos, list):
            projetos = []
            
        # Converte IDs em códigos
        projetos_convertidos = []

        for projeto in projetos:

            # Formato novo (ID)
            if projeto in mapa_id_para_codigo:
                projetos_convertidos.append(mapa_id_para_codigo[projeto])

            # Formato antigo (código)
            else:
                projetos_convertidos.append(projeto)

        projetos = projetos_convertidos

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
        tipo_usuario = row.get("Tipo de usuário", "").strip()
        col5.write(tipo_usuario)
        
        # STATUS -----------------
        col6.write(row["Status"])
        
        # BOTÃO DE EDITAR -----------------
        col7.button(
            ":material/edit:",
            key=f'inativo_{row["_id"]}',
            on_click=editar_pessoa,
            args=(row["_id"],)
        )
