import streamlit as st
from funcoes_auxiliares import conectar_mongo_coruja, obter_servico_drive, obter_pasta_projeto, add_permissao_drive

import pandas as pd
from bson import ObjectId
import time
from io import BytesIO



st.set_page_config(page_title="Beneficiários", page_icon=":material/group:")



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
# Converte objectId para string
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

    # Status
    status = st.selectbox(
        "Status",
        options=["ativo", "inativo"],
        index=0 if pessoa.get("status", "ativo") == "ativo" else 1
    )
    
    if "codigo" in df_projetos.columns:
        opcoes_projetos = df_projetos["codigo"].dropna().astype(str).tolist()
    else:
        opcoes_projetos = []
        st.warning("Projetos sem coluna 'codigo'.")

    # Projetos
    projetos = st.multiselect(
        "Projetos",
        options=opcoes_projetos,
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

        # Atualiza o registro
        col_pessoas.update_one({"_id": ObjectId(_id)}, {"$set": update_data})



        # ==========================================================
        # Concede permissões de leitura no Google Drive para os projetos vinculados
        # ==========================================================


        # Só executa se houver e-mail válido
        if email:

            # Inicializa serviço do Drive sob demanda
            servico_drive = obter_servico_drive()

            # Percorre todos os projetos do banco
            for projeto in col_projetos.find():

                codigo_projeto = projeto.get("codigo")

                # Só aplica para projetos selecionados
                if codigo_projeto not in projetos:
                    continue

                try:
                    # Recupera sigla diretamente do documento
                    sigla = projeto.get("sigla", "")

                    # Obtém (ou cria) a pasta do projeto
                    pasta_id = obter_pasta_projeto(
                        servico_drive,
                        codigo_projeto,
                        sigla
                    )

                    # Estrutura mínima esperada pela função
                    contato_drive = {
                        "email": email
                    }

                    # Aplica permissão de leitura
                    add_permissao_drive(servico_drive, pasta_id, contato_drive)

                except Exception:
                    # Falhas individuais não interrompem o fluxo
                    continue


        # ==========================================================
        # Atualiza contatos nos projetos selecionados
        # ==========================================================

        # percorre todos os projetos do banco
        for projeto in col_projetos.find():

            codigo_projeto = projeto.get("codigo")

            # só continua se o projeto estiver selecionado no multiselect
            if codigo_projeto not in projetos:
                continue

            contatos = projeto.get("contatos", [])

            # verifica se já existe contato com o mesmo e-mail
            ja_existe = any(
                c.get("email", "").lower() == email.lower()
                for c in contatos
            )

            if not ja_existe:

                novo_contato = {
                    "nome": nome,
                    "funcao": "Usuário(a) do sistema",
                    "telefone": telefone,
                    "email": email,
                    "assina_docs": False
                }

                # adiciona o contato ao projeto
                col_projetos.update_one(
                    {"_id": projeto["_id"]},
                    {"$push": {"contatos": novo_contato}}
                )



        st.success("Pessoa atualizada com sucesso!")
        time.sleep(2)
        st.rerun()





###########################################################################################################
# INTERFACE
###########################################################################################################


# Logo do sidebar
st.logo("images/logo_fundo_ecos.png", size='large')

st.header('Beneficiários(as)')

# Separando só os beneficiários
if "Tipo de usuário" in df_pessoas.columns:
    df_benef = df_pessoas[
        df_pessoas["Tipo de usuário"] == "beneficiario"
    ]
else:
    df_benef = pd.DataFrame()
    st.warning("Coluna 'Tipo de usuário' não encontrada.")


###########################################################################################################
# EXPORTAÇÃO DE PESSOAS
###########################################################################################################

# st.write('')

# # Inicializa variáveis de estado caso ainda não existam
# if "xlsx_pessoas" not in st.session_state:
#     st.session_state.xlsx_pessoas = None

# if "tabela_gerada" not in st.session_state:
#     st.session_state.tabela_gerada = False

# with st.container(horizontal=True, horizontal_alignment="right"):

#     # Popover para download da tabela
#     with st.popover("Baixar tabela", width=200):

#         # Fragment para isolar a renderização dos botões
#         @st.fragment
#         def fragment_exportacao():

#             # BOTÃO PARA GERAR A TABELA ------------------------------------------------
#             if st.button("Gerar tabela", icon=":material/settings:", width="stretch"):

#                 # Filtra apenas usuários do tipo beneficiario
#                 df_export = df_pessoas[
#                     df_pessoas["Tipo de usuário"] == "beneficiario"
#                 ].copy()

#                 # Mantém apenas as colunas necessárias
#                 colunas_export = [
#                     col for col in [
#                         "Nome",
#                         "E-mail",
#                         "Telefone",
#                         "Status",
#                         "Projetos"
#                     ] if col in df_export.columns
#                 ]

#                 df_export = df_export[colunas_export]

#                 # Renomeia coluna Nome para Nome completo
#                 df_export = df_export.rename(columns={
#                     "Nome": "Nome completo"
#                 })

#                 # Converte lista de projetos em string separada por vírgula
#                 def tratar_projetos(valor):
#                     if isinstance(valor, list):
#                         return ", ".join(valor)
#                     if isinstance(valor, str):
#                         return valor
#                     return ""

#                 df_export["Projetos"] = df_export["Projetos"].apply(tratar_projetos)

#                 # Cria arquivo XLSX em memória
#                 buffer = BytesIO()

#                 # Salva dataframe no Excel
#                 with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
#                     df_export.to_excel(writer, index=False, sheet_name="Pessoas")

#                 # Move o cursor do buffer para o início
#                 buffer.seek(0)

#                 # Armazena o arquivo em memória
#                 st.session_state.xlsx_pessoas = buffer

#                 # Marca que a tabela foi gerada
#                 st.session_state.tabela_gerada = True



#             # BOTÃO DE DOWNLOAD -------------------------------------------------------
#             if st.session_state.tabela_gerada:

#                 st.caption("Tabela gerada! Clique para baixar.")

#                 st.download_button(
#                     label="Baixar tabela",
#                     data=st.session_state.xlsx_pessoas,
#                     file_name="beneficiarios.xlsx",
#                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#                     icon=":material/download:",
#                     type="primary",
#                     width="stretch"
#                 )

#         # Executa o fragment
#         fragment_exportacao()


st.divider()

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
for _, row in df_benef.iterrows():
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
    tipo_usuario = row.get("Tipo de usuário", "").strip()

    tipo_exibido = tipo_usuario

    col5.write(tipo_exibido)

    # STATUS -----------------       
    col6.write(row["Status"])

    # BOTÃO DE EDITAR -----------------
    col7.button(":material/edit:", key=row["_id"], on_click=editar_pessoa, args=(row["_id"],))
