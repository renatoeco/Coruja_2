import streamlit as st
from funcoes_auxiliares import conectar_mongo_cepf_gestao # Funções personalizadas
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
db = conectar_mongo_cepf_gestao()

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
        <p><a href="https://cepf-ieb.streamlit.app/">Acesse aqui a Plataforma</a></p>
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



projetos = df_projetos["codigo"].unique().tolist()

###########################################################################################################
# INTERFACE PRINCIPAL DA PÁGINA
###########################################################################################################


# Logo do sidebar
st.logo("images/ieb_logo.svg", size='large')

# Título da página
st.header("Convidar pessoa")


opcao_cadastro = st.radio("", ["Convite individual", "Convite em massa"], key="opcao_cadastro", horizontal=True)

st.write('')





# --------------------------
# FORMULÁRIO DE CADASTRO
# --------------------------
if opcao_cadastro == "Convite individual":

    # --- campos do formulário que vamos controlar ---
    CAMPOS_FORM_PESSOA = {
        "nome_completo_novo": "",
        "tipo_novo_usuario": "",
        "tipo_beneficiario": "",   # string; só usado quando beneficiário
        "e_mail": "",
        "telefone": "",
        "projetos_escolhidos": []  # multiselect espera lista
    }

    # --- limpeza no topo: se o flag estiver setado, reseta APENAS esses campos ---
    if st.session_state.get("limpar_form_pessoa", False):
        for k, default in CAMPOS_FORM_PESSOA.items():
            st.session_state[k] = default
        # remove o flag para não ficar em loop
        st.session_state.pop("limpar_form_pessoa", None)
        # re-renderiza com campos zerados (não necessário sempre, mas seguro)
        st.rerun()


    col1, col2 = st.columns(2)

    # --- Inputs com keys que coincidem com as chaves do session_state ---
    nome_completo_novo = col1.text_input("Nome completo", key="nome_completo_novo")

    # depende do tipo de usuário logado (ex.: tipo_usuario vem do login)
    if tipo_usuario == "equipe":
        tipo_novo_usuario = col2.selectbox(
            "Tipo de usuário", ["", "beneficiario", "visitante"], key="tipo_novo_usuario"
        )
    elif tipo_usuario == "admin":
        tipo_novo_usuario = col2.selectbox(
            "Tipo de usuário", ["", "admin", "equipe", "beneficiario", "visitante"], key="tipo_novo_usuario"
        )

    # mostra apenas se selecionado beneficiário
    if st.session_state.get("tipo_novo_usuario") == "beneficiario":
        tipo_beneficiario = col2.selectbox(
            "Tipo de beneficiário", ["", "técnico", "financeiro"], key="tipo_beneficiario"
        )
    else:
        # garante que o key exista (útil para limpeza/validação)
        if "tipo_beneficiario" not in st.session_state:
            st.session_state["tipo_beneficiario"] = ""

    col1, col2 = st.columns(2)

    e_mail = col1.text_input("E-mail", key="e_mail")
    e_mail = e_mail.strip()
    
    telefone = col2.text_input("Telefone", key="telefone")

    # Garante que a key exista com lista vazia caso ainda não exista
    if "projetos_escolhidos" not in st.session_state:
        st.session_state["projetos_escolhidos"] = []

    # Agora cria o multiselect sem passar default
    projetos_escolhidos = st.multiselect(
        "Projetos",
        projetos,
        key="projetos_escolhidos"
    )



    st.write("")
    submit_button = st.button("Salvar", icon=":material/save:", type="primary", width=150)



    if submit_button:
        # 1) Validações
        if not st.session_state["nome_completo_novo"] or not st.session_state["tipo_novo_usuario"] \
        or not st.session_state["e_mail"] or not st.session_state["telefone"]:
            st.error(":material/error: Todos os campos obrigatórios devem ser preenchidos.")
            st.stop()

        if st.session_state["tipo_novo_usuario"] == "beneficiario" and not st.session_state.get("tipo_beneficiario"):
            st.error(":material/error: O campo 'Tipo de beneficiário' é obrigatório para beneficiários.")
            st.stop()

        if not validar_email(st.session_state["e_mail"]):
            st.error(":material/error: E-mail inválido.")
            st.stop()

        if col_pessoas.find_one({"e_mail": st.session_state["e_mail"]}):
            st.error(f":material/error: O e-mail '{st.session_state['e_mail']}' já está cadastrado.")
            st.stop()

        # 2) Gera código de 6 dígitos
        codigo_6_digitos = gerar_codigo_aleatorio()

        # 3) Monta documento a inserir no MongoDB
        novo_doc = {
            "nome_completo": st.session_state["nome_completo_novo"],
            "tipo_usuario": st.session_state["tipo_novo_usuario"],
            "e_mail": st.session_state["e_mail"],
            "telefone": st.session_state["telefone"],
            "status": "convidado",
            "projetos": st.session_state.get("projetos_escolhidos", []),
            "data_convite": datetime.datetime.now().strftime("%d/%m/%Y"),
            "senha": None,
            "codigo_convite": codigo_6_digitos
        }

        if st.session_state["tipo_novo_usuario"] == "beneficiario":
            novo_doc["tipo_beneficiario"] = st.session_state.get("tipo_beneficiario")

        # 4) Inserir no banco
        col_pessoas.insert_one(novo_doc)

        with st.spinner("Cadastrando pessoa... aguarde..."):

            time.sleep(2)

            st.success(":material/check: Pessoa cadastrada com sucesso no banco de dados!")

            # 5) Envio do e-mail de convite
            enviado = enviar_email_convite(
                nome_completo=st.session_state["nome_completo_novo"],
                email_destino=st.session_state["e_mail"],
                codigo=codigo_6_digitos
            )



            # 6) Limpar campos do formulário e rerun
            st.session_state["limpar_form_pessoa"] = True
            time.sleep(6)
            st.rerun()







# ----------------------------
#   CONVITE EM MASSA
# ----------------------------



elif opcao_cadastro == "Convite em massa":

    # Inicializa o 'key' do file_uploader se ele não existir
    if 'uploader_key' not in st.session_state:
        st.session_state['uploader_key'] = str(uuid.uuid4())

    st.write('**Convite em massa disponível apenas para usuários(as) do tipo "beneficiário".**')

    st.write('')

    st.write("Baixe aqui o modelo de tabela para convite em massa:")

    with open("modelos/modelo_convite_pessoas_em_massa.xlsx", "rb") as f:
        st.download_button(
            label=":material/download: Baixar modelo XLSX",
            data=f,
            file_name="modelo_convite_pessoas_em_massa.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.divider()

    # ------------------------------
    # Upload
    # ------------------------------
    arquivo = st.file_uploader(
        "Envie um arquivo XLSX preenchido para convidar múltiplas pessoas:",
        type=["xlsx"],
        key=st.session_state['uploader_key'],
        width=400
    )

    st.write("")

    if arquivo is not None:
        try:
            df_upload = pd.read_excel(arquivo)

            st.write(":material/check: Arquivo carregado com sucesso!")

            # ==========================================================
            # Renomear colunas do modelo para padronizar
            # ==========================================================
            if "tipo_beneficiario (técnico ou financeiro)" in df_upload.columns:
                df_upload.rename(columns={"tipo_beneficiario (técnico ou financeiro)": "tipo_beneficiario"}, inplace=True)

            if "projetos (códigos separados por vírgula) (opcional)" in df_upload.columns:
                df_upload.rename(columns={"projetos (códigos separados por vírgula) (opcional)": "projetos"}, inplace=True)

            # ==========================================================
            # 0) Validar se o arquivo está vazio
            # ==========================================================
            if df_upload.empty or df_upload.dropna(how="all").empty:
                st.error(
                    ":material/error: O arquivo enviado está vazio!\n\n"
                    "Nenhum cadastro foi realizado. Corrija os dados e carregue novamente."
                )
                st.stop()

            # Exibir com index iniciado em 1
            st.dataframe(df_index1(df_upload))
            st.write("")

            # ==========================================================
            # 1) Validar colunas obrigatórias
            # ==========================================================
            colunas_obrigatorias = ["nome_completo", "e_mail", "tipo_beneficiario"]
            faltando = [c for c in colunas_obrigatorias if c not in df_upload.columns]
            if faltando:
                st.error(
                    f":material/error: Faltam colunas obrigatórias no arquivo: {faltando}\n\n"
                    "Nenhum cadastro foi realizado. Corrija os dados e carregue novamente."
                )
                st.stop()

            # Criar colunas opcionais se não existirem
            if "telefone (opcional)" not in df_upload.columns:
                df_upload["telefone (opcional)"] = ""
            if "projetos" not in df_upload.columns:
                df_upload["projetos"] = ""

            # ==========================================================
            # 2) Validar e-mails
            # ==========================================================
            df_upload["e_mail"] = df_upload["e_mail"].astype(str).str.strip()
            invalidos_email = df_upload[~df_upload["e_mail"].apply(validar_email)]
            if not invalidos_email.empty:
                st.error(
                    ":material/error: Existem e-mails inválidos!\n\n"
                    "Nenhum cadastro foi realizado. Corrija os dados e carregue novamente."
                )
                st.dataframe(df_index1(invalidos_email))
                st.stop()

            # ==========================================================
            # 3) Validar tipo_beneficiario
            # ==========================================================
            valores_validos_benef = ["técnico", "financeiro"]
            df_upload["tipo_beneficiario"] = df_upload["tipo_beneficiario"].astype(str).str.strip()

            invalidos_benef = df_upload[~df_upload["tipo_beneficiario"].isin(valores_validos_benef)]
            if not invalidos_benef.empty:
                st.error(
                    ":material/error: Existem registros com 'tipo_beneficiario' inválido!\n"
                    "Os valores válidos são: técnico ou financeiro.\n\n"
                    "Nenhum cadastro foi realizado. Corrija os dados e carregue novamente."
                )
                st.dataframe(df_index1(invalidos_benef))
                st.stop()

            erros_benef = df_upload[df_upload["tipo_beneficiario"] == ""]
            if not erros_benef.empty:
                st.error(
                    ":material/error: Todos os registros devem ter o campo 'tipo_beneficiario' preenchido.\n\n"
                    "Nenhum cadastro foi realizado. Corrija os dados e carregue novamente."
                )
                st.dataframe(df_index1(erros_benef))
                st.stop()

            # ==========================================================
            # 4) Verificar duplicidade interna no arquivo
            # ==========================================================
            dup_email = df_upload[df_upload.duplicated("e_mail", keep=False)]
            if not dup_email.empty:
                st.error(
                    ":material/error: Existem e-mails duplicados dentro do próprio arquivo.\n\n"
                    "Nenhum cadastro foi realizado. Corrija os dados e carregue novamente."
                )
                st.subheader("E-mails duplicados")
                st.dataframe(df_index1(dup_email))
                st.stop()



            # ==========================================================
            # 5) Verificar duplicidades no banco
            # ==========================================================
            existentes = pd.DataFrame(list(col_pessoas.find({}, {"e_mail": 1})))
            conflitos_email = []
            if not existentes.empty:
                for _, row in df_upload.iterrows():
                    if row["e_mail"] in existentes["e_mail"].values:
                        conflitos_email.append(row.to_dict())
            if conflitos_email:
                st.error(
                    ":material/error: Existem e-mails que já estão cadastrados no banco de dados!\n\n"
                    "Nenhum cadastro foi realizado. Corrija os dados e carregue novamente."
                )
                st.write("**E-mails já existentes:**")
                st.dataframe(df_index1(pd.DataFrame(conflitos_email)))
                st.stop()


            # ==========================================================
            # 6) Validar projetos no banco
            # ==========================================================

            # Códigos válidos vindos da tabela de projetos
            codigos_validos = df_projetos["codigo"].astype(str).str.strip().unique()

            # Converte cada célula da coluna "projetos" em lista
            df_upload["projetos"] = df_upload["projetos"].apply(
                lambda x:
                    [] if pd.isna(x) or str(x).strip() == "" or str(x).strip().lower() == "nan"
                    else [p.strip() for p in str(x).split(",") if p.strip()]
            )

            # Verifica se há algum código inválido
            invalidos_projetos = df_upload[df_upload["projetos"].apply(
                lambda lst: any(codigo not in codigos_validos for codigo in lst)
            )]

            if not invalidos_projetos.empty:
                st.error(
                    ":material/error: Existem projetos com códigos inválidos ou inexistentes no banco!\n\n"
                    "Nenhum cadastro foi realizado. Corrija os dados e carregue novamente."
                )
                st.dataframe(df_index1(invalidos_projetos))
                st.stop()












            # # ==========================================================
            # # 5) Verificar duplicidades no banco
            # # ==========================================================
            # existentes = pd.DataFrame(list(col_pessoas.find({}, {"e_mail": 1})))
            # conflitos_email = []
            # if not existentes.empty:
            #     for _, row in df_upload.iterrows():
            #         if row["e_mail"] in existentes["e_mail"].values:
            #             conflitos_email.append(row.to_dict())
            # if conflitos_email:
            #     st.error(
            #         ":material/error: Existem e-mails que já estão cadastrados no banco de dados!\n\n"
            #         "Nenhum cadastro foi realizado. Corrija os dados e carregue novamente."
            #     )
            #     st.write("**E-mails já existentes:**")
            #     st.dataframe(df_index1(pd.DataFrame(conflitos_email)))
            #     st.stop()


            #     # ==========================================================
            #     # 6) Validar projetos no banco
            #     # ==========================================================

            #     # Criar lista de códigos válidos a partir do banco
            #     codigos_validos = df_projetos["codigo"].astype(str).str.strip().unique()

            #     # Transformar a coluna projetos do upload em lista (aceitando vazio)
            #     df_upload["projetos"] = df_upload["projetos"].apply(
            #         lambda x:
            #             [] if pd.isna(x) or str(x).strip() == "" or str(x).strip().lower() == "nan"
            #             else [p.strip() for p in str(x).split(",") if p.strip()]
            #     )

            #     # Verificar códigos inválidos
            #     invalidos_projetos = df_upload[df_upload["projetos"].apply(
            #         lambda lst: any(codigo not in codigos_validos for codigo in lst)
            #     )]

            #     if not invalidos_projetos.empty:
            #         st.error(
            #             ":material/error: Existem projetos com códigos inválidos ou inexistentes no banco!\n\n"
            #             "Nenhum cadastro foi realizado. Corrija os dados e carregue novamente."
            #         )
            #         st.dataframe(df_index1(invalidos_projetos))
            #         st.stop()



            # ==========================================================
            # 7) Inserir no banco + Enviar e-mails de convite
            # ==========================================================
            if st.button(":material/save: Confirmar e convidar pessoas", type="primary"):

                registros = []
                for _, row in df_upload.iterrows():

                    # gera código único para cada pessoa
                    codigo_6_digitos_massa = gerar_codigo_aleatorio()

                    doc = {
                        "nome_completo": row["nome_completo"],
                        "tipo_usuario": "beneficiario",
                        "tipo_beneficiario": row["tipo_beneficiario"],
                        "e_mail": row["e_mail"],
                        "status": "convidado",
                        "codigo_convite": codigo_6_digitos_massa,
                        "data_convite": datetime.datetime.now().strftime("%d/%m/%Y"),
                        "senha": None
                    }

                    if pd.notna(row["telefone (opcional)"]) and str(row["telefone (opcional)"]).strip():
                        doc["telefone"] = str(row["telefone (opcional)"]).strip()

                    if row["projetos"]:
                        doc["projetos"] = row["projetos"]

                    registros.append(doc)

                # 1) Inserção em massa no banco
                resultado = col_pessoas.insert_many(registros)

                st.success(f":material/check: {len(resultado.inserted_ids)} pessoas cadastradas no banco de dados!")
                st.write('')

                # 2) Envio de e-mails com barra de progresso

                st.write('')

                progress_bar = st.progress(0)
                status_text = st.empty()

                total = len(registros)
                falhas = []  # <- LISTA PARA ARMAZENAR FALHAS



                status_line = st.empty()   # <-- Placeholder que será atualizado a cada iteração

                with st.spinner("Enviando e-mails... Aguarde..."):

                    for i, pessoa in enumerate(registros):

                        nome = pessoa["nome_completo"]
                        email = pessoa["e_mail"]
                        codigo = pessoa["codigo_convite"]

                        # Mostra mensagem atual (não acumula)
                        status_line.write(f"Enviando e-mail para **{email}**...")

                        try:
                            enviar_email_convite(
                                nome_completo=nome,
                                email_destino=email,
                                codigo=codigo
                            )

                        except Exception as e:
                            falhas.append((email, str(e)))
                            status_line.error(f":material/error: Falha ao enviar e-mail para {email}. Erro: {e}")

                        progress_bar.progress((i + 1) / total)

                        time.sleep(2)

                # Após terminar, limpar o placeholder
                status_line.empty()






                # --- Relatório final ---

                sucessos = total - len(falhas)

                if len(falhas) == 0:
                    st.success(f":material/check: Todos os {sucessos} convites foram enviados com sucesso!")
                else:
                    st.success(f":material/check: {sucessos} convites foram enviados com sucesso.")
                    st.warning(f":material/warning: Porém, {len(falhas)} e-mails não puderam ser enviados.")
                    
                    st.write("### E-mails com falha:")
                    for email, motivo in falhas:
                        st.write(f"- **{email}** — erro: {motivo}")

                # Resetar uploader
                st.session_state['uploader_key'] = str(uuid.uuid4())
                time.sleep(3)
                st.rerun()



        except Exception as e:
            st.error(
                ":material/error: Erro ao processar o arquivo.\n\n"
                "Nenhum cadastro foi realizado. Corrija os dados e carregue novamente."
            )
            st.exception(e)








