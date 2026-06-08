import streamlit as st
import pandas as pd
import streamlit_antd_components as sac
import time
import datetime
import bson
from collections import defaultdict
import uuid
from st_rsuite import date_picker


from zoneinfo import ZoneInfo 


from funcoes_auxiliares import (
    conectar_mongo_coruja,
    sidebar_projeto,
    obter_servico_drive,
    obter_ou_criar_pasta,
    obter_pasta_pesquisas,
    obter_pasta_projeto,
    obter_pasta_relatos_financeiros,
    obter_pasta_relatorios,
    enviar_arquivo_drive,
    gerar_link_drive,
    enviar_email
)



st.set_page_config(page_title="Relatórios", page_icon=":material/edit_note:")





###########################################################################################################
# CONFIGURAÇÕES DO STREAMLIT
###########################################################################################################


# Traduzindo o texto do st.file_uploader
# Texto interno
st.markdown("""
<style>
/* Esconde o texto padrão */
[data-testid="stFileUploaderDropzone"] div div::before {
    content: "";
    color: rgba(49, 51, 63, 0.7);
    font-size: 0.9rem;
    font-weight: 400;
    position: absolute;
    top: 50px;              /* fixa no topo */
    left: 50%;
    transform: translate(-50%, 10%);
    pointer-events: none;
}
/* Esconde o texto original */
[data-testid="stFileUploaderDropzone"] div div span {
    visibility: hidden !important;
}
</style>
""", unsafe_allow_html=True)

# Traduzindo Botão do file_uploader
st.markdown("""
<style>
/* Alvo: apenas o botão dentro do componente de upload */
section[data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"] {
    font-size: 0px !important;   /* esconde o texto original */
    padding-left: 14px !important;
    padding-right: 14px !important;
    min-width: 160px !important;
}
/* Insere o texto traduzido */
section[data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"]::after {
    content: "Selecionar arquivo";
    font-size: 14px !important;
    color: inherit;
}
</style>
""", unsafe_allow_html=True)


###########################################################################################################
# CONEXÃO COM O BANCO DE DADOS MONGODB
###########################################################################################################

# Conecta-se ao banco de dados MongoDB (usa cache automático para melhorar performance)
db = conectar_mongo_coruja()




###########################################################################################################
# CARREGAMENTO DOS DADOS
###########################################################################################################

col_projetos = db["projetos"]

col_editais = db["editais"]

col_beneficios = db["beneficios"]

col_publicos = db["publicos"]

col_categorias_despesa = db["categorias_despesa"]

categorias_map = {
    str(cat["_id"]): cat["categoria"]
    for cat in col_categorias_despesa.find({}, {"categoria": 1})
}

col_pessoas = db["pessoas"]

lista_publicos = list(col_publicos.find({}, {"_id": 0, "publico": 1}))

# SEMPRE insere a opção Outros
opcoes_publicos = sorted({p["publico"] for p in lista_publicos} - {"Outros"})
opcoes_publicos.append("Outros")

codigo_projeto_atual = st.session_state.projeto_atual

df_projeto = pd.DataFrame(
    list(
        col_projetos.find(
            {"codigo": codigo_projeto_atual}
        )
    )
)

if df_projeto.empty:
    st.error("Projeto não encontrado.")
    st.stop()

projeto = df_projeto.iloc[0]

relatorios = projeto.get("relatorios", [])

edital = col_editais.find_one({"codigo_edital": projeto["edital"]})

tipo_usuario = st.session_state.get("tipo_usuario")





###########################################################################################################
# FUNÇÕES
###########################################################################################################

def calcular_saldo_parcela():
    # ==================================================
    # CÁLCULO DO SALDO DA PARCELA
    # ==================================================
    # Regra:
    # - parcela = relatorio_numero
    # - saldo = valor da parcela - total gasto na parcela
    # - exibir em porcentagem (%)

    parcela_atual = next(
        (p for p in projeto.get("financeiro", {}).get("parcelas", [])
        if p.get("numero") == st.session_state.get("relatorio_numero")),
        None
    )

    if parcela_atual:

        valor_parcela = parcela_atual.get("valor", 0)

        # Soma todas as despesas desta parcela
        total_gasto = 0
        for despesa in projeto.get("financeiro", {}).get("orcamento", []):
            for lanc in despesa.get("lancamentos", []):
                if lanc.get("relatorio_numero") == relatorio_numero:
                    total_gasto += lanc.get("valor_despesa", 0)

        saldo = valor_parcela - total_gasto

        if valor_parcela > 0:
            saldo_pct = (saldo / valor_parcela) * 100
        else:
            saldo_pct = 0

        # Exibição 

        return saldo_pct




# Texto do status da avaliação de Relatos de Atividades ou de Despesas de relatório
def texto_verificacao():
    nome = st.session_state.get("nome", "Usuário")
    data = datetime.datetime.now().strftime("%d/%m/%Y")
    return f"Verificado por {nome} em {data}"


# Atualiza o status da avaliação de Relatos de Atividades ou de Despesas
def atualizar_verificacao_relatorio(projeto_codigo, relatorio_numero, campo, checkbox_key):
    marcado = st.session_state.get(checkbox_key, False)

    nome = st.session_state.get("nome", "Usuário")
    data = datetime.datetime.now().strftime("%d/%m/%Y")

    if marcado:
        col_projetos.update_one(
            {
                "codigo": projeto_codigo,
                "relatorios.numero": relatorio_numero
            },
            {
                "$set": {
                    f"relatorios.$.{campo}": f"Verificado por {nome} em {data}"
                }
            }
        )
    else:
        col_projetos.update_one(
            {
                "codigo": projeto_codigo,
                "relatorios.numero": relatorio_numero
            },
            {
                "$unset": {
                    f"relatorios.$.{campo}": ""
                }
            }
        )


def todos_relatos_aceitos(projeto, relatorio_numero):
    """
    Retorna True se TODOS os relatos do relatório informado
    estiverem com status_relato == 'aceito'.

    Se existir ao menos um relato do relatório que não seja aceito,
    retorna False.

    Se não existir nenhum relato nesse relatório, retorna False.
    """

    relatos_encontrados = []

    componentes = projeto.get("plano_trabalho", {}).get("componentes", [])

    for componente in componentes:
        for atividade in componente.get("atividades", []):
                for relato in atividade.get("relatos", []):
                    if relato.get("relatorio_numero") == relatorio_numero:
                        relatos_encontrados.append(relato)

    # Se não existe nenhum relato nesse relatório, não aprova
    if not relatos_encontrados:
        return False

    # Todos precisam estar aceitos
    return all(r.get("status_relato") == "aceito" for r in relatos_encontrados)


def todas_despesas_aceitas(projeto, relatorio_numero):
    """
    Retorna True se TODOS os lançamentos de despesas do relatório
    estiverem com status_despesa == 'aceito'.

    Se existir ao menos uma despesa não aceita, retorna False.
    Se não existir nenhuma despesa nesse relatório, retorna False.
    """

    lancamentos = []

    orcamento = projeto.get("financeiro", {}).get("orcamento", [])

    for item in orcamento:
        for lanc in item.get("lancamentos", []):
            if lanc.get("relatorio_numero") == relatorio_numero:
                lancamentos.append(lanc)

    if not lancamentos:
        return False

    return all(l.get("status_despesa") == "aceito" for l in lancamentos)


def todos_indicadores_aceitos(projeto, relatorio_numero):
    """
    Retorna True se TODOS os lançamentos de indicadores do relatório
    estiverem com status_indicador == 'aceito'.

    Se existir ao menos um indicador não aceito, retorna False.
    Se não existir nenhum indicador lançado nesse relatório, retorna False.
    """

    lancamentos = []

    indicadores = projeto.get("indicadores", [])

    for indicador in indicadores:
        for lanc in indicador.get("lancamentos", []):
            if lanc.get("relatorio_numero") == relatorio_numero:
                lancamentos.append(lanc)

    # Se não existe nenhum indicador lançado, não aprova
    if not lancamentos:
        return False

    # Todos precisam estar aceitos
    return all(
        l.get("status_indicador") == "aceito"
        for l in lancamentos
    )


def gerar_email_relatorio_aprovado(
    nome_do_contato: str,
    relatorio_numero: int,
    projeto: dict,
    organizacao: str,
    logo_url: str
):

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-top: 6px solid #2e7d32;
            padding: 30px;
        }}
        .logo {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .content {{
            color: #333;
            font-size: 15px;
            line-height: 1.6;
        }}
        .footer {{
            margin-top: 40px;
            font-size: 12px;
            color: #777;
            text-align: center;
        }}
        .highlight {{
            color: #2e7d32;
            font-weight: bold;
        }}
    </style>
</head>
<body>

    <div class="container">

        <div class="logo">
            <img src="{logo_url}" height="70" alt="IEB">
        </div>

        <div class="content">

            <p>Olá <strong>{nome_do_contato}</strong>,</p>

            <p>
                Informamos que o <span class="highlight">Relatório {relatorio_numero}</span>
                do projeto <span class="highlight">{projeto['nome_do_projeto']}</span>
                da organização <strong>{organizacao}</strong> foi <strong>aprovado</strong>.
            </p>

            <p>
                O relatório já está validado no sistema e segue para os próximos encaminhamentos.
            </p>

            <p>
                Atenciosamente,<br>
                <strong>Sistema de Gestão de Projetos do IEB</strong>
            </p>
        </div>

        <div class="footer">
            Este é um e-mail automático. Não responda.
        </div>

    </div>

</body>
</html>
"""




def gerar_email_relatorio_reprovado(
    nome_do_contato: str,
    relatorio_numero: int,
    projeto: dict,
    organizacao: str,
    logo_url: str
):
    """
    Gera o HTML do e-mail de reprovação de relatório.
    Segue o mesmo padrão visual do e-mail de aprovação.
    """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-top: 6px solid #C82333;
            padding: 30px;
        }}
        .logo {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .content {{
            color: #333;
            font-size: 15px;
            line-height: 1.6;
        }}
        .footer {{
            margin-top: 40px;
            font-size: 12px;
            color: #777;
            text-align: center;
        }}
        .highlight {{
            color: #C82333;
            font-weight: bold;
        }}
    </style>
</head>
<body>

    <div class="container">

        <div class="logo">
            <img src="{logo_url}" height="70" alt="IEB">
        </div>

        <div class="content">

            <p><strong>{nome_do_contato}</strong>,</p>

            <p>
                Informamos que o <span class="highlight">Relatório {relatorio_numero}</span>
                do projeto {projeto['nome_do_projeto']}
                da organização <strong>{organizacao}</strong> <span class="highlight">não foi aprovado</span>.
            </p>

            <p>
                Acesse o sistema Veredas para ver em detalhes os ajustes necessários no Relatório.
            </p>

            <p>
                <strong>Após realizar todos os ajustes, envie o relatório novamente.</strong>
            </p>

            <p>
                Atenciosamente,<br>
                <strong>Sistema Veredas</strong>
            </p>
        </div>

        <div class="footer">
            Este é um e-mail automático. Não responda.
        </div>

    </div>

</body>
</html>
"""







def notificar_padrinhos_relatorio(
    col_pessoas,
    numero_relatorio,
    projeto,
    logo_url
):
    padrinhos = buscar_padrinhos_do_projeto(col_pessoas, projeto["codigo"])

    if not padrinhos:
        return False

    for padrinho in padrinhos:
        html = montar_email_relatorio_envio(
            nome=padrinho["nome_completo"],
            numero_relatorio=numero_relatorio,
            codigo=projeto["codigo"],
            sigla=projeto["sigla"],
            logo_url=logo_url
        )

        enviar_email(
            corpo_html=html,
            destinatarios=[padrinho["e_mail"]],
            assunto=f"Coruja 2 - Relatório {numero_relatorio} recebido - Projeto {projeto['codigo']} - {projeto['sigla']}"
        )

    return True







def montar_email_relatorio_envio(
    nome: str,
    numero_relatorio: int,
    codigo: str,
    sigla: str,
    logo_url: str
):
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-top: 6px solid #b30000;
            padding: 30px;
        }}
        .logo {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .content {{
            color: #333;
            font-size: 15px;
            line-height: 1.6;
        }}
        .footer {{
            margin-top: 40px;
            font-size: 12px;
            color: #777;
            text-align: center;
        }}
        .highlight {{
            color: #b30000;
            font-weight: bold;
        }}
    </style>
</head>
<body>

    <div class="container">
        <div class="logo">
            <img src="{logo_url}" height="70" alt="CEPF">
        </div>

        <div class="content">
            <br>
            <p>Olá <strong>{nome}</strong>,</p>

            <p>
                O relatório <span class="highlight">{numero_relatorio}</span> do projeto
                <span class="highlight">{codigo} - {sigla}</span> está disponível para análise.
            </p>

            <p>
                Por favor, acesse o sistema para realizar a avaliação.
            </p>

            <p>Atenciosamente,<br>
            <strong>Sistema de Gestão de Projetos</strong></p>
        </div>

        <div class="footer">
            Este é um e-mail automático. Não responda.
        </div>
    </div>

</body>
</html>
"""





def buscar_padrinhos_do_projeto(col_pessoas, codigo_projeto: str):
    """
    Retorna lista de pessoas (dict) que são padrinhos do projeto.
    Regra:
      - tipo_usuario != beneficiario
      - tipo_usuario != visitante
      - projetos contém o código do projeto
    """

    padrinhos = list(
        col_pessoas.find(
            {
                "tipo_usuario": {"$nin": ["beneficiario", "visitante"]},
                "projetos": codigo_projeto,
                "status": "ativo"
            },
            {
                "nome_completo": 1,
                "e_mail": 1
            }
        )
    )

    return padrinhos




def gerar_id_lanc_despesa(projeto):
    """
    Gera id sequencial no formato despesa_001, despesa_002...
    """

    numeros = []

    for despesa in projeto.get("financeiro", {}).get("orcamento", []):
        for lanc in despesa.get("lancamentos", []):
            idd = lanc.get("id_lanc_despesa")
            if idd and idd.startswith("despesa_"):
                try:
                    numeros.append(int(idd.split("_")[1]))
                except:
                    pass

    proximo = max(numeros, default=0) + 1
    return f"despesa_{str(proximo).zfill(3)}"




# ==================================================
# REGISTRO DE DESPESA (EXPANDER)
# ==================================================
def render_registro_despesa(
    relatorio_numero,
    projeto,
    col_projetos,
    categorias_map
):

    # --------------------------------------------------
    # Controle de reset do formulário
    # --------------------------------------------------
    if "form_despesa_key" not in st.session_state:
        st.session_state["form_despesa_key"] = 0

    form_key = st.session_state["form_despesa_key"]

    with st.expander("Registrar despesa", expanded=False):

        # ==================================================
        # OPÇÕES DE DESPESA
        # ==================================================
        orcamento = projeto["financeiro"]["orcamento"]

        opcoes = []
        mapa_opcoes = {}

        for o in orcamento:

            categoria_id = str(o["categoria"])

            nome_categoria = categorias_map.get(
                categoria_id,
                "Categoria não encontrada"
            )

            label = f"{nome_categoria} | {o['nome_despesa']}"

            opcoes.append(label)

            # Mapeamento da opção selecionada
            mapa_opcoes[label] = {
                "categoria_id": categoria_id,
                "nome_despesa": o["nome_despesa"],
                "nome_categoria": nome_categoria
            }

        opcoes = sorted(opcoes, key=lambda x: x.lower())

        escolha = st.selectbox(
            "Categoria / Despesa *",
            options=opcoes,
            key=f"desp_categoria_{form_key}"
        )

        categoria = mapa_opcoes[escolha]["categoria_id"]

        nome_despesa = mapa_opcoes[escolha]["nome_despesa"]

        nome_categoria = mapa_opcoes[escolha]["nome_categoria"]

        # ==================================================
        # DADOS DO LANÇAMENTO
        # ==================================================
        id_despesa = gerar_id_lanc_despesa(projeto)

        col1, col2 = st.columns(2)

        with col1:

            data_despesa = st.date_input(
                "Data da despesa *",
                format="DD/MM/YYYY",
                key=f"desp_data_{form_key}"
            )

        with col2:

            valor = st.number_input(
                "Valor (reais) *",
                min_value=0.0,
                format="%.2f",
                key=f"desp_valor_{form_key}"
            )

        descricao = st.text_area(
            "Descrição da despesa *",
            key=f"desp_desc_{form_key}"
        )

        col1, col2 = st.columns([2, 1])

        fornecedor = col1.text_input(
            "Fornecedor *",
            key=f"desp_forn_{form_key}"
        )

        cpf_cnpj = col2.text_input(
            "CPF / CNPJ *",
            key=f"desp_doc_{form_key}"
        )

        # ==================================================
        # ANEXOS
        # ==================================================
        categoria_nome_lower = nome_categoria.lower()

        is_taxa_bancaria = (
            "taxas bancárias" in categoria_nome_lower
        )

        label_anexos = (
            "Anexos"
            if is_taxa_bancaria
            else "Anexos *"
        )

        anexos = st.file_uploader(
            label_anexos,
            accept_multiple_files=True,
            key=f"desp_anexos_{form_key}"
        )

        # ==================================================
        # AÇÕES
        # ==================================================
        with st.container(horizontal=True):

            botao_salvar_despesa = st.button(
                "Salvar",
                type="primary",
                icon=":material/save:"
            )

            area_notif_despesas = st.container()

        # ==================================================
        # AÇÃO: SALVAR
        # ==================================================
        if botao_salvar_despesa:

            erros_campos = []
            erro_consistencia = None

            # --------------------------------------------------
            # Validação dos campos obrigatórios
            # --------------------------------------------------
            if not data_despesa:
                erros_campos.append("Data da despesa")

            if not valor or valor <= 0:
                erros_campos.append("Valor (reais)")

            if not descricao or not descricao.strip():
                erros_campos.append("Descrição da despesa")

            if not fornecedor or not fornecedor.strip():
                erros_campos.append("Fornecedor")

            if not cpf_cnpj or not cpf_cnpj.strip():
                erros_campos.append("CPF / CNPJ")

            # --------------------------------------------------
            # Validação dos anexos
            # --------------------------------------------------
            if not is_taxa_bancaria:

                if not anexos or len(anexos) == 0:
                    erros_campos.append("Anexos")

            # --------------------------------------------------
            # Exibição de mensagens
            # --------------------------------------------------
            if erros_campos:

                campos = ", ".join(erros_campos)

                area_notif_despesas.warning(
                    f"Preencha os seguintes campos obrigatórios: {campos}"
                )

            if erro_consistencia:
                area_notif_despesas.warning(
                    erro_consistencia
                )

            # --------------------------------------------------
            # Interrupção do fluxo em caso de erro
            # --------------------------------------------------
            if erros_campos or erro_consistencia:
                st.stop()

            # ==================================================
            # SALVAMENTO
            # ==================================================
            with area_notif_despesas.spinner(
                "Salvando despesa..."
            ):

                novo_lancamento = {
                    "id_lanc_despesa": id_despesa,
                    "relatorio_numero": relatorio_numero,
                    "data_despesa": data_despesa.strftime("%d/%m/%Y"),
                    "descricao_despesa": descricao,
                    "fornecedor": fornecedor,
                    "cpf_cnpj": cpf_cnpj,
                    "valor_despesa": valor,
                    "status_despesa": "aberto",
                    "anexos": []
                }

                # --------------------------------------------------
                # Upload dos anexos no Google Drive
                # --------------------------------------------------
                servico = obter_servico_drive()

                pasta_projeto = obter_pasta_projeto(
                    servico,
                    projeto["codigo"],
                    projeto["sigla"]
                )

                pasta_financeiro = (
                    obter_pasta_relatos_financeiros(
                        servico,
                        pasta_projeto
                    )
                )

                pasta_lanc = obter_ou_criar_pasta(
                    servico,
                    id_despesa,
                    pasta_financeiro
                )

                for arq in anexos:

                    id_drive = enviar_arquivo_drive(
                        servico,
                        pasta_lanc,
                        arq
                    )

                    novo_lancamento["anexos"].append({
                        "nome_arquivo": arq.name,
                        "id_arquivo": id_drive
                    })

                # --------------------------------------------------
                # Inserção do lançamento no orçamento
                # --------------------------------------------------
                for d in projeto["financeiro"]["orcamento"]:

                    if (
                        d["categoria"] == categoria
                        and d["nome_despesa"] == nome_despesa
                    ):

                        d.setdefault(
                            "lancamentos",
                            []
                        ).append(novo_lancamento)

                        break

                # --------------------------------------------------
                # Persistência no MongoDB
                # --------------------------------------------------
                col_projetos.update_one(
                    {"codigo": projeto["codigo"]},
                    {
                        "$set": {
                            "financeiro.orcamento":
                            projeto["financeiro"]["orcamento"]
                        }
                    }
                )

            # --------------------------------------------------
            # Reset do formulário
            # --------------------------------------------------
            st.session_state["form_despesa_key"] += 1

            area_notif_despesas.success(
                "Despesa registrada com sucesso!",
                icon=":material/check:"
            )

            time.sleep(3)

            st.rerun()






# ==========================================================
# LOCALIZA UMA ATIVIDADE NO DOCUMENTO DO PROJETO
# ==========================================================
def obter_atividade_mongo(projeto, id_atividade):
    """
    Percorre plano_trabalho → componentes → atividades
    e retorna a atividade correspondente ao id informado.
    """

    componentes = projeto.get("plano_trabalho", {}).get("componentes", [])

    for componente in componentes:
        for atividade in componente.get("atividades", []):
                if atividade.get("id") == id_atividade:
                    return atividade

    return None


# ==========================================================
# LISTA OS RELATOS DE UMA ATIVIDADE (UI)
# ==========================================================
def listar_relatos_atividade(atividade, relatorio_numero):
    """
    Lista os relatos cadastrados para a atividade,
    filtrando pelo relatório atual.
    """

    relatos = atividade.get("relatos", [])

    relatos = [
        r for r in relatos
        if r.get("relatorio_numero") == relatorio_numero
    ]

    if not relatos:
        st.info("Nenhum relato cadastrado para esta atividade neste relatório.")
        return

    for relato in relatos:
        with st.expander(
            f"{relato.get('id_relato')} — {relato.get('quando')}"
        ):
            st.write(f"Relato: {relato.get('relato')}")
            st.write(f"Onde: {relato.get('onde', '—')}")
            st.write(f"Autor: {relato.get('autor', '—')}")

            if relato.get("anexos"):
                st.write("Anexos:")
                for a in relato["anexos"]:
                    st.write(f"- {a['nome_arquivo']}")

            if relato.get("fotos"):
                st.write("Fotografias:")
                for f in relato["fotos"]:
                    st.write(
                        f"- {f.get('nome_arquivo')} | "
                        f"{f.get('descricao', '')} | "
                        f"{f.get('fotografo', '')}"
                    )





# Função para salvar o relato
def salvar_relato():
    """
    Salva um relato de atividade:
    - valida campos obrigatórios
    - cria pastas no Google Drive (Relatos_atividades/relato_xxx)
    - envia anexos e fotos
    - grava no MongoDB
    - limpa o session_state
    - executa rerun ao final
    """

    # --------------------------------------------------
    # 1. CAMPOS DO FORMULÁRIO
    # --------------------------------------------------
    texto_relato = st.session_state.get("campo_relato", "")
    data_inicio = st.session_state.get("campo_data_inicio")
    data_fim = st.session_state.get("campo_data_fim")
    anexos = st.session_state.get("campo_anexos", [])
    fotos = st.session_state.get("fotos_relato", [])
    porcentagem_atividade = st.session_state.get("campo_porcentagem_atividade", 0)

    # --------------------------------------------------
    # 2. VALIDAÇÕES
    # --------------------------------------------------
    erros = []
    if not texto_relato.strip():
        erros.append("O campo Relato é obrigatório.")
    # --------------------------------------------------
    # VALIDAÇÃO DAS DATAS
    # --------------------------------------------------

    if not data_inicio:
        erros.append("O campo Data de início é obrigatório.")

    if not data_fim:
        erros.append("O campo Data de fim é obrigatório.")

    if erros:
        for e in erros:
            st.error(e)
        return

    # --------------------------------------------------
    # 3. CONEXÃO COM GOOGLE DRIVE
    # --------------------------------------------------
    servico = obter_servico_drive()

    projeto = st.session_state.get("projeto_mongo")
    if not projeto:
        st.error("Projeto não encontrado na sessão.")
        return

    codigo = projeto["codigo"]
    sigla = projeto["sigla"]

    # Pasta do projeto (padrão já usado em Locais)
    pasta_projeto_id = obter_pasta_projeto(
        servico,
        codigo,
        sigla
    )

    # Pasta Relatos_atividades
    pasta_relatos_id = obter_ou_criar_pasta(
        servico,
        "Relatos_atividades",
        pasta_projeto_id
    )

    # --------------------------------------------------
    # 4. ATIVIDADE SELECIONADA
    # --------------------------------------------------
    atividade = st.session_state.get("atividade_selecionada_drive")
    if not atividade:
        st.error("Atividade não selecionada.")
        return

    id_atividade = atividade.get("id")

    # --------------------------------------------------
    # 5. LOCALIZA ATIVIDADE NO MONGO
    # --------------------------------------------------
    atividade_mongo = obter_atividade_mongo(projeto, id_atividade)
    if not atividade_mongo:
        st.error("Atividade não encontrada no banco de dados.")
        return

   
    # --------------------------------------------------
    # GERA ID DE RELATO GLOBALMENTE ÚNICO
    # --------------------------------------------------
    maior_numero = 0

    for componente in projeto["plano_trabalho"]["componentes"]:
        for atividade in componente["atividades"]:
                for relato in atividade.get("relatos", []):
                    id_existente = relato.get("id_relato", "")
                    if id_existente.startswith("relato_"):
                        try:
                            numero = int(id_existente.replace("relato_", ""))
                            maior_numero = max(maior_numero, numero)
                        except ValueError:
                            pass

    # Próximo número disponível
    novo_numero = maior_numero + 1
    id_relato = f"relato_{novo_numero:03d}"




    # --------------------------------------------------
    # 6. PASTA DO RELATO (DIRETAMENTE EM Relatos_atividades)
    # --------------------------------------------------
    pasta_relato_id = obter_ou_criar_pasta(
        servico,
        id_relato,
        pasta_relatos_id
    )


    # --------------------------------------------------
    # 7. UPLOAD DE ANEXOS
    # --------------------------------------------------
    lista_anexos = []

    if anexos:
        pasta_anexos_id = obter_ou_criar_pasta(
            servico,
            "anexos",
            pasta_relato_id
        )

        for arq in anexos:
            id_drive = enviar_arquivo_drive(
                servico,
                pasta_anexos_id,
                arq
            )

            if id_drive:
                lista_anexos.append({
                    "nome_arquivo": arq.name,
                    "id_arquivo": id_drive
                })



    # --------------------------------------------------
    # 8. UPLOAD DE FOTOGRAFIAS
    # --------------------------------------------------
    lista_fotos = []

    fotos_validas = [
        f for f in fotos
        if f.get("arquivo") is not None
    ]



    if fotos_validas:

        # --------------------------------------------------
        # CRIA PASTA FOTOS (SE NÃO EXISTIR)
        # --------------------------------------------------
        # Verifica se já existe antes
        consulta = (
            f"name='fotos' and "
            f"'{pasta_relato_id}' in parents and "
            f"mimeType='application/vnd.google-apps.folder' and trashed=false"
        )

        resultado = servico.files().list(
            q=consulta,
            fields="files(id)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        arquivos = resultado.get("files", [])

        if arquivos:
            pasta_fotos_id = arquivos[0]["id"]
        else:
            # Cria pasta
            pasta_fotos_id = obter_ou_criar_pasta(
                servico,
                "fotos",
                pasta_relato_id
            )


            # DEFINE PERMISSÃO PÚBLICA na pasta de fotos de cada relato
            garantir_permissao_publica_leitura(servico, pasta_fotos_id)


        for foto in fotos_validas:
            arq = foto["arquivo"]

            id_drive = enviar_arquivo_drive(
                servico,
                pasta_fotos_id,
                arq
            )

            if id_drive:
                lista_fotos.append({
                    "nome_arquivo": arq.name,
                    "descricao": foto.get("descricao", ""),
                    "fotografo": foto.get("fotografo", ""),
                    "id_arquivo": id_drive
                })




    # --------------------------------------------------
    # 9. OBJETO FINAL DO RELATO
    # --------------------------------------------------
    

    data_inicio_str = data_inicio.strftime("%d/%m/%Y") if data_inicio else None
    data_fim_str = data_fim.strftime("%d/%m/%Y") if data_fim else None    
    

    novo_relato = {
        "id_relato": id_relato,
        "status_relato": "aberto",
        "relatorio_numero": st.session_state.get("relatorio_numero"),
        "relato": texto_relato.strip(),

        "data_inicio": data_inicio_str,
        "data_fim": data_fim_str,

        "porc_ativ_relato": int(porcentagem_atividade),

        "autor": st.session_state.get("nome", "Usuário")
    }



    if lista_anexos:
        novo_relato["anexos"] = lista_anexos

    if lista_fotos:
        novo_relato["fotos"] = lista_fotos

    atividade_mongo.setdefault("relatos", []).append(novo_relato)

    col_projetos.update_one(
        {"codigo": codigo},
        {
            "$set": {
                "plano_trabalho.componentes": projeto["plano_trabalho"]["componentes"]
            }
        }
    )

    # --------------------------------------------------
    # 10. LIMPEZA DO SESSION_STATE (CRÍTICO)
    # --------------------------------------------------

    for chave in [
        "campo_relato",
        "campo_data_inicio",
        "campo_data_fim",
        "campo_porcentagem_atividade",
        "campo_anexos",
        "fotos_relato"
    ]:

        if chave in st.session_state:
            del st.session_state[chave]

    # Remove chaves dinâmicas das fotos
    for k in list(st.session_state.keys()):
        if k.startswith("foto_"):
            del st.session_state[k]

    # --------------------------------------------------
    # 11. FINALIZAÇÃO
    # --------------------------------------------------
    st.success("Relato salvo com sucesso.", icon=":material/check:")
    time.sleep(3)
    st.rerun()


# Função auxiliar para o salvar_relato, que dá permissão de leitura pública para a pasta de fotos no ato da criação da pasta no drivce
def garantir_permissao_publica_leitura(servico, pasta_id):
    """
    Define permissão:
    Qualquer pessoa com o link → Leitor
    (somente se ainda não existir)
    """

    try:
        servico.permissions().create(
            fileId=pasta_id,
            body={
                "type": "anyone",
                "role": "reader"
            },
            supportsAllDrives=True
        ).execute()
    except Exception as e:
        st.error(f"Erro ao definir permissão: {str(e)}")
        raise




# ==========================================================================================
# DIÁLOGO: RELATAR ATIVIDADE
# ==========================================================================================


def renderizar_formulario_relato():

# @st.dialog("Relatar atividade", width="medium")
# def dialog_relatos():

    projeto = st.session_state.get("projeto_mongo")
    if not projeto:
        st.error("Projeto não encontrado.")
        return

    # --------------------------------------------------
    # 1. MONTA LISTA DE ATIVIDADES
    # --------------------------------------------------
    atividades = []

    for componente in projeto["plano_trabalho"]["componentes"]:
        for atividade in componente["atividades"]:
                atividades.append({
                    "id": atividade["id"],
                    "atividade": atividade["atividade"],
                    "componente": componente["componente"],
                    "data_inicio": atividade.get("data_inicio"),
                    "data_fim": atividade.get("data_fim"),
                    "relatos": atividade.get("relatos", [])
                })

    if not atividades:
        st.info("Nenhuma atividade cadastrada.")
        time.sleep(3)
        return

    # --------------------------------------------------
    # 2. SELECTBOX COM OPÇÃO VAZIA
    # --------------------------------------------------
    atividades_com_placeholder = (
        [{"id": None, "atividade": ""}]
        + atividades
    )

    atividade_selecionada = st.selectbox(
        "Selecione a atividade *",
        atividades_com_placeholder,
        format_func=lambda x: x["atividade"],
        key="atividade_select_dialog"
    )




    # recupera datas da atividade selecionada
    data_inicio_atv = None
    data_fim_atv = None

    if atividade_selecionada and atividade_selecionada.get("id"):

        atividade_mongo = obter_atividade_mongo(
            projeto,
            atividade_selecionada["id"]
        )

        if atividade_mongo:
            data_inicio_atv = atividade_mongo.get("data_inicio")
            data_fim_atv = atividade_mongo.get("data_fim")

    # # mostra período programado da atividade
    # if data_inicio_atv and data_fim_atv:
    #     st.write(
    #         f"Programada para começar em **{data_inicio_atv}** e terminar em **{data_fim_atv}**."
    #     )

        # st.write('')







    # SELECTBOX DE PORCENTAGEM DE EXECUÇÃO DA ATIVIDADE

    # opções de porcentagem
    porcentagens = list(range(0, 101, 10))

    porcentagem_atual = 0

    # busca a porcentagem atual da atividade selecionada
    if atividade_selecionada and atividade_selecionada.get("id"):

        atividade_mongo = obter_atividade_mongo(
            projeto,
            atividade_selecionada["id"]
        )

        if atividade_mongo:
            porcentagem_atual = atividade_mongo.get("porcentagem_atv", 0)

    # garante que esteja dentro das opções
    if porcentagem_atual not in porcentagens:
        porcentagem_atual = 0

    # sincroniza o session_state quando a atividade muda
    if (
        "campo_porcentagem_atividade" not in st.session_state
        or st.session_state.get("atividade_porcentagem_ref") != atividade_selecionada.get("id")
    ):
        st.session_state["campo_porcentagem_atividade"] = porcentagem_atual
        st.session_state["atividade_porcentagem_ref"] = atividade_selecionada.get("id")

    # selectbox de porcentagem
    porcentagem_escolhida = st.selectbox(
        "Atualize a porcentagem de execução da atividade *",
        options=porcentagens,
        format_func=lambda x: f"{x}%",
        key="campo_porcentagem_atividade",
        width=300
    )






    # Salva no session_state (mesmo vazia, para validação)
    st.session_state["atividade_selecionada"] = atividade_selecionada
    st.session_state["atividade_selecionada_drive"] = atividade_selecionada



    

    # ==================================================
    # 3. FORMULÁRIO DO RELATO
    # ==================================================
    @st.fragment
    def corpo_formulario():

        st.divider()

        # -----------------------------
        # CAMPOS BÁSICOS
        # -----------------------------
        st.text_area(
            "Relato *",
            placeholder="Descreva o que foi feito",
            key="campo_relato"
        )


        # --------------------------------------------------
        # CAMPOS DE DATA DO RELATO
        # --------------------------------------------------
        # Substitui os campos "Quando" e "Onde" por
        # "Data de início" e "Data de fim".
        # Utiliza st.date_input para garantir formato válido.

        col1, col2 = st.columns(2)

        col1.date_input(
            "Data de início *",
            key="campo_data_inicio",
            format="DD/MM/YYYY"
        )

        col2.date_input(
            "Data de fim *",
            key="campo_data_fim",
            format="DD/MM/YYYY"
        )


        st.divider()

        # -----------------------------
        # ANEXOS
        # -----------------------------
        st.write("**Anexos**")
        st.write("Adicione aqui todos os anexos relevantes para esse relato: listas de presença, relatórios, publicações, etc.")
        st.write("Você pode adicionar vários arquivos de uma só vez. **Não inclua fotos aqui**.")
        st.write("")
        
        st.file_uploader(
            "Selecione um ou vários arquivos.",
            type=["pdf", "docx", "xlsx", "csv", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="campo_anexos"
        )

        st.divider()


        # -----------------------------
        # FOTOGRAFIAS
        # -----------------------------
        st.write("**Fotografias**")

        st.write("Selecione aqui todas as **fotografias** relevantes para esse relato.")
        st.write("Você pode adicionar várias fotografias, mas uma de cada vez. Clique no botão **'Adicionar fotografia'** sempre que quiser adicionar mais uma.")


        if "fotos_relato" not in st.session_state:
            st.session_state["fotos_relato"] = []

        st.write('')
        # Botão para adicionar
        if st.button("Adicionar fotografia", icon=":material/add_a_photo:"):
            # Usamos um ID único para cada foto em vez de apenas o índice

            st.session_state["fotos_relato"].append({
                "id": str(uuid.uuid4()), 
                "arquivo": None,
                "descricao": "",
                "fotografo": ""
            })
            st.rerun(scope="fragment") # Atualiza APENAS o fragmento

        # Iteramos sobre uma cópia da lista para evitar erros de índice ao deletar
        for i, foto in enumerate(st.session_state["fotos_relato"]):
            # Criamos uma chave única baseada no ID gerado, não apenas no índice i
            # Isso evita que o Streamlit confunda os campos após uma remoção
            foto_id = foto["id"]
            
            with st.container(border=True):
                col_info, col_delete = st.columns([8, 2])
                col_info.write(f"Fotografia {i+1}")
                

                with col_delete.container(horizontal=True, horizontal_alignment="right"):

                    if st.button("", 
                                        key=f"btn_del_{foto_id}", 
                                        help="Remover foto", 
                                        icon=":material/close:",
                                        type="tertiary"):
                        
                        st.session_state["fotos_relato"].pop(i)
                        st.rerun(scope="fragment") # O "pulo do gato": atualiza só o fragmento

                arquivo_foto = st.file_uploader(
                    "Selecione a foto",
                    type=["jpg", "jpeg", "png"],
                    key=f"file_{foto_id}"
                )

                descricao = st.text_input(
                    "Descrição da foto",
                    key=f"desc_{foto_id}"
                )

                fotografo = st.text_input(
                    "Nome do(a) fotógrafo(a)",
                    key=f"autor_{foto_id}"
                )

            # Sincronização
            foto["arquivo"] = arquivo_foto
            foto["descricao"] = descricao
            foto["fotografo"] = fotografo




        # --------------------------------------------------
        # AÇÕES FINAIS: BOTÕES + VALIDAÇÃO + SPINNER
        # --------------------------------------------------
        st.write('')
        with st.container(horizontal=True):

            # Botão salvar
            salvar = st.button(
                "Salvar relato",
                type="primary",
                icon=":material/save:"
            )

            # Botão cancelar
            cancelar = st.button("Cancelar")

        if salvar:

            erros = []

            # Valida atividade
            if not atividade_selecionada.get("id"):
                erros.append("Selecione uma atividade.")

            # Valida campos obrigatórios
            if not st.session_state.get("campo_relato", "").strip():
                erros.append("O campo Relato é obrigatório.")

            # VALIDAÇÃO DAS DATAS
            # Verifica se ambas as datas foram informadas.

            data_inicio = st.session_state.get("campo_data_inicio")
            data_fim = st.session_state.get("campo_data_fim")

            if not data_inicio:
                erros.append("O campo Data de início é obrigatório.")

            if not data_fim:
                erros.append("O campo Data de fim é obrigatório.")


            # Mostra erros (mesma funcionalidade de antes)
            if erros:
                for e in erros:
                    st.error(e)
                return

            # Se passou na validação, salva
            with st.spinner("Salvando, aguarde..."):
                salvar_relato()

            st.success("Relato salvo com sucesso.")
            st.rerun()

        # Cancelar apenas faz rerun
        if cancelar:
            st.rerun()

    corpo_formulario()






# Função para liberar o próximo relatório quando o relatório anterior for aprovado
def liberar_proximo_relatorio(projeto_codigo, relatorios):
    """
    Se um relatório estiver aprovado, libera o próximo
    caso ele esteja como 'aguardando'.
    """
    for i in range(len(relatorios) - 1):
        status_atual = relatorios[i].get("status_relatorio")
        status_proximo = relatorios[i + 1].get("status_relatorio")

        if status_atual == "aprovado" and status_proximo == "aguardando":
            col_projetos.update_one(
                {
                    "codigo": projeto_codigo,
                    "relatorios.numero": relatorios[i + 1]["numero"]
                },
                {
                    "$set": {
                        "relatorios.$.status_relatorio": "modo_edicao"
                    }
                }
            )




# Renderiza as perguntas em modo visualização
def renderizar_visualizacao(pergunta, resposta):
    """
    Renderiza pergunta em negrito e resposta em texto normal
    """
    st.markdown(f"**{pergunta}**")
    if resposta in [None, "", [], {}]:
        st.write("—")
    else:
        st.write(resposta)
    st.write("")



# Atualiza o status do relatório no banco de dados, apoiando o segmented_control

STATUS_UI_TO_DB = {
    "Modo edição": "modo_edicao",
    "Em análise": "em_analise",
    "Aprovado": "aprovado",
}

STATUS_DB_TO_UI = {v: k for k, v in STATUS_UI_TO_DB.items()}




def atualizar_status_relatorio(idx, relatorio_numero, projeto_codigo):
    """
    Atualiza o status do relatório no MongoDB quando o segmented_control muda.

    Regras de sincronização dos relatos:

    A) Se o relatório voltar de 'em_analise' ou 'aprovado' para 'modo_edicao':
       - relatos deste relatório com status 'em_analise' voltam para 'aberto'

    B) Se o relatório sair de 'modo_edicao' para 'em_analise' ou 'aprovado':
       - relatos deste relatório com status 'aberto' passam para 'em_analise'
    """

    # --------------------------------------------------
    # 1. STATUS SELECIONADO NA UI
    # --------------------------------------------------
    status_ui = st.session_state.get(f"status_relatorio_{idx}")
    status_novo = STATUS_UI_TO_DB.get(status_ui)

    if not status_novo:
        return  # segurança extra

    # --------------------------------------------------
    # 2. BUSCA STATUS ATUAL DO RELATÓRIO NO BANCO
    # --------------------------------------------------
    projeto = col_projetos.find_one(
        {
            "codigo": projeto_codigo,
            "relatorios.numero": relatorio_numero
        },
        {
            "relatorios.$": 1
        }
    )

    if not projeto or "relatorios" not in projeto:
        return

    relatorio = projeto["relatorios"][0]
    status_anterior = relatorio.get("status_relatorio")

    # --------------------------------------------------
    # 3. ATUALIZA STATUS DO RELATÓRIO
    # --------------------------------------------------
    col_projetos.update_one(
        {
            "codigo": projeto_codigo,
            "relatorios.numero": relatorio_numero
        },
        {
            "$set": {
                "relatorios.$.status_relatorio": status_novo
            }
        }
    )

    # --------------------------------------------------
    # 4. VERIFICA SE ALGUMA REGRA DE RELATOS SE APLICA
    # --------------------------------------------------
    aplica_regra_a = (
        status_novo == "modo_edicao"
        and status_anterior in ["em_analise", "aprovado"]
    )

    aplica_regra_b = (
        status_anterior == "modo_edicao"
        and status_novo in ["em_analise", "aprovado"]
    )

    if not (aplica_regra_a or aplica_regra_b):
        return  # nada a fazer nos relatos

    # --------------------------------------------------
    # 5. RECARREGA O PROJETO COMPLETO
    # --------------------------------------------------
    projeto_atualizado = col_projetos.find_one(
        {"codigo": projeto_codigo}
    )

    componentes = projeto_atualizado["plano_trabalho"]["componentes"]
    houve_alteracao = False

    # --------------------------------------------------
    # 6. APLICA AS REGRAS NOS RELATOS
    # --------------------------------------------------
    # ------------------------------------------------------------------
    # Percorre todos os componentes
    # ------------------------------------------------------------------
    for componente in componentes:

        # Recupera atividades de forma segura
        atividades = componente.get("atividades", [])

        # Se não houver atividades, continua
        if not atividades:
            continue

        # ------------------------------------------------------------------
        # Percorre atividades
        # ------------------------------------------------------------------
        for atividade in atividades:

            # --------------------------------------------------------------
            # Se não tiver atividades, apenas ignora
            # --------------------------------------------------------------
            if not atividades:
                continue

            # --------------------------------------------------------------
            # Percorre atividades
            # --------------------------------------------------------------
            else:

                # Recupera relatos de forma segura
                relatos = atividade.get("relatos", [])

                # Se não houver relatos, continua
                if not relatos:
                    continue

                # ----------------------------------------------------------
                # Percorre relatos
                # ----------------------------------------------------------
                for relato in relatos:

                    # Apenas relatos do relatório atual
                    if relato.get("relatorio_numero") != relatorio_numero:
                        continue

                    # Regra A: em_analise -> aberto
                    if aplica_regra_a and relato.get("status_relato") == "em_analise":
                        relato["status_relato"] = "aberto"
                        houve_alteracao = True

                    # Regra B: aberto -> em_analise
                    if aplica_regra_b and relato.get("status_relato") == "aberto":
                        relato["status_relato"] = "em_analise"
                        houve_alteracao = True


    # --------------------------------------------------
    # 7. SALVA NO BANCO APENAS SE HOUVE ALTERAÇÃO
    # --------------------------------------------------
    if houve_alteracao:
        col_projetos.update_one(
            {"codigo": projeto_codigo},
            {
                "$set": {
                    "plano_trabalho.componentes": componentes
                }
            }
        )







def extrair_atividades(projeto):
    atividades = []

    plano = projeto.get("plano_trabalho", {})
    componentes = plano.get("componentes", [])

    for componente in componentes:
        for atividade in componente.get("atividades", []):
                atividades.append({
                    "id": atividade.get("id"),
                    "nome": atividade.get("atividade"),
                    "data_inicio": atividade.get("data_inicio"),
                    "data_fim": atividade.get("data_fim"),
                    "componente": componente.get("componente"),
                })

    return atividades



# Função para formatar números no padrão brasileiro, com poucas casas decimais (dinamicamente)
def formatar_numero_br_dinamico(valor):
    """
    Formata número no padrão brasileiro:
    - Sem decimais → não mostra casas
    - 1 decimal → mostra 1 casa
    - 2+ decimais → mostra até 2 casas (sem zeros desnecessários)
    """
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return "—"

    # Verifica parte decimal
    inteiro = int(valor)
    decimal = abs(valor - inteiro)

    # Define casas decimais dinamicamente
    if decimal == 0:
        casas = 0
    elif round(decimal * 10) == decimal * 10:
        casas = 1
    else:
        casas = 2

    texto = f"{valor:,.{casas}f}"

    # Converte para padrão pt-BR
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")

# Função para formatar números no padrão brasileiro na aba de Indicadores de Resultados
def parse_numero_br(valor_str):
    """
    Converte string no formato brasileiro para float.
    Ex:
    - '50,15' -> 50.15
    - '1.234,56' -> 1234.56
    """
    if valor_str is None:
        return None

    valor_str = valor_str.strip()

    if not valor_str:
        return None

    try:
        return float(
            valor_str.replace(".", "").replace(",", ".")
        )
    except ValueError:
        return None


def data_hoje_br():
    return datetime.datetime.now().strftime("%d/%m/%Y")




###########################################################################################################
# TRATAMENTO DOS DADOS E CONTROLES DE SESSÃO
###########################################################################################################


# Libera automaticamente o próximo relatório, se aplicável
liberar_proximo_relatorio(projeto["codigo"], relatorios)

# Recarrega o projeto para refletir possíveis mudanças
projeto = col_projetos.find_one({"codigo": projeto["codigo"]})
relatorios = projeto.get("relatorios", [])




# -------------------------------------------
# CONTROLE DE STEP DO RELATÓRIO
# -------------------------------------------

if "step_relatorio" not in st.session_state:
    st.session_state.step_relatorio = "Atividades"




###########################################################################################################
# INTERFACE PRINCIPAL DA PÁGINA
###########################################################################################################

# Logo hospedada no site do IEB para renderizar nos e-mails.
logo_cepf = "https://fundoecos.org.br/wp-content/uploads/2025/05/Logo-Fundo-Ecos-PNG-sem-fundo-sem-margem.png"


# Logo do sidebar
st.logo("images/logo_fundo_ecos.png", size='large')

# Título da página e identificação
col_titulo, col_identificacao = st.columns([3, 2])

with col_titulo:
    st.header("Relatórios")

with col_identificacao:
    st.markdown(
        f"<div style='text-align: right; margin-top: 30px;'>{df_projeto['codigo'].values[0]} - {df_projeto['sigla'].values[0]}</div>",
        unsafe_allow_html=True
    )


st.write('')
st.write('')







###########################################################################################################
# CONFIGURAÇÃO DOS STEPS DO RELATÓRIO
###########################################################################################################



if tipo_usuario in ["admin", "equipe"]:
    steps_relatorio = [
        "Atividades",
        "Despesas",
        "Indicadores",
        "Beneficiários",
        "Formulário",
        "Avaliação"
    ]
else:
    steps_relatorio = [
        "Atividades",
        "Despesas",
        "Indicadores",
        "Beneficiários",
        "Formulário",
        "Enviar"
    ]


###########################################################################################################
# VERIFICA SE EXISTEM RELATÓRIOS
###########################################################################################################

if not relatorios:
    st.warning("Este projeto ainda não possui relatórios cadastrados.")
    st.stop()

###########################################################################################################
# ABAS DOS RELATÓRIOS (sac.tabs)
###########################################################################################################

labels_relatorios = [f"Relatório {r.get('numero')}" for r in relatorios]

aba_selecionada = sac.tabs(
    items=[sac.TabsItem(label=l) for l in labels_relatorios],
    align="left",
    variant="outline",
    key="tabs_relatorios"
    # size="xl"
)

idx = labels_relatorios.index(aba_selecionada)
relatorio = relatorios[idx]

###########################################################################################################
# DADOS DO RELATÓRIO
###########################################################################################################

relatorio_numero = relatorio["numero"]
projeto_codigo = projeto["codigo"]

st.subheader(f"Relatório {relatorio_numero}")

###########################################################################################################
# STATUS ATUAL DO RELATÓRIO
###########################################################################################################

status_atual_db = relatorio.get("status_relatorio", "modo_edicao")
status_atual_ui = STATUS_DB_TO_UI.get(status_atual_db, "Modo edição")

aguardando = False

###########################################################################################################
# CONTROLE CENTRAL DE PERMISSÃO DE EDIÇÃO
###########################################################################################################

pode_editar_relatorio = (
    status_atual_db == "modo_edicao"
    and tipo_usuario == "beneficiario"
)

###########################################################################################################
# CONTROLE DE ESTADO – NOVA COMUNIDADE
###########################################################################################################

if f"mostrar_nova_comunidade_{idx}" not in st.session_state:
    st.session_state[f"mostrar_nova_comunidade_{idx}"] = False

###########################################################################################################
# REGRA DE BLOQUEIO (a partir do 2º relatório)
###########################################################################################################

if idx > 0:
    status_anterior = relatorios[idx - 1].get("status_relatorio")

    if status_anterior != "aprovado":
        aguardando = True

        col_projetos.update_one(
            {
                "codigo": projeto_codigo,
                "relatorios.numero": relatorio_numero,
                "relatorios.status_relatorio": {"$ne": "aguardando"}
            },
            {
                "$set": {
                    "relatorios.$.status_relatorio": "aguardando"
                }
            }
        )

        status_atual_ui = "Modo edição"

###########################################################################################################
# MENSAGEM DE STATUS DO RELATÓRIO PARA BENEFICIÁRIO E VISITANTE
###########################################################################################################

if tipo_usuario in ["beneficiario", "visitante"]:

    if status_atual_db == "em_analise":
        st.write("")
        st.warning("Relatório em análise. Aguarde o retorno.", icon=":material/manage_search:")

    elif status_atual_db == "aprovado":
        st.write("")
        st.success("Relatório aprovado", icon=":material/check:")

###########################################################################################################
# SINCRONIZA STATUS DO RELATÓRIO COM A UI
###########################################################################################################

status_key = f"status_relatorio_{idx}"
status_atual_ui = STATUS_DB_TO_UI.get(status_atual_db, "Modo edição")

if st.session_state.get(status_key) != status_atual_ui:
    st.session_state[status_key] = status_atual_ui

###########################################################################################################
# SEGMENTED CONTROL (somente equipe interna)
###########################################################################################################

if tipo_usuario in ["equipe", "admin"]:
    with st.container(horizontal=True, horizontal_alignment="center"):
        st.segmented_control(
            label="Status do relatório",
            label_visibility="collapsed",
            options=["Modo edição", "Em análise", "Aprovado"],
            key=f"status_relatorio_{idx}",
            disabled=aguardando,
            on_change=atualizar_status_relatorio if not aguardando else None,
            args=(idx, relatorio_numero, projeto_codigo) if not aguardando else None
        )




###########################################################################################################
# MENSAGEM DE AGUARDO + STEPS DO RELATÓRIO
###########################################################################################################

labels_steps = steps_relatorio

if aguardando:
    st.write("")
    st.info(
        "Aguardando a aprovação do relatório anterior.",
        icon=":material/nest_clock_farsight_analog:"
    )
    step_selecionado = None  # importante para evitar uso depois
else:
    st.write("")
    st.write("")

    step_selecionado = sac.tabs(
        items=[sac.TabsItem(label=s) for s in labels_steps],
        align="start",
        use_container_width=True,
        key=f"steps_relatorio_{idx}"
        # size="md"
    )





###########################################################################################################
# CONTEÚDO DOS STEPS
###########################################################################################################










# ---------- ATIVIDADES ----------

if step_selecionado == "Atividades":

    # Guarda para uso no diálogo e no salvar_relato
    st.session_state["projeto_mongo"] = projeto
    st.session_state["relatorio_numero"] = relatorio_numero

    st.write("")
    st.write("")

    st.markdown("#### Relatos de atividades")
    st.write('')


    # --------------------------------------------------
    # FORMULÁRIO DE NOVO RELATO
    # --------------------------------------------------
    if pode_editar_relatorio:

        with st.expander(
            "Relatar atividade",
            expanded=False
        ):

            renderizar_formulario_relato()


    # --------------------------------------------------
    # LISTAGEM DE TODOS OS RELATOS DO RELATÓRIO
    # AGRUPADOS POR ATIVIDADE
    # --------------------------------------------------

    if "relato_editando_id" not in st.session_state:
        st.session_state["relato_editando_id"] = None

    tem_relato = False

    # ------------------------------------------------------------------
    # Percorre componentes do plano de trabalho
    # ------------------------------------------------------------------
    for componente in projeto["plano_trabalho"]["componentes"]:

        # Recupera atividades do componente de forma segura
        atividades = componente.get("atividades", [])

        # Caso o componente não tenha atividades, apenas continua
        if not atividades:
            continue

        # ------------------------------------------------------------------
        # Percorre atividades
        # ------------------------------------------------------------------
        for atividade in atividades:

            # ----------------------------------------------------------
            # Filtra relatos do relatório atual
            # ----------------------------------------------------------
            relatos = [
                r for r in atividade.get("relatos", [])
                if r.get("relatorio_numero") == relatorio_numero
            ]

            # Se não há relatos para essa atividade, pula
            if not relatos:
                continue

            tem_relato = True

            st.write("")
            st.markdown(f"#### {atividade['atividade']}")




            for relato in relatos:

                id_relato = relato["id_relato"]
                editando = st.session_state["relato_editando_id"] == id_relato

                # --------------------------------------------------
                # GARANTE QUE WIDGETS DE VISUALIZAÇÃO NÃO EXISTAM EM EDIÇÃO
                # --------------------------------------------------
                if editando:
                    # remove qualquer state de devolutiva para evitar conflito
                    st.session_state.pop(f"devolutiva_{id_relato}", None)
                    st.session_state.pop(f"status_relato_ui_{id_relato}", None)


                with st.container(border=True):

                    # ==================================================
                    # MODO VISUALIZAÇÃO DO RELATO
                    # ==================================================
                    if not editando:

                        # --------------------------------------------------
                        # Lógica de status visual (depende de devolutiva)
                        # --------------------------------------------------
                        status_relato_db = relato.get("status_relato", "em_analise")
                        tem_devolutiva = bool(relato.get("devolutiva"))

                        # Regras visuais:
                        # - aberto + devolutiva → Pendente (vermelho)
                        # - aberto sem devolutiva → Aberto (amarelo)
                        # - em_analise → Em análise (azul)
                        # - aceito → Aceito (verde)

                        if status_relato_db == "aberto" and tem_devolutiva:
                            badge = {
                                "label": "Pendente",
                                "bg": "#F8D7DA",
                                "color": "#721C24"
                            }
                        elif status_relato_db == "aberto":
                            badge = {
                                "label": "Aberto",
                                "bg": "#FFF3CD",
                                "color": "#856404"
                            }
                        elif status_relato_db == "aceito":
                            badge = {
                                "label": "Aceito",
                                "bg": "#D4EDDA",
                                "color": "#155724"
                            }
                        else:
                            badge = {
                                "label": "Em análise",
                                "bg": "#D1ECF1",
                                "color": "#0C5460"
                            }

                        # --------------------------------------------------
                        # BADGE VISUAL
                        # --------------------------------------------------
                        
                        col1, col2 = st.columns([9, 1])
                        
                        col2.markdown(
                            f"""
                            <div style="margin-bottom:6px;">
                                <span style="
                                    background:{badge['bg']};
                                    color:{badge['color']};
                                    padding:4px 10px;
                                    border-radius:20px;
                                    font-size:12px;
                                    font-weight:600;
                                ">
                                    {badge['label']}
                                </span>
                            </div>
                            """,
                            unsafe_allow_html=True
                            )


                        # --------------------------------------------------
                        # CONTEÚDO DO RELATO
                        # --------------------------------------------------
                        st.write(f"**{id_relato.upper()}:** {relato.get("relato")}")

                        col1, col2 = st.columns([2, 3])

                        col1.write(f"**Data de início:** {relato.get('data_inicio')}")
                        col2.write(f"**Data de fim:** {relato.get('data_fim')}")

                        if relato.get("porc_ativ_relato") is not None:
                            st.write(f"**Progresso da atividade informado:** {relato.get('porc_ativ_relato')}%")

                        # col1.write(f"**Quando:** {relato.get('quando')}")
                        # col2.write(f"**Onde:** {relato.get('onde')}")

                        # --------------------------------------------------
                        # ANEXOS (links do Drive)
                        # --------------------------------------------------
                        if relato.get("anexos"):
                            with col1:
                                c1, c2 = st.columns([1, 5])
                                c1.write("**Anexos:**")
                                for a in relato["anexos"]:
                                    if a.get("id_arquivo"):
                                        link = gerar_link_drive(a["id_arquivo"])
                                        c2.markdown(
                                            f"[{a['nome_arquivo']}]({link})",
                                            unsafe_allow_html=True
                                        )

                        # --------------------------------------------------
                        # FOTOGRAFIAS (links + metadados)
                        # --------------------------------------------------
                        if relato.get("fotos"):
                            with col2:
                                c1, c2 = st.columns([1, 5])
                                c1.write("**Fotografias:**")
                                for f in relato["fotos"]:
                                    if f.get("id_arquivo"):
                                        link = gerar_link_drive(f["id_arquivo"])
                                        linha = f"[{f['nome_arquivo']}]({link})"
                                        if f.get("descricao"):
                                            linha += f" | {f['descricao']}"
                                        if f.get("fotografo"):
                                            linha += f" | {f['fotografo']}"
                                        c2.markdown(linha, unsafe_allow_html=True)









                        # ==========================
                        # STATUS DO RELATO (ADMIN/EQUIPE)
                        # ==========================

                        STATUS_RELATO_LABEL = {
                            "em_analise": "Em análise",
                            "aberto": "Devolver",
                            "aceito": "Aceito"
                        }

                        STATUS_RELATO_LABEL_INV = {v: k for k, v in STATUS_RELATO_LABEL.items()}

                        usuario_admin = tipo_usuario == "admin"
                        usuario_equipe = tipo_usuario == "equipe"

                        if (usuario_admin or usuario_equipe) and status_atual_db == "em_analise":

                            status_relato_db = relato.get("status_relato", "em_analise")
                            status_relato_label = STATUS_RELATO_LABEL.get(status_relato_db, "Em análise")

                            status_key = f"status_relato_ui_{id_relato}"
                            devolutiva_key = f"devolutiva_{id_relato}"

                            if status_key not in st.session_state:
                                st.session_state[status_key] = status_relato_label

                            # --------------------------------------------------
                            # CONTROLE DE STATUS
                            # --------------------------------------------------
                            with st.container(horizontal=True, horizontal_alignment="right"):
                                novo_status_label = st.segmented_control(
                                    label="Status do relato",
                                    label_visibility="collapsed",
                                    options=["Em análise", "Devolver", "Aceito"],
                                    key=status_key
                                )

                            novo_status_db = STATUS_RELATO_LABEL_INV.get(novo_status_label)

                            # --------------------------------------------------
                            # TEXTO DE AUDITORIA (status_aprovacao)
                            # --------------------------------------------------
                            status_aprovacao = relato.get("status_aprovacao")
                            if status_aprovacao:

                                st.markdown(
                                    f"""
                                    <div style="
                                        text-align: right;
                                        color: #6c757d;
                                        font-size: 0.85rem;
                                        margin-top: 4px;
                                    ">
                                        {status_aprovacao}
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                                st.write('')


                                # with st.container(horizontal=True, horizontal_alignment="right"):
                                #     st.caption(status_aprovacao)

                            # ==================================================
                            # CASO DEVOLVER
                            # ==================================================
                            if novo_status_label == "Devolver":

                                if devolutiva_key not in st.session_state:
                                    st.session_state[devolutiva_key] = relato.get("devolutiva", "")

                                st.text_area(
                                    "Devolutiva:",
                                    key=devolutiva_key,
                                    placeholder="Explique o que precisa ser ajustado neste relato..."
                                )

                                tem_devolutiva = bool(st.session_state.get(devolutiva_key, "").strip())
                                label_botao = "Atualizar" if tem_devolutiva else "Salvar devolutiva"

                                with st.container(horizontal=True):

                                    if st.button(
                                        label_botao,
                                        key=f"btn_salvar_devolutiva_{id_relato}",
                                        type="primary",
                                        icon=":material/save:"
                                    ):

                                        nome = st.session_state.get("nome", "Usuário")
                                        data = data_hoje_br()

                                        relato["status_relato"] = "aberto"
                                        relato["devolutiva"] = st.session_state.get(devolutiva_key, "")
                                        relato["status_aprovacao"] = f"Devolvido por {nome} em {data}"

                                        col_projetos.update_one(
                                            {"codigo": projeto["codigo"]},
                                            {
                                                "$set": {
                                                    "plano_trabalho.componentes": projeto["plano_trabalho"]["componentes"]
                                                }
                                            }
                                        )

                                        st.session_state.pop(status_key, None)
                                        st.session_state.pop(devolutiva_key, None)

                                        st.success("Devolutiva salva.", icon=":material/check:")
                                        time.sleep(3)
                                        st.rerun()

                            # ==================================================
                            # CASO EM ANÁLISE OU ACEITO
                            # ==================================================
                            elif novo_status_db != status_relato_db:

                                nome = st.session_state.get("nome", "Usuário")
                                data = data_hoje_br()

                                relato["status_relato"] = novo_status_db

                                if novo_status_db == "aceito":
                                    relato.pop("devolutiva", None)
                                    relato["status_aprovacao"] = f"Verificado por {nome} em {data}"

                                    # Atualiza progresso da atividade com base no relato aprovado
                                    if "porc_ativ_relato" in relato:

                                        atividade_id = atividade["id"]
                                        porcentagem_relato = int(relato["porc_ativ_relato"])

                                        atividade_mongo = obter_atividade_mongo(projeto, atividade_id)

                                        if atividade_mongo:
                                            atividade_mongo["porcentagem_atv"] = porcentagem_relato



                                elif novo_status_db == "em_analise":
                                    relato.pop("status_aprovacao", None)

                                col_projetos.update_one(
                                    {"codigo": projeto["codigo"]},
                                    {
                                        "$set": {
                                            "plano_trabalho.componentes": projeto["plano_trabalho"]["componentes"]
                                        }
                                    }
                                )

                                st.session_state.pop(status_key, None)
                                st.rerun()







                        # ==================================================
                        # MOSTRA DEVOLUTIVA SE EXISTIR (em_analise ou aberto)
                        # ==================================================

                        status_relato_db = relato.get("status_relato")
                        devolutiva = relato.get("devolutiva")

                        mostrar_devolutiva = False

                        # --------------------------------------------------
                        # REGRA 1: relatório em modo edição
                        # --------------------------------------------------
                        if status_atual_db == "modo_edicao":
                            mostrar_devolutiva = bool(devolutiva)

                        # --------------------------------------------------
                        # REGRA 2: relatório em análise
                        # --------------------------------------------------
                        elif status_atual_db == "em_analise":
                            # se for admin/equipe E relato está devolvido → não mostra
                            if (
                                tipo_usuario in ["admin", "equipe"]
                                and status_relato_db == "aberto"
                            ):
                                mostrar_devolutiva = False
                            else:
                                mostrar_devolutiva = bool(devolutiva)

                        if mostrar_devolutiva:

                            texto = devolutiva.replace("\n", "\n> ")

                            st.markdown(
                                f"""
                            <blockquote style="
                                color: #000000;
                                opacity: 0.9;
                                border-left: 4px solid #F8D7DA;
                                padding-left: 12px;
                                margin-left: 0;
                            ">
                            <strong>Ajuste necessário:</strong><br>
                            {texto.replace('\n', '<br>')}
                            </blockquote>
                            """,
                                unsafe_allow_html=True
                            )


                        # --------------------------------------------------
                        # BOTÃO EDITAR (somente se o relato estiver aberto)
                        # --------------------------------------------------
                        if (
                            pode_editar_relatorio
                            and relato.get("status_relato") == "aberto"
                        ):
                            with st.container(horizontal=True, horizontal_alignment="right"):
                                if st.button(
                                    "Editar",
                                    key=f"btn_edit_{id_relato}",
                                    icon=":material/edit:",
                                    type="tertiary"
                                ):
                                    st.session_state["relato_editando_id"] = id_relato
                                    st.rerun()



                    # ==================================================
                    # MODO EDIÇÃO INLINE DO RELATO DA ATIVIDADE
                    # ==================================================
                    else:
                        st.markdown(f"**Editando {id_relato.upper()}**")



                        # -----------------------------
                        # PORCENTAGEM DA ATIVIDADE (RELATO)
                        # -----------------------------

                        # opções de 0 a 100 de 10 em 10
                        porcentagens = list(range(0, 101, 10))

                        # valor atual salvo (se existir)
                        porc_atual = 0

                        if atividade and atividade.get("id"):
                            atividade_mongo = obter_atividade_mongo(
                                projeto,
                                atividade["id"]
                            )

                            if atividade_mongo:
                                porc_atual = atividade_mongo.get("porcentagem_atv", 0)

                        # garante consistência com opções
                        if porc_atual not in porcentagens:
                            porc_atual = 0

                        # sincroniza session_state ao trocar atividade
                        if (
                            "campo_porcentagem_atividade_relato" not in st.session_state
                            or st.session_state.get("atividade_porcentagem_relato_ref") != atividade.get("id")
                        ):
                            st.session_state["campo_porcentagem_atividade_relato"] = porc_atual
                            st.session_state["atividade_porcentagem_relato_ref"] = atividade.get("id")


                        # selectbox
                        porc_ativ_relato = st.selectbox(
                            "Atualize a porcentagem de execução da atividade *",
                            options=porcentagens,
                            format_func=lambda x: f"{x}%",
                            key="campo_porcentagem_atividade_relato",
                            width=300
                        )





                        # --------------------------------------------------
                        # CAMPOS DE TEXTO
                        # --------------------------------------------------
                        relato_texto = st.text_area(
                            "Relato *",
                            value=relato.get("relato", ""),
                            key=f"edit_relato_{id_relato}"
                        )


                        # --------------------------------------------------
                        # CAMPOS DE DATA NA EDIÇÃO DO RELATO
                        # --------------------------------------------------
                        # Converte as datas armazenadas como string
                        # (dd/mm/yyyy) para objeto datetime.date
                        # necessário para o st.date_input.


                        data_inicio_str = relato.get("data_inicio")
                        data_fim_str = relato.get("data_fim")

                        # Conversão segura para datetime.date
                        data_inicio_valor = None
                        data_fim_valor = None

                        if data_inicio_str:
                            try:
                                data_inicio_valor = datetime.datetime.strptime(
                                    data_inicio_str,
                                    "%d/%m/%Y"
                                ).strftime("%Y-%m-%d")
                            except Exception:
                                pass

                        if data_fim_str:
                            try:
                                data_fim_valor = datetime.datetime.strptime(
                                    data_fim_str,
                                    "%d/%m/%Y"
                                ).strftime("%Y-%m-%d")
                            except Exception:
                                pass


                        # Interface de edição das datas
                        col1, col2 = st.columns(2)

                        with col1:

                            data_inicio = date_picker(
                                label="Data de início *",
                                value=data_inicio_valor,
                                key=f"edit_data_inicio_{id_relato}",
                                locale="pt_BR",
                                one_tap=True,
                                format="dd/MM/yyyy"
                            )

                        with col2:

                            data_fim = date_picker(
                                label="Data de fim *",
                                value=data_fim_valor,
                                key=f"edit_data_fim_{id_relato}",
                                locale="pt_BR",
                                one_tap=True,
                                format="dd/MM/yyyy"
                            )


                        st.divider()

                        # --------------------------------------------------
                        # ANEXOS EXISTENTES (REMOVER)
                        # --------------------------------------------------
                        anexos_remover = []
                        anexos_existentes = relato.get("anexos", [])

                        if anexos_existentes:
                            st.markdown("**Anexos:**")

                            for i, a in enumerate(anexos_existentes):
                                nome = a.get("nome_arquivo", "arquivo")

                                if st.checkbox(
                                    f"**Remover:** {nome}",
                                    key=f"rm_anexo_{id_relato}_{i}"
                                ):
                                    anexos_remover.append(a)

                        # --------------------------------------------------
                        # NOVOS ANEXOS
                        # --------------------------------------------------
                        st.write('')
                        novos_anexos = st.file_uploader(
                            "Adicionar novos anexos",
                            type=["pdf", "docx", "xlsx", "csv", "jpg", "jpeg", "png"],
                            accept_multiple_files=True,
                            key=f"novos_anexos_{id_relato}"
                        )

                        st.divider()

                        # --------------------------------------------------
                        # FOTOS EXISTENTES (REMOVER)
                        # --------------------------------------------------
                        fotos_remover = []
                        fotos_existentes = relato.get("fotos", [])

                        if fotos_existentes:
                            st.markdown("**Fotografias:**")

                            for i, f in enumerate(fotos_existentes):
                                nome = f.get("nome_arquivo", "foto")
                                descricao = f.get("descricao", "")
                                fotografo = f.get("fotografo", "")

                                label = nome
                                if descricao:
                                    label += f" | {descricao}"
                                if fotografo:
                                    label += f" | {fotografo}"

                                if st.checkbox(
                                    f"**Remover:** {label}",
                                    key=f"rm_foto_{id_relato}_{i}"
                                ):
                                    fotos_remover.append(f)


                        # --------------------------------------------------
                        # NOVAS FOTOS
                        # --------------------------------------------------
                        st.write('')
                        st.write("**Adicionar novas fotografias**")

                        fotos_novas_key = f"fotos_novas_{id_relato}"
                        if fotos_novas_key not in st.session_state:
                            st.session_state[fotos_novas_key] = []

                        if st.button(
                            "Adicionar fotografia",
                            key=f"btn_add_foto_{id_relato}",
                            icon=":material/add_a_photo:"
                        ):
                            st.session_state[fotos_novas_key].append({
                                "arquivo": None,
                                "descricao": "",
                                "fotografo": ""
                            })

                        for i, foto in enumerate(st.session_state[fotos_novas_key]):
                            with st.container(border=True):

                                foto["arquivo"] = st.file_uploader(
                                    "Arquivo da foto",
                                    type=["jpg", "jpeg", "png"],
                                    key=f"foto_edit_file_{id_relato}_{i}"
                                )

                                foto["descricao"] = st.text_input(
                                    "Descrição",
                                    key=f"foto_edit_desc_{id_relato}_{i}"
                                )

                                foto["fotografo"] = st.text_input(
                                    "Fotógrafo(a)",
                                    key=f"foto_edit_autor_{id_relato}_{i}"
                                )

                        st.divider()

                        # --------------------------------------------------
                        # AÇÕES
                        # --------------------------------------------------
                        # col_save, col_cancel = st.columns([1, 1])

                        with st.container(horizontal=True, horizontal_alignment="left"):


                            if st.button(
                                "Cancelar",
                                key=f"btn_cancel_{id_relato}"
                            ):
                                st.session_state["relato_editando_id"] = None
                                st.session_state.pop(fotos_novas_key, None)
                                st.rerun()



                            if st.button(
                                "Salvar alterações",
                                key=f"btn_save_{id_relato}",
                                type="primary",
                                icon=":material/save:"
                            ):

                                # ==================================================
                                # VALIDAÇÃO
                                # ==================================================
                                erros = []

                                # Relato obrigatório
                                if not relato_texto or not relato_texto.strip():
                                    erros.append("Relato")

                                # Datas obrigatórias
                                if not data_inicio:
                                    erros.append("Data de início")

                                if not data_fim:
                                    erros.append("Data de fim")


                                # Exibe erros
                                if erros:
                                    campos = ", ".join(erros)
                                    st.warning(f"Preencha os seguintes campos obrigatórios: {campos}")
                                    st.stop()

                                # ==================================================
                                # SALVAMENTO
                                # ==================================================
                                with st.spinner("Salvando alterações. Aguarde..."):

                                    # -----------------------------
                                    # TEXTO E DATAS
                                    # -----------------------------
                                    relato["relato"] = relato_texto

                                    relato["data_inicio"] = (
                                        data_inicio.strftime("%d/%m/%Y") if data_inicio else None
                                    )

                                    relato["data_fim"] = (
                                        data_fim.strftime("%d/%m/%Y") if data_fim else None
                                    )

                                    # -----------------------------
                                    # PORCENTAGEM DO RELATO
                                    # -----------------------------
                                    relato["porc_ativ_relato"] = int(porc_ativ_relato)

                                    # ==================================================
                                    # REMOVE ITENS MARCADOS
                                    # ==================================================
                                    if anexos_remover:
                                        relato["anexos"] = [
                                            a for a in relato.get("anexos", [])
                                            if a not in anexos_remover
                                        ]

                                    if fotos_remover:
                                        relato["fotos"] = [
                                            f for f in relato.get("fotos", [])
                                            if f not in fotos_remover
                                        ]

                                    # ==================================================
                                    # DRIVE
                                    # ==================================================
                                    servico = obter_servico_drive()

                                    pasta_projeto_id = obter_pasta_projeto(
                                        servico,
                                        projeto["codigo"],
                                        projeto["sigla"]
                                    )

                                    pasta_relatos_id = obter_ou_criar_pasta(
                                        servico,
                                        "Relatos_atividades",
                                        pasta_projeto_id
                                    )

                                    pasta_relato_id = obter_ou_criar_pasta(
                                        servico,
                                        id_relato,
                                        pasta_relatos_id
                                    )

                                    # -----------------------------
                                    # ANEXOS
                                    # -----------------------------
                                    if novos_anexos:
                                        pasta_anexos_id = obter_ou_criar_pasta(
                                            servico,
                                            "anexos",
                                            pasta_relato_id
                                        )

                                        relato.setdefault("anexos", [])

                                        for arq in novos_anexos:
                                            id_drive = enviar_arquivo_drive(servico, pasta_anexos_id, arq)
                                            if id_drive:
                                                relato["anexos"].append({
                                                    "nome_arquivo": arq.name,
                                                    "id_arquivo": id_drive
                                                })

                                    # -----------------------------
                                    # FOTOS
                                    # -----------------------------
                                    fotos_validas = [
                                        f for f in st.session_state[fotos_novas_key]
                                        if f.get("arquivo") is not None
                                    ]

                                    if fotos_validas:
                                        pasta_fotos_id = obter_ou_criar_pasta(
                                            servico,
                                            "fotos",
                                            pasta_relato_id
                                        )

                                        relato.setdefault("fotos", [])

                                        for foto in fotos_validas:
                                            arq = foto["arquivo"]
                                            id_drive = enviar_arquivo_drive(servico, pasta_fotos_id, arq)
                                            if id_drive:
                                                relato["fotos"].append({
                                                    "nome_arquivo": arq.name,
                                                    "descricao": foto.get("descricao", ""),
                                                    "fotografo": foto.get("fotografo", ""),
                                                    "id_arquivo": id_drive
                                                })

                                    # ==================================================
                                    # SALVA NO MONGO
                                    # ==================================================
                                    col_projetos.update_one(
                                        {"codigo": projeto["codigo"]},
                                        {"$set": {
                                            "plano_trabalho.componentes": projeto["plano_trabalho"]["componentes"]
                                        }}
                                    )

                                    # Limpa estado
                                    st.session_state["relato_editando_id"] = None
                                    st.session_state.pop(fotos_novas_key, None)

                                    st.success("Relato atualizado com sucesso!", icon=":material/check:")
                                    time.sleep(3)
                                    st.rerun()



                st.write('')


    if not tem_relato:
        st.caption("Nenhum relato cadastrado neste relatório.")












# ==================================================
# ---------- DESPESAS ----------
# ==================================================
if step_selecionado == "Despesas":


    st.write("")
    st.write("")

    st.markdown("#### Registros de despesas")
    st.write("")

    # --------------------------------------------------
    # PERFIS DE USUÁRIO
    # --------------------------------------------------
    usuario_admin = tipo_usuario == "admin"
    usuario_equipe = tipo_usuario == "equipe"
    usuario_beneficiario = tipo_usuario == "beneficiario"
    usuario_visitante = tipo_usuario == "visitante"

    # --------------------------------------------------
    # REGRA: quem pode registrar despesas
    # --------------------------------------------------
    pode_registrar = (
        usuario_beneficiario and status_atual_db == "modo_edicao"
    )

    # ==================================================
    # BOTÃO: REGISTRAR DESPESA
    # ==================================================
    # with st.container(horizontal=True, horizontal_alignment="distribute"):

    saldo_parcela = calcular_saldo_parcela()

    saldo_formatado = f"{saldo_parcela:.1f}".replace(".", ",")


    st.markdown(
        f"Saldo disponível da parcela: "
        f"<span style='font-size:22px'><b>{saldo_formatado}%</b></span>",
        unsafe_allow_html=True
    )


    if pode_registrar:
        render_registro_despesa(
            relatorio_numero,
            projeto,
            col_projetos,
            categorias_map,
        )

    st.write("")




    # ==================================================
    # AGRUPAMENTO DE DESPESAS (CATEGORIA > NOME)
    # ==================================================
    grupo = defaultdict(lambda: defaultdict(list))

    for despesa in projeto.get("financeiro", {}).get("orcamento", []):
        categoria_id = str(despesa.get("categoria"))
        nome_categoria = categorias_map.get(categoria_id, "Categoria não encontrada")

        for lanc in despesa.get("lancamentos", []):
            if lanc.get("relatorio_numero") == relatorio_numero:
                grupo[nome_categoria][despesa["nome_despesa"]].append({
                    "lancamento": lanc,
                    "categoria_id": categoria_id
                })

    # --------------------------------------------------
    # SE NÃO HÁ DESPESAS
    # --------------------------------------------------
    if not grupo:
        st.caption("Nenhuma despesa registrada neste relatório.")
        st.stop()

    # ==================================================
    # RENDERIZAÇÃO DAS DESPESAS
    # ==================================================
    for nome_categoria, despesas in grupo.items():

        st.markdown(f"##### {nome_categoria}")

        for nome_despesa, lancamentos in despesas.items():

            st.markdown(f"###### {nome_despesa}")

            for item in lancamentos:
                lanc = item["lancamento"]
                categoria_id = item["categoria_id"]

                id_despesa = lanc["id_lanc_despesa"]

                # --------------------------------------------------
                # CONTROLE DE EDIÇÃO INLINE
                # --------------------------------------------------
                if "despesa_editando_id" not in st.session_state:
                    st.session_state["despesa_editando_id"] = None

                editando = st.session_state["despesa_editando_id"] == id_despesa

                with st.container(border=True):

                    # ==================================================
                    # BADGE DE STATUS
                    # ==================================================
                    status_despesa_db = lanc.get("status_despesa", "em_analise")
                    tem_devolutiva = bool(lanc.get("devolutiva"))

                    if status_despesa_db == "aberto" and tem_devolutiva:
                        badge = {"label": "Pendente", "bg": "#F8D7DA", "color": "#721C24"}
                    elif status_despesa_db == "aberto":
                        badge = {"label": "Aberto", "bg": "#FFF3CD", "color": "#856404"}
                    elif status_despesa_db == "aceito":
                        badge = {"label": "Aceito", "bg": "#D4EDDA", "color": "#155724"}
                    else:
                        badge = {"label": "Em análise", "bg": "#D1ECF1", "color": "#0C5460"}


                    col1, col2 = st.columns([9, 1])

                    col2.markdown(
                        f"""
                        <div style="margin-bottom:6px;">
                            <span style="
                                background:{badge['bg']};
                                color:{badge['color']};
                                padding:4px 10px;
                                border-radius:20px;
                                font-size:12px;
                                font-weight:600;
                            ">
                                {badge['label']}
                            </span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )





                    # ==================================================
                    # PERMISSÕES
                    # ==================================================
                    pode_editar_despesa = (
                        usuario_beneficiario
                        and status_atual_db == "modo_edicao"
                        and status_despesa_db == "aberto"
                    )

                    pode_avaliar_despesa = (
                        (usuario_admin or usuario_equipe)
                        and status_atual_db == "em_analise"
                    )




                    # ==================================================
                    # VISUALIZAÇÃO DA DESPESA
                    # ==================================================
                    if not editando:

                        st.write(f"**{id_despesa.upper()}:** {lanc.get('descricao_despesa')}")

                        col1, col2 = st.columns(2)

                        with col1:

                            # DADOS DA DESPESA
                            def linha(label, valor):
                                c1, c2 = st.columns([1, 3])
                                c1.write(f"**{label}:**")
                                c2.write(valor if valor else "-")

                            linha("Data", lanc.get("data_despesa"))
                            linha("Fornecedor", lanc.get("fornecedor"))
                            linha("CPF/CNPJ", lanc.get("cpf_cnpj"))

                            valor = lanc.get("valor_despesa", 0)
                            valor_br = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                            linha("Valor (R$)", valor_br)


                        with col2:

                            anexos = lanc.get("anexos", [])
                            if anexos:
                                st.markdown("**Anexos:**")
                                for a in anexos:
                                    link = gerar_link_drive(a["id_arquivo"])
                                    st.markdown(f"- [{a['nome_arquivo']}]({link})")




                        # ==================================================
                        # MOSTRA DEVOLUTIVA
                        # ==================================================
                        status_despesa_db = lanc.get("status_despesa")
                        devolutiva = lanc.get("devolutiva")

                        mostrar_devolutiva = False

                        # --------------------------------------------------
                        # REGRA 0: se estiver ACEITO, nunca mostra
                        # --------------------------------------------------
                        if status_despesa_db == "aceito":
                            mostrar_devolutiva = False

                        # --------------------------------------------------
                        # REGRA 1: relatório em modo edição
                        # --------------------------------------------------
                        elif status_atual_db == "modo_edicao":
                            mostrar_devolutiva = bool(devolutiva)

                        # --------------------------------------------------
                        # REGRA 2: relatório em análise
                        # --------------------------------------------------
                        elif status_atual_db == "em_analise":

                            # admin/equipe avaliando não veem devolutiva enquanto avaliam
                            if (
                                tipo_usuario in ["admin", "equipe"]
                                and status_despesa_db == "aberto"
                            ):
                                mostrar_devolutiva = False
                            else:
                                mostrar_devolutiva = bool(devolutiva)

                        # --------------------------------------------------
                        # REGRA 3: fallback seguro (ex: visitante)
                        # --------------------------------------------------
                        else:
                            mostrar_devolutiva = bool(devolutiva)

                        # --------------------------------------------------
                        # Renderização visual
                        # --------------------------------------------------
                        if mostrar_devolutiva and devolutiva:
                            texto = devolutiva.replace("\n", "<br>")

                            st.markdown(
                                f"""
                                <blockquote style="
                                    color: #000000;
                                    opacity: 0.9;
                                    border-left: 4px solid #F8D7DA;
                                    padding-left: 12px;
                                    margin-left: 0;
                                ">
                                <strong>Ajuste necessário:</strong><br>
                                {texto}
                                </blockquote>
                                """,
                                unsafe_allow_html=True
                            )


                        # --------------------------------------------------
                        # BOTÃO EDITAR (somente beneficiário, despesa aberta)
                        # --------------------------------------------------
                        if pode_editar_despesa:

                            with st.container(horizontal=True, horizontal_alignment="right"):
                                if st.button(
                                    "Editar",
                                    key=f"btn_edit_despesa_{id_despesa}",
                                    icon=":material/edit:",
                                    type="tertiary"
                                ):
                                    st.session_state["despesa_editando_id"] = id_despesa
                                    st.rerun()







                    # ==================================================
                    # MODO EDIÇÃO INLINE DA DESPESA
                    # ==================================================
                    if editando:

                        st.markdown(f"**Editando {id_despesa.upper()}**")

                        # --------------------------------------------------
                        # CAMPOS PRINCIPAIS
                        # --------------------------------------------------
                        col1, col2 = st.columns(2)



                        # --------------------------------------------------
                        # DATA
                        # --------------------------------------------------
                        with col1:
                            data = date_picker(
                                label="Data da despesa *",
                                value=pd.to_datetime(lanc["data_despesa"], dayfirst=True).date(),
                                key=f"edit_data_{id_despesa}",
                                format="dd/MM/yyyy",
                                locale="pt_BR",
                                one_tap=True
                            )


                        with col2:
                            valor = st.number_input(
                                "Valor total (R$) *",
                                min_value=0.0,
                                value=float(lanc.get("valor_despesa", 0)),
                                format="%.2f",
                                key=f"edit_valor_{id_despesa}"
                            )



                        descricao = st.text_area(
                            "Descrição da despesa *",
                            value=lanc.get("descricao_despesa", ""),
                            key=f"edit_desc_{id_despesa}"
                        )

                        col1, col2 = st.columns([2, 1])

                        fornecedor = col1.text_input(
                            "Fornecedor *",
                            value=lanc.get("fornecedor", ""),
                            key=f"edit_forn_{id_despesa}"
                        )

                        cpf_cnpj = col2.text_input(
                            "CPF/CNPJ *",
                            value=lanc.get("cpf_cnpj", ""),
                            key=f"edit_doc_{id_despesa}"
                        )

                        st.divider()

                        # --------------------------------------------------
                        # ANEXOS EXISTENTES (REMOVER)
                        # --------------------------------------------------
                        anexos_remover = []
                        anexos_existentes = lanc.get("anexos", [])

                        if anexos_existentes:
                            st.markdown("**Anexos:**")
                            for i, a in enumerate(anexos_existentes):
                                nome = a.get("nome_arquivo", "arquivo")

                                if st.checkbox(
                                    f"Remover: {nome}",
                                    key=f"rm_anexo_desp_{id_despesa}_{i}"
                                ):
                                    anexos_remover.append(a)

                            st.divider()

                        # --------------------------------------------------
                        # NOVOS ANEXOS
                        # --------------------------------------------------
                        novos_anexos = st.file_uploader(
                            "Adicionar novos anexos",
                            accept_multiple_files=True,
                            key=f"novos_anexos_{id_despesa}"
                        )

                        st.divider()




                        # # ==================================================
                        # # ÁREA DE MENSAGENS (ERROS / WARNINGS)
                        # # ==================================================
                        # container_erros = st.container()


                        # --------------------------------------------------
                        # AÇÕES
                        # --------------------------------------------------
                        with st.container(horizontal=True):


                            with st.container(horizontal=True):


                                if st.button(
                                    "Cancelar",
                                    key=f"btn_cancel_desp_{id_despesa}"
                                ):
                                    st.session_state["despesa_editando_id"] = None
                                    st.rerun()



                                if st.button(
                                    "Salvar alterações",
                                    key=f"btn_save_desp_{id_despesa}",
                                    type="primary",
                                    icon=":material/save:"
                                ):

                                    # ==================================================
                                    # VALIDAÇÕES
                                    # ==================================================

                                    erros_campos = []
                                    erro_consistencia = None

                                    # -------------------------------
                                    # CAMPOS OBRIGATÓRIOS
                                    # -------------------------------

                                    if not data:
                                        erros_campos.append("Data da despesa")

                                    if not valor or valor <= 0:
                                        erros_campos.append("Valor total (R$)")

                                    if not descricao or not descricao.strip():
                                        erros_campos.append("Descrição da despesa")

                                    if not fornecedor or not fornecedor.strip():
                                        erros_campos.append("Fornecedor")

                                    if not cpf_cnpj or not cpf_cnpj.strip():
                                        erros_campos.append("CPF / CNPJ")


                                    # ==================================================
                                    # VALIDAÇÃO DE ANEXOS (COM REMOÇÃO + NOVOS)
                                    # ==================================================

                                    # Regra:
                                    # - Se NÃO for taxa bancária → precisa ter pelo menos 1 anexo no final

                                    categoria_nome_lower = nome_categoria.lower()
                                    is_taxa_bancaria = "taxas bancárias" in categoria_nome_lower

                                    if not is_taxa_bancaria:

                                        anexos_existentes = lanc.get("anexos", [])

                                        # Quantos permanecem após remoção
                                        qtd_restantes = len(anexos_existentes) - len(anexos_remover)

                                        # Quantos novos serão adicionados
                                        qtd_novos = len(novos_anexos) if novos_anexos else 0

                                        total_final = qtd_restantes + qtd_novos

                                        if total_final <= 0:
                                            erros_campos.append("Anexos (mínimo de 1 arquivo)")




                                    # ==================================================
                                    # EXIBE ERROS
                                    # ==================================================

                                    if erros_campos:
                                        campos = ", ".join(erros_campos)
                                        st.warning(f"Preencha os seguintes campos obrigatórios: {campos}")

                                    if erro_consistencia:
                                        st.warning(erro_consistencia)

                                    if erros_campos or erro_consistencia:
                                        st.stop()

                                    # ==================================================
                                    # SALVAR
                                    # ==================================================
                                    with st.spinner("Salvando alterações..."):

                                        lanc.update({
                                            "data_despesa": data.strftime("%d/%m/%Y"),
                                            "descricao_despesa": descricao,
                                            "fornecedor": fornecedor,
                                            "cpf_cnpj": cpf_cnpj,
                                            "valor_despesa": valor
                                        })



                                        # Remove anexos marcados
                                        if anexos_remover:
                                            lanc["anexos"] = [
                                                a for a in lanc.get("anexos", [])
                                                if a not in anexos_remover
                                            ]

                                        # Upload de novos anexos
                                        if novos_anexos:
                                            servico = obter_servico_drive()
                                            pasta_proj = obter_pasta_projeto(
                                                servico,
                                                projeto["codigo"],
                                                projeto["sigla"]
                                            )
                                            pasta_fin = obter_pasta_relatos_financeiros(servico, pasta_proj)
                                            pasta_lanc = obter_ou_criar_pasta(servico, id_despesa, pasta_fin)

                                            lanc.setdefault("anexos", [])

                                            for arq in novos_anexos:
                                                id_drive = enviar_arquivo_drive(servico, pasta_lanc, arq)
                                                lanc["anexos"].append({
                                                    "nome_arquivo": arq.name,
                                                    "id_arquivo": id_drive
                                                })

                                        # Persistência no Mongo
                                        col_projetos.update_one(
                                            {"codigo": projeto["codigo"]},
                                            {"$set": {"financeiro.orcamento": projeto["financeiro"]["orcamento"]}}
                                        )

                                    # Limpa estado
                                    st.session_state["despesa_editando_id"] = None
                                    st.success("Despesa atualizada com sucesso!", icon=":material/check:")
                                    time.sleep(3)
                                    st.rerun()

                        
                            with st.container(horizontal=True):



                                # ==================================================
                                # BOTÃO EXCLUIR DESPESA (SOMENTE SE STATUS = ABERTO)
                                # ==================================================

                                status_despesa_db = lanc.get("status_despesa")

                                # Controle de estado da confirmação
                                confirm_delete_key = f"confirm_delete_despesa_{id_despesa}"

                                if confirm_delete_key not in st.session_state:
                                    st.session_state[confirm_delete_key] = False

                                # Só permite excluir se estiver aberto
                                if status_despesa_db == "aberto":

                                    with st.container(horizontal=True, horizontal_alignment="right"):

                                        # Botão inicial (ícone de lixeira)
                                        if not st.session_state[confirm_delete_key]:
                                            if st.button(
                                                "",
                                                key=f"btn_delete_{id_despesa}",
                                                icon=":material/delete:",
                                                type="secondary"
                                            ):
                                                # Ativa confirmação
                                                st.session_state[confirm_delete_key] = True
                                                st.rerun()

                                        # ==================================================
                                        # CONFIRMAÇÃO DE EXCLUSÃO
                                        # ==================================================
                                        else:

                                            with st.container(horizontal=True):

                                                st.warning("Deseja realmente excluir esta despesa?")

                                                # col1, col2 = st.columns(2)

                                                # Botão CONFIRMAR
                                                if st.button(
                                                    "Sim, excluir",
                                                    key=f"btn_confirm_delete_{id_despesa}",
                                                    type="primary",
                                                    icon=":material/delete:"
                                                ):
                                                    with st.spinner("Excluindo despesa..."):

                                                        # Remove o lançamento da estrutura
                                                        for d in projeto["financeiro"]["orcamento"]:
                                                            if str(d["categoria"]) == categoria_id and d["nome_despesa"] == nome_despesa:
                                                                d["lancamentos"] = [
                                                                    l for l in d.get("lancamentos", [])
                                                                    if l.get("id_lanc_despesa") != id_despesa
                                                                ]
                                                                break

                                                        # Salva no Mongo
                                                        col_projetos.update_one(
                                                            {"codigo": projeto["codigo"]},
                                                            {"$set": {"financeiro.orcamento": projeto["financeiro"]["orcamento"]}}
                                                        )

                                                    # Limpa estados
                                                    st.session_state["despesa_editando_id"] = None
                                                    st.session_state.pop(confirm_delete_key, None)

                                                    st.success("Despesa excluída com sucesso!", icon=":material/check:")
                                                    time.sleep(3)
                                                    st.rerun()

                                                # Botão CANCELAR
                                                if st.button(
                                                    "Cancelar",
                                                    key=f"btn_cancel_delete_{id_despesa}"
                                                ):
                                                    st.session_state[confirm_delete_key] = False
                                                    st.rerun()









                    # ==================================================
                    # AVALIAÇÃO (ADMIN / EQUIPE) — MESMA REGRA DE ATIVIDADES
                    # ==================================================
                    if pode_avaliar_despesa:

                        STATUS_DESPESA_LABEL = {
                            "em_analise": "Em análise",
                            "aberto": "Devolver",
                            "aceito": "Aceito"
                        }

                        STATUS_DESPESA_LABEL_INV = {v: k for k, v in STATUS_DESPESA_LABEL.items()}

                        status_despesa_db = lanc.get("status_despesa", "em_analise")
                        status_label = STATUS_DESPESA_LABEL.get(status_despesa_db, "Em análise")

                        status_key = f"status_despesa_ui_{id_despesa}"
                        devolutiva_key = f"devolutiva_despesa_{id_despesa}"

                        # --------------------------------------------------
                        # Estado inicial do segmented_control
                        # Regra igual à Atividades:
                        # aberto sem devolutiva → Em análise
                        # --------------------------------------------------
                        if status_despesa_db == "aberto" and not lanc.get("devolutiva"):
                            status_label = "Em análise"

                        if status_key not in st.session_state:
                            st.session_state[status_key] = status_label

                        # --------------------------------------------------
                        # SEGMENTED CONTROL
                        # --------------------------------------------------
                        with st.container(horizontal=True, horizontal_alignment="right"):
                            novo_status_label = st.segmented_control(
                                label="novo_status",
                                label_visibility="collapsed",
                                options=["Em análise", "Devolver", "Aceito"],
                                key=status_key
                            )

                        novo_status_db = STATUS_DESPESA_LABEL_INV.get(novo_status_label)

                        # --------------------------------------------------
                        # TEXTO DE AUDITORIA
                        # --------------------------------------------------
                        status_aprovacao = lanc.get("status_aprovacao")
                        if status_aprovacao:
                            st.markdown(
                                f"""
                                <div style="
                                    text-align: right;
                                    color: rgba(0,0,0,0.55);
                                    font-size: 0.8rem;
                                    margin-top: 4px;
                                ">
                                    {status_aprovacao}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            st.write("")

                        # ==================================================
                        # CASO DEVOLVER (ação, não mudança de status)
                        # ==================================================
                        if novo_status_label == "Devolver":

                            if devolutiva_key not in st.session_state:
                                st.session_state[devolutiva_key] = lanc.get("devolutiva", "")

                            st.text_area(
                                "**Devolutiva:**",
                                key=devolutiva_key,
                                placeholder="Explique o que precisa ser ajustado nesta despesa..."
                            )

                            tem_devolutiva = bool(st.session_state.get(devolutiva_key, "").strip())
                            label_botao = "Atualizar" if tem_devolutiva else "Salvar devolutiva"

                            with st.container(horizontal=True):
                                if st.button(
                                    label_botao,
                                    key=f"btn_save_dev_{id_despesa}",
                                    type="primary",
                                    icon=":material/save:"
                                ):
                                    nome = st.session_state.get("nome", "Usuário")
                                    data = data_hoje_br()

                                    lanc["status_despesa"] = "aberto"
                                    lanc["devolutiva"] = st.session_state.get(devolutiva_key, "")
                                    lanc["status_aprovacao"] = f"Devolvido por {nome} em {data}"

                                    col_projetos.update_one(
                                        {"codigo": projeto["codigo"]},
                                        {"$set": {"financeiro.orcamento": projeto["financeiro"]["orcamento"]}}
                                    )

                                    st.session_state.pop(status_key, None)
                                    st.session_state.pop(devolutiva_key, None)

                                    st.success("Devolutiva salva.", icon=":material/check:")
                                    time.sleep(3)
                                    st.rerun()

                        # ==================================================
                        # CASO EM ANÁLISE OU ACEITO (mudança real de status)
                        # ==================================================
                        elif novo_status_db != status_despesa_db:

                            nome = st.session_state.get("nome", "Usuário")
                            data = data_hoje_br()

                            lanc["status_despesa"] = novo_status_db

                            if novo_status_db == "aceito":
                                lanc.pop("devolutiva", None)
                                lanc["status_aprovacao"] = f"Verificado por {nome} em {data}"

                            elif novo_status_db == "em_analise":
                                lanc.pop("status_aprovacao", None)

                            col_projetos.update_one(
                                {"codigo": projeto["codigo"]},
                                {"$set": {"financeiro.orcamento": projeto["financeiro"]["orcamento"]}}
                            )

                            st.session_state.pop(status_key, None)
                            st.rerun()


                    # ==================================================
                    # MOSTRA DEVOLUTIVA (MESMA REGRA DE ATIVIDADES)
                    # ==================================================
                    status_despesa_db = lanc.get("status_despesa")
                    devolutiva = lanc.get("devolutiva")

                    mostrar_devolutiva = False

                    # Regra 1: relatório em modo edição
                    if status_atual_db == "modo_edicao":
                        mostrar_devolutiva = bool(devolutiva)

                    # Regra 2: relatório em análise
                    elif status_atual_db == "em_analise":
                        if (
                            tipo_usuario in ["admin", "equipe"]
                            and status_despesa_db == "aberto"
                        ):
                            mostrar_devolutiva = False
                        else:
                            mostrar_devolutiva = bool(devolutiva)


            st.write('')


# ==================================================
# ---------- INDICADORES ----------
# ==================================================

if step_selecionado == "Indicadores":

    st.write("")
    st.write("")

    st.markdown("#### Indicadores de projeto")
    st.write("")

    # --------------------------------------------------
    # PERFIS
    # --------------------------------------------------
    usuario_admin = tipo_usuario == "admin"
    usuario_equipe = tipo_usuario == "equipe"
    usuario_beneficiario = tipo_usuario == "beneficiario"

    # --------------------------------------------------
    # MAPA DE INDICADORES DO EDITAL
    # --------------------------------------------------
    mapa_indicadores = {
        item["_id"]: item["indicador"]
        for item in edital.get("indicadores", [])
    }

    indicadores = projeto.get("indicadores", [])

    # --------------------------------------------------
    # SEM INDICADORES
    # --------------------------------------------------
    if not indicadores:
        st.caption("Nenhum indicador cadastrado neste projeto.")
        st.stop()

    # --------------------------------------------------
    # SESSION STATE DE EDIÇÃO
    # --------------------------------------------------
    if "indicador_editando_id" not in st.session_state:
        st.session_state["indicador_editando_id"] = None

    # --------------------------------------------------
    # HELPERS
    # --------------------------------------------------
    def linha(label, valor):
        c1, c2 = st.columns([1, 3])
        c1.write(f"**{label}:**")
        c2.write(valor if valor not in [None, ""] else "-")


    def badge_status(status_db, tem_devolutiva):
        if status_db == "aberto" and tem_devolutiva:
            return {
                "label": "Pendente",
                "bg": "#F8D7DA",
                "color": "#721C24"
            }

        elif status_db == "aberto":
            return {
                "label": "Aberto",
                "bg": "#FFF3CD",
                "color": "#856404"
            }

        elif status_db == "aceito":
            return {
                "label": "Aceito",
                "bg": "#D4EDDA",
                "color": "#155724"
            }

        else:
            return {
                "label": "Em análise",
                "bg": "#D1ECF1",
                "color": "#0C5460"
            }


    def salvar_indicadores():
        col_projetos.update_one(
            {"codigo": projeto["codigo"]},
            {
                "$set": {
                    "indicadores": projeto["indicadores"]
                }
            }
        )

    # --------------------------------------------------
    # LOOP
    # --------------------------------------------------
    for indicador in indicadores:

        id_indicador = indicador.get("id_indicador")

        nome_indicador = mapa_indicadores.get(
            id_indicador,
            "Indicador não encontrado"
        )

        # ----------------------------------------------
        # UM LANÇAMENTO POR RELATÓRIO
        # ----------------------------------------------
        lanc = None

        for item in indicador.get("lancamentos", []):
            if item.get("relatorio_numero") == relatorio_numero:
                lanc = item
                break

        # ----------------------------------------------
        # CRIAÇÃO AUTOMÁTICA DO FORMULÁRIO
        # (beneficiário em modo edição sem lançamento)
        # ----------------------------------------------
        criar_novo = (
            usuario_beneficiario
            and status_atual_db == "modo_edicao"
            and lanc is None
        )

        # ----------------------------------------------
        # CONTROLE DE EDIÇÃO INLINE
        # ----------------------------------------------
        editando = (
            st.session_state["indicador_editando_id"] == id_indicador
        )

        with st.container(border=True):

            # ==================================================
            # STATUS / BADGE
            # ==================================================
            status_indicador_db = (
                lanc.get("status_indicador", "em_analise")
                if lanc is not None
                else "aberto"
            )

            tem_devolutiva = (
                bool(lanc.get("devolutiva"))
                if lanc is not None
                else False
            )

            badge = badge_status(
                status_indicador_db,
                tem_devolutiva
            )

            if (
                status_atual_db == "em_analise"
                and status_indicador_db == "aberto"
                and not tem_devolutiva
                and (usuario_admin or usuario_equipe)
            ):
                badge = {
                    "label": "Em análise",
                    "bg": "#D1ECF1",
                    "color": "#0C5460"
                }

            with st.container(
                horizontal=True,
                horizontal_alignment="right"
            ):
                st.markdown(
                    f"""
                    <div>
                        <span style="
                            background:{badge['bg']};
                            color:{badge['color']};
                            padding:4px 10px;
                            border-radius:20px;
                            font-size:12px;
                            font-weight:600;
                        ">
                            {badge['label']}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
            st.write("")

            st.markdown(
                f"**Indicador:** {nome_indicador}"
            )

            st.markdown(
                f"**Descrição da contribuição:** "
                f"{indicador.get('descricao_contribuicao', '-')}"
            )

            col_a, col_b, col_c = st.columns(3)

            with col_a:
                st.markdown(
                    f"**Início do projeto:** "
                    f"{formatar_numero_br_dinamico(
                        indicador.get("marco_zero")
                    )}"
                )

            with col_b:
                st.markdown(
                    f"**Meta:** "
                    f"{formatar_numero_br_dinamico(indicador.get('valor'))}"
                )
                
            # ==================================================
            # CRIAÇÃO AUTOMÁTICA DE NOVO LANÇAMENTO
            # ==================================================
            if criar_novo:

                key_resultado_novo = (
                    f"novo_resultado_{id_indicador}_{relatorio_numero}"
                )

                key_obs_novo = (
                    f"novo_obs_{id_indicador}_{relatorio_numero}"
                )
                
                col1, col2 = st.columns([1,3])

                resultado_novo = col1.number_input(
                    "Resultado atual",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key=key_resultado_novo
                )

                observacoes_novo = col2.text_area(
                    "Observações",
                    key=key_obs_novo
                )

                with st.container(
                    horizontal=True,
                    horizontal_alignment="left"
                ):
                    if st.button(
                        "Salvar",
                        key=f"btn_save_novo_ind_{id_indicador}",
                        type="primary",
                        icon=":material/save:"
                    ):

                        resultado_float = float(resultado_novo)

                        novo_lanc = {
                            "id_lanc_indicador": str(bson.ObjectId()),
                            "relatorio_numero": relatorio_numero,
                            "resultado_atual": resultado_float,
                            "observacoes": observacoes_novo or "",
                            "status_indicador": "aberto",
                            "devolutiva": "",
                            "status_aprovacao": "",
                            "data_coleta": datetime.datetime.now(
                                datetime.timezone.utc
                            )
                        }

                        indicador.setdefault("lancamentos", []).append(
                            novo_lanc
                        )

                        salvar_indicadores()

                        st.success(
                            "Indicador registrado com sucesso.",
                            icon=":material/check:"
                        )

                        time.sleep(2)
                        st.rerun()

                st.write("")
                continue

            # ==================================================
            # SEM LANÇAMENTO E SEM PERMISSÃO
            # ==================================================
            if lanc is None:
                st.caption(
                    "Nenhum lançamento registrado para este relatório."
                )
                st.write("")
                continue

        
            # ==================================================
            # PERMISSÕES
            # ==================================================
            pode_editar_indicador = (
                usuario_beneficiario
                and status_atual_db == "modo_edicao"
                and status_indicador_db == "aberto"
            )

            pode_avaliar_indicador = (
                (usuario_admin or usuario_equipe)
                and status_atual_db == "em_analise"
            )

            # ==================================================
            # VISUALIZAÇÃO
            # ==================================================
            if not editando:

                with col_c:
                    st.markdown(
                        f"**Resultado atual:** "
                        f"{formatar_numero_br_dinamico(lanc.get('resultado_atual'))}"
                    )

                obs = lanc.get("observacoes")

                if obs not in [None, "", "None"]:
                    st.markdown(
                        f"**Observações:** "
                        f"{obs}"
                    )

                # ----------------------------------------------
                # DATA COLETA
                # ----------------------------------------------
                data_str = None
                data_coleta = lanc.get("data_coleta")

                if data_coleta:

                    if isinstance(data_coleta, datetime.datetime):

                        if data_coleta.tzinfo is None:
                            data_coleta = data_coleta.replace(
                                tzinfo=datetime.timezone.utc
                            )

                        data_local = data_coleta.astimezone(
                            ZoneInfo("America/Sao_Paulo")
                        )

                        data_str = data_local.strftime(
                            "%d/%m/%Y %H:%M"
                        )

                    else:
                        data_str = str(data_coleta)


                # ----------------------------------------------
                # RODAPÉ (DATA + EDITAR)
                # ----------------------------------------------
                if data_str or pode_editar_indicador:
                    
                    with st.container(
                        horizontal=True,
                        horizontal_alignment="distribute",
                        vertical_alignment="center"
                    ):

                        if data_str:
                            st.caption(
                                f"Último registro em {data_str}"
                            )
                        else:
                            st.write("")

                        if pode_editar_indicador:
                            if st.button(
                                "Editar",
                                key=f"btn_edit_ind_{id_indicador}",
                                icon=":material/edit:",
                                type="tertiary"
                            ):
                                st.session_state[
                                    "indicador_editando_id"
                                ] = id_indicador
                                st.rerun()

                # ----------------------------------------------
                # DEVOLUTIVA
                # ----------------------------------------------
                devolutiva = lanc.get("devolutiva")
                mostrar_devolutiva = False

                if status_indicador_db == "aceito":
                    mostrar_devolutiva = False

                elif status_atual_db == "modo_edicao":
                    mostrar_devolutiva = bool(devolutiva)

                elif status_atual_db == "em_analise":

                    if (
                        tipo_usuario in ["admin", "equipe"]
                        and status_indicador_db == "aberto"
                    ):
                        mostrar_devolutiva = False
                    else:
                        mostrar_devolutiva = bool(devolutiva)

                else:
                    mostrar_devolutiva = bool(devolutiva)

                if mostrar_devolutiva and devolutiva:

                    texto = devolutiva.replace(
                        "\n",
                        "<br>"
                    )

                    st.markdown(
                        f"""
                        <blockquote style="
                            color: #000000;
                            opacity: 0.9;
                            border-left: 4px solid #F8D7DA;
                            padding-left: 12px;
                            margin-left: 0;
                        ">
                        <strong>Ajuste necessário:</strong><br>
                        {texto}
                        </blockquote>
                        """,
                        unsafe_allow_html=True
                    )

                # ----------------------------------------------
                # AUDITORIA
                # ----------------------------------------------
                status_aprovacao = lanc.get("status_aprovacao")

                if status_aprovacao:
                    st.markdown(
                        f"""
                        <div style="
                            text-align: right;
                            color: rgba(0,0,0,0.55);
                            font-size: 0.8rem;
                            margin-top: 4px;
                        ">
                            {status_aprovacao}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
        
            # ==================================================
            # EDIÇÃO INLINE
            # ==================================================
            if editando:

                #st.markdown("##### Editando lançamento")

                key_edit_resultado = (
                    f"edit_resultado_{id_indicador}_{relatorio_numero}"
                )

                key_edit_obs = (
                    f"edit_obs_{id_indicador}_{relatorio_numero}"
                )

                resultado_padrao = float(
                    lanc.get("resultado_atual", 0) or 0
                )
                
                col1, col2 = st.columns([1,3])

                resultado_edit = col1.number_input(
                    "Resultado atual",
                    min_value=0.0,
                    value=resultado_padrao,
                    step=1.0,
                    key=key_edit_resultado
                )

                observacoes_edit = col2.text_area(
                    "Observações",
                    value=lanc.get("observacoes", ""),
                    key=key_edit_obs
                )
                
                st.write("")

                with st.container(horizontal=True):

                    if st.button(
                        "Cancelar",
                        key=f"btn_cancel_ind_{id_indicador}"
                    ):
                        st.session_state[
                            "indicador_editando_id"
                        ] = None
                        st.rerun()

                    if st.button(
                        "Salvar alterações",
                        key=f"btn_save_edit_ind_{id_indicador}",
                        type="primary",
                        icon=":material/save:"
                    ):

                        resultado_float = float(resultado_edit)

                        lanc["resultado_atual"] = resultado_float
                        lanc["observacoes"] = observacoes_edit or ""
                        lanc["data_coleta"] = datetime.datetime.now(
                            datetime.timezone.utc
                        )

                        salvar_indicadores()

                        st.session_state[
                            "indicador_editando_id"
                        ] = None

                        st.success(
                            "Indicador atualizado com sucesso.",
                            icon=":material/check:"
                        )

                        time.sleep(2)
                        st.rerun()

            # ==================================================
            # AVALIAÇÃO
            # ==================================================
            if pode_avaliar_indicador:

                STATUS_IND_LABEL = {
                    "em_analise": "Em análise",
                    "aberto": "Devolver",
                    "aceito": "Aceito"
                }

                STATUS_IND_LABEL_INV = {
                    v: k for k, v in STATUS_IND_LABEL.items()
                }

                status_label = STATUS_IND_LABEL.get(
                    status_indicador_db,
                    "Em análise"
                )

                status_key = (
                    f"status_indicador_ui_{id_indicador}"
                )

                devolutiva_key = (
                    f"devolutiva_indicador_{id_indicador}"
                )

                # ----------------------------------------------
                # aberto sem devolutiva = visualmente em análise
                # ----------------------------------------------
                if (
                    status_indicador_db == "aberto"
                    and not lanc.get("devolutiva")
                ):
                    status_label = "Em análise"

                if status_key not in st.session_state:
                    st.session_state[status_key] = status_label

                # ----------------------------------------------
                # segmented control
                # ----------------------------------------------
                with st.container(
                    horizontal=True,
                    horizontal_alignment="right"
                ):
                    novo_status_label = st.segmented_control(
                        label="novo_status_indicador",
                        label_visibility="collapsed",
                        options=[
                            "Em análise",
                            "Devolver",
                            "Aceito"
                        ],
                        key=status_key
                    )

                novo_status_db = STATUS_IND_LABEL_INV.get(
                    novo_status_label
                )

                # ----------------------------------------------
                # DEVOLVER
                # ----------------------------------------------
                if novo_status_label == "Devolver":

                    if devolutiva_key not in st.session_state:
                        st.session_state[devolutiva_key] = (
                            lanc.get("devolutiva", "")
                        )

                    st.text_area(
                        "**Devolutiva:**",
                        key=devolutiva_key,
                        placeholder=(
                            "Explique o que precisa ser "
                            "ajustado neste indicador..."
                        )
                    )

                    tem_devolutiva = bool(
                        st.session_state.get(
                            devolutiva_key,
                            ""
                        ).strip()
                    )

                    label_botao = (
                        "Atualizar"
                        if tem_devolutiva
                        else "Salvar devolutiva"
                    )

                    with st.container(horizontal=True):

                        if st.button(
                            label_botao,
                            key=f"btn_save_dev_ind_{id_indicador}",
                            type="primary",
                            icon=":material/save:"
                        ):

                            nome = st.session_state.get(
                                "nome",
                                "Usuário"
                            )

                            data = data_hoje_br()

                            lanc["status_indicador"] = "aberto"
                            lanc["devolutiva"] = (
                                st.session_state.get(
                                    devolutiva_key,
                                    ""
                                )
                            )

                            lanc["status_aprovacao"] = (
                                f"Devolvido por {nome} em {data}"
                            )

                            salvar_indicadores()

                            st.session_state.pop(
                                status_key,
                                None
                            )

                            st.session_state.pop(
                                devolutiva_key,
                                None
                            )

                            st.success(
                                "Devolutiva salva.",
                                icon=":material/check:"
                            )

                            time.sleep(2)
                            st.rerun()

                # ----------------------------------------------
                # EM ANÁLISE / ACEITO
                # ----------------------------------------------
                elif novo_status_db != status_indicador_db:

                    nome = st.session_state.get(
                        "nome",
                        "Usuário"
                    )

                    data = data_hoje_br()

                    lanc["status_indicador"] = novo_status_db

                    if novo_status_db == "aceito":
                        lanc.pop("devolutiva", None)
                        lanc["status_aprovacao"] = (
                            f"Verificado por {nome} em {data}"
                        )

                    elif novo_status_db == "em_analise":
                        lanc.pop("status_aprovacao", None)

                    salvar_indicadores()

                    st.session_state.pop(status_key, None)
                    st.rerun()

        st.write("")


# ---------- BENEFÍCIOS ----------

if step_selecionado == "Beneficiários":


    # =====================================================
    # CARREGA TIPOS DE BENEFÍCIO DO BANCO
    # =====================================================

    dados_beneficios = list(
        col_beneficios.find({}, {"beneficio": 1}).sort("beneficio", 1)
    )

    OPCOES_BENEFICIOS = [
        d["beneficio"]
        for d in dados_beneficios
        if d.get("beneficio")
    ]


    # ============================================
    # CONTROLE DE USUÁRIO / STATUS DO RELATÓRIO
    # ============================================

    usuario_admin = tipo_usuario == "admin"
    usuario_equipe = tipo_usuario == "equipe"
    usuario_beneficiario = tipo_usuario == "beneficiario"
    usuario_visitante = tipo_usuario == "visitante"

    # Se o relatório NÃO estiver em modo_edicao,
    # força modo VISUALIZAÇÃO dos beneficiários
    if status_atual_db != "modo_edicao":
        modo_edicao_benef = False
        modo_visualizacao_benef = True
    else:
        modo_edicao_benef = usuario_beneficiario
        modo_visualizacao_benef = not usuario_beneficiario





    # PARTE 1 - QUANTITATIVO DE BENEFICIÁRIOS ---------------------------------------------------------------------------------------------------------------------------
    st.write('')
    st.write('')




    # ======================================================
    # INICIALIZAÇÃO DO ESTADO DA MATRIZ DE BENEFICIÁRIOS
    # ======================================================


    key_benef_quant = f"beneficiarios_quant_rel_{relatorio_numero}"

    if key_benef_quant not in st.session_state:
        st.session_state[key_benef_quant] = (
            relatorio.get("beneficiarios_quant") or {
                "mulheres": {"jovens": 0, "adultas": 0, "idosas": 0},
                "homens": {"jovens": 0, "adultos": 0, "idosos": 0},
                "nao_binarios": {"jovens": 0, "adultos": 0, "idosos": 0}
            }
        )




    # ======================================================
    # TÍTULO DO BLOCO
    # ======================================================

    st.markdown("##### Número de beneficiários por gênero e faixa etária")

    st.write("")


    # ======================================================
    # MODO EDIÇÃO
    # ======================================================

    if pode_editar_relatorio:


        # Coluna à esquerda para diminuir a largura dos inputs de beneficiários
        content, vazio_d = st.columns([8, 4])

        # -------------------------------
        # LINHA: JOVENS
        # -------------------------------
        col_m, col_h, col_nb = content.columns(3)

        with col_m:
            st.session_state[key_benef_quant]["mulheres"]["jovens"] = st.number_input(
                "Mulheres – Jovens (até 24 anos)",
                min_value=0,
                step=1,
                value=st.session_state[key_benef_quant]["mulheres"]["jovens"],
                key="bq_mulheres_jovens"
            )

        with col_h:
            st.session_state[key_benef_quant]["homens"]["jovens"] = st.number_input(
                "Homens – Jovens (até 24 anos)",
                min_value=0,
                step=1,
                value=st.session_state[key_benef_quant]["homens"]["jovens"],
                key="bq_homens_jovens"
            )

        with col_nb:
            st.session_state[key_benef_quant]["nao_binarios"]["jovens"] = st.number_input(
                "Não-binários – Jovens (até 24 anos)",
                min_value=0,
                step=1,
                value=st.session_state[key_benef_quant]["nao_binarios"]["jovens"],
                key="bq_nb_jovens"
            )

        # -------------------------------
        # LINHA: ADULTOS
        # -------------------------------
        col_m, col_h, col_nb = content.columns(3)

        with col_m:
            st.session_state[key_benef_quant]["mulheres"]["adultas"] = st.number_input(
                "Mulheres – Adultas",
                min_value=0,
                step=1,
                value=st.session_state[key_benef_quant]["mulheres"]["adultas"],
                key="bq_mulheres_adultas"
            )

        with col_h:
            st.session_state[key_benef_quant]["homens"]["adultos"] = st.number_input(
                "Homens – Adultos",
                min_value=0,
                step=1,
                value=st.session_state[key_benef_quant]["homens"]["adultos"],
                key="bq_homens_adultos"
            )

        with col_nb:
            st.session_state[key_benef_quant]["nao_binarios"]["adultos"] = st.number_input(
                "Não-binários – Adultos",
                min_value=0,
                step=1,
                value=st.session_state[key_benef_quant]["nao_binarios"]["adultos"],
                key="bq_nb_adultos"
            )

        # -------------------------------
        # LINHA: IDOSOS
        # -------------------------------
        col_m, col_h, col_nb = content.columns(3)

        with col_m:
            st.session_state[key_benef_quant]["mulheres"]["idosas"] = st.number_input(
                "Mulheres – Idosas (60+ anos)",
                min_value=0,
                step=1,
                value=st.session_state[key_benef_quant]["mulheres"]["idosas"],
                key="bq_mulheres_idosas"
            )

        with col_h:
            st.session_state[key_benef_quant]["homens"]["idosos"] = st.number_input(
                "Homens – Idosos (60+ anos)",
                min_value=0,
                step=1,
                value=st.session_state[key_benef_quant]["homens"]["idosos"],
                key="bq_homens_idosos"
            )

        with col_nb:
            st.session_state[key_benef_quant]["nao_binarios"]["idosos"] = st.number_input(
                "Não-binários – Idosos (60+ anos)",
                min_value=0,
                step=1,
                value=st.session_state[key_benef_quant]["nao_binarios"]["idosos"],
                key="bq_nb_idosos"
            )




        # ======================================================
        # BOTÃO DE SALVAR EXCLUSIVO DA MATRIZ
        # ======================================================
        # Este botão salva SOMENTE a matriz de quantitativos

        if pode_editar_relatorio:

            st.write("")

            salvar_matriz = st.button(
                "Atualizar beneficiários",
                type="primary",
                key=f"salvar_beneficiarios_quant_{relatorio_numero}",
                icon=":material/save:"
            )

            if salvar_matriz:

                # Atualiza apenas a chave 'beneficiarios_quant' no relatório correto
                nome_usuario = st.session_state.get("nome", "Usuário")
                data_verificacao = datetime.datetime.now().strftime("%d/%m/%Y")

                col_projetos.update_one(
                    {
                        "codigo": projeto["codigo"],
                        "relatorios.numero": relatorio_numero
                    },
                    {
                        "$set": {
                            "relatorios.$.beneficiarios_quant":
                                st.session_state[key_benef_quant],

                            "relatorios.$.benef_verif_por":
                                f"{nome_usuario} em {data_verificacao}"
                        }
                    }
                )

                st.success("Beneficiários salvos com sucesso.", icon=":material/check:")
                time.sleep(3)
                st.rerun()











    # ======================================================
    # MODO VISUALIZAÇÃO
    # ======================================================

    else:


        dados = st.session_state[key_benef_quant]


        # -------------------------------
        # Totais por gênero
        # -------------------------------
        total_mulheres = sum(dados["mulheres"].values())
        total_homens = sum(dados["homens"].values())
        total_nb = sum(dados["nao_binarios"].values())

        # -------------------------------
        # Totais por faixa etária
        # -------------------------------
        total_jovens = (
            dados["mulheres"]["jovens"]
            + dados["homens"]["jovens"]
            + dados["nao_binarios"]["jovens"]
        )

        total_adultos = (
            dados["mulheres"]["adultas"]
            + dados["homens"]["adultos"]
            + dados["nao_binarios"]["adultos"]
        )

        total_idosos = (
            dados["mulheres"]["idosas"]
            + dados["homens"]["idosos"]
            + dados["nao_binarios"]["idosos"]
        )

        total_geral = total_mulheres + total_homens + total_nb

        st.write("")

        # -------------------------------
        # LAYOUT EM 4 COLUNAS
        # -------------------------------
        col_m, col_h, col_nb, col_totais = st.columns(4)

        # -------- MULHERES --------
        with col_m:
            l, v = st.columns(2)
            l.write("Mulheres jovens"); v.write(str(dados["mulheres"]["jovens"]))

            l, v = st.columns(2)
            l.write("Mulheres adultas"); v.write(str(dados["mulheres"]["adultas"]))

            l, v = st.columns(2)
            l.write("Mulheres idosas"); v.write(str(dados["mulheres"]["idosas"]))

            l, v = st.columns(2)
            l.markdown("**Total de mulheres**"); v.markdown(f"**{total_mulheres}**")

        # -------- HOMENS --------
        with col_h:
            l, v = st.columns(2)
            l.write("Homens jovens"); v.write(str(dados["homens"]["jovens"]))

            l, v = st.columns(2)
            l.write("Homens adultos"); v.write(str(dados["homens"]["adultos"]))

            l, v = st.columns(2)
            l.write("Homens idosos"); v.write(str(dados["homens"]["idosos"]))

            l, v = st.columns(2)
            l.markdown("**Total de homens**"); v.markdown(f"**{total_homens}**")

        # -------- NÃO-BINÁRIOS --------
        with col_nb:
            l, v = st.columns(2)
            l.write("Não-binários jovens"); v.write(str(dados["nao_binarios"]["jovens"]))

            l, v = st.columns(2)
            l.write("Não-binários adultos"); v.write(str(dados["nao_binarios"]["adultos"]))

            l, v = st.columns(2)
            l.write("Não-binários idosos"); v.write(str(dados["nao_binarios"]["idosos"]))

            l, v = st.columns(2)
            l.markdown("**Total de não-binários**"); v.markdown(f"**{total_nb}**")

        # -------- TOTAIS GERAIS (NEGRITO) --------
        with col_totais:
            l, v = st.columns(2)
            l.markdown("**Total de jovens**"); v.markdown(f"**{total_jovens}**")

            l, v = st.columns(2)
            l.markdown("**Total de adultos**"); v.markdown(f"**{total_adultos}**")

            l, v = st.columns(2)
            l.markdown("**Total de idosos**"); v.markdown(f"**{total_idosos}**")

            l, v = st.columns(2)
            l.markdown("**Total geral**"); v.markdown(f"**{total_geral}**")








    # st.divider()

    # # ============================================================================================================
    # # PARTE 2 - TIPOS DE BENEFICIÁRIOS E BENEFICIOS 
    # # ============================================================================================================

    # st.write('')
    # st.markdown("##### Tipos de Beneficiários e Benefícios")

    # if usuario_beneficiario:

    #     st.write("")
    #     st.write(
    #         "Registre aqui os tipos de **Beneficiários** e **Benefícios** do projeto para cada comunidade."
    #     )

    # st.write(
    #     "Se precisar, cadastre novas comunidades na opção **Locais** no menu lateral."
    # )

    # st.write("")
    # st.write("")


    # projeto = col_projetos.find_one({"codigo": projeto["codigo"]})
    # localidades = projeto.get("locais", {}).get("localidades", [])

    # if not localidades:
    #     st.info(
    #         "Nenhuma comunidade cadastrada no projeto. "
    #         "Adicione comunidades na página **Locais**."
    #     )
    #     st.stop()

    # # =====================================================
    # # LOOP DAS COMUNIDADES
    # # =====================================================
    # for localidade in localidades:

    #     nome_localidade = localidade.get("nome_localidade")
    #     beneficiarios_bd = localidade.get("beneficiarios", []) or []

    #     # -------------------------------------------------
    #     # ESTADO ORIGINAL DO BANCO
    #     # -------------------------------------------------
    #     estado_original = {
    #         b["tipo_beneficiario"]: sorted(b.get("beneficios") or [])
    #         for b in beneficiarios_bd
    #         if b.get("tipo_beneficiario")
    #     }

    #     # -------------------------------------------------
    #     # PÚBLICOS PARA RENDERIZAÇÃO
    #     # -------------------------------------------------
    #     publicos_renderizacao = list(opcoes_publicos[:-1])

    #     for tipo in estado_original.keys():
    #         if tipo not in publicos_renderizacao:
    #             publicos_renderizacao.append(tipo)

    #     publicos_renderizacao = sorted(publicos_renderizacao)

    #     estado_atual = {}
    #     houve_alteracao = False

    #     col1, col2 = st.columns([1, 3])

    #     # -------- COLUNA 1 --------

    #     with col1:
    #         st.markdown(f"**{nome_localidade}**")

    #         municipio = localidade.get("municipio")

    #         if municipio:
    #             st.write(municipio)




        # # -------- COLUNA 2 --------
        # with col2:

        #     st.write("**Tipos de Beneficiários e Benefícios:**")



        #     # =====================================================
        #     # MODO VISUALIZAÇÃO COM LISTA EM PILLS
        #     # =====================================================
        #     if modo_visualizacao_benef:

        #         if not beneficiarios_bd:
        #             st.write("Nenhum beneficiário cadastrado.")
        #         else:
        #             for b in beneficiarios_bd:

        #                 tipo = b.get("tipo_beneficiario")
        #                 beneficios = b.get("beneficios") or []

        #                 with st.container():
        #                     st.write(' ')
        #                     if beneficios:
        #                         st.pills(
        #                             label=tipo,
        #                             options=beneficios,
        #                             width="content",
        #                             key=f"pill_{projeto['codigo']}_{nome_localidade}_{tipo}"
        #                         )
        #                     else:
        #                         st.pills(
        #                             label=tipo,
        #                             options=["Nenhum benefício informado"],
        #                             width="content",
        #                             key=f"pill_{projeto['codigo']}_{nome_localidade}_{tipo}"
        #                         )


        #     # =====================================================
        #     # MODO EDIÇÃO
        #     # =====================================================
        #     if modo_edicao_benef:

        #         # =============================================
        #         # BENEFICIÁRIOS EXISTENTES
        #         # =============================================
        #         for publico in publicos_renderizacao:

        #             with st.container(horizontal=True):

        #                 chk_key = f"chk_{projeto['codigo']}_{nome_localidade}_{publico}"

        #                 marcado_inicial = publico in estado_original

        #                 marcado = st.checkbox(
        #                     publico,
        #                     value=marcado_inicial,
        #                     key=chk_key,
        #                     width=300
        #                 )

        #                 if marcado:

        #                     beneficios_iniciais = estado_original.get(publico, [])

        #                     beneficios = st.multiselect(
        #                         f"Benefícios para {publico.lower()}",
        #                         options=OPCOES_BENEFICIOS,
        #                         default=beneficios_iniciais,
        #                         key=f"ms_{projeto['codigo']}_{nome_localidade}_{publico}"
        #                     )

        #                     estado_atual[publico] = sorted(beneficios)

        #                     if (
        #                         publico not in estado_original
        #                         or sorted(beneficios) != estado_original.get(publico, [])
        #                     ):
        #                         houve_alteracao = True

        #                 else:
        #                     if publico in estado_original:
        #                         houve_alteracao = True

        #         # =============================================
        #         # CHECKBOX OUTROS
        #         # =============================================
        #         with st.container(horizontal=True):

        #             chk_outros_key = f"chk_outros_{projeto['codigo']}_{nome_localidade}"

        #             outros_marcado = st.checkbox(
        #                 "Outros",
        #                 value=False,
        #                 key=chk_outros_key,
        #                 width=300
        #             )

        #         # =============================================
        #         # FORMULÁRIO OUTROS
        #         # =============================================
        #         if outros_marcado:

        #             with st.container(horizontal=True):

        #                 st.text_input(
        #                     "Tipo de beneficiário",
        #                     key=f"novo_tipo_{projeto['codigo']}_{nome_localidade}"
        #                 )

        #                 st.multiselect(
        #                     "Benefícios",
        #                     options=OPCOES_BENEFICIOS,
        #                     key=f"novo_beneficios_{projeto['codigo']}_{nome_localidade}"
        #                 )

        #             novo_tipo = st.session_state.get(
        #                 f"novo_tipo_{projeto['codigo']}_{nome_localidade}", ""
        #             ).strip()

        #             novos_beneficios = st.session_state.get(
        #                 f"novo_beneficios_{projeto['codigo']}_{nome_localidade}", []
        #             )

        #             if novo_tipo and novos_beneficios:
        #                 houve_alteracao = True

        # # =================================================
        # # BOTÃO SALVAR
        # # =================================================
        # if houve_alteracao:

        #     st.write("")

        #     erros = []

        #     # with st.container(horizontal=True, horizontal_alignment="right"):
        #     clicou_salvar = st.button(
        #         f"Atualizar {nome_localidade}",
        #         type="primary",
        #         key=f"salvar_{projeto['codigo']}_{nome_localidade}",
        #         icon=":material/save:"
        #     )

        #     if clicou_salvar:

        #         beneficiarios_para_salvar = []

        #         # -----------------------------------------
        #         # BENEFICIÁRIOS EXISTENTES
        #         # -----------------------------------------
        #         for tipo, beneficios in estado_atual.items():
        #             if not beneficios:
        #                 erros.append(
        #                     f"Selecione ao menos um benefício para **{tipo}**."
        #                 )
        #             else:
        #                 beneficiarios_para_salvar.append({
        #                     "tipo_beneficiario": tipo,
        #                     "beneficios": beneficios
        #                 })

        #         # -----------------------------------------
        #         # NOVO BENEFICIÁRIO (OUTROS)
        #         # -----------------------------------------
        #         if outros_marcado and novo_tipo:
        #             beneficiarios_para_salvar.append({
        #                 "tipo_beneficiario": novo_tipo,
        #                 "beneficios": novos_beneficios
        #             })

        #         if erros:
        #             for erro in erros:
        #                 st.error(erro)
        #             time.sleep(3)
        #             st.rerun()

        #         # -----------------------------------------
        #         # SALVA NO BANCO
        #         # -----------------------------------------
        #         col_projetos.update_one(
        #             {
        #                 "codigo": projeto["codigo"],
        #                 "locais.localidades.nome_localidade": nome_localidade
        #             },
        #             {
        #                 "$set": {
        #                     "locais.localidades.$.beneficiarios":
        #                         beneficiarios_para_salvar
        #                 }
        #             }
        #         )

        #         st.success(
        #             f"Beneficiários da comunidade "
        #             f"**{nome_localidade}** salvos com sucesso."
        #         )
        #         time.sleep(3)
        #         st.rerun()


        # st.divider()


























# # ---------- PESQUISAS ----------
# if step_selecionado == "Pesquisas":

#     # ============================
#     # CONTROLE DE USUÁRIO
#     # ============================

#     usuario_admin = tipo_usuario == "admin"
#     usuario_equipe = tipo_usuario == "equipe"
#     usuario_beneficiario = tipo_usuario == "beneficiario"
    

#     pode_editar = usuario_admin or usuario_equipe or usuario_beneficiario
#     pode_verificar = usuario_admin or usuario_equipe

#     # ============================
#     # BUSCA DADOS
#     # ============================

#     pesquisas = edital.get("pesquisas_relatorio", []) if edital else []

#     if not pesquisas:
#         st.caption("Nenhuma pesquisa cadastrada.")
#         st.stop()

#     st.write("")
#     st.write("")
#     st.markdown("##### Pesquisas / Ferramentas de Monitoramento")
#     st.write("")

#     pesquisas_projeto = projeto.get("pesquisas", [])
#     status_map = {p["id_pesquisa"]: p for p in pesquisas_projeto}

#     # ============================
#     # RENDERIZAÇÃO DAS LINHAS
#     # ============================

#     for pesquisa in pesquisas:

#         status = status_map.get(pesquisa["id"], {})

#         # Valores atuais do banco
#         respondida_db = status.get("respondida", False)
#         verificada_db = status.get("verificada", False)
#         url_anexo_db = status.get("url_anexo")

#         # Chaves únicas
#         upload_key = f"upload_{relatorio_numero}_{pesquisa['id']}"
#         upload_salvo_key = f"upload_salvo_{relatorio_numero}_{pesquisa['id']}"

#         col1, col2, col3, col4, col5 = st.columns([4, 3, 2, 2, 2])

#         # -------- PESQUISA --------
#         with col1:
#             st.markdown(f"**{pesquisa['nome_pesquisa']}**")


#         # -------- ANEXO --------
#         arquivo = None

#         with col2:
#             # Caso a pesquisa exija upload
#             if pesquisa.get("upload_arquivo"):

#                 # -----------------------------
#                 # BENEFICIÁRIO → pode anexar
#                 # -----------------------------
#                 if (
#                     tipo_usuario == "beneficiario"
#                     and not verificada_db
#                     and status_atual_db == "modo_edicao"
#                 ):
#                     arquivo = st.file_uploader(
#                         "Anexo",
#                         key=f"upload_{relatorio_numero}_{pesquisa['id']}"
#                     )

#                 # -----------------------------
#                 # NÃO BENEFICIÁRIO
#                 # Mostra aviso SOMENTE se não houver anexo salvo
#                 # -----------------------------
#                 elif tipo_usuario != "beneficiario" and not url_anexo_db:
#                     st.write(":material/attach_file: Demanda anexo")

#             # -----------------------------
#             # Link do anexo (se existir)
#             # -----------------------------
#             if url_anexo_db:
#                 st.markdown(f":material/attach_file: [Ver anexo]({url_anexo_db})")



#         # -------- RESPONDIDA --------
#         with col3:
#             respondida_ui = st.checkbox(
#                 "Respondida",
#                 value=respondida_db,
#                 disabled = (
#                     # Visitante nunca pode
#                     tipo_usuario == "visitante"

#                     # Beneficiário só pode no modo edição
#                     or (
#                         tipo_usuario == "beneficiario"
#                         and status_atual_db != "modo_edicao"
#                     )

#                     # Beneficiário não pode se já verificada
#                     or (
#                         tipo_usuario == "beneficiario"
#                         and verificada_db
#                     )

#                     # Admin/equipe não podem no modo edição
#                     or (
#                         tipo_usuario in ["admin", "equipe"]
#                         and status_atual_db == "modo_edicao"
#                     )
#                 ),
#                 key=f"resp_{relatorio_numero}_{pesquisa['id']}"
#             )

#         # -------- VERIFICADA --------
#         with col4:
#             verificada_ui = st.checkbox(
#                 "Verificada",
#                 value=verificada_db,
#                 disabled = (
#                     # Visitante nunca pode
#                     tipo_usuario == "visitante"

#                     # Beneficiário nunca pode verificar
#                     or tipo_usuario == "beneficiario"

#                     # Relatório em modo edição trava todos
#                     or status_atual_db == "modo_edicao"
#                 ),
#                 key=f"verif_{relatorio_numero}_{pesquisa['id']}"
#             )

#         # -------- DETECTA ALTERAÇÃO --------
#         linha_modificada = (
#             respondida_ui != respondida_db
#             or verificada_ui != verificada_db
#             or (
#                 arquivo is not None
#                 and not st.session_state.get(upload_salvo_key, False)
#             )
#         )

#         # -------- BOTÃO SALVAR --------
#         with col5:
#             if linha_modificada and pode_editar:

#                 if st.button(
#                     "Salvar",
#                     type="primary",
#                     key=f"salvar_{relatorio_numero}_{pesquisa['id']}",
#                     icon=":material/save:",
#                 ):


#                     with st.spinner("Salvando..."):

#                         # Conecta ao Drive SOMENTE aqui
#                         servico = obter_servico_drive()

#                         # Pasta do projeto
#                         pasta_projeto = obter_pasta_projeto(
#                             servico,
#                             projeto["codigo"],
#                             projeto["sigla"]
#                         )

#                         # Pasta Pesquisas (direto no projeto)
#                         pasta_pesquisas = obter_pasta_pesquisas(
#                             servico,
#                             pasta_projeto,
#                             projeto["codigo"]
#                         )

#                         url_anexo_final = url_anexo_db  # valor já salvo no banco (se existir)

#                         # ------------------------------
#                         # UPLOAD (somente se houver novo arquivo)
#                         # ------------------------------
#                         if (
#                             arquivo is not None
#                             and not st.session_state.get(upload_salvo_key, False)
#                         ):
#                             id_drive = enviar_arquivo_drive(
#                                 servico,
#                                 pasta_pesquisas,
#                                 arquivo
#                             )

#                             url_anexo_final = gerar_link_drive(id_drive)

#                             # Marca upload como concluído
#                             st.session_state[upload_salvo_key] = True

#                         # ------------------------------
#                         # MONTA O OBJETO DA PESQUISA
#                         # ------------------------------
#                         pesquisa_obj = {
#                             "id_pesquisa": pesquisa["id"],
#                             "respondida": respondida_ui,
#                             "verificada": verificada_ui
#                         }

#                         if url_anexo_final:
#                             pesquisa_obj["url_anexo"] = url_anexo_final

#                         # ------------------------------
#                         # VERIFICA SE JÁ EXISTE NO PROJETO
#                         # ------------------------------
#                         existe = col_projetos.count_documents(
#                             {
#                                 "codigo": codigo_projeto_atual,
#                                 "pesquisas.id_pesquisa": pesquisa["id"]
#                             }
#                         ) > 0

#                         if existe:
#                             col_projetos.update_one(
#                                 {
#                                     "codigo": codigo_projeto_atual,
#                                     "pesquisas.id_pesquisa": pesquisa["id"]
#                                 },
#                                 {
#                                     "$set": {
#                                         "pesquisas.$": pesquisa_obj
#                                     }
#                                 }
#                             )
#                         else:
#                             col_projetos.update_one(
#                                 {"codigo": codigo_projeto_atual},
#                                 {
#                                     "$push": {
#                                         "pesquisas": pesquisa_obj
#                                     }
#                                 }
#                             )



#                     # Limpa estados temporários
#                     st.session_state.pop(upload_key, None)
#                     st.session_state.pop(upload_salvo_key, None)

#                     st.success(":material/check: Salvo!")
#                     time.sleep(3)
#                     st.rerun()

#         st.divider()




# ---------- FORMULÁRIO ----------
if step_selecionado == "Formulário":

    ###########################################################################
    # 1. BUSCA O EDITAL CORRESPONDENTE AO PROJETO
    ###########################################################################

    edital = col_editais.find_one(
        {"codigo_edital": projeto["edital"]}
    )

    if not edital:
        st.error("Edital não encontrado para este projeto.")
        st.stop()

    perguntas = edital.get("perguntas_relatorio", [])

    if not perguntas:
        st.write('')
        st.error("O edital não possui perguntas cadastradas.")
        st.stop()

    # Ordena as perguntas pela ordem definida no edital
    perguntas = sorted(perguntas, key=lambda x: x.get("ordem", 0))


    ###########################################################################
    # 2. CONTROLE DE ESTADO POR RELATÓRIO (EVITA VAZAMENTO ENTRE ABAS)
    ###########################################################################

    # Identificador único do relatório atual
    relatorio_numero = relatorio["numero"]
    chave_relatorio_ativo = f"form_relatorio_{relatorio_numero}"

    # Se mudou de relatório, recarrega respostas do banco
    if st.session_state.get("form_relatorio_ativo") != chave_relatorio_ativo:
        st.session_state.form_relatorio_ativo = chave_relatorio_ativo


        # -------------------------------------------
        # CARREGA RESPOSTAS DO RELATÓRIO (DICT DE OBJETOS)
        # -------------------------------------------

        # Identificador único do relatório
        relatorio_numero = relatorio["numero"]

        # Evita vazamento entre abas
        if st.session_state.get("form_relatorio_ativo") != relatorio_numero:
            st.session_state.form_relatorio_ativo = relatorio_numero

            # Dicionário
            st.session_state.respostas_formulario = (
                relatorio.get("respostas_formulario", {}).copy()
            )




    ###########################################################################
    # 3. RENDERIZAÇÃO DO FORMULÁRIO
    ###########################################################################

    st.write("")
    st.write("")

    # -------------------------------------------------------------------------
    # Armazena uploads temporários em memória (evita múltiplos envios no rerun)
    # Somente no clique do botão "Salvar formulário" os arquivos serão enviados
    # -------------------------------------------------------------------------
    if "temp_uploads" not in st.session_state:
        st.session_state.temp_uploads = {}


    for pergunta in perguntas:
        tipo = pergunta.get("tipo")
        texto = pergunta.get("pergunta")
        opcoes = pergunta.get("opcoes", [])
        ordem = pergunta.get("ordem")

        # Chave única da pergunta dentro do relatório
        chave = f"pergunta_{ordem}"


        # ---------------------------------------------------------------------
        # TÍTULO (não salva resposta)
        # ---------------------------------------------------------------------
        if tipo == "titulo":
            st.subheader(texto)
            st.write("")
            continue


        # ---------------------------------------------------------------------
        # SUBTÍTULO (não salva resposta)
        # ---------------------------------------------------------------------
        elif tipo == "subtitulo":
            st.markdown(f"##### {texto}")
            st.write("")
            continue


        # ---------------------------------------------------------------------
        # PARÁGRAFO → apenas texto informativo
        # ---------------------------------------------------------------------
        elif tipo == "paragrafo":
            st.write(texto)
            st.write("")
            continue


        # ---------------------------------------------------------------------
        # TEXTO CURTO
        # ---------------------------------------------------------------------
        elif tipo == "texto_curto":

            resposta_atual = (
                st.session_state.respostas_formulario
                .get(chave, {})
                .get("resposta", "")
            )

            if pode_editar_relatorio:
                resposta = st.text_input(
                    label=texto,
                    value=resposta_atual,
                    key=f"input_{chave}"
                )

                st.session_state.respostas_formulario[chave] = {
                    "tipo": tipo,
                    "ordem": ordem,
                    "pergunta": texto,
                    "resposta": resposta
                }
            else:
                renderizar_visualizacao(texto, resposta_atual)


        # ---------------------------------------------------------------------
        # TEXTO LONGO
        # ---------------------------------------------------------------------
        elif tipo == "texto_longo":

            resposta_atual = (
                st.session_state.respostas_formulario
                .get(chave, {})
                .get("resposta", "")
            )

            if pode_editar_relatorio:
                resposta = st.text_area(
                    label=texto,
                    value=resposta_atual,
                    height=150,
                    key=f"input_{chave}"
                )

                st.session_state.respostas_formulario[chave] = {
                    "tipo": tipo,
                    "ordem": ordem,
                    "pergunta": texto,
                    "resposta": resposta
                }
            else:
                renderizar_visualizacao(texto, resposta_atual)


        # ---------------------------------------------------------------------
        # NÚMERO
        # ---------------------------------------------------------------------
        elif tipo == "numero":

            resposta_atual = (
                st.session_state.respostas_formulario
                .get(chave, {})
                .get("resposta", 0)
            )

            if pode_editar_relatorio:
                resposta = st.number_input(
                    label=texto,
                    value=float(resposta_atual),
                    step=1.0,
                    format="%g",
                    key=f"input_{chave}"
                )

                st.session_state.respostas_formulario[chave] = {
                    "tipo": tipo,
                    "ordem": ordem,
                    "pergunta": texto,
                    "resposta": resposta
                }
            else:
                renderizar_visualizacao(
                    texto,
                    formatar_numero_br_dinamico(resposta_atual)
                )


        # ---------------------------------------------------------------------
        # ESCOLHA ÚNICA
        # ---------------------------------------------------------------------
        elif tipo == "escolha_unica":

            resposta_atual = (
                st.session_state.respostas_formulario
                .get(chave, {})
                .get("resposta", opcoes[0] if opcoes else "")
            )

            if pode_editar_relatorio:
                resposta = st.radio(
                    label=texto,
                    options=opcoes,
                    index=opcoes.index(resposta_atual) if resposta_atual in opcoes else 0,
                    key=f"input_{chave}"
                )

                st.session_state.respostas_formulario[chave] = {
                    "tipo": tipo,
                    "ordem": ordem,
                    "pergunta": texto,
                    "resposta": resposta
                }
            else:
                renderizar_visualizacao(texto, resposta_atual)


        # ---------------------------------------------------------------------
        # MÚLTIPLA ESCOLHA
        # ---------------------------------------------------------------------
        elif tipo == "multipla_escolha":

            resposta_atual = (
                st.session_state.respostas_formulario
                .get(chave, {})
                .get("resposta", [])
            )

            if pode_editar_relatorio:
                resposta = st.multiselect(
                    label=texto,
                    options=opcoes,
                    default=resposta_atual,
                    key=f"input_{chave}"
                )

                st.session_state.respostas_formulario[chave] = {
                    "tipo": tipo,
                    "ordem": ordem,
                    "pergunta": texto,
                    "resposta": resposta
                }
            else:
                renderizar_visualizacao(texto, ", ".join(resposta_atual))



        # ---------------------------------------------------------------------
        # UPLOAD DE ARQUIVOS
        # ---------------------------------------------------------------------
        elif tipo == "upload_arquivo":

            MAX_MB = 10
            MAX_BYTES = MAX_MB * 1024 * 1024

            resposta_atual = (
                st.session_state.respostas_formulario
                .get(chave, {})
                .get("resposta", [])
            )

            if pode_editar_relatorio:

                arquivos = st.file_uploader(
                    label=f"{texto} (máx. 10 MB por arquivo)",
                    accept_multiple_files=True,
                    key=f"input_{chave}"
                )

                # ---------------------------------------------------------
                # Validação 
                # ---------------------------------------------------------
                if arquivos:
                    validos = [
                        arq for arq in arquivos
                        if arq.size <= MAX_BYTES
                    ]

                    for arq in arquivos:
                        if arq.size > MAX_BYTES:
                            st.warning(
                                f"O arquivo '{arq.name}' excede 10 MB e não será enviado."
                            )

                    # substitui (não acumula)
                    st.session_state.temp_uploads[chave] = validos
                else:
                    # se remover seleção, limpa também
                    st.session_state.temp_uploads.pop(chave, None)

                # ---------------------------------------------------------
                # Lista de arquivos já salvos (após uploader)
                # ---------------------------------------------------------
                if resposta_atual:
                    st.caption("Arquivos já enviados:")
                    for arq in resposta_atual:
                        link = gerar_link_drive(arq["id"])
                        st.markdown(
                            f":material/attach_file: [{arq['nome']}]({link})"
                        )

                st.session_state.respostas_formulario[chave] = {
                    "tipo": tipo,
                    "ordem": ordem,
                    "pergunta": texto,
                    "resposta": resposta_atual
                }

            else:
                st.markdown(f"**{texto}**")

                if resposta_atual:
                    for arq in resposta_atual:
                        link = gerar_link_drive(arq["id"])
                        st.markdown(
                            f":material/attach_file: [{arq['nome']}]({link})"
                        )
                else:
                    st.caption("Nenhum arquivo enviado")


        # ---------------------------------------------------------------------
        # TIPO NÃO SUPORTADO
        # ---------------------------------------------------------------------
        else:
            st.warning(f"Tipo de pergunta não suportado: {tipo}")

        st.write("")




    ###########################################################################
    # 4. BOTÃO PARA SALVAR RESPOSTAS + UPLOAD REAL PARA O DRIVE
    ###########################################################################
    if pode_editar_relatorio:
        if st.button("Salvar formulário", type="primary", icon=":material/save:"):

            with st.spinner("Salvando o formulário..."):

                servico = None

                # ---------------------------------------------------------
                # Upload incremental (somente se houver novos arquivos)
                # ---------------------------------------------------------
                for chave, arquivos in list(st.session_state.temp_uploads.items()):

                    if not arquivos:
                        continue

                    if not servico:
                        servico = obter_servico_drive()

                    pasta_projeto_id = obter_pasta_projeto(
                        servico,
                        projeto["codigo"],
                        projeto["sigla"]
                    )

                    pasta_relatorios_id = obter_pasta_relatorios(
                        servico,
                        pasta_projeto_id
                    )

                    novos_arquivos = []

                    for arquivo in arquivos:
                        arquivo_id = enviar_arquivo_drive(
                            servico,
                            pasta_relatorios_id,
                            arquivo
                        )

                        if arquivo_id:
                            novos_arquivos.append({
                                "id": arquivo_id,
                                "nome": arquivo.name
                            })

                    existentes = (
                        st.session_state.respostas_formulario[chave]
                        .get("resposta", [])
                    )

                    st.session_state.respostas_formulario[chave]["resposta"] = (
                        existentes + novos_arquivos
                    )

                # ---------------------------------------------------------
                # LIMPEZA CRÍTICA (evita duplicação no rerun)
                # ---------------------------------------------------------
                st.session_state.temp_uploads = {}

                # limpa widgets file_uploader
                for k in list(st.session_state.keys()):
                    if k.startswith("input_pergunta_"):
                        del st.session_state[k]

                # ---------------------------------------------------------
                # Salva no Mongo
                # ---------------------------------------------------------
                nome_usuario = st.session_state.get("nome", "Usuário")
                data_verificacao = datetime.datetime.now().strftime("%d/%m/%Y")

                col_projetos.update_one(
                    {
                        "codigo": projeto["codigo"],
                        "relatorios.numero": relatorio_numero
                    },
                    {
                        "$set": {
                            "relatorios.$.respostas_formulario":
                                st.session_state.respostas_formulario,

                            "relatorios.$.form_verif_por":
                                f"{nome_usuario} em {data_verificacao}"
                        }
                    }
                )

            st.success("Respostas salvas com sucesso!", icon=":material/check:")
            time.sleep(3)
            st.rerun()


# ---------- ENVIAR ----------
if step_selecionado == "Enviar":

    st.write('')
    st.write('')

    # --------------------------------------------------
    # CASO 1: RELATÓRIO JÁ ENVIADO (EM ANÁLISE)
    # --------------------------------------------------
    if status_atual_db == "em_analise":

        # Recupera a data de envio salva no banco
        data_envio = relatorio.get("data_envio")

        # Formata a data para exibição (DD/MM/YYYY)
        if data_envio:
            data_formatada = datetime.datetime.strptime(
                data_envio, "%Y-%m-%d"
            ).strftime("%d/%m/%Y")
        else:
            data_formatada = "—"

        st.markdown(
            f"##### Relatório enviado em {data_formatada}.")

        st.write("Aguardando análise.")
    # --------------------------------------------------
    # CASO 2: RELATÓRIO APROVADO
    # --------------------------------------------------
    elif status_atual_db == "aprovado":
        st.markdown("##### Relatório aprovado.")

    # --------------------------------------------------
    # CASO 3: RELATÓRIO EM MODO EDIÇÃO E USUÁRIO PODE EDITAR
    # --------------------------------------------------
    elif pode_editar_relatorio:

        st.markdown("### Enviar relatório")

        saldo_parcela = calcular_saldo_parcela()

        saldo_formatado = f"{saldo_parcela:.1f}".replace(".", ",")


        # Mensagem do saldo 
        if saldo_parcela > 20:

            st.markdown(
                f"A parcela atual ainda tem "
                f"<span style='font-size:22px'><b>{saldo_formatado}%</b></span> de saldo.",
                unsafe_allow_html=True
            )

            st.markdown(
                "Recomendamos que **envie o relatório** quando o saldo for **menor que 20%**."
            )

        else:
            st.markdown(
                f"A parcela atual tem "
                f"<span style='font-size:22px'><b>{saldo_formatado}%</b></span> de saldo.",
                unsafe_allow_html=True
            )

            st.markdown(
                "**O relatório já pode ser enviado.**"
            )



        st.divider()
        
        st.write(
            "Ao enviar o relatório, ele será encaminhado para análise "
            "e não poderá mais ser editado enquanto estiver em análise."
        )

        enviar = st.button(
            "Enviar relatório",
            type="primary",
            icon=":material/send:"
        )

        if enviar:

            # Gera a data de envio no formato ISO (YYYY-MM-DD)
            data_envio = datetime.datetime.now().strftime("%Y-%m-%d")

            with st.spinner("Enviando relatório ..."):

                # --------------------------------------------------
                # 1. ATUALIZA STATUS E DATA DO RELATÓRIO
                # --------------------------------------------------
                col_projetos.update_one(
                    {
                        "codigo": projeto_codigo,
                        "relatorios.numero": relatorio_numero
                    },
                    {
                        "$set": {
                            "relatorios.$.status_relatorio": "em_analise",
                            "relatorios.$.data_envio": data_envio
                        }
                    }
                )

                # --------------------------------------------------
                # 2. ATUALIZA STATUS DOS RELATOS ABERTOS
                #    (somente os relatos deste relatório)
                # --------------------------------------------------
                projeto_atualizado = col_projetos.find_one(
                    {"codigo": projeto_codigo}
                )

                componentes = projeto_atualizado["plano_trabalho"]["componentes"]

                houve_alteracao = False


                # ------------------------------------------------------
                # Percorre componentes do plano de trabalho
                # ------------------------------------------------------
                for componente in componentes:

                    # Recupera atividades de forma segura
                    atividades = componente.get("atividades", [])

                    # Se não houver atividades, pula o componente
                    if not atividades:
                        continue

                    # --------------------------------------------------
                    # Percorre atividades
                    # --------------------------------------------------
                    for atividade in atividades:


                        # Recupera relatos de forma segura
                        relatos = atividade.get("relatos", [])

                        # Se não houver relatos, continua
                        if not relatos:
                            continue

                        # --------------------------------------------------
                        # Percorre relatos
                        # --------------------------------------------------
                        for relato in relatos:

                            # ----------------------------------------------
                            # Apenas relatos do relatório atual
                            # e que ainda estejam abertos
                            # ----------------------------------------------
                            if (
                                relato.get("relatorio_numero") == relatorio_numero
                                and relato.get("status_relato") == "aberto"
                            ):
                                relato["status_relato"] = "em_analise"
                                houve_alteracao = True



                # Salva no Mongo apenas se houve mudança
                if houve_alteracao:
                    col_projetos.update_one(
                        {"codigo": projeto_codigo},
                        {
                            "$set": {
                                "plano_trabalho.componentes": componentes
                            }
                        }
                    )


                # --------------------------------------------------
                # ENVIA E-MAIL PARA PADRINHOS
                # --------------------------------------------------
                
                
                notificar_padrinhos_relatorio(
                    col_pessoas=col_pessoas,
                    numero_relatorio=relatorio_numero,
                    projeto=projeto_atualizado,
                    logo_url=logo_cepf
                )


            st.success("Relatório enviado para análise.", icon=":material/check:")

            # Reseta para o rerun não se perder.
            st.session_state.step_relatorio = "Atividades"

            time.sleep(3)
            st.rerun()

    # --------------------------------------------------
    # CASO 4: USUÁRIO NÃO PODE EDITAR
    # --------------------------------------------------
    else:
        st.info("Este relatório não pode ser editado no momento.")


# ---------- AVALIAÇÃO ----------
if step_selecionado == "Avaliação":

    st.write("")
    st.write("")

    relatos_ok = todos_relatos_aceitos(projeto, relatorio_numero)
    despesas_ok = todas_despesas_aceitas(projeto, relatorio_numero)
    indicadores_ok = todos_indicadores_aceitos(projeto, relatorio_numero)

    relatorio_db = next(
        r for r in projeto["relatorios"]
        if r["numero"] == relatorio_numero
    )
    
    edital = col_editais.find_one(
        {"codigo_edital": projeto["edital"]}
    )

    perguntas_monitoramento = sorted(
        edital.get("perguntas_monitoramento", []),
        key=lambda x: x.get("ordem", 0)
    )
    
    if not perguntas_monitoramento:
        st.caption(
            "Nenhuma pergunta de monitoramento foi cadastrada para este edital."
        )
    
    chave_monitoramento = f"monitoramento_{relatorio_numero}"

    if st.session_state.get("monitoramento_ativo") != chave_monitoramento:

        st.session_state.monitoramento_ativo = chave_monitoramento

        st.session_state.respostas_monitoramento = (
            relatorio.get("respostas_monitoramento", {}).copy()
        )

    # Layout em quatro colunas para avaliação, devolutiva e aprovação
    col1, col2 = st.columns([1, 1], gap="medium")

    # Relatório de monitoramento
    with col1:

        st.write("**Relatório de Monitoramento**")
        st.write("")
        
        # -------------------------------------------------------------------------
        # Armazena uploads temporários em memória (evita múltiplos envios no rerun)
        # Somente no clique do botão "Salvar formulário" os arquivos serão enviados
        # -------------------------------------------------------------------------
        if "temp_uploads_monitoramento" not in st.session_state:
            st.session_state.temp_uploads_monitoramento = {}
            
        pode_editar_monitoramento = (
            status_atual_db == "em_analise"
        )


        for pergunta in perguntas_monitoramento:
            tipo = pergunta.get("tipo")
            texto = pergunta.get("pergunta")
            opcoes = pergunta.get("opcoes", [])
            ordem = pergunta.get("ordem")

            # Chave única da pergunta dentro do relatório
            chave = f"pergunta_{ordem}"


            # ---------------------------------------------------------------------
            # TÍTULO (não salva resposta)
            # ---------------------------------------------------------------------
            if tipo == "titulo":
                st.subheader(texto)
                st.write("")
                continue


            # ---------------------------------------------------------------------
            # SUBTÍTULO (não salva resposta)
            # ---------------------------------------------------------------------
            elif tipo == "subtitulo":
                st.markdown(f"##### {texto}")
                st.write("")
                continue


            # ---------------------------------------------------------------------
            # PARÁGRAFO → apenas texto informativo
            # ---------------------------------------------------------------------
            elif tipo == "paragrafo":
                st.write(texto)
                st.write("")
                continue


            # ---------------------------------------------------------------------
            # TEXTO CURTO
            # ---------------------------------------------------------------------
            elif tipo == "texto_curto":

                resposta_atual = (
                    st.session_state.respostas_monitoramento
                    .get(chave, {})
                    .get("resposta", "")
                )

                if pode_editar_monitoramento:
                    resposta = st.text_input(
                        label=texto,
                        value=resposta_atual,
                        key=f"monitoramento_{chave}"
                    )

                    st.session_state.respostas_monitoramento[chave] = {
                        "tipo": tipo,
                        "ordem": ordem,
                        "pergunta": texto,
                        "resposta": resposta
                    }
                else:
                    renderizar_visualizacao(texto, resposta_atual)


            # ---------------------------------------------------------------------
            # TEXTO LONGO
            # ---------------------------------------------------------------------
            elif tipo == "texto_longo":

                resposta_atual = (
                    st.session_state.respostas_monitoramento
                    .get(chave, {})
                    .get("resposta", "")
                )

                if pode_editar_monitoramento:
                    resposta = st.text_area(
                        label=texto,
                        value=resposta_atual,
                        height=150,
                        key=f"monitoramento_{chave}"
                    )

                    st.session_state.respostas_monitoramento[chave] = {
                        "tipo": tipo,
                        "ordem": ordem,
                        "pergunta": texto,
                        "resposta": resposta
                    }
                else:
                    renderizar_visualizacao(texto, resposta_atual)


            # ---------------------------------------------------------------------
            # NÚMERO
            # ---------------------------------------------------------------------
            elif tipo == "numero":

                resposta_atual = (
                    st.session_state.respostas_monitoramento
                    .get(chave, {})
                    .get("resposta", 0)
                )

                if pode_editar_monitoramento:
                    resposta = st.number_input(
                        label=texto,
                        value=float(resposta_atual),
                        step=1.0,
                        format="%g",
                        key=f"monitoramento_{chave}"
                    )

                    st.session_state.respostas_monitoramento[chave] = {
                        "tipo": tipo,
                        "ordem": ordem,
                        "pergunta": texto,
                        "resposta": resposta
                    }
                else:
                    renderizar_visualizacao(
                        texto,
                        formatar_numero_br_dinamico(resposta_atual)
                    )


            # ---------------------------------------------------------------------
            # ESCOLHA ÚNICA
            # ---------------------------------------------------------------------
            elif tipo == "escolha_unica":

                resposta_atual = (
                    st.session_state.respostas_monitoramento
                    .get(chave, {})
                    .get("resposta", opcoes[0] if opcoes else "")
                )

                if pode_editar_monitoramento:
                    resposta = st.radio(
                        label=texto,
                        options=opcoes,
                        index=opcoes.index(resposta_atual) if resposta_atual in opcoes else 0,
                        key=f"monitoramento_{chave}"
                    )

                    st.session_state.respostas_monitoramento[chave] = {
                        "tipo": tipo,
                        "ordem": ordem,
                        "pergunta": texto,
                        "resposta": resposta
                    }
                else:
                    renderizar_visualizacao(texto, resposta_atual)


            # ---------------------------------------------------------------------
            # MÚLTIPLA ESCOLHA
            # ---------------------------------------------------------------------
            elif tipo == "multipla_escolha":

                resposta_atual = (
                    st.session_state.respostas_monitoramento
                    .get(chave, {})
                    .get("resposta", [])
                )

                if not isinstance(resposta_atual, list):
                    resposta_atual = []

                resposta_atual = [
                    item
                    for item in resposta_atual
                    if item in opcoes
                ]

                if pode_editar_monitoramento:
                    resposta = st.multiselect(
                        label=texto,
                        options=opcoes,
                        default=resposta_atual,
                        key=f"monitoramento_{chave}",
                        placeholder=""
                    )

                    st.session_state.respostas_monitoramento[chave] = {
                        "tipo": tipo,
                        "ordem": ordem,
                        "pergunta": texto,
                        "resposta": resposta
                    }
                else:
                    renderizar_visualizacao(texto, ", ".join(resposta_atual))



            # ---------------------------------------------------------------------
            # UPLOAD DE ARQUIVOS
            # ---------------------------------------------------------------------
            elif tipo == "upload_arquivo":

                MAX_MB = 10
                MAX_BYTES = MAX_MB * 1024 * 1024

                resposta_atual = (
                    st.session_state.respostas_monitoramento
                    .get(chave, {})
                    .get("resposta", [])
                )

                if pode_editar_monitoramento:

                    arquivos = st.file_uploader(
                        label=f"{texto} (máx. 10 MB por arquivo)",
                        accept_multiple_files=True,
                        key=f"monitoramento_{chave}"
                    )

                    # ---------------------------------------------------------
                    # Validação 
                    # ---------------------------------------------------------
                    if arquivos:
                        validos = [
                            arq for arq in arquivos
                            if arq.size <= MAX_BYTES
                        ]

                        for arq in arquivos:
                            if arq.size > MAX_BYTES:
                                st.warning(
                                    f"O arquivo '{arq.name}' excede 10 MB e não será enviado."
                                )

                        # substitui (não acumula)
                        st.session_state.temp_uploads_monitoramento[chave] = validos
                    else:
                        # se remover seleção, limpa também
                        st.session_state.temp_uploads_monitoramento.pop(chave, None)

                    # ---------------------------------------------------------
                    # Lista de arquivos já salvos (após uploader)
                    # ---------------------------------------------------------
                    if resposta_atual:
                        st.caption("Arquivos já enviados:")
                        for arq in resposta_atual:
                            link = gerar_link_drive(arq["id"])
                            st.markdown(
                                f":material/attach_file: [{arq['nome']}]({link})"
                            )

                    st.session_state.respostas_monitoramento[chave] = {
                        "tipo": tipo,
                        "ordem": ordem,
                        "pergunta": texto,
                        "resposta": resposta_atual
                    }

                else:
                    st.markdown(f"**{texto}**")

                    if resposta_atual:
                        for arq in resposta_atual:
                            link = gerar_link_drive(arq["id"])
                            st.markdown(
                                f":material/attach_file: [{arq['nome']}]({link})"
                            )
                    else:
                        st.caption("Nenhum arquivo enviado")


            # ---------------------------------------------------------------------
            # TIPO NÃO SUPORTADO
            # ---------------------------------------------------------------------
            else:
                st.warning(f"Tipo de pergunta não suportado: {tipo}")

            st.write("")
                
        ###########################################################################
        # 4. BOTÃO PARA SALVAR RESPOSTAS + UPLOAD REAL PARA O DRIVE
        ###########################################################################
        if pode_editar_monitoramento:
            if st.button("Salvar monitoramento", type="primary", icon=":material/save:", key="salvar_monitoramento"):

                with st.spinner("Salvando o relatório de monitoramento..."):

                    servico = None

                    # ---------------------------------------------------------
                    # Upload incremental (somente se houver novos arquivos)
                    # ---------------------------------------------------------
                    for chave, arquivos in list(st.session_state.temp_uploads_monitoramento.items()):

                        if not arquivos:
                            continue

                        if not servico:
                            servico = obter_servico_drive()

                        pasta_projeto_id = obter_pasta_projeto(
                            servico,
                            projeto["codigo"],
                            projeto["sigla"]
                        )

                        pasta_relatorios_id = obter_pasta_relatorios(
                            servico,
                            pasta_projeto_id
                        )

                        novos_arquivos = []

                        for arquivo in arquivos:
                            arquivo_id = enviar_arquivo_drive(
                                servico,
                                pasta_relatorios_id,
                                arquivo
                            )

                            if arquivo_id:
                                novos_arquivos.append({
                                    "id": arquivo_id,
                                    "nome": arquivo.name
                                })

                        existentes = (
                            st.session_state.respostas_monitoramento[chave]
                            .get("resposta", [])
                        )

                        st.session_state.respostas_monitoramento[chave]["resposta"] = (
                            existentes + novos_arquivos
                        )

                    # ---------------------------------------------------------
                    # LIMPEZA CRÍTICA (evita duplicação no rerun)
                    # ---------------------------------------------------------
                    st.session_state.temp_uploads_monitoramento = {}

                    # # limpa widgets file_uploader
                    # for k in list(st.session_state.keys()):
                    #     if k.startswith("monitoramento_pergunta_"):
                    #         del st.session_state[k]

                    # ---------------------------------------------------------
                    # Salva no Mongo
                    # ---------------------------------------------------------
                    nome_usuario = st.session_state.get("nome", "Usuário")
                    data_verificacao = datetime.datetime.now().strftime("%d/%m/%Y")

                    col_projetos.update_one(
                        {
                            "codigo": projeto["codigo"],
                            "relatorios.numero": relatorio_numero
                        },
                        {
                            "$set": {
                                "relatorios.$.respostas_monitoramento":
                                    st.session_state.respostas_monitoramento,

                                "relatorios.$.monitoramento_preenchido_por":
                                    f"{nome_usuario} em {data_verificacao}"
                            }
                        }
                    )

                st.success("Respostas salvas com sucesso!", icon=":material/check:")
                time.sleep(3)
                st.rerun()
            
            if relatorio_db.get("monitoramento_preenchido_por"):
                st.caption(
                    f"Monitoramento verificado por "
                    f"{relatorio_db['monitoramento_preenchido_por']}"
                )        

    # ###############################################################
    # COLUNA 3 — ENCAMINHAMENTO
    # ###############################################################
    with col2:

        st.write("**Encaminhamento**")
        st.write("")

        # --------------------------------------------------
        # CONTROLE DE PERMISSÃO
        # --------------------------------------------------
        pode_encaminhar = status_atual_db == "em_analise"

        if "confirmar_reprovacao" not in st.session_state:
            st.session_state["confirmar_reprovacao"] = False

        if "confirmar_aprovacao" not in st.session_state:
            st.session_state["confirmar_aprovacao"] = False

        # Segurança adicional
        if not pode_encaminhar:
            st.session_state["confirmar_reprovacao"] = False
            st.session_state["confirmar_aprovacao"] = False

        # --------------------------------------------------
        # INPUT
        # --------------------------------------------------
        texto_devolutiva = st.text_area(
            "Devolutiva",
            placeholder="Escreva uma mensagem de devolutiva...",
            disabled=not pode_encaminhar
        )
        
        monitoramento_ok = bool(
            relatorio_db.get("respostas_monitoramento", {})
        )
        
        # --------------------------------------------------
        # REGRA: CHECKLIST PARA APROVAÇÃO
        # --------------------------------------------------
        pode_aprovar = all([
            relatos_ok,
            despesas_ok,
            indicadores_ok,
            "benef_verif_por" in relatorio_db,
            "form_verif_por" in relatorio_db,
            monitoramento_ok
        ])

        # --------------------------------------------------
        # BOTÕES
        # --------------------------------------------------
        with st.container(horizontal=True):

            botao_reprovar = st.button(
                "Reprovar e devolver",
                type="secondary",
                icon=":material/replay:",
                disabled=not pode_encaminhar,
                width=225
            )

            botao_aprovar = st.button(
                "Aprovar",
                type="primary",
                icon=":material/check_circle:",
                disabled=(not pode_encaminhar or not pode_aprovar),
                width=225
            )

        # ==================================================
        # AÇÃO — REPROVAR
        # ==================================================
        if botao_reprovar:

            if "monitoramento_preenchido_por" not in relatorio_db:

                st.warning(
                    "O relatório de monitoramento deve ser preenchido e salvo antes da avaliação."
                )

            elif not texto_devolutiva or not texto_devolutiva.strip():

                st.warning(
                    "A devolutiva deve ser preenchida para a reprovação."
                )

            else:

                st.session_state["confirmar_reprovacao"] = True

        if st.session_state["confirmar_reprovacao"]:

            st.warning(
                "Você tem certeza que deseja reprovar o relatório?\n\n"
                "Os responsáveis pelo projeto serão notificados por e-mail."
            )

            if st.button(
                "Sim, reprovar relatório",
                type="primary",
                icon=":material/check:",
                width=225
            ):

                nova_devolucao = {
                    "data_devolucao": datetime.datetime.now().strftime("%d/%m/%Y"),
                    "autor": st.session_state.get("nome", "Usuário não identificado"),
                    "texto_devolutiva": texto_devolutiva.strip(),
                    "status_devolucao": "Devolvido"

                }

                col_projetos.update_one(
                    {
                        "codigo": projeto_codigo,
                        "relatorios.numero": relatorio_numero
                    },
                    {
                        "$push": {"relatorios.$.devolucao": nova_devolucao},
                        "$set": {"relatorios.$.status_relatorio": "modo_edicao"}
                    }
                )

                # envio de email
                organizacao = db["organizacoes"].find_one(
                    {"_id": projeto.get("id_organizacao")}
                )

                nome_org = organizacao.get("nome_organizacao") if organizacao else "Organização"

                emails_destino = [
                    c.get("email")
                    for c in projeto.get("contatos", [])
                    if c.get("email")
                ]

                if emails_destino:
                    email_html = gerar_email_relatorio_reprovado(
                        nome_do_contato="Prezados(as)",
                        relatorio_numero=relatorio_numero,
                        projeto=projeto,
                        organizacao=nome_org,
                        logo_url=logo_cepf
                    )

                    enviar_email(
                        email_html,
                        emails_destino,
                        f"Relatório {relatorio_numero} não aprovado"
                    )

                st.success("Relatório reprovado e devolutiva enviada.", icon=":material/check:")
                time.sleep(3)

                st.session_state["confirmar_reprovacao"] = False
                st.rerun()


        # ==================================================
        # AÇÃO — APROVAR (COM CONFIRMAÇÃO + VALIDAÇÃO)
        # ==================================================
        if botao_aprovar:

            if "monitoramento_preenchido_por" not in relatorio_db:

                st.warning(
                    "O relatório de monitoramento deve ser preenchido e salvo antes da aprovação."
                )

            elif not texto_devolutiva or not texto_devolutiva.strip():
                st.warning("A devolutiva deve ser preenchida para aprovação.")
                
            else:
                st.session_state["confirmar_aprovacao"] = True

        if st.session_state["confirmar_aprovacao"]:

            st.warning(
                "Você tem certeza que deseja aprovar o relatório? \n\n"
                "Os responsáveis serão notificados por e-mail."
            )

            if st.button(
                "Sim, aprovar relatório",
                type="primary",
                icon=":material/check:",
                width=225
            ):

                # --------------------------------------------------
                # REGISTRA DEVOLUTIVA 
                # --------------------------------------------------
                nova_devolucao = {
                    "data_devolucao": datetime.datetime.now().strftime("%d/%m/%Y"),
                    "autor": st.session_state.get("nome", "Usuário"),
                    "texto_devolutiva": texto_devolutiva.strip(),
                    "status_devolucao": "Aprovado"
                }

                projeto["relatorios"][idx].setdefault("devolucao", []).append(nova_devolucao)

                # --------------------------------------------------
                # APROVAÇÃO
                # --------------------------------------------------
                data_hoje = datetime.datetime.now().strftime("%d/%m/%Y")
                nome_aprovador = st.session_state.get("nome", "Usuário")

                projeto["relatorios"][idx]["status_relatorio"] = "aprovado"
                projeto["relatorios"][idx]["data_aprovacao"] = data_hoje
                projeto["relatorios"][idx]["aprovado_por"] = nome_aprovador

                col_projetos.update_one(
                    {"codigo": projeto_codigo},
                    {"$set": {"relatorios": projeto["relatorios"]}}
                )

                # --------------------------------------------------
                # EMAIL
                # --------------------------------------------------

                # COLETA TODOS OS EMAILS DOS CONTATOS
                emails_destino = [
                    c.get("email")
                    for c in projeto.get("contatos", [])
                    if c.get("email")
                ]

                # --------------------------------------------------
                # ENVIO ÚNICO DE EMAIL
                # --------------------------------------------------

                organizacao = db["organizacoes"].find_one(
                    {"_id": projeto.get("id_organizacao")}
                )

                nome_org = organizacao.get("nome_organizacao") if organizacao else "Organização"

                emails_destino = [
                    c.get("email")
                    for c in projeto.get("contatos", [])
                    if c.get("email")
                ]

                if emails_destino:

                    email_html = gerar_email_relatorio_aprovado(
                        nome_do_contato="Prezados(as)",
                        relatorio_numero=relatorio_numero,
                        projeto=projeto,
                        organizacao=nome_org,
                        logo_url=logo_cepf
                    )

                    enviar_email(
                        email_html,
                        emails_destino,
                        f"Relatório {relatorio_numero} aprovado"
                    )

                st.success("Relatório aprovado com sucesso.", icon=":material/check:")
                time.sleep(3)

                st.session_state["confirmar_aprovacao"] = False
                st.rerun()

        # --------------------------------------------------
        # LISTAGEM DE DEVOLUÇÕES
        # --------------------------------------------------

        devolucoes = relatorio_db.get("devolucao", [])


        if devolucoes:

            # --------------------------------------------------
            # CONTROLE DE ESTADO DE EXCLUSÃO
            # --------------------------------------------------
            if "dev_avaliacao_apagando" not in st.session_state:
                st.session_state["dev_avaliacao_apagando"] = None

            elif st.session_state["dev_avaliacao_apagando"] is not None:
                if st.session_state["dev_avaliacao_apagando"] >= len(devolucoes):
                    st.session_state["dev_avaliacao_apagando"] = None


            st.write("")
            st.write("**Histórico de devolutivas**")

            for i, d in enumerate(reversed(devolucoes)):

                idx_real = len(devolucoes) - 1 - i


                with st.container(border=True):

                    status = d.get("status_devolucao", "—")

                    # --------------------------------------------------
                    # DEFINIÇÃO DE COR POR STATUS
                    # --------------------------------------------------
                    if status == "Devolvido":
                        cor = "rgba(226, 101, 12)"
                    elif status == "Aprovado":
                        cor = "rgba(110, 140, 60)"
                    else:
                        cor = "#999999"  # fallback neutro

                    # --------------------------------------------------
                    # RENDERIZAÇÃO
                    # --------------------------------------------------
                    st.markdown(
                        f"<span style='color: {cor}; font-weight: 600;'>{status}</span>",
                        unsafe_allow_html=True
                    )

                    st.markdown(
                        f"**{d.get('autor')}** · {d.get('data_devolucao')}"
                    )

                    st.markdown(
                        d.get("texto_devolutiva", "").replace("\n", "<br>"),
                        unsafe_allow_html=True
                    )

                    # --------------------------------------------------
                    # BOTÃO EXCLUIR
                    # --------------------------------------------------
                    with st.container(horizontal=True, horizontal_alignment="right"):

                        if st.button(
                            "Excluir",
                            key=f"del_dev_avaliacao_{relatorio_numero}_{idx_real}",
                            type="tertiary",
                            icon=":material/delete:"
                        ):
                            st.session_state["dev_avaliacao_apagando"] = idx_real
                            st.rerun()

                    if st.session_state["dev_avaliacao_apagando"] == idx_real:

                        st.warning(
                            "Tem certeza que deseja apagar esta devolução? Esta ação não pode ser desfeita.",
                            icon=":material/warning:"
                        )

                        with st.container(horizontal=True):

                            if st.button(
                                "Sim, apagar",
                                key=f"confirm_del_dev_avaliacao_{relatorio_numero}_{idx_real}",
                                type="primary",
                                icon=":material/delete:"
                            ):

                                # --------------------------------------------------
                                # REMOVE DA LISTA
                                # --------------------------------------------------
                                relatorio["devolucao"].pop(idx_real)

                                # --------------------------------------------------
                                # ATUALIZA NO MONGO
                                # --------------------------------------------------
                                col_projetos.update_one(
                                    {"codigo": projeto_codigo},
                                    {
                                        "$set": {
                                            "relatorios": projeto["relatorios"]
                                        }
                                    }
                                )

                                st.success("Devolutiva excluída.", icon=":material/check:")
                                time.sleep(3)

                                st.session_state["dev_avaliacao_apagando"] = None
                                st.rerun()

                            if st.button(
                                "Cancelar",
                                key=f"cancel_del_dev_avaliacao_{relatorio_numero}_{idx_real}"
                            ):
                                st.session_state["dev_avaliacao_apagando"] = None
                                st.rerun()


# ###################################################################################################
# SIDEBAR DA PÁGINA DO PROJETO
# ###################################################################################################

sidebar_projeto()
