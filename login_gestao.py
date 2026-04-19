import streamlit as st  
# from pymongo import MongoClient  
import time 
import random  
import smtplib  
from email.mime.text import MIMEText  
from funcoes_auxiliares import conectar_mongo_coruja  # Função personalizada para conectar ao MongoDB
import bcrypt
import textwrap


# Configurar o streamlit para tela wide
st.set_page_config(layout="wide", page_title="Coruja - Fundo Ecos", page_icon=":material/owl:")


##############################################################################################################
# CONEXÃO COM O BANCO DE DADOS (MONGODB)
###############################################################################################################


# Conecta ao banco de dados MongoDB usando função importada (com cache para otimizar desempenho)
db = conectar_mongo_coruja()

# Define a coleção a ser utilizada
col_pessoas = db["pessoas"]





##############################################################################################################
# FUNÇÕES AUXILIARES
##############################################################################################################

def validar_senha(senha: str) -> bool:
    """Valida se a senha tem pelo menos 8 caracteres, contém letras e números."""
    if len(senha) < 8:
        return False
    has_letter = any(c.isalpha() for c in senha)
    has_digit = any(c.isdigit() for c in senha)
    return has_letter and has_digit



def encontrar_usuario_por_email(pessoas, email_busca):
    usuario = pessoas.find_one({"e_mail": email_busca})
    if usuario:
        return usuario.get("nome_completo"), usuario  # Retorna o nome e os dados do usuário
    return None, None  # Caso não encontre


# Função para enviar um e_mail com código de verificação
def enviar_email(destinatario, codigo):
    # Dados de autenticação, retirados do arquivo secrets.toml
    remetente = st.secrets["senhas"]["endereco_email"]
    senha = st.secrets["senhas"]["senha_email"]

    # Conteúdo do e_mail
    assunto = f"Código de Verificação - Coruja 2: {codigo}"
    corpo = f"""
    <html>
        <body>
            <p style='font-size: 1.5em;'>
                Seu código para redefinição é: <strong>{codigo}</strong>
            </p>
        </body>
    </html>
    """

    # Cria o e_mail formatado com HTML
    msg = MIMEText(corpo, "html", "utf-8")
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario

    # Tenta enviar o e_mail via SMTP seguro (SSL)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(remetente, senha)
            server.sendmail(remetente, destinatario, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Erro ao enviar e-mail: {e}")
        return False


##############################################################################################################
# CAIXA DE DIÁLOGO PARA PRIMEIRO ACESSO
##############################################################################################################

@st.dialog("Primeiro Acesso")
def primeiro_acesso_dialog():
    # Containers para esconder elementos
    container_email_codigo = st.empty()
    container_nova_senha = st.empty()

    # Variáveis de sessão
    st.session_state.setdefault("usuario_validado", False)
    st.session_state.setdefault("usuario_id", None)

    # --- FORMULÁRIO 1: Email + Código ---
    if not st.session_state.usuario_validado:
        with container_email_codigo.form("form_email_codigo", clear_on_submit=False):
            email_input = st.text_input("Digite seu e-mail")
            codigo_input = st.text_input("Digite o código que você recebeu por e-mail")
            enviar_codigo = st.form_submit_button("Confirmar")

            if enviar_codigo:
                usuario = col_pessoas.find_one({"e_mail": email_input})
                if not usuario:
                    st.error("Usuário não encontrado. Entre em contato com o administrador.")
                elif usuario.get("codigo_convite") != codigo_input:
                    st.error("Código inválido. Verifique o e-mail enviado.")
                else:
                    st.success(f"Código validado! Aguarde...")
                    time.sleep(3)
                    # Guarda info na sessão
                    st.session_state.usuario_validado = True
                    st.session_state.usuario_id = usuario["_id"]
                    # Esconde formulário 1
                    container_email_codigo.empty()


    # --- FORMULÁRIO 2: Nova Senha ---
    if st.session_state.usuario_validado:
        with container_nova_senha.form("form_nova_senha", clear_on_submit=False):
            
            st.write('**Crie uma nova senha** com pelo menos 8 caracteres, contendo letras e números.')
            # st.write('Mínimo de 8 caracteres com letras e números.')
            
            nova_senha = st.text_input("Nova senha", type="password")
            confirmar_senha = st.text_input("Confirme a senha", type="password")
            salvar_senha = st.form_submit_button("Salvar")

            if salvar_senha:
                if nova_senha != confirmar_senha:
                    st.error("As senhas não coincidem.")
                elif not validar_senha(nova_senha):
                    st.error("Senha deve ter pelo menos 8 caracteres e conter letras e números.")
                else:
                    # Hash da senha
                    hash_senha = bcrypt.hashpw(nova_senha.encode("utf-8"), bcrypt.gensalt())

                    # Atualiza banco
                    col_pessoas.update_one(
                        {"_id": st.session_state.usuario_id},
                        {"$set": {"senha": hash_senha, "status": "ativo"},
                        "$unset": {"codigo_convite": ""}}
                    )

                    # Limpa sessão
                    for key in ["usuario_validado", "usuario_id"]:
                        st.session_state.pop(key, None)

                    # Mensagem final
                    sucesso = st.success(
                        "Senha cadastrada com sucesso.\n\nFaça o login normalmente."
                    )

                    time.sleep(3)
                    sucesso.empty()
                    st.rerun()




@st.dialog("Recuperação de Senha")
def recuperar_senha_dialog():

    st.session_state.setdefault("codigo_enviado", False)
    st.session_state.setdefault("codigo_verificacao", "")
    st.session_state.setdefault("email_verificado", "")
    st.session_state.setdefault("codigo_validado", False)

    conteudo_dialogo = st.empty()

    # Etapa 1: entrada do e-mail
    if not st.session_state.codigo_enviado:
        with conteudo_dialogo.form(key="recover_password_form", border=False):
            email_default = st.session_state.get("email_para_recuperar", "")
            email = st.text_input("Digite seu e-mail:", value=email_default)

            if st.form_submit_button("Enviar código de verificação", icon=":material/mail:"):
                if email:
                    nome, verificar_colaboradores = encontrar_usuario_por_email(col_pessoas, email)

                    if verificar_colaboradores:

                        if verificar_colaboradores.get("status", "").lower() != "ativo":
                            st.error("Usuário inativo. Entre em contato com o administrador do sistema.")
                            return
                        
                        codigo = str(random.randint(100, 999))

                        with st.spinner(f"Enviando código para {email}..."):
                            if enviar_email(email, codigo):
                                st.session_state.codigo_verificacao = codigo
                                st.session_state.codigo_enviado = True
                                st.session_state.email_verificado = email
                                st.success(f"Código enviado para {email}.")
                            else:
                                st.error("Erro ao enviar o e-mail. Tente novamente.")
                    else:
                        st.error("E-mail não encontrado. Tente novamente.")
                else:
                    st.error("Por favor, insira um e-mail.")

    # Etapa 2: verificação do código
    if st.session_state.codigo_enviado and not st.session_state.codigo_validado:
        with conteudo_dialogo.form(key="codigo_verificacao_form", border=False):
            st.subheader("Código de verificação")
            email_mask = st.session_state.email_verificado.replace("@", "​@")
            st.write(f"Um código foi enviado para: **{email_mask}**")

            codigo_input = st.text_input("Informe o código recebido por e-mail", placeholder="000")

            if st.form_submit_button("Verificar"):
                if codigo_input == st.session_state.codigo_verificacao:
                    sucesso = st.success("Código verificado com sucesso!")
                    time.sleep(2)
                    sucesso.empty()
                    st.session_state.codigo_validado = True
                else:
                    st.error("Código inválido. Tente novamente.")

    # Etapa 3: redefinição da senha
    if st.session_state.codigo_validado:
        with conteudo_dialogo.form("nova_senha_form", border=True):
            
            st.markdown("### Defina sua nova senha")
            nova_senha = st.text_input("Nova senha", type="password")
            confirmar_senha = st.text_input("Confirme a senha", type="password")
            enviar_nova_senha = st.form_submit_button("Salvar")

            if enviar_nova_senha:
                if nova_senha == confirmar_senha and nova_senha.strip():

                    email = st.session_state.email_verificado
                    usuario = col_pessoas.find_one({"e_mail": email})

                    if usuario:
                        try:
                            # geração de hash seguro da senha
                            hash_senha = bcrypt.hashpw(nova_senha.encode("utf-8"), bcrypt.gensalt())

                            # atualização no banco
                            result = col_pessoas.update_one(
                                {"e_mail": email},
                                {"$set": {"senha": hash_senha}}
                            )

                            if result.matched_count > 0:
                                st.success("Senha redefinida com sucesso!")



                                # reconstrução completa da sessão exatamente como no login
                                st.session_state["logged_in"] = True

                                # garante consistência com o login principal
                                st.session_state["tipo_usuario"] = usuario.get("tipo_usuario", "")

                                st.session_state["nome"] = usuario.get("nome_completo")
                                st.session_state["id_usuario"] = usuario.get("_id")

                                # mantém compatibilidade com outras partes do sistema
                                st.session_state["email"] = usuario.get("e_mail", "")
                                st.session_state["projetos"] = usuario.get("projetos", [])

                                # reseta navegação para forçar fluxo correto
                                st.session_state["pagina_atual"] = None
                                st.session_state["projeto_atual"] = None

                                # limpeza das variáveis temporárias do fluxo
                                for key in ["codigo_enviado", "codigo_verificacao", "email_verificado", "codigo_validado"]:
                                    st.session_state.pop(key, None)

                                # delay controlado para consistência visual
                                time.sleep(3)

                                st.rerun()
                            else:
                                st.error("Erro ao redefinir a senha. Tente novamente.")

                        except Exception as e:
                            st.error(f"Erro ao atualizar a senha: {e}")
                    else:
                        st.error("Nenhum usuário encontrado com esse e-mail.")
                else:
                    st.error("As senhas não coincidem ou estão vazias.")




##############################################################################################################
# TELA DE LOGIN
##############################################################################################################

def login():

    # st.image("images/logo_ISPN_horizontal_ass.png", width=300)
    
    # Exibe o logo
    container_logo = st.container(horizontal=True, horizontal_alignment="center")
    container_logo.image("images/logo_fundo_ecos.png", width=300)

    st.write('')
    st.write('')
    st.write('')
    st.write('')
    st.write('')

    # CSS para centralizar e estilizar
    st.markdown(
        """
        <h2 style='text-align: center; color: slategray; font-size: 3rem'>
            CORUJA 2
        </h2>
        <p style='text-align: center; color: slategray; font-size: 1.5rem'>em desenvolvimento ...</p>
        """,
        unsafe_allow_html=True
    )

    # Pula 7 linhas
    for _ in range(7):
        st.write('')

    esq, centro, dir = st.columns([2, 1, 2])

    with centro.form("login_form", border=False):
        # Campo de e-mail
        email_input = st.text_input("E-mail", width="stretch")

        # Campo de senha
        password = st.text_input("Senha", type="password", width="stretch")

        if st.form_submit_button("Entrar", type="primary"):
            # Busca apenas pelo e-mail
            usuario_encontrado = col_pessoas.find_one({
                "e_mail": {"$regex": f"^{email_input.strip()}$", "$options": "i"}
            })

            # Salva o email para possível recuperação de senha
            st.session_state["email_para_recuperar"] = email_input.strip()

            if usuario_encontrado:
                senha_hash = usuario_encontrado.get("senha")

                # Forma segura: só aceita hashes válidos (bytes)
                if isinstance(senha_hash, bytes) and bcrypt.checkpw(password.encode("utf-8"), senha_hash):
                    if usuario_encontrado.get("status", "").lower() != "ativo":
                        with st.container(width="stretch"):
                            st.error("Usuário inativo. Entre em contato com o a equipe do CEPF.")

                        st.stop()

                    # tipo_usuario = usuario_encontrado.get("tipo_usuario", [])
                    tipo_usuario = usuario_encontrado.get("tipo_usuario", "")


                    # Autentica
                    st.session_state["logged_in"] = True
                    st.session_state["tipo_usuario"] = tipo_usuario
                    st.session_state["nome"] = usuario_encontrado.get("nome_completo")
                    # st.session_state["cpf"] = usuario_encontrado.get("CPF")
                    st.session_state["id_usuario"] = usuario_encontrado.get("_id")
                    st.session_state["projetos"] = usuario_encontrado.get("projetos", [])
                    st.rerun()
                else:
                    # Senha inválida ou não hashada corretamente
                    st.error("E-mail ou senha inválidos!", width=300)
            else:
                st.error("E-mail ou senha inválidos!", width=300)

    st.write('')
    st.write('')

    with centro.container(horizontal=True, horizontal_alignment="left", gap="large"):

        # Botão para recuperar senha
        st.button(
            "Esqueci a senha", 
            key="forgot_password", 
            type="tertiary", 
            on_click=recuperar_senha_dialog
        )

        

        # Botão de primeiro acesso
        st.button(
            "Primeiro acesso", 
            key="primeiro_acesso", 
            type="tertiary", 
            on_click=primeiro_acesso_dialog
        )




##############################################################################################################
# EXECUÇÃO PRINCIPAL: VERIFICA LOGIN E NAVEGA ENTRE PÁGINAS
##############################################################################################################

# Verifica se está logado

# Não logado:
if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    login()  # Mostra tela de login


# Logado:
else:



    # Define as páginas disponíveis para cada tipo de usuário (com seções)
    pags_por_tipo = {
        "home_admin": {
            "Projetos": [
                st.Page("projetos_home_visao_geral.py", title="Visão geral", icon=":material/analytics:"),
                st.Page("projetos_lista.py", title="Projetos", icon=":material/list:"),
                st.Page("mapa.py", title="Mapa", icon=":material/map:"),
                st.Page("projeto_novo.py", title="Novo projeto", icon=":material/add_circle:"),
            ],
            "Fases operacionais": [
                st.Page("ciclos_visao_geral.py", title="Visão geral", icon=":material/analytics:"),
                st.Page("ciclos_gerenciar.py", title="Gerenciar", icon=":material/settings:"),
            ],
            "Organizações": [
                st.Page("organizacoes_visao_geral.py", title="Visão geral", icon=":material/analytics:"),
                st.Page("organizacao_nova.py", title="Nova organização", icon=":material/add_business:"),
            ],
            "Pessoas": [
                st.Page("pessoas_equipe.py", title="Equipe", icon=":material/badge:"),
                st.Page("pessoas_beneficiarios.py", title="Beneficiários", icon=":material/group:"),
                st.Page("pessoas_visitantes.py", title="Visitantes", icon=":material/visibility:"),
                st.Page("pessoas_cadastrar.py", title="Convidar pessoas", icon=":material/person_add:"),
                st.Page("pessoas_convites.py", title="Convites pendentes", icon=":material/mail:"),
            ],
            "Administração": [
                st.Page("cadastros_auxiliares.py", title="Cadastros auxiliares", icon=":material/tune:"),
                st.Page("relatorio_acessos.py", title="Relatório de acessos", icon=":material/bar_chart:"),
                st.Page("relatorio_armazenamento.py", title="Armazenamento", icon=":material/home_storage:"),
                #st.Page("relatorios_admin.py", title="Exportar relatórios", icon=":material/assignment:"),

            ],
        },

        "home_equipe": {
            "Projetos": [
                st.Page("projetos_home_visao_geral.py", title="Visão geral", icon=":material/analytics:"),
                st.Page("projetos_lista.py", title="Projetos", icon=":material/list:"),
                st.Page("mapa.py", title="Mapa", icon=":material/map:"),
                st.Page("projeto_novo.py", title="Novo projeto", icon=":material/add_circle:"),
            ],
            "Fases operacionais": [
                st.Page("ciclos_visao_geral.py", title="Visão geral", icon=":material/analytics:"),
                st.Page("ciclos_gerenciar.py", title="Gerenciar", icon=":material/settings:"),
            ],
            "Organizações": [
                st.Page("organizacoes_visao_geral.py", title="Visão geral", icon=":material/analytics:"),
                st.Page("organizacao_nova.py", title="Nova organização", icon=":material/add_business:"),
            ],
            "Pessoas": [
                st.Page("pessoas_equipe.py", title="Equipe", icon=":material/badge:"),
                st.Page("pessoas_beneficiarios.py", title="Beneficiários", icon=":material/group:"),
                st.Page("pessoas_visitantes.py", title="Visitantes", icon=":material/visibility:"),
                st.Page("pessoas_cadastrar.py", title="Convidar pessoas", icon=":material/person_add:"),
                st.Page("pessoas_convites.py", title="Convites pendentes", icon=":material/mail:"),
            ],
            "Administração": [
                # st.Page("cadastros_auxiliares.py", title="Cadastros auxiliares", icon=":material/tune:"),
                st.Page("relatorio_acessos.py", title="Relatório de acessos", icon=":material/bar_chart:"),
                st.Page("relatorio_armazenamento.py", title="Armazenamento", icon=":material/home_storage:"),
                #st.Page("relatorios_admin.py", title="Exportar relatórios", icon=":material/assignment:"),

            ],
        },

        "ver_projeto": [
            st.Page("projeto_visao_geral.py", title="Visão geral", icon=":material/home:"),
            st.Page("projeto_atividades.py", title="Atividades", icon=":material/assignment:"),
            st.Page("projeto_financeiro.py", title="Financeiro", icon=":material/payments:"),
            st.Page("projeto_locais.py", title="Locais", icon=":material/map:"),
            st.Page("projeto_relatorios.py", title="Relatórios", icon=":material/edit_note:"),
            st.Page("projeto_fotos.py", title="Fotos", icon=":material/image:"),
        ],


        "ben_selec_projeto": [
                st.Page("ben_selec_projeto.py", title="Selecione o projeto", icon=":material/assignment:"),
            ],
       

        "visitante": {
            "PROJETOS": [
                st.Page("projetos_home_visao_geral.py", title="Projetos", icon=":material/assignment:"),
                st.Page("mapa.py", title="Mapa", icon=":material/map:"),
            ],
        },
    }



    # Inicializa variáveis de controle no session_state ----------------------
    # Inicializa a página atual se não existir
    if "pagina_atual" not in st.session_state:
        st.session_state.pagina_atual = None

    # Inicializa a projeto atual se não existir
    if "projeto_atual" not in st.session_state:
        st.session_state.projeto_atual = None
    # ----------------------------------------------------------------------



    # Garante que tipo_usuario existe
    # tipo_usuario = set(st.session_state.get("tipo_usuario", []))
    tipo_usuario = st.session_state.get("tipo_usuario", "")


    # ROTEAMENTO DO ADMIN ---------------------------------
    if tipo_usuario == "admin":
        
        # Página inicial do admin 




        # Primeira execução: 
        # se pagina_atual == None, a pagina atual será home_admin
        if st.session_state.pagina_atual is None:
            st.session_state.pagina_atual = "home_admin"

        # Demais execuções
        # Home do admin
        if st.session_state.pagina_atual == "home_admin":
            pages = pags_por_tipo["home_admin"]

        # Admin visita projetos
        elif st.session_state.pagina_atual == "ver_projeto":
            pages = pags_por_tipo["ver_projeto"]




    # ROTEAMENTO DA EQUIPE ---------------------------------
    elif tipo_usuario == "equipe":
        
        # Primeira execução: 
        # se pagina_atual == None, a pagina atual será home_equipe
        if st.session_state.pagina_atual is None:
            st.session_state.pagina_atual = "home_equipe"

        # Demais execuções
        # Home da equipe
        if st.session_state.pagina_atual == "home_equipe":
            pages = pags_por_tipo["home_equipe"]

        # Equipe visita projetos
        elif st.session_state.pagina_atual == "ver_projeto":
            pages = pags_por_tipo["ver_projeto"]



    # ROTEAMENTO DO BENEFICIÁRIO ---------------------------------
    elif tipo_usuario == "beneficiario":

        projetos_raw = st.session_state.get("projetos")
        projetos = projetos_raw if isinstance(projetos_raw, list) else []

        # Primeira execução:
        if st.session_state.pagina_atual is None:

            # Verifica quantos projetos o beneficiário tem
            if len(projetos) == 1:
                st.session_state.pagina_atual = "ver_projeto"
            else:
                st.session_state.pagina_atual = "ben_selec_projeto"

        # Demais execuções
        if st.session_state.pagina_atual == "ver_projeto":

            if not st.session_state.get("projeto_atual") and len(projetos) >= 1:
                st.session_state.projeto_atual = projetos[0]

            pages = pags_por_tipo["ver_projeto"]

        elif st.session_state.pagina_atual == "ben_selec_projeto":
            pages = pags_por_tipo["ben_selec_projeto"]



    # ROTEAMENTO DO VISITANTE ---------------------------------
    elif tipo_usuario == "visitante":

        projetos_raw = st.session_state.get("projetos")
        projetos = projetos_raw if isinstance(projetos_raw, list) else []

        # Primeira execução:
        if st.session_state.pagina_atual is None:

            # Verifica quantos projetos o visitante tem
            if len(projetos) == 1:
                st.session_state.pagina_atual = "ver_projeto"
            else:
                st.session_state.pagina_atual = "ben_selec_projeto"

        # Demais execuções
        if st.session_state.pagina_atual == "ver_projeto":

            if not st.session_state.get("projeto_atual") and len(projetos) >= 1:
                st.session_state.projeto_atual = projetos[0]

            pages = pags_por_tipo["ver_projeto"]

        elif st.session_state.pagina_atual == "ben_selec_projeto":
            pages = pags_por_tipo["ben_selec_projeto"]





    # Cria e executa a navegação
    pg = st.navigation(pages)
    pg.run()

