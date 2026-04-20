import streamlit as st
from funcoes_auxiliares import conectar_mongo_coruja, obter_servico_drive, obter_pasta_projeto, add_permissao_drive

import pandas as pd
import locale
import re
import time
import uuid
import datetime
import smtplib
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


st.set_page_config(page_title="Convidar", page_icon=":material/person_add:")




###########################################################################################################
# CONEXÃO COM O BANCO DE DADOS MONGODB
###########################################################################################################

# Conecta-se ao banco de dados MongoDB (usa cache automático para melhorar performance)
db = conectar_mongo_coruja()

# Importa coleções e cria dataframes
col_pessoas = db["pessoas"]
df_pessoas = pd.DataFrame(list(col_pessoas.find()))

col_projetos = db["projetos"]
df_projetos = pd.DataFrame(list(col_projetos.find()))




###########################################################################################################
# FUNÇÕES
###########################################################################################################

def gerar_codigo_aleatorio():
    """Gera um código numérico aleatório de 6 dígitos como string."""
    return f"{random.randint(0, 999999):06d}"


def enviar_email_convite(nome_completo, email_destino, codigo):
    """
    Envia um e-mail de convite com código de 6 dígitos usando credenciais do st.secrets.
    Retorna True se enviado, False se falhou.
    """
    try:
        smtp_server = st.secrets["senhas"]["smtp_server"]
        port = st.secrets["senhas"]["port"]
        endereco_email = st.secrets["senhas"]["endereco_email"]
        senha_email = st.secrets["senhas"]["senha_email"]

        msg = MIMEMultipart()
        msg['From'] = endereco_email
        msg['To'] = email_destino
        msg['Subject'] = "Convite para a Plataforma CEPF"

        corpo_html = f"""
        <p>Olá {nome_completo},</p>
        <p>Você foi convidado para utilizar a <strong>Plataforma de Gestão de Projetos do CEPF</strong>.</p>
        <p>Para realizar seu cadastro, acesse o link abaixo e clique no botão <strong>"Primeiro acesso"</strong>:</p>
        <p><a href="https://coruja-2-dev.streamlit.app/">Acesse aqui a Plataforma</a></p>
        <p>Insira o seu <strong>e-mail</strong> e o <strong>código</strong> que te enviamos abaixo:</p>
        <h2>{codigo}</h2>
        <p>Se tiver alguma dúvida, entre em contato com a equipe do CEPF.</p>
        """
        msg.attach(MIMEText(corpo_html, 'html'))

        server = smtplib.SMTP(smtp_server, port)
        server.starttls()
        server.login(endereco_email, senha_email)
        server.send_message(msg)
        server.quit()

        # st.success(f":material/mail: E-mail de convite enviado para {email_destino}.")
        return True
    except Exception as e:
        st.error(f"Erro ao enviar e-mail para {email_destino}: {e}")
        return False





def df_index1(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2.index = range(1, len(df2) + 1)
    return df2


# Regex para validar e-mail
EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
def validar_email(email):
    if not email:
        return False
    return bool(re.match(EMAIL_REGEX, str(email).strip()))






###########################################################################################################
# TRATAMENTO DE DADOS   
###########################################################################################################

tipo_usuario = st.session_state.get("tipo_usuario", "")


# ---------------------------------------------------------------------------------------------------------
# Garante que a lista de projetos seja sempre válida, mesmo quando não houver dados no banco
# ---------------------------------------------------------------------------------------------------------

if df_projetos.empty or "codigo" not in df_projetos.columns:
    # Caso não existam projetos cadastrados ou a coluna não exista,
    # define uma lista vazia para evitar erro no Streamlit
    projetos = []
else:
    # Caso existam dados válidos, extrai os códigos únicos normalmente
    projetos = df_projetos["codigo"].dropna().astype(str).unique().tolist()

# projetos = df_projetos["codigo"].unique().tolist()

###########################################################################################################
# INTERFACE PRINCIPAL DA PÁGINA
###########################################################################################################


# Logo do sidebar
st.logo("images/logo_fundo_ecos.png", size='large')

# Título da página
st.header("Convidar pessoa")


# ---------------------------------------------------------------------------------------------
# CONVITE DE PESSOAS (ÚNICO FLUXO COM DATA_EDITOR)
# ---------------------------------------------------------------------------------------------

st.write("")
st.write("Preencha os dados abaixo para convidar uma ou mais pessoas:")

# ---------------------------------------------------------------------------------------------
# DATAFRAME BASE
# ---------------------------------------------------------------------------------------------
df_base = pd.DataFrame({
    "nome_completo": [""],
    "tipo_usuario": [""],
    "e_mail": [""],
    "telefone": [""],
    "projetos": [[]],
})

# ---------------------------------------------------------------------------------------------
# LISTAS AUXILIARES
# ---------------------------------------------------------------------------------------------

# TODOS os tipos disponíveis
tipos_usuario = ["", "admin", "equipe", "beneficiario", "visitante"]

# ---------------------------------------------------------------------------------------------
# DATA EDITOR
# ---------------------------------------------------------------------------------------------
df_editado = st.data_editor(
    df_base,
    num_rows="dynamic",
    width="stretch",
    column_config={
        "nome_completo": st.column_config.TextColumn("Nome completo", width=250),

        "tipo_usuario": st.column_config.SelectboxColumn(
            "Tipo de usuário",
            options=["", "admin", "equipe", "beneficiario", "visitante"],
            width=150
        ),

        "e_mail": st.column_config.TextColumn("E-mail", width=200),

        "telefone": st.column_config.TextColumn("Telefone", width=150),

        "projetos": st.column_config.MultiselectColumn(
            "Projetos",
            options=projetos,  # lista vinda do banco
            width="large",
        ),
    }
)

st.write("")

# ---------------------------------------------------------------------------------------------
# BOTÃO DE SALVAR
# ---------------------------------------------------------------------------------------------
if st.button(":material/save: Convidar pessoas", type="primary"):

    with st.spinner("Enviando e-mails... Aguarde..."):


        df = df_editado.copy()

        # -----------------------------------------------------------------------------------------
        # LIMPEZA DE LINHAS VAZIAS
        # -----------------------------------------------------------------------------------------
        df = df.dropna(how="all")

        df = df[
            df.apply(
                lambda row: any(
                    str(v).strip() not in ["", "[]", "nan", "None"]
                    for v in row
                ),
                axis=1
            )
        ]

        if df.empty:
            st.error("Nenhum dado válido para cadastro.")
            st.stop()

        # -----------------------------------------------------------------------------------------
        # VALIDAÇÕES
        # -----------------------------------------------------------------------------------------
        registros_validos = []
        erros = []

        # Emails existentes
        existentes = pd.DataFrame(list(col_pessoas.find({}, {"e_mail": 1})))
        emails_existentes = existentes["e_mail"].tolist() if not existentes.empty else []

        # Projetos válidos
        codigos_validos = df_projetos["codigo"].astype(str).str.strip().unique() if not df_projetos.empty else []

        for idx, row in df.iterrows():

            linha_num = idx + 1

            nome = str(row["nome_completo"]).strip()
            tipo = str(row["tipo_usuario"]).strip()
            email = str(row["e_mail"]).strip()
            telefone = str(row["telefone"]).strip()
            projetos_lista = row["projetos"]

            # garantir que é lista
            if not isinstance(projetos_lista, list):
                projetos_lista = []

            identificador = f"Linha {linha_num} ({nome if nome else email})"

            # -----------------------------
            # CAMPOS OBRIGATÓRIOS
            # -----------------------------
            if not nome or not tipo or not email:
                erros.append(f"{identificador}: Campos obrigatórios não preenchidos.")
                continue

            # -----------------------------
            # EMAIL
            # -----------------------------
            if not validar_email(email):
                erros.append(f"{identificador}: E-mail inválido.")
                continue

            if email in emails_existentes:
                erros.append(f"{identificador}: E-mail já cadastrado.")
                continue

            # -----------------------------
            # PROJETOS
            # -----------------------------
            projetos_lista = row["projetos"]

            # garantir que é lista
            if not isinstance(projetos_lista, list):
                projetos_lista = []

            # validar projetos
            invalidos = [p for p in projetos_lista if p not in codigos_validos]

            if invalidos:
                erros.append(f"{identificador}: Projetos inválidos {invalidos}.")
                continue

            # -----------------------------
            # GERAR CÓDIGO
            # -----------------------------
            codigo = gerar_codigo_aleatorio()

            # -----------------------------
            # DOCUMENTO FINAL
            # -----------------------------
            doc = {
                "nome_completo": nome,
                "tipo_usuario": tipo,
                "e_mail": email,
                "status": "convidado",
                "codigo_convite": codigo,
                "data_convite": datetime.datetime.now().strftime("%d/%m/%Y"),
                "senha": None
            }

            if telefone:
                doc["telefone"] = telefone

            if projetos_lista:
                doc["projetos"] = projetos_lista

            registros_validos.append(doc)

        # -----------------------------------------------------------------------------------------
        # EXIBIÇÃO DE ERROS
        # -----------------------------------------------------------------------------------------
        if erros:
            st.error("Alguns dados precisam ser corrigidos:")
            for e in erros:
                st.write(f"- {e}")
            st.stop()

        # -----------------------------------------------------------------------------------------
        # INSERÇÃO
        # -----------------------------------------------------------------------------------------
        if registros_validos:

            resultado = col_pessoas.insert_many(registros_validos)

            st.success(f"{len(resultado.inserted_ids)} pessoas cadastradas com sucesso!")

            # -------------------------------------------------------------------------------------
            # ENVIO DE E-MAILS
            # -------------------------------------------------------------------------------------
            progress_bar = st.progress(0)
            status = st.empty()

            total = len(registros_validos)

            # Inicializa serviço do Drive uma única vez
            servico_drive = obter_servico_drive()


            for i, pessoa in enumerate(registros_validos):

                status.write(f"Enviando e-mail para {pessoa['e_mail']}...")

                # Envio de e-mail
                enviar_email_convite(
                    nome_completo=pessoa["nome_completo"],
                    email_destino=pessoa["e_mail"],
                    codigo=pessoa["codigo_convite"]
                )

                # ==========================================================
                # Concede permissões no Google Drive para os projetos da pessoa
                # ==========================================================

                email = pessoa.get("e_mail")

                if email:

                    for codigo_projeto in pessoa.get("projetos", []):

                        try:
                            # Busca o projeto para obter a sigla
                            projeto = col_projetos.find_one({"codigo": codigo_projeto})

                            if not projeto:
                                continue

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

                progress_bar.progress((i + 1) / total)

                time.sleep(3)


            status.empty()

            st.success("Convites enviados com sucesso!")

            time.sleep(3)
            st.rerun()

