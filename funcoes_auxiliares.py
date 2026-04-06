import streamlit as st
from pymongo import MongoClient
import datetime
import pandas as pd
import io
import re
from num2words import num2words

# Google Drive API
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Envio de e-mail
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr







# -------------------------------------------------------------------------------------------------
# VALIDAÇÃO E NORMALIZAÇÃO DE CEP
# -------------------------------------------------------------------------------------------------

def limpar_e_validar_cep(cep_str):
    """
    Remove todos os caracteres não numéricos do CEP e valida se possui exatamente 8 dígitos.

    Parâmetros:
    cep_str (str): CEP informado pelo usuário (pode conter máscara ou caracteres extras)

    Retorno:
    tuple:
        - cep_limpo (str): CEP contendo apenas números
        - valido (bool): Indica se o CEP possui exatamente 8 dígitos
    """

    # Remove qualquer caractere que não seja número
    cep_limpo = re.sub(r"\D", "", str(cep_str))

    # Verifica se possui exatamente 8 dígitos
    if len(cep_limpo) == 8:
        return cep_limpo, True

    return cep_limpo, False







def registrar_estatistica_sessao(db):

    ###########################################################################################################
    # CONTROLE DE CONTABILIZAÇÃO DE VISITA
    ###########################################################################################################



    # Verifica se a visita já foi contabilizada nesta sessão
    if "visita_contabilizada" not in st.session_state:
        st.session_state.visita_contabilizada = False

    # Executa apenas se ainda não foi contabilizado
    if not st.session_state.visita_contabilizada:

        # --------------------------------------------------------------------------------------------------
        # PREPARAÇÃO DA DATA ATUAL
        # --------------------------------------------------------------------------------------------------

        # Obtém a data atual no formato desejado
        data_hoje = datetime.datetime.now().strftime("%d/%m/%Y")

        # --------------------------------------------------------------------------------------------------
        # GARANTIA DA EXISTÊNCIA DA COLEÇÃO E DOCUMENTO
        # --------------------------------------------------------------------------------------------------

        # Acessa a coleção 'estatistica'
        colecao = db["estatistica"]

        # Tenta encontrar o documento principal
        doc = colecao.find_one({"_id": "controle_acessos"})

        # Caso o documento não exista, cria com estrutura inicial
        if not doc:
            colecao.insert_one({
                "_id": "controle_acessos",
                "total_sessoes": []
            })
            doc = colecao.find_one({"_id": "controle_acessos"})

        # --------------------------------------------------------------------------------------------------
        # VERIFICAÇÃO DO REGISTRO DO DIA
        # --------------------------------------------------------------------------------------------------

        lista_sessoes = doc.get("total_sessoes", [])

        # Procura se já existe registro para a data atual
        registro_hoje = next((item for item in lista_sessoes if item["data"] == data_hoje), None)

        # Caso não exista, cria um novo registro para o dia
        if not registro_hoje:
            novo_registro = {
                "data": data_hoje,
                "equipe": 0,
                "benef": 0,
                "visit": 0
            }

            colecao.update_one(
                {"_id": "controle_acessos"},
                {"$push": {"total_sessoes": novo_registro}}
            )

            # Atualiza variável local para uso posterior
            registro_hoje = novo_registro

        # --------------------------------------------------------------------------------------------------
        # INCREMENTO DE SESSÕES POR TIPO DE USUÁRIO
        # --------------------------------------------------------------------------------------------------

        tipo_usuario = st.session_state.get("tipo_usuario", "visitante")

        # Define qual campo será incrementado
        if tipo_usuario in ["equipe", "admin"]:
            campo_incremento = "total_sessoes.$.equipe"
        elif tipo_usuario == "beneficiario":
            campo_incremento = "total_sessoes.$.benef"
        else:
            campo_incremento = "total_sessoes.$.visit"

        # Atualiza o contador diretamente no MongoDB
        colecao.update_one(
            {
                "_id": "controle_acessos",
                "total_sessoes.data": data_hoje
            },
            {
                "$inc": {campo_incremento: 1}
            }
        )

        # --------------------------------------------------------------------------------------------------
        # FINALIZAÇÃO DO PROCESSO
        # --------------------------------------------------------------------------------------------------

        # Marca que a visita já foi contabilizada nesta sessão
        st.session_state.visita_contabilizada = True



















def calcular_status_atividade(atividade):

    hoje = pd.Timestamp.today().normalize()

    data_inicio = pd.to_datetime(
        atividade.get("data_inicio"),
        format="%d/%m/%Y",
        errors="coerce"
    )

    data_fim = pd.to_datetime(
        atividade.get("data_fim"),
        format="%d/%m/%Y",
        errors="coerce"
    )

    porcentagem = atividade.get("porcentagem_atv", 0)

    # Segurança
    if pd.isna(data_inicio) or pd.isna(data_fim):
        return "sem_data"

    # Regra 1 — concluída
    if porcentagem == 100:
        return "concluída"

    # Marcos de tempo
    inicio_mais_30 = data_inicio + pd.Timedelta(days=30)
    fim_menos_30 = data_fim - pd.Timedelta(days=30)

    # Regra 2 — porcentagem == 0
    if porcentagem == 0:

        if hoje < inicio_mais_30:
            return "prevista"

        elif inicio_mais_30 <= hoje < fim_menos_30:
            return "atrasada"

        elif fim_menos_30 <= hoje <= data_fim:
            return "próximo ao prazo"

        elif hoje > data_fim:
            return "atrasada"

    # Regra 3 — em andamento
    if 0 < porcentagem < 100:

        if hoje < fim_menos_30:
            return "em andamento"

        elif fim_menos_30 <= hoje <= data_fim:
            return "próximo ao prazo"

        elif hoje > data_fim:
            return "atrasada"

    return "indefinido"















def gerar_recibo_docx(
    caminho_arquivo,
    valor_parcela,
    numero_parcela,
    nome_projeto,
    data_assinatura_contrato,
    contatos,
    nome_organizacao,
    cnpj_organizacao
):
    """
    Gera um arquivo DOCX de recibo com texto padrão do projeto.
    """

    doc = Document()

    # ============================
    # TÍTULO
    # ============================
    titulo = doc.add_paragraph("Recibo")
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    titulo.runs[0].bold = True
    titulo.runs[0].font.size = Pt(14)

    doc.add_paragraph("")

    # ============================
    # TEXTO PRINCIPAL
    # ============================
    valor_fmt = f"R$ {valor_parcela:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    valor_extenso = valor_por_extenso(valor_parcela)
    ordinal = numero_ordinal_pt(numero_parcela)

    data_assinatura = data_extenso_pt(data_assinatura_contrato)
    data_hoje = data_extenso_pt(datetime.today())

    texto = (
        f"Recebi do Instituto Internacional de Educação do Brasil (IEB), "
        f"a quantia de {valor_fmt} ({valor_extenso}), referente à {ordinal} "
        f"parcela de Recursos destinados a apoiar o projeto titulado {nome_projeto}, "
        f"sob o Mecanismo de Pequenos Apoios, conforme o contrato de subvenção nº "
        f"IEB/CEPF/33-2025, assinado em {data_assinatura}, no âmbito do Fundo de "
        f"Parceria para Ecossistemas Críticos - CEPF Cerrado.\n\n"
        f"Brasília-DF, {data_hoje}"
    )

    p = doc.add_paragraph(texto)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph("\n")

    # ============================
    # ASSINATURAS
    # ============================
    for contato in contatos:

        doc.add_paragraph("\n\n")

        linha = doc.add_paragraph("_" * 50)
        linha.alignment = WD_ALIGN_PARAGRAPH.CENTER

        nome_org = doc.add_paragraph(nome_organizacao)
        nome_org.alignment = WD_ALIGN_PARAGRAPH.CENTER
        nome_org.runs[0].bold = True

        doc.add_paragraph(f"CNPJ {cnpj_organizacao}").alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph(contato.get("nome", "")).alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph(contato.get("funcao", "")).alignment = WD_ALIGN_PARAGRAPH.CENTER

    # ============================
    # SALVAR
    # ============================
    doc.save(caminho_arquivo)







def valor_por_extenso(valor: float) -> str:
    return num2words(valor, lang="pt_BR", to="currency")




def data_extenso_pt(data: datetime) -> str:
    meses = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
    ]

    return f"{data.day} de {meses[data.month - 1]} de {data.year}"




def numero_ordinal_pt(numero: int) -> str:
    mapa = {
        1: "primeira",
        2: "segunda",
        3: "terceira",
        4: "quarta",
        5: "quinta",
        6: "sexta",
        7: "sétima",
        8: "oitava",
        9: "nona",
        10: "décima"
    }
    return mapa.get(numero, f"{numero}ª")




###########################################################################################################
# FUNÇÃO PARA ENVIAR E-MAIL
###########################################################################################################


def enviar_email(corpo_html: str, destinatarios: list[str], assunto: str):
    """
    Envia e-mail em HTML usando configurações do st.secrets
    
    Parâmetros:
        corpo_html (str): Conteúdo do e-mail em HTML
        destinatarios (list[str]): Lista de e-mails de destino
        assunto (str): Assunto do e-mail
    """

    # Lendo segredos
    smtp_server = st.secrets["senhas"]["smtp_server"]
    port = st.secrets["senhas"]["port"]
    endereco_email = st.secrets["senhas"]["endereco_email"]
    senha_email = st.secrets["senhas"]["senha_email"]

    # Criando mensagem
    msg = MIMEMultipart()
    # msg["From"] = endereco_email
    msg["From"] = formataddr(("Sistema de Gestão de Projetos do Fundo Ecos", endereco_email))
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = assunto

    msg.attach(MIMEText(corpo_html, "html"))

    # Enviando
    try:
        with smtplib.SMTP(smtp_server, port) as server:
            server.starttls()
            server.login(endereco_email, senha_email)
            server.send_message(msg)

        return True

    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False












###########################################################################################################
# CONEXÃO COM GOOGLE DRIVE
###########################################################################################################

# Escopo mínimo necessário para Drive
ESCOPO_DRIVE = ["https://www.googleapis.com/auth/drive"]

@st.cache_resource
def obter_servico_drive():
    """
    Retorna o cliente autenticado do Google Drive,
    usando as credenciais armazenadas em st.secrets.

    IMPORTANTE:
    - Não cria conexão automaticamente
    - Só executa quando chamada
    - Cache evita recriar o cliente
    """
    credenciais = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=ESCOPO_DRIVE
    )
    return build("drive", "v3", credentials=credenciais)


###########################################################################################################
# FUNÇÕES DE PASTAS NO GOOGLE DRIVE
###########################################################################################################

def obter_ou_criar_pasta(servico, nome_pasta, id_pasta_pai):
    """
    Busca uma pasta com o nome especificado dentro da pasta pai no Google Drive.
    Se não existir, cria a pasta.

    Retorna o ID da pasta.
    """

    consulta = (
        f"name='{nome_pasta}' and "
        f"'{id_pasta_pai}' in parents and "
        f"mimeType='application/vnd.google-apps.folder' and trashed=false"
    )

    resultado = servico.files().list(
        q=consulta,
        fields="files(id)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute()

    arquivos = resultado.get("files", [])

    if arquivos:
        return arquivos[0]["id"]

    pasta = servico.files().create(
        body={
            "name": nome_pasta,
            "parents": [id_pasta_pai],
            "mimeType": "application/vnd.google-apps.folder"
        },
        fields="id",
        supportsAllDrives=True
    ).execute()

    return pasta["id"]


def obter_pasta_projeto(servico, codigo, sigla):
    """
    Retorna o ID da pasta do projeto no Google Drive.
    Cria se não existir.

    Usa session_state para evitar duplicação.
    """

    chave = f"pasta_projeto_{codigo}"

    if chave in st.session_state:
        return st.session_state[chave]

    pasta_id = obter_ou_criar_pasta(
        servico,
        f"{codigo} - {sigla}",
        st.secrets["drive"]["pasta_drive_projetos"]
    )

    st.session_state[chave] = pasta_id
    return pasta_id


# Função para obter o ID da pasta 'Locais' no Drive, para salvar os anexos dos locais.

def obter_pasta_locais(servico, pasta_projeto_id):
    """
    Retorna o ID da subpasta 'Locais' dentro da pasta do projeto.

    Também usa cache no session_state para evitar múltiplas criações.
    """

    if "pasta_locais_id" in st.session_state:
        return st.session_state["pasta_locais_id"]

    pasta_id = obter_ou_criar_pasta(
        servico,
        "Locais",
        pasta_projeto_id
    )

    st.session_state["pasta_locais_id"] = pasta_id
    return pasta_id




# Função para obter o ID da pasta 'Pesquisas' no Drive, para salvar os anexos das pesquisas.
def obter_pasta_pesquisas(servico, pasta_projeto_id, codigo_projeto):
    """
    Retorna o ID da pasta 'Pesquisas' dentro da pasta do projeto.

    - Cria a pasta se não existir
    - Cache separado por projeto
    - Garante parent válido
    """

    # Cache por projeto (NUNCA global)
    chave = f"pasta_pesquisas_{codigo_projeto}"

    if chave in st.session_state:
        return st.session_state[chave]

    if not pasta_projeto_id:
        raise ValueError("ID da pasta do projeto inválido")

    pasta_id = obter_ou_criar_pasta(
        servico,
        "Pesquisas",
        pasta_projeto_id
    )

    # Guarda no session_state
    st.session_state[chave] = pasta_id
    return pasta_id

# Função para obter o ID da pasta 'Relatos_atividades' no Drive, para salvar os anexos das atividades.
def obter_pasta_relatos_atividades(servico, pasta_projeto_id):
    """
    Retorna o ID da pasta 'Relatos_atividades' dentro da pasta do projeto.

    - Cria a pasta se não existir
    - Usa cache no session_state
    """

    if "pasta_relatos_atividades_id" in st.session_state:
        return st.session_state["pasta_relatos_atividades_id"]

    pasta_id = obter_ou_criar_pasta(
        servico,
        "Relatos_atividades",
        pasta_projeto_id
    )

    st.session_state["pasta_relatos_atividades_id"] = pasta_id
    return pasta_id


def obter_pasta_relatos_financeiros(servico, pasta_projeto_id):
    return obter_ou_criar_pasta(
        servico,
        "Relatos_financeiros",
        pasta_projeto_id
    )

def obter_pasta_relatorios(servico, pasta_projeto_id):
    """
    Retorna o ID da subpasta 'Relatorios' dentro da pasta do projeto.
    Cria se não existir.
    """

    chave = f"pasta_relatorios_{pasta_projeto_id}"

    if chave in st.session_state:
        return st.session_state[chave]

    pasta_id = obter_ou_criar_pasta(
        servico,
        "Relatorios",
        pasta_projeto_id
    )

    st.session_state[chave] = pasta_id
    return pasta_id


def obter_pasta_recibos(servico, pasta_projeto_id):
    """
    Retorna o ID da subpasta 'Recibos' dentro da pasta do projeto.
    Cria se não existir.

    Usa cache no session_state para evitar múltiplas criações.
    """

    if "pasta_recibos_id" in st.session_state:
        return st.session_state["pasta_recibos_id"]

    pasta_id = obter_ou_criar_pasta(
        servico,
        "Recibos",
        pasta_projeto_id
    )

    st.session_state["pasta_recibos_id"] = pasta_id
    return pasta_id





###########################################################################################################
# UPLOAD E LINK DE ARQUIVOS
###########################################################################################################

def enviar_arquivo_drive(servico, id_pasta, arquivo):
    """
    Faz upload seguro de um arquivo do Streamlit para o Google Drive.

    - Usa upload resumable (mais estável)
    - Trata erros de rede/SSL
    - NÃO propaga exceção para a UI
    - Retorna None em caso de erro
    """

    try:
        # Garante que o ponteiro do arquivo está no início
        arquivo.seek(0)

        media = MediaIoBaseUpload(
            arquivo,
            mimetype=arquivo.type,
            resumable=True
        )

        arq = servico.files().create(
            body={
                "name": arquivo.name,
                "parents": [id_pasta]
            },
            media_body=media,
            fields="id",
            supportsAllDrives=True
        ).execute()

        return arq["id"]

    except Exception as e:
        st.error("Erro temporário ao enviar arquivo. Tente novamente mais tarde.")

        # Retorna None para a camada de UI decidir o que fazer
        return None



def gerar_link_drive(id_arquivo):
    """
    Gera o link público padrão de visualização do Google Drive.
    """
    return f"https://drive.google.com/file/d/{id_arquivo}/view"






def gerar_cronograma_financeiro(parcelas: list, relatorios: list) -> pd.DataFrame:
    """
    Gera um DataFrame com o cronograma financeiro (parcelas + relatórios).

    :param parcelas: lista de parcelas (financeiro["parcelas"])
    :param relatorios: lista de relatórios (projeto["relatorios"])
    :return: DataFrame formatado para exibição
    """

    linhas_cronograma = []

    # =====================
    # PARCELAS
    # =====================
    for p in parcelas or []:
        numero = p.get("numero")
        valor = p.get("valor")
        data_prevista = p.get("data_prevista")
        data_realizada = p.get("data_realizada")

        linhas_cronograma.append(
            {
                "evento": f"Parcela {numero}",
                "Entregas": "",
                "Valor R$": (
                    f"{valor:,.2f}"
                    .replace(",", "X")
                    .replace(".", ",")
                    .replace("X", ".")
                    if valor is not None else ""
                ),
                "Data prevista": pd.to_datetime(data_prevista, errors="coerce"),
                "Data realizada": (
                    pd.to_datetime(data_realizada).strftime("%d/%m/%Y")
                    if data_realizada else ""
                ),
            }
        )

    # =====================
    # RELATÓRIOS
    # =====================
    for r in relatorios or []:
        numero = r.get("numero")
        entregas = r.get("entregas", [])
        data_prevista = r.get("data_prevista")
        data_realizada = r.get("data_realizada")

        linhas_cronograma.append(
            {
                "evento": f"Relatório {numero}",
                "Entregas": " / ".join(entregas) if isinstance(entregas, list) else "",
                "Valor R$": "",
                "Data prevista": pd.to_datetime(data_prevista, errors="coerce"),
                "Data realizada": (
                    pd.to_datetime(data_realizada).strftime("%d/%m/%Y")
                    if data_realizada else ""
                ),
            }
        )

    # =====================
    # DataFrame final
    # =====================
    df_cronograma = pd.DataFrame(linhas_cronograma)

    if df_cronograma.empty:
        return df_cronograma

    return df_cronograma.sort_values(by="Data prevista", ascending=True)






@st.cache_resource
def conectar_mongo_coruja():
    # CONEXÃO LOCAL
    cliente = MongoClient(st.secrets["senhas"]["senha_mongo_coruja"])
    db_coruja_mongo = cliente["Coruja"] 
    return db_coruja_mongo




def ajustar_altura_dataframe(
    df_nao_atualizado,
    linhas_adicionais=0,
    altura_maxima=None,  # Se None, não aplica limite
    use_container_width=True,
    hide_index=True,
    # column_config={
    #     "Link": st.column_config.Column(
    #         width="medium"  
    #     ),
    #     "Data da Última Ação Legislativa": st.column_config.Column(
    #         label="Última ação",  
    #     )
    # }
):
    """
    Ajusta a altura da exibição de um DataFrame no Streamlit com base no número de linhas.
    Se 'altura_maxima' for informado, limita a altura até esse valor.
    """

    # Define a altura em pixels de cada linha
    altura_por_linha = 35  

    # Calcula a altura total necessária
    altura_total = ((df_nao_atualizado.shape[0] + linhas_adicionais) * altura_por_linha) + 2

    # Se altura_maxima foi informada, aplica o limite
    if altura_maxima is not None:
        altura_total = min(altura_total, altura_maxima)

    # Exibe o DataFrame no Streamlit
    st.dataframe(
        df_nao_atualizado,
        height=altura_total,
        use_container_width=use_container_width,
        hide_index=hide_index,
        # column_config=column_config
    )



def ajustar_altura_data_editor(df, linhas_adicionais=1):
    """
    Calcula a altura ideal para st.data_editor,
    garantindo que todas as linhas fiquem visíveis
    sem barra de rolagem.

    Parâmetros:
    - df: DataFrame exibido no data_editor
    - linhas_adicionais: linhas extras de folga (default=1)

    Retorna:
    - altura em pixels (int)
    """

    ALTURA_LINHA = 35      # altura média de cada linha
    ALTURA_HEADER = 38    # cabeçalho do data_editor

    try:
        total_linhas = len(df) + linhas_adicionais
    except Exception:
        total_linhas = linhas_adicionais

    altura = (total_linhas * ALTURA_LINHA) + ALTURA_HEADER

    return altura


# Envia mensagem para a área de notificação
def notificar(mensagem: str):

    if "notificacoes" not in st.session_state:
        st.session_state.notificacoes = []
        
    st.session_state.notificacoes.append(mensagem)



def calcular_status_projetos(df_projetos: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula o status dos projetos com base em parcelas e relatórios.

    Regras:
    - Se status == "Cancelado", mantém.
    - Se NÃO houver parcelas OU relatórios → "Sem cronograma".
    - Se houver ambos, calcula normalmente.
    - Totalmente seguro contra campos ausentes, None ou NaN.
    """

    if df_projetos.empty:
        return df_projetos

    # Garante colunas necessárias
    for col in ["status", "dias_atraso", "proximo_evento", "data_proximo_evento"]:
        if col not in df_projetos.columns:
            df_projetos[col] = None

    # # ???
    # # DEBUG: MANIPULAÇÃO DA DATA DE HOJE
    # hoje = datetime.date(2026, 4, 30)


    hoje = datetime.date.today()

    for idx, projeto in df_projetos.iterrows():

        codigo = projeto.get("codigo")
        sigla = projeto.get("sigla")

        # ----------------------------------------------------------
        # MANTÉM STATUS CANCELADO
        # ----------------------------------------------------------
        if projeto.get("status") == "Cancelado":
            df_projetos.at[idx, "status"] = "Cancelado"
            df_projetos.at[idx, "dias_atraso"] = None
            df_projetos.at[idx, "proximo_evento"] = None
            df_projetos.at[idx, "data_proximo_evento"] = None
            continue

        # ----------------------------------------------------------
        # COLETA SEGURA DOS DADOS
        # ----------------------------------------------------------
        financeiro = projeto.get("financeiro")
        if not isinstance(financeiro, dict):
            financeiro = {}

        parcelas = financeiro.get("parcelas")
        if not isinstance(parcelas, list):
            parcelas = []

        relatorios = projeto.get("relatorios")
        if not isinstance(relatorios, list):
            relatorios = []

        # ----------------------------------------------------------
        # REGRA: precisa ter parcelas E relatórios
        # ----------------------------------------------------------
        if not parcelas or not relatorios:
            notificar(
                f"O projeto {codigo} - {sigla} não possui parcelas e/ou relatórios cadastrados. Não é possível determinar o status."
            )

            df_projetos.at[idx, "status"] = "Sem cronograma"
            df_projetos.at[idx, "dias_atraso"] = None
            df_projetos.at[idx, "proximo_evento"] = None
            df_projetos.at[idx, "data_proximo_evento"] = None
            continue

        # ----------------------------------------------------------
        # MONTA EVENTOS
        # ----------------------------------------------------------
        eventos = []

        for p in parcelas:
            if isinstance(p, dict):
                eventos.append({
                    "tipo": "Parcela",
                    "numero": p.get("numero"),
                    "data_prevista": pd.to_datetime(p.get("data_prevista"), errors="coerce"),
                    "realizado": p.get("data_realizada") is not None
                })

        for r in relatorios:
            if isinstance(r, dict):
                eventos.append({
                    "tipo": "Relatório",
                    "numero": r.get("numero"),
                    "data_prevista": pd.to_datetime(r.get("data_prevista"), errors="coerce"),
                    "realizado": r.get("data_envio") is not None
                })

        # Remove eventos inválidos
        eventos = [e for e in eventos if pd.notna(e["data_prevista"])]

        if not eventos:
            notificar(
                f"O projeto {codigo} - {sigla} não possui eventos com data válida."
            )

            df_projetos.at[idx, "status"] = "Sem cronograma"
            df_projetos.at[idx, "dias_atraso"] = None
            df_projetos.at[idx, "proximo_evento"] = None
            df_projetos.at[idx, "data_proximo_evento"] = None
            continue

        # ----------------------------------------------------------
        # ORDENA E DEFINE PRÓXIMO EVENTO
        # ----------------------------------------------------------
        eventos.sort(key=lambda x: x["data_prevista"])

        proximo = next((e for e in eventos if not e["realizado"]), None)


        if not proximo:
            df_projetos.at[idx, "status"] = "Concluído"
            df_projetos.at[idx, "dias_atraso"] = 0
            df_projetos.at[idx, "proximo_evento"] = None
            df_projetos.at[idx, "data_proximo_evento"] = None
            continue

        # ----------------------------------------------------------
        # CALCULA STATUS
        # ----------------------------------------------------------
        data_prevista = proximo["data_prevista"].date()
        dias_atraso = (hoje - data_prevista).days

        status = "Atrasado" if dias_atraso > 0 else "Em dia"

        df_projetos.at[idx, "status"] = status
        df_projetos.at[idx, "dias_atraso"] = dias_atraso
        df_projetos.at[idx, "proximo_evento"] = f"{proximo['tipo']} {proximo['numero']}"
        df_projetos.at[idx, "data_proximo_evento"] = data_prevista

    return df_projetos







# ###################################################################################################
# SIDEBAR DA PÁGINA DO PROJETO
# ###################################################################################################

def sidebar_projeto():

    st.sidebar.write('')

    # Botão de voltar para a home_interna só para admin, equipe e visitante
    if st.session_state.tipo_usuario in ['admin', 'equipe', 'visitante']:

        # if st.sidebar.button("Voltar para Home", icon=":material/arrow_back:", type="tertiary"):
        if st.sidebar.button("Voltar ao Painel", icon=":material/arrow_back:", type="tertiary"):
            
            if st.session_state.tipo_usuario == 'admin':
                st.session_state.pagina_atual = 'home_admin'
                st.rerun()

            elif st.session_state.tipo_usuario == 'equipe':
                st.session_state.pagina_atual = 'home_equipe'
                st.rerun()


    # Botão de voltar para beneficiário — apenas se tiver mais de um projeto
    if (
        st.session_state.get("tipo_usuario") == "beneficiario"
        and len(st.session_state.get("projetos", [])) > 1
    ):
        if st.sidebar.button("Voltar", icon=":material/arrow_back:", type="tertiary"):
        # if st.sidebar.button("Fechar projeto", icon=":material/close:", type="tertiary"):
            st.session_state.pagina_atual = "ben_selec_projeto"
            st.session_state.projeto_atual = None
            st.rerun()



    # Pequeno cabeçalho no sidebar

    tipo_usuario = st.session_state.get("tipo_usuario")


    st.sidebar.caption(st.session_state.get("nome"))

    if tipo_usuario == 'beneficiario':

        st.sidebar.caption("Tipo: beneficiário(a)")

    elif tipo_usuario == 'admin':
        st.sidebar.caption("Tipo: administrador(a)")

    elif tipo_usuario == 'equipe':
        st.sidebar.caption("Tipo: equipe")

    elif tipo_usuario == 'visitante':
        st.sidebar.caption("Tipo: visitante")

    st.sidebar.caption("Projeto: " + st.session_state.get("projeto_atual", "-"))


    st.sidebar.divider()

    if tipo_usuario == 'beneficiario':

        st.sidebar.caption("Em caso de dúvidas, sugestões ou comentários, entre em contato com cepfcerrado@iieb.org.br")


###########################################################################################################
# FUNÇÕES DE SEGURANÇA
###########################################################################################################


def validar_df(df, nome, colunas_obrigatorias=None):
    """
    Valida se um DataFrame tem dados e as colunas necessárias.

    Parâmetros:
    - df: DataFrame
    - nome: nome amigável (para mensagem)
    - colunas_obrigatorias: lista de colunas obrigatórias

    Retorna:
    - (bool, lista_erros)
    """
    erros = []

    if df.empty:
        erros.append(f"{nome} está vazio")

    if colunas_obrigatorias:
        for col in colunas_obrigatorias:
            if col not in df.columns:
                erros.append(f"{nome} não possui a coluna '{col}'")

    return len(erros) == 0, erros


def safe_col(df, col, default=None):
    """
    Retorna uma coluna com segurança.
    Se não existir, retorna valor padrão.
    """
    if col in df.columns:
        return df[col]
    return default


def safe_get(row, col, default=None):
    """
    Acesso seguro a valores de uma linha (Series).
    """
    return row[col] if col in row else default