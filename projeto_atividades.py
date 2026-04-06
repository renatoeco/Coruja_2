import streamlit as st
import pandas as pd
import streamlit_shadcn_ui as ui
import datetime
import time
import bson

from funcoes_auxiliares import (
    conectar_mongo_coruja, 
    gerar_link_drive,
    sidebar_projeto,
    enviar_email,
    calcular_status_atividade
)




st.set_page_config(page_title="Atividades", page_icon=":material/assignment:")




# ###################################################################################################
# SIDEBAR DA PÁGINA DO PROJETO
# ###################################################################################################

sidebar_projeto()



###########################################################################################################
# CONFIGURAÇÕES DO STREAMLIT
###########################################################################################################






###########################################################################################################
# CONEXÃO COM O BANCO DE DADOS MONGODB
###########################################################################################################

# Conecta-se ao banco de dados MongoDB (usa cache automático para melhorar performance)
db = conectar_mongo_coruja()

# Projetos
col_projetos = db["projetos"]

# Indicadores
col_indicadores = db["indicadores"]

# Editais
col_editais = db["editais"]

# Pessoas
col_pessoas = db["pessoas"]

#Organizações
col_organizacoes = db["organizacoes"]




###########################################################################################################
# FUNÇÕES
###########################################################################################################



# Função para calcuar o status da atividade

# def calcular_status_atividade(atividade):

#     hoje = pd.Timestamp.today().normalize()

#     data_inicio = pd.to_datetime(
#         atividade.get("data_inicio"),
#         format="%d/%m/%Y",
#         errors="coerce"
#     )

#     data_fim = pd.to_datetime(
#         atividade.get("data_fim"),
#         format="%d/%m/%Y",
#         errors="coerce"
#     )

#     porcentagem = atividade.get("porcentagem_atv", 0)

#     # Segurança
#     if pd.isna(data_inicio) or pd.isna(data_fim):
#         return "sem_data"

#     # Regra 1 — concluída
#     if porcentagem == 100:
#         return "concluída"

#     # Marcos de tempo
#     inicio_mais_30 = data_inicio + pd.Timedelta(days=30)
#     fim_menos_30 = data_fim - pd.Timedelta(days=30)

#     # Regra 2 — porcentagem == 0
#     if porcentagem == 0:

#         if hoje < inicio_mais_30:
#             return "prevista"

#         elif inicio_mais_30 <= hoje < fim_menos_30:
#             return "atrasada"

#         elif fim_menos_30 <= hoje <= data_fim:
#             return "próximo ao prazo"

#         elif hoje > data_fim:
#             return "atrasada"

#     # Regra 3 — em andamento
#     if 0 < porcentagem < 100:

#         if hoje < fim_menos_30:
#             return "em andamento"

#         elif fim_menos_30 <= hoje <= data_fim:
#             return "próximo ao prazo"

#         elif hoje > data_fim:
#             return "atrasada"

#     return "indefinido"

# ==================================================
# Função para renderizar a interface de ações da equipe, no modo análise da solicitação de remanejamento
# ==================================================


def renderizar_acoes_remanejamento(item, idx):

    status = item.get("status_remanejamento")

    if st.session_state.get("tipo_usuario") in ["admin", "equipe"] and status == "em_analise":

        # ==================================================
        # BOTÃO APROVAR
        # ==================================================

        if st.button(
            "Aprovar",
            key=f"aprovar_remanej_atv_{idx}",
            type="primary",
            icon=":material/check:",
            width="stretch"
        ):

            # ==================================================
            # REMANEJAMENTO TIPO ALTERAÇÃO
            # ==================================================

            if "antes" in item:

                atividade_id = item.get("atividade_id")
                alteracoes = item.get("depois", {})

                set_updates = {}

                for campo, valor in alteracoes.items():

                    set_updates[
                        f"plano_trabalho.componentes.$[].atividades.$[atv].{campo}"
                    ] = valor


                col_projetos.update_one(
                    {"codigo": codigo_projeto_atual},
                    {
                        "$set": {
                            **set_updates,
                            f"plano_trabalho.remanejamentos_atividades.{idx}.status_remanejamento": "aceito",
                            f"plano_trabalho.remanejamentos_atividades.{idx}.data_aprov_remanej": datetime.datetime.now().strftime("%d/%m/%Y")
                        }
                    },
                    array_filters=[
                        {"atv.id": atividade_id}
                    ]
                )


            # ==================================================
            # REMANEJAMENTO TIPO ADICIONAR ATIVIDADE
            # ==================================================

            elif "add_atividade" in item:

                componente_nome = item.get("componente")

                descricao = item.get("add_atividade")
                data_inicio = item.get("data_inicio")
                data_fim = item.get("data_fim")

                novo_id = str(bson.ObjectId())

                nova_atividade = {
                    "id": novo_id,
                    "atividade": descricao,
                    "data_inicio": data_inicio,
                    "data_fim": data_fim,
                }

                col_projetos.update_one(
                    {"codigo": codigo_projeto_atual},
                    {
                        "$push": {
                            "plano_trabalho.componentes.$[comp].atividades": nova_atividade
                        },
                        "$set": {
                            f"plano_trabalho.remanejamentos_atividades.{idx}.status_remanejamento": "aceito",
                            f"plano_trabalho.remanejamentos_atividades.{idx}.data_aprov_remanej": datetime.datetime.now().strftime("%d/%m/%Y")
                        }
                    },
                    array_filters=[
                        {"comp.componente": componente_nome},
                    ]
                )


            # ==================================================
            # REMANEJAMENTO TIPO REMOVER ATIVIDADE
            # ==================================================

            elif "del_atividade" in item:

                componente_nome = item.get("componente")
                atividade_id = item.get("atividade_id")

                col_projetos.update_one(
                    {"codigo": codigo_projeto_atual},
                    {
                        "$pull": {
                            "plano_trabalho.componentes.$[comp].atividades": {
                                "id": atividade_id
                            }
                        },
                        "$set": {
                            f"plano_trabalho.remanejamentos_atividades.{idx}.status_remanejamento": "aceito",
                            f"plano_trabalho.remanejamentos_atividades.{idx}.data_aprov_remanej": datetime.datetime.now().strftime("%d/%m/%Y")
                        }
                    },
                    array_filters=[
                        {"comp.componente": componente_nome},
                    ]
                )


            # ==================================================
            # Buscar projeto atualizado
            # ==================================================

            projeto_atualizado = col_projetos.find_one(
                {"codigo": codigo_projeto_atual}
            )

            item_atualizado = projeto_atualizado["plano_trabalho"]["remanejamentos_atividades"][idx]


            # ==================================================
            # Enviar e-mail conforme tipo de remanejamento
            # ==================================================

            if "add_atividade" in item_atualizado:

                enviar_email_nova_atividade_aprovada(
                    projeto_atualizado,
                    item_atualizado
                )

            elif "antes" in item_atualizado:

                enviar_email_remanejamento_atividade_aprovado(
                    projeto_atualizado,
                    item_atualizado
                )

            elif "del_atividade" in item_atualizado:

                enviar_email_remocao_atividade_aprovada(
                    projeto_atualizado,
                    item_atualizado
                )


            st.success("Remanejamento aprovado.", icon=":material/check:")
            time.sleep(3)
            st.rerun()







        # ==================================================
        # BOTÃO RECUSAR
        # ==================================================

        recusar_key = f"abrir_recusa_atv_{idx}"

        if recusar_key not in st.session_state:
            st.session_state[recusar_key] = False


        if st.button(
            "Recusar",
            key=f"recusar_atv_{idx}",
            type="secondary",
            icon=":material/close:",
            width="stretch"
        ):
            st.session_state[recusar_key] = True


        if st.session_state[recusar_key]:

            motivo = st.text_area(
                "Justificativa da recusa:",
                key=f"motivo_recusa_atv_{idx}"
            )

            if st.button(
                "Confirmar recusa",
                key=f"confirmar_recusa_atv_{idx}",
                type="primary",
                width="stretch"
            ):

                if not motivo.strip():
                    st.warning("Informe a justificativa da recusa.")

                else:


                    nome = st.session_state.get("nome", "Usuário")
                    data = datetime.datetime.now().strftime("%d/%m/%Y")

                    log_recusa = f"Recusado por {nome} em {data}"

                    col_projetos.update_one(
                        {"codigo": codigo_projeto_atual},
                        {
                            "$set": {
                                f"plano_trabalho.remanejamentos_atividades.{idx}.status_remanejamento": "recusado",
                                f"plano_trabalho.remanejamentos_atividades.{idx}.motivo_recusa": motivo.strip(),
                                f"plano_trabalho.remanejamentos_atividades.{idx}.log_recusa": log_recusa
                            }
                        }
                    )

                    projeto_atualizado = col_projetos.find_one(
                        {"codigo": codigo_projeto_atual}
                    )

                    item_atualizado = projeto_atualizado["plano_trabalho"]["remanejamentos_atividades"][idx]

                    # ==================================================
                    # Enviar e-mail conforme tipo de remanejamento
                    # ==================================================

                    if "add_atividade" in item_atualizado:

                        enviar_email_nova_atividade_recusada(
                            projeto_atualizado,
                            item_atualizado
                        )

                    elif "antes" in item_atualizado:

                        enviar_email_remanejamento_atividade_recusado(
                            projeto_atualizado,
                            item_atualizado
                        )

                    # (preparado para quando existir remoção)
                    elif "del_atividade" in item_atualizado:

                        enviar_email_remocao_atividade_recusada(
                            projeto_atualizado,
                            item_atualizado
                        )

                    st.session_state[recusar_key] = False
                    st.rerun()


# ==================================================
# Função auxiliar do badge de status dos remanejamentos de atividade
# ==================================================
def renderizar_badge_status(status):

    if status == "aceito":
        badge = {"label":"Aceito","bg":"#D4EDDA","color":"#155724"}

    elif status == "em_analise":
        badge = {"label":"Em análise","bg":"#FFF3CD","color":"#856404"}

    elif status == "recusado":
        badge = {"label":"Recusado","bg":"#F8D7DA","color":"#721C24"}

    st.markdown(
        f"""
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
        """,
        unsafe_allow_html=True
    )


# ==================================================
# Renderiza card de remanejamento do tipo "remover atividade"
# ==================================================

def renderizar_card_del(item, idx):

    data_solic = item.get("data_solicit_remanej")
    data_aprov = item.get("data_aprov_remanej")
    status = item.get("status_remanejamento")
    
    componente = item.get("componente")

    atividade = item.get("del_atividade")
    justificativa = item.get("justificativa")

    st.markdown("##### :material/cancel: Remover atividade")

    esquerda, direita = st.columns([4,1])

    # ==================================================
    # COLUNA ESQUERDA
    # ==================================================

    with esquerda:

        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Data da solicitação:** {data_solic}")
            st.write("")
            st.write("")
            
            

        with col2:
            if data_aprov:
                st.write(f"**Data de aceite:** {data_aprov}")
                st.write("")
                st.write("")
        
            
            
                
        with col1:
            st.write(f"**Objetivo específico:** {componente}")

        with col1:
            st.write(f"**Atividade a ser removida:** {atividade}")
            
        

        st.write("")
        st.write("")
        
        st.write(f"**Justificativa:** {justificativa}")


    # ==================================================
    # COLUNA DIREITA
    # ==================================================

    with direita:

        renderizar_badge_status(status)

        st.write("")

        renderizar_acoes_remanejamento(item, idx)

        # ------------------------------------------
        # LOG DE RECUSA
        # ------------------------------------------

        if status == "recusado":

            if item.get("log_recusa"):
                st.caption(item["log_recusa"])

            if item.get("motivo_recusa"):
                st.caption(f"Motivo: {item['motivo_recusa']}")


def remover_linhas_vazias(df):
    """
    Remove linhas totalmente vazias de um DataFrame.

    Considera vazio:
    - NaN
    - string vazia ""
    - espaços em branco
    """

    df = df.copy()

    # Substitui strings vazias/espacos por NaN
    df = df.replace(r'^\s*$', pd.NA, regex=True)

    # Remove linhas onde TODOS os campos são NaN
    df = df.dropna(how="all")

    return df


# ==================================================
# Renderiza card de remanejamento do tipo "adicionar atividade"
# ==================================================

def renderizar_card_add(item):

    data_solic = item.get("data_solicit_remanej")
    data_aprov = item.get("data_aprov_remanej")
    status = item.get("status_remanejamento")

    componente = item.get("componente")

    atividade = item.get("add_atividade")
    data_inicio = item.get("data_inicio")
    data_fim = item.get("data_fim")

    justificativa = item.get("justificativa")


    st.markdown("##### :material/add: Adicionar atividade")


    # Frame principal com duas colunas

    esquerda, direita = st.columns([4,1])

    with esquerda:

        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Data da solicitação:** {data_solic}")

        with col2:
            if data_aprov:
                st.write(f"**Data de aceite:** {data_aprov}")            

        st.write("")

        st.write(f"**Objetivo específico:** {componente}")
        st.write(f"**Nova atividade proposta:** {atividade}")
        
        st.write("")
    
        col1, col2 = st.columns(2)
    
        with col1:
            st.write(f"**Data de início:** {data_inicio}")
    
        with col2:
            st.write(f"**Data de fim:** {data_fim}")
        
    
        st.write("")
        st.write(f"**Justificativa:** {justificativa}")


    with direita:

        renderizar_badge_status(status)

        st.write("")

        renderizar_acoes_remanejamento(item, idx)

        # --------------------------------------------------
        # Mostrar motivo da recusa
        # --------------------------------------------------

        if status == "recusado":

            if item.get("log_recusa"):
                st.caption(item["log_recusa"])

            if item.get("motivo_recusa"):
                st.caption(f"Motivo: {item['motivo_recusa']}")
    



# ==================================================
# Renderiza card de remanejamento do tipo "alterar atividade"
# ==================================================

def renderizar_card_alteracao(
    item,
    idx,
    plano_trabalho_dict
):

    data_solic = item.get("data_solicit_remanej")
    data_aprov = item.get("data_aprov_remanej")
    status = item.get("status_remanejamento", "-")

    dist_colunas = [2,2,1]

    st.markdown("##### :material/compare_arrows: Alterar atividade")

    col1, col2, col3 = st.columns(dist_colunas)

    with col1:
        st.write(f"**Data da solicitação:** {data_solic}")

    with col2:
        if data_aprov:
            st.write(f"**Data de aceite:** {data_aprov}")

    with col3:

        if status == "aceito":
            badge = {"label":"Aceito","bg":"#D4EDDA","color":"#155724"}

        elif status == "em_analise":
            badge = {"label":"Em análise","bg":"#FFF3CD","color":"#856404"}

        elif status == "recusado":
            badge = {"label":"Recusado","bg":"#F8D7DA","color":"#721C24"}

        st.markdown(
            f"""
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
            """,
            unsafe_allow_html=True
        )

    st.write("")

    # localizar atividade no plano de trabalho
    atividade_id = item.get("atividade_id")

    atividade_bd = None

    for comp in plano_trabalho_dict.get("componentes", []):
        for atv in comp.get("atividades", []):
            if atv.get("id") == atividade_id:
                atividade_bd = atv
                break

    antes = item.get("antes", {})
    depois = item.get("depois", {})

    # --------------------------------------------------
    # FALLBACK SE NÃO ENCONTRAR A ATIVIDADE
    # --------------------------------------------------

    if not atividade_bd:

        atividade_nome = (
            item.get("antes", {}).get("atividade")
            or item.get("depois", {}).get("atividade")
            or "Atividade não encontrada"
        )

        data_inicio = (
            item.get("antes", {}).get("data_inicio")
            or item.get("depois", {}).get("data_inicio")
            or "-"
        )

        data_fim = (
            item.get("antes", {}).get("data_fim")
            or item.get("depois", {}).get("data_fim")
            or "-"
        )

    else:

        atividade_nome = atividade_bd.get("atividade")
        data_fim = atividade_bd.get("data_fim")
        data_inicio = atividade_bd.get("data_inicio")

    def highlight(valor):
        return f"<span style='background-color:#FFF3CD;padding:2px 4px;border-radius:3px'>{valor}</span>"

    col1, col2, col3 = st.columns(dist_colunas)

    with col1:

        st.write("ANTES")

        atividade_antes = antes.get("atividade", atividade_nome)
        data_inicio_antes = antes.get("data_inicio", data_inicio)
        data_fim_antes = antes.get("data_fim", data_fim)

        atividade_md = highlight(atividade_antes) if "atividade" in antes else atividade_antes
        inicio_md = highlight(data_inicio_antes) if "data_inicio" in antes else data_inicio_antes
        fim_md = highlight(data_fim_antes) if "data_fim" in antes else data_fim_antes

        st.markdown(f"**Atividade:** {atividade_md}", unsafe_allow_html=True)
        st.markdown(f"**Data de início:** {inicio_md}", unsafe_allow_html=True)
        st.markdown(f"**Data de fim:** {fim_md}", unsafe_allow_html=True)

    with col2:

        st.write("DEPOIS")

        atividade_depois = depois.get("atividade", atividade_nome)
        data_inicio_depois = depois.get("data_inicio", data_inicio)
        data_fim_depois = depois.get("data_fim", data_fim)

        atividade_md = highlight(atividade_depois) if "atividade" in depois else atividade_depois
        inicio_md = highlight(data_inicio_depois) if "data_inicio" in depois else data_inicio_depois
        fim_md = highlight(data_fim_depois) if "data_fim" in depois else data_fim_depois

        st.markdown(f"**Atividade:** {atividade_md}", unsafe_allow_html=True)
        st.markdown(f"**Data de início:** {inicio_md}", unsafe_allow_html=True)
        st.markdown(f"**Data de fim:** {fim_md}", unsafe_allow_html=True)

    with col3:

        renderizar_acoes_remanejamento(item, idx)

        # --------------------------------------------------
        # Mostrar motivo da recusa
        # --------------------------------------------------

        if status == "recusado":

            if item.get("log_recusa"):
                st.caption(item["log_recusa"])

            if item.get("motivo_recusa"):
                st.caption(f"Motivo: {item['motivo_recusa']}")
    


    st.write("")
    st.write(f"**Justificativa:** {item.get('justificativa','')}")


def get_nome_organizacao(projeto):
    """
    Retorna o nome da organização a partir do id_organizacao do projeto.
    """

    organizacao_id = projeto.get("id_organizacao")

    if not organizacao_id:
        return "-"

    org = col_organizacoes.find_one(
        {"_id": organizacao_id},
        {"nome_organizacao": 1}
    )

    if not org:
        return "-"

    return org.get("nome_organizacao", "-")


# ==================================================
# Envia e-mail quando há nova solicitação de remanejamento de alteração de atividade
# ==================================================
def enviar_email_remanejamento_atividade(
    projeto,
    item_remanejamento
):
    """
    Envia e-mail para todos os usuários vinculados ao projeto
    quando uma nova solicitação de remanejamento de atividade é criada.
    """

    # --------------------------------------------------
    # Buscar pessoas vinculadas ao projeto
    # --------------------------------------------------
    pessoas = list(
        col_pessoas.find(
            {
                "status": "ativo",
                "projetos": projeto.get("codigo"),
                "tipo_usuario": {"$in": ["admin", "equipe"]}
            }
        )
    )

    destinatarios = [
        p.get("e_mail")
        for p in pessoas
        if p.get("e_mail")
    ]

    if not destinatarios:
        return


    codigo = projeto.get("codigo")
    nome_projeto = projeto.get("nome_do_projeto")
    organizacao = get_nome_organizacao(projeto)

    # justificativa = item_remanejamento.get("justificativa", "")
    antes = item_remanejamento.get("antes", {})
    depois = item_remanejamento.get("depois", {})

    atividade_nome = item_remanejamento.get("atividade_nome", "Atividade")

    autor = st.session_state.get("nome", "Usuário")
    data_solic = item_remanejamento.get("data_solicit_remanej")

    # --------------------------------------------------
    # Montar tabela de alterações
    # --------------------------------------------------

    linhas_alteracoes = ""

    campos = set(list(antes.keys()) + list(depois.keys()))

    nomes_campos = {
        "atividade": "Descrição da atividade",
        "data_inicio": "Data de início",
        "data_fim": "Data de fim"
    }

    for campo in campos:

        valor_antes = antes.get(campo, "-")
        valor_depois = depois.get(campo, "-")

        campo_legivel = nomes_campos.get(campo, campo)

        linhas_alteracoes += f"""
        <tr>
            <td style="padding:6px 10px; border:1px solid #ddd;">{campo_legivel}</td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{valor_antes}</td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{valor_depois}</td>
        </tr>
        """


    assunto = f"Nova solicitação de alteração de atividade - {codigo}"

    logo = logo_cepf


    # --------------------------------------------------
    # Corpo do email
    # --------------------------------------------------


    corpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>

    body {{
        font-family: Arial, Helvetica, sans-serif;
        background-color: #f5f5f5;
    }}

    .container {{
        max-width: 760px;
        margin: 0 auto;
        background: white;
        border-top: 6px solid #28A745; /* verde */
        padding: 30px;
    }}

    .logo {{
        text-align: center;
        margin-bottom: 20px;
    }}

    .highlight {{
        color: #28A745;
        font-weight: bold;
    }}

    </style>
    </head>

    <body>

    <div class="container">

        <div class="logo">
            <img src="{logo}" height="60">
        </div>

        <p>
        Foi enviada uma nova solicitação de
        <span class="highlight"><strong>remanejamento de atividade</strong></span>
        no projeto
        <span class="highlight">{codigo} - {nome_projeto}</span>
        da organização
        <span class="highlight">{organizacao}</span>.
        </p>

        <p>
        <strong>Solicitado por:</strong> {autor}<br>
        <strong>Data:</strong> {data_solic}
        </p>

        <br>

        <p>
        <strong>AÇÃO NECESSÁRIA:</strong><br>
        Acesse a aba de <strong>Remanejamentos</strong>
        na página de <strong>Atividades</strong>
        para ver os detalhes desta solicitação.
        </p>

        <br>

        <p>Sistema de Gestão de Projetos</p>

    </div>

    </body>
    </html>
    """


    enviar_email(corpo_html, destinatarios, assunto)






# ==================================================
# Envia e-mail quando remanejamento de alteração de atividade é aprovado
# ==================================================
def enviar_email_remanejamento_atividade_aprovado(
    projeto,
    item_remanejamento
):
    """
    Envia e-mail para todos os contatos cadastrados
    na chave 'contatos' do projeto quando o
    remanejamento de atividade for aprovado.
    """

    contatos = projeto.get("contatos", [])

    # --------------------------------------------------
    # Coletar e-mails
    # --------------------------------------------------
    destinatarios = [
        c.get("email")
        for c in contatos
        if c.get("email")
    ]

    if not destinatarios:
        return

    codigo = projeto.get("codigo")
    nome_projeto = projeto.get("nome_do_projeto")
    organizacao = get_nome_organizacao(projeto)

    justificativa = item_remanejamento.get("justificativa", "")

    antes = item_remanejamento.get("antes", {})
    depois = item_remanejamento.get("depois", {})

    atividade_nome = item_remanejamento.get("atividade_nome", "Atividade")

    # --------------------------------------------------
    # Montar tabela de alterações
    # --------------------------------------------------

    linhas_alteracoes = ""

    campos = set(list(antes.keys()) + list(depois.keys()))

    for campo in campos:

        valor_antes = antes.get(campo, "-")
        valor_depois = depois.get(campo, "-")

        nomes_campos = {
            "atividade": "Descrição da atividade",
            "data_inicio": "Data de início",
            "data_fim": "Data de fim"
        }

        campo_legivel = nomes_campos.get(campo, campo)

        linhas_alteracoes += f"""
        <tr>
            <td style="padding:6px 10px; border:1px solid #ddd;">{campo_legivel}</td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{valor_antes}</td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{valor_depois}</td>
        </tr>
        """

    assunto = "Remanejamento de atividade aprovado"

    logo = logo_cepf

    corpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>

    body {{
        font-family: Arial, Helvetica, sans-serif;
        background-color: #f5f5f5;
    }}

    .container {{
        max-width: 760px;
        margin: 0 auto;
        background: white;
        border-top: 6px solid #28A745;
        padding: 30px;
    }}

    .logo {{
        text-align: center;
        margin-bottom: 20px;
    }}

    .highlight {{
        color: #28A745;
        font-weight: bold;
    }}

    table {{
        border-collapse: collapse;
        font-size: 14px;
    }}

    </style>
    </head>

    <body>

    <div class="container">

        <div class="logo">
            <img src="{logo}" height="60">
        </div>

        <p>
        Foi <span class="highlight"><strong>aprovada</strong></span>
        uma solicitação de remanejamento de atividade
        no projeto
        <span class="highlight">{codigo} - {nome_projeto}</span>
        da organização
        <span class="highlight">{organizacao}</span>.
        </p>

        <br>

        <p><strong>Alterações aprovadas:</strong></p>

        <table width="100%">
        <tr style="background:#f5f5f5;">
            <th style="padding:6px 10px; border:1px solid #ddd;">Campo</th>
            <th style="padding:6px 10px; border:1px solid #ddd;">Antes</th>
            <th style="padding:6px 10px; border:1px solid #ddd;">Depois</th>
        </tr>

        {linhas_alteracoes}

        </table>

        <br>

        <p><strong>Justificativa original:</strong></p>
        <p>{justificativa}</p>

        <br>
        <p>Sistema de Gestão de Projetos</p>

    </div>

    </body>
    </html>
    """

    enviar_email(corpo_html, destinatarios, assunto)







# ==================================================
# Envia e-mail quando remanejamento de alteração de atividade é recusado
# ==================================================
def enviar_email_remanejamento_atividade_recusado(
    projeto,
    item_remanejamento
):
    """
    Envia e-mail para todos os contatos cadastrados
    na chave 'contatos' do projeto quando o
    remanejamento de atividade for recusado.
    """

    contatos = projeto.get("contatos", [])

    # --------------------------------------------------
    # Coletar e-mails
    # --------------------------------------------------
    destinatarios = [
        c.get("email")
        for c in contatos
        if c.get("email")
    ]

    if not destinatarios:
        return

    codigo = projeto.get("codigo")
    nome_projeto = projeto.get("nome_do_projeto")
    organizacao = get_nome_organizacao(projeto)

    justificativa = item_remanejamento.get("justificativa", "")
    motivo_recusa = item_remanejamento.get("motivo_recusa", "")

    antes = item_remanejamento.get("antes", {})
    depois = item_remanejamento.get("depois", {})

    atividade_nome = item_remanejamento.get("atividade_nome", "Atividade")

    # --------------------------------------------------
    # Montar tabela de alterações
    # --------------------------------------------------

    linhas_alteracoes = ""

    campos = set(list(antes.keys()) + list(depois.keys()))

    for campo in campos:

        valor_antes = antes.get(campo, "-")
        valor_depois = depois.get(campo, "-")

        nomes_campos = {
            "atividade": "Descrição da atividade",
            "data_inicio": "Data de início",
            "data_fim": "Data de fim"
        }

        campo_legivel = nomes_campos.get(campo, campo)

        linhas_alteracoes += f"""
        <tr>
            <td style="padding:6px 10px; border:1px solid #ddd;">{campo_legivel}</td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{valor_antes}</td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{valor_depois}</td>
        </tr>
        """

    assunto = "Remanejamento de atividade recusado"

    logo = logo_cepf

    corpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>

    body {{
        font-family: Arial, Helvetica, sans-serif;
        background-color: #f5f5f5;
    }}

    .container {{
        max-width: 760px;
        margin: 0 auto;
        background: white;
        border-top: 6px solid #C82333;
        padding: 30px;
    }}

    .logo {{
        text-align: center;
        margin-bottom: 20px;
    }}

    .highlight {{
        color: #C82333;
        font-weight: bold;
    }}

    table {{
        border-collapse: collapse;
        font-size: 14px;
    }}

    </style>
    </head>

    <body>

    <div class="container">

        <div class="logo">
            <img src="{logo}" height="60">
        </div>

        <p>
        Foi <span class="highlight"><strong>recusada</strong></span>
        uma solicitação de remanejamento de atividade
        no projeto
        <span class="highlight">{codigo} - {nome_projeto}</span>
        da organização
        <span class="highlight">{organizacao}</span>.
        </p>

        <br>

        <p><strong>Alterações solicitadas:</strong></p>

        <table width="100%">
        <tr style="background:#f5f5f5;">
            <th style="padding:6px 10px; border:1px solid #ddd;">Campo</th>
            <th style="padding:6px 10px; border:1px solid #ddd;">Antes</th>
            <th style="padding:6px 10px; border:1px solid #ddd;">Depois</th>
        </tr>

        {linhas_alteracoes}

        </table>

        <br>

        <p><strong>Justificativa original:</strong></p>
        <p>{justificativa}</p>

        <br>

        <p><strong>Motivo da recusa:</strong></p>
        <p>{motivo_recusa}</p>

        <br>
        <p>Sistema de Gestão de Projetos</p>

    </div>

    </body>
    </html>
    """

    enviar_email(corpo_html, destinatarios, assunto)





# ==================================================
# Envia e-mail quando há nova solicitação de nova atividade
# ==================================================

def enviar_email_nova_atividade(
    codigo_projeto,
    projeto,
):


    pessoas = list(
        col_pessoas.find(
            {
                "status": "ativo",
                "projetos": codigo_projeto,
                "tipo_usuario": {"$in": ["admin", "equipe"]}
            }
        )
    )

    destinatarios = [
        p.get("e_mail")
        for p in pessoas
        if p.get("e_mail")
    ]



    if not destinatarios:
        return

    nome_projeto = projeto.get("nome_do_projeto")
    organizacao = get_nome_organizacao(projeto)

    logo = logo_cepf

    assunto = f"Solicitação de nova atividade - {codigo_projeto}"

    corpo_html = f"""
    <html>
    <head>
    <style>

    body {{
        font-family: Arial;
        background:#f5f5f5;
    }}

    .container {{
        max-width:760px;
        margin:auto;
        background:white;
        border-top:6px solid #28A745;
        padding:30px;
    }}

    .logo {{
        text-align:center;
        margin-bottom:20px;
    }}

    </style>
    </head>

    <body>

    <div class="container">

        <div class="logo">
            <img src="{logo}" height="60">
        </div>

        <p>
        Foi recebida uma solicitação de
        <strong>nova atividade</strong>
        no projeto
        <strong>{codigo_projeto} - {nome_projeto}</strong>
        da organização
        <strong>{organizacao}</strong>.
        </p>

        <br>

        <p>
        <strong>AÇÃO NECESSÁRIA:</strong><br>
        Acesse a aba de <strong>Remanejamentos</strong>
        na página de <strong>Atividades</strong>
        para ver os detalhes desta solicitação.
        </p>

        <br>

        <p>Sistema de Gestão de Projetos</p>

    </div>

    </body>
    </html>
    """

    enviar_email(corpo_html, destinatarios, assunto)





# ==================================================
# Envia e-mail quando solicitação de NOVA atividade é aprovada
# ==================================================
def enviar_email_nova_atividade_aprovada(
    projeto,
    item_remanejamento
):
    """
    Envia e-mail para todos os contatos cadastrados
    na chave 'contatos' do projeto quando uma
    solicitação de nova atividade for aprovada.
    """

    contatos = projeto.get("contatos", [])

    # --------------------------------------------------
    # Coletar e-mails
    # --------------------------------------------------
    destinatarios = [
        c.get("email")
        for c in contatos
        if c.get("email")
    ]

    if not destinatarios:
        return


    codigo = projeto.get("codigo")
    nome_projeto = projeto.get("nome_do_projeto")
    organizacao = get_nome_organizacao(projeto)

    componente = item_remanejamento.get("componente")

    atividade = item_remanejamento.get("add_atividade")
    data_inicio = item_remanejamento.get("data_inicio")
    data_fim = item_remanejamento.get("data_fim")

    justificativa = item_remanejamento.get("justificativa", "")

    assunto = "Nova atividade aprovada"

    logo = logo_cepf


    corpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>

    body {{
        font-family: Arial, Helvetica, sans-serif;
        background-color: #f5f5f5;
    }}

    .container {{
        max-width: 760px;
        margin: 0 auto;
        background: white;
        border-top: 6px solid #28A745;
        padding: 30px;
    }}

    .logo {{
        text-align: center;
        margin-bottom: 20px;
    }}

    .highlight {{
        color: #28A745;
        font-weight: bold;
    }}

    table {{
        border-collapse: collapse;
        font-size: 14px;
    }}

    </style>
    </head>

    <body>

    <div class="container">

        <div class="logo">
            <img src="{logo}" height="60">
        </div>

        <p>
        Foi <span class="highlight"><strong>aprovada</strong></span>
        uma solicitação de <strong>nova atividade</strong>
        no projeto
        <span class="highlight">{codigo} - {nome_projeto}</span>
        da organização
        <span class="highlight">{organizacao}</span>.
        </p>

        <br>

        <p><strong>Atividade criada:</strong></p>

        <table width="100%">

        <tr>
            <td style="padding:6px 10px; border:1px solid #ddd;"><strong>Objetivo específico</strong></td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{componente}</td>
        </tr>

        <tr>
            <td style="padding:6px 10px; border:1px solid #ddd;"><strong>Descrição da atividade</strong></td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{atividade}</td>
        </tr>

        <tr>
            <td style="padding:6px 10px; border:1px solid #ddd;"><strong>Data de início</strong></td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{data_inicio}</td>
        </tr>

        <tr>
            <td style="padding:6px 10px; border:1px solid #ddd;"><strong>Data de fim</strong></td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{data_fim}</td>
        </tr>

        </table>

        <br>

        <p><strong>Justificativa apresentada:</strong></p>
        <p>{justificativa}</p>

        <br>

        <p>Sistema de Gestão de Projetos</p>

    </div>

    </body>
    </html>
    """

    enviar_email(corpo_html, destinatarios, assunto)






# ==================================================
# Envia e-mail quando solicitação de NOVA atividade é recusada
# ==================================================
def enviar_email_nova_atividade_recusada(
    projeto,
    item_remanejamento
):

    contatos = projeto.get("contatos", [])

    # --------------------------------------------------
    # Coletar e-mails
    # --------------------------------------------------
    destinatarios = [
        c.get("email")
        for c in contatos
        if c.get("email")
    ]

    if not destinatarios:
        return


    codigo = projeto.get("codigo")
    nome_projeto = projeto.get("nome_do_projeto")
    organizacao = get_nome_organizacao(projeto)

    atividade = item_remanejamento.get("add_atividade")
    data_inicio = item_remanejamento.get("data_inicio")
    data_fim = item_remanejamento.get("data_fim")

    justificativa = item_remanejamento.get("justificativa", "")
    motivo_recusa = item_remanejamento.get("motivo_recusa", "")

    assunto = "Solicitação de nova atividade recusada"

    logo = logo_cepf


    corpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>

    body {{
        font-family: Arial, Helvetica, sans-serif;
        background-color: #f5f5f5;
    }}

    .container {{
        max-width: 760px;
        margin: 0 auto;
        background: white;
        border-top: 6px solid #C82333;
        padding: 30px;
    }}

    .logo {{
        text-align: center;
        margin-bottom: 20px;
    }}

    .highlight {{
        color: #C82333;
        font-weight: bold;
    }}

    table {{
        border-collapse: collapse;
        font-size: 14px;
    }}

    </style>
    </head>

    <body>

    <div class="container">

        <div class="logo">
            <img src="{logo}" height="60">
        </div>

        <p>
        Foi <span class="highlight"><strong>recusada</strong></span>
        uma solicitação de <strong>nova atividade</strong>
        no projeto
        <span class="highlight">{codigo} - {nome_projeto}</span>
        da organização
        <span class="highlight">{organizacao}</span>.
        </p>

        <br>

        <p><strong>Atividade solicitada:</strong></p>

        <table width="100%">
        <tr>
            <td style="padding:6px 10px; border:1px solid #ddd;"><strong>Descrição</strong></td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{atividade}</td>
        </tr>

        <tr>
            <td style="padding:6px 10px; border:1px solid #ddd;"><strong>Data de início</strong></td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{data_inicio}</td>
        </tr>

        <tr>
            <td style="padding:6px 10px; border:1px solid #ddd;"><strong>Data de fim</strong></td>
            <td style="padding:6px 10px; border:1px solid #ddd;">{data_fim}</td>
        </tr>
        </table>

        <br>

        <p><strong>Justificativa apresentada:</strong></p>
        <p>{justificativa}</p>

        <br>

        <p><strong>Motivo da recusa:</strong></p>
        <p>{motivo_recusa}</p>

        <br>

        <p>Sistema de Gestão de Projetos</p>

    </div>

    </body>
    </html>
    """

    enviar_email(corpo_html, destinatarios, assunto)





# ==================================================
# Email quando há solicitação de remoção de atividade
# ==================================================

def enviar_email_remocao_atividade_solicitada(
    codigo_projeto,
    projeto
):

    pessoas = list(
        col_pessoas.find(
            {
                "status": "ativo",
                "projetos": codigo_projeto,
                "tipo_usuario": {"$in": ["admin", "equipe"]}
            }
        )
    )


    destinatarios = [
        p.get("e_mail")
        for p in pessoas
        if p.get("e_mail")
    ]

    if not destinatarios:
        return


    codigo = projeto.get("codigo")
    nome_projeto = projeto.get("nome_do_projeto")
    organizacao = get_nome_organizacao(projeto)

    assunto = f"Nova solicitação de remoção de atividade - {codigo}"

    logo = logo_cepf


    corpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>

    body {{
        font-family: Arial, Helvetica, sans-serif;
        background-color: #f5f5f5;
    }}

    .container {{
        max-width: 760px;
        margin: 0 auto;
        background: white;
        border-top: 6px solid #28A745;
        padding: 30px;
    }}

    .logo {{
        text-align: center;
        margin-bottom: 20px;
    }}

    .highlight {{
        color: #28A745;
        font-weight: bold;
    }}

    </style>
    </head>

    <body>

    <div class="container">

        <div class="logo">
            <img src="{logo}" height="60">
        </div>

        <p>
        Foi enviada uma nova solicitação de
        <span class="highlight"><strong>remoção de atividade</strong></span>
        no projeto
        <span class="highlight">{codigo} - {nome_projeto}</span>
        da organização
        <span class="highlight">{organizacao}</span>.
        </p>

        <br>

        <p>
        <strong>AÇÃO NECESSÁRIA:</strong><br>
        Acesse a aba de <strong>Remanejamentos</strong>
        na página de <strong>Atividades</strong>
        para analisar esta solicitação.
        </p>

        <br>

        <p>Sistema de Gestão de Projetos</p>

    </div>

    </body>
    </html>
    """

    enviar_email(corpo_html, destinatarios, assunto)






# ==================================================
# Envia e-mail quando remoção de atividade é aprovada
# ==================================================

def enviar_email_remocao_atividade_aprovada(
    projeto,
    item_remanejamento
):

    contatos = projeto.get("contatos", [])

    destinatarios = [
        c.get("email")
        for c in contatos
        if c.get("email")
    ]

    if not destinatarios:
        return


    codigo = projeto.get("codigo")
    nome_projeto = projeto.get("nome_do_projeto")
    organizacao = get_nome_organizacao(projeto)

    atividade = item_remanejamento.get("del_atividade")
    data_inicio = item_remanejamento.get("data_inicio")
    data_fim = item_remanejamento.get("data_fim")

    justificativa = item_remanejamento.get("justificativa", "")
    autor = item_remanejamento.get("autor", "-")
    data_aprov = item_remanejamento.get("data_aprov_remanej", "-")

    assunto = "Remoção de atividade aprovada"

    logo = logo_cepf


    corpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>

    body {{
        font-family: Arial, Helvetica, sans-serif;
        background-color: #f5f5f5;
    }}

    .container {{
        max-width: 760px;
        margin: 0 auto;
        background: white;
        border-top: 6px solid #28A745;
        padding: 30px;
    }}

    .logo {{
        text-align: center;
        margin-bottom: 20px;
    }}

    .highlight {{
        color: #28A745;
        font-weight: bold;
    }}

    </style>
    </head>

    <body>

    <div class="container">

        <div class="logo">
            <img src="{logo}" height="60">
        </div>

        <p>
        Foi <span class="highlight"><strong>aprovada</strong></span>
        uma solicitação de <strong>remoção de atividade</strong>
        no projeto
        <span class="highlight">{codigo} - {nome_projeto}</span>
        da organização
        <span class="highlight">{organizacao}</span>.
        </p>

        <br>


        <p><strong>Atividade removida:</strong></p>

        <p>
        {atividade}
        </p>

        <br>

        <p><strong>Justificativa da solicitação:</strong></p>
        <p>{justificativa}</p>

        <br>

        <p>Sistema de Gestão de Projetos</p>

    </div>

    </body>
    </html>
    """

    enviar_email(corpo_html, destinatarios, assunto)





# ==================================================
# Envia e-mail quando solicitação de REMOÇÃO de atividade é recusada
# ==================================================
def enviar_email_remocao_atividade_recusada(
    projeto,
    item_remanejamento
):
    """
    Envia e-mail para todos os contatos cadastrados
    na chave 'contatos' do projeto quando uma
    solicitação de remoção de atividade for recusada.
    """

    contatos = projeto.get("contatos", [])

    # --------------------------------------------------
    # Coletar e-mails
    # --------------------------------------------------
    destinatarios = [
        c.get("email")
        for c in contatos
        if c.get("email")
    ]

    if not destinatarios:
        return


    codigo = projeto.get("codigo")
    nome_projeto = projeto.get("nome_do_projeto")
    organizacao = get_nome_organizacao(projeto)

    atividade = item_remanejamento.get("del_atividade")

    justificativa = item_remanejamento.get("justificativa", "")
    motivo_recusa = item_remanejamento.get("motivo_recusa", "")

    assunto = "Solicitação de remoção de atividade recusada"

    logo = logo_cepf


    corpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>

    body {{
        font-family: Arial, Helvetica, sans-serif;
        background-color: #f5f5f5;
    }}

    .container {{
        max-width: 760px;
        margin: 0 auto;
        background: white;
        border-top: 6px solid #C82333;
        padding: 30px;
    }}

    .logo {{
        text-align: center;
        margin-bottom: 20px;
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
            <img src="{logo}" height="60">
        </div>

        <p>
        Foi <span class="highlight"><strong>recusada</strong></span>
        uma solicitação de <strong>remoção de atividade</strong>
        no projeto
        <span class="highlight">{codigo} - {nome_projeto}</span>
        da organização
        <span class="highlight">{organizacao}</span>.
        </p>

        <br>

        <p><strong>Atividade solicitada para remoção:</strong></p>
        <p>{atividade}</p>

        <br>

        <p><strong>Justificativa apresentada:</strong></p>
        <p>{justificativa}</p>

        <br>

        <p><strong>Motivo da recusa:</strong></p>
        <p>{motivo_recusa}</p>

        <br>

        <p>Sistema de Gestão de Projetos</p>

    </div>

    </body>
    </html>
    """

    enviar_email(corpo_html, destinatarios, assunto)





# Função auxiliar que salva lista de impactos no banco
# def salvar_impactos(chave, impactos, codigo_projeto):
#     """
#     Salva lista de impactos no banco.
#     """
#     resultado = col_projetos.update_one(
#         {"codigo": codigo_projeto},
#         {"$set": {chave: impactos}}
#     )

#     return resultado.modified_count == 1


# DIÁLOGO: VER RELATOS 

@st.dialog("Relatos de atividade", width="large")
def dialog_relatos():

    atividade = st.session_state.get("atividade_selecionada")

    if not isinstance(atividade, dict):
        st.warning("Nenhuma atividade selecionada.")
        return

    nome_atividade = (
        atividade.get("atividade")
        or atividade.get("Atividade")
        or "Atividade sem nome"
    )

    st.markdown(f"## {nome_atividade}")
    st.write("")

    # ============================================================
    # BUSCAR RELATOS DA ATIVIDADE NO DOCUMENTO DO PROJETO
    # ============================================================
    projeto = df_projeto.iloc[0].to_dict()
    relatos_encontrados = []

    for componente in projeto.get("plano_trabalho", {}).get("componentes", []):
        for atv in componente.get("atividades", []):
            if atv.get("id") == atividade.get("id"):
                relatos_encontrados = atv.get("relatos", [])
                break

    if not relatos_encontrados:
        st.info("Esta atividade ainda não possui relatos.")
        return

    # ============================================================
    # RENDERIZAÇÃO DOS RELATOS
    # ============================================================

    for relato in relatos_encontrados:

        with st.container(border=True):

            id_relato = relato.get("id_relato", "relato").upper()
            numero_relatorio = relato.get("relatorio_numero")

            # Cabeçalho
            st.markdown(
                f"#### {id_relato} "
                f"<span style='font-size: 0.9em; color: gray;'>(R{numero_relatorio})</span>",
                unsafe_allow_html=True
            )

            # Texto do relato
            st.write(relato.get("relato", ""))

            col1, col2 = st.columns([2, 3])
            col1.write(f"**Quando:** {relato.get('quando', '-')}")
            col2.write(f"**Onde:** {relato.get('onde', '-')}")

            # --------------------------------------------------
            # ANEXOS
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
            # FOTOGRAFIAS
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

 



###########################################################################################################
# TRATAMENTO DE DADOS
###########################################################################################################

# Logo hospedada no site do Fundo Ecos para renderizar nos e-mails.
logo_cepf = "https://fundoecos.org.br/wp-content/uploads/2025/05/Logo-Fundo-Ecos-PNG-sem-fundo-sem-margem.png"


codigo_projeto_atual = st.session_state.get("projeto_atual")

if not codigo_projeto_atual:
    st.error("Nenhum projeto selecionado.")
    st.stop()

# Capturando o projeto atual no bd
df_projeto = pd.DataFrame(
    list(
        col_projetos.find(
            {"codigo": codigo_projeto_atual}
        )
    )
)

if df_projeto.empty:
    st.error("Projeto não encontrado no banco de dados.")
    st.stop()


# Transformar o id em string
df_projeto = df_projeto.copy()
if "_id" in df_projeto.columns:
    df_projeto["_id"] = df_projeto["_id"].astype(str)




# -----------------------------------------------------------------------------------
# Converte o projeto para dicionário
# -----------------------------------------------------------------------------------

projeto_dict = df_projeto.iloc[0].to_dict()

# Blocos principais do documento
plano_trabalho_dict = projeto_dict.get("plano_trabalho", {}) or {}
financeiro_dict = projeto_dict.get("financeiro", {}) or {}
#salvaguardas_dict = projeto_dict.get("salvaguardas", {}) or {}





# CARREGAR INDICADORES DO EDITAL VINCULADO AO PROJETO

# Obtém o nome do edital vinculado ao projeto
nome_edital_projeto = df_projeto["edital"].values[0]

# Busca o edital correspondente
edital_doc = col_editais.find_one({"codigo_edital": nome_edital_projeto})

# Verifica se encontrou o edital
if not edital_doc:
    st.error("Edital vinculado ao projeto não encontrado.")
    lista_indicadores_edital = []
else:
    # Extrai indicadores do edital
    indicadores_edital = edital_doc.get("indicadores", [])

    # Lista apenas os nomes dos indicadores
    lista_indicadores_edital = [
        ind.get("indicador") for ind in indicadores_edital
    ]

# Extrai indicadores do edital
indicadores_edital = edital_doc.get("indicadores", [])

# Lista apenas os nomes dos indicadores
lista_indicadores_edital = [
    ind.get("indicador") for ind in indicadores_edital
]




###########################################################################################################
# INTERFACE PRINCIPAL DA PÁGINA
###########################################################################################################


# Logo do sidebar
st.logo("images/logo_fundo_ecos.png", size='large')



# Título da página e identificação
col_titulo, col_identificacao = st.columns([3, 2])

with col_titulo:
    st.header("Marco Lógico")

with col_identificacao:
    st.markdown(
        f"<div style='text-align: right; margin-top: 30px;'>{df_projeto['codigo'].values[0]} - {df_projeto['sigla'].values[0]}</div>",
        unsafe_allow_html=True
    )



#plano_trabalho, impactos, indicadores, monitoramento, salvaguardas, remanejamentos = st.tabs(["Plano de trabalho", "Impactos", "Indicadores do Portifólio", "Plano de Monitoramento", "Salvaguardas", "Remanejamentos"])
plano_trabalho, indicadores, remanejamentos = st.tabs(["Plano de trabalho", "Indicadores do Portifólio", "Remanejamentos"])






# ###################################################################################################
# PLANO DE TRABALHO
# ###################################################################################################

with plano_trabalho:

    # ===============================================================================================
    # NORMALIZAÇÃO SEGURA DOS DADOS DO PROJETO
    # ===============================================================================================

    projeto_dict = df_projeto.iloc[0].to_dict()

    plano_trabalho_dict = projeto_dict.get("plano_trabalho") or {}

    if not isinstance(plano_trabalho_dict, dict):
        plano_trabalho_dict = {}

    componentes = plano_trabalho_dict.get("componentes") or []

    if not isinstance(componentes, list):
        componentes = []


    # ===============================================================================================
    # PERMISSÃO
    # -----------------------------------------------------------------------------------------------
    # Apenas admin/equipe podem editar
    # ===============================================================================================

    usuario_interno = st.session_state.tipo_usuario in ["admin", "equipe"]
    modo_edicao = False

    if usuario_interno:
        with st.container(horizontal=True, horizontal_alignment="right"):
            modo_edicao = st.toggle(
                "Modo de edição",
                key="editar_plano_trabalho"
            )

    st.write("")


    # ===============================================================================================
    # MODO VISUALIZAÇÃO
    # ===============================================================================================

    if not modo_edicao:

        # Caso não exista plano de trabalho
        if not componentes:
            st.caption("Este projeto não possui plano de trabalho cadastrado.")
        else:

            # Percorre componentes
            for componente in componentes:

                st.markdown(f"#### {componente.get('componente', 'Objetivo específico sem nome')}")

                atividades = componente.get("atividades", [])

                if not atividades:
                    st.caption("Nenhuma atividade cadastrada neste objetivo específico.")
                    continue

                # Calcular o status das atividades
                atividades_processadas = []

                for a in atividades:

                    status = calcular_status_atividade(a)

                    atividades_processadas.append({
                        "Atividade": a.get("atividade"),
                        "Data de início": a.get("data_inicio"),
                        "Data de fim": a.get("data_fim"),
                        "Status": status,
                        "Porcentagem": a.get("porcentagem_atv", 0)
                    })

                df_atividades = pd.DataFrame(atividades_processadas)

                st.dataframe(
                    df_atividades[
                        ["Atividade", "Data de início", "Data de fim", "Status", "Porcentagem"]
                    ],
                    hide_index=True,
                    column_config={

                        "Atividade": st.column_config.TextColumn(
                            "Atividade",
                            width=700
                        ),

                        "Data de início": st.column_config.TextColumn(
                            "Data de início",
                            width=20
                        ),

                        "Data de fim": st.column_config.TextColumn(
                            "Data de fim",
                            width=20
                        ),

                        "Status": st.column_config.TextColumn(
                            "Status",
                            width=20
                        ),

                        "Porcentagem": st.column_config.ProgressColumn(
                            "Porcentagem",
                            min_value=0,
                            max_value=100,
                            format="%d%%",
                            width=20
                        )

                    }
                )



                st.write("")


    # ===============================================================================================
    # MODO EDIÇÃO
    # ===============================================================================================

    else:

        # Escolha do que editar
        opcao_editar_pt = st.radio(
            "O que deseja editar?",
            ["Atividades", "Objetivos Específicos"],
            horizontal=True
        )



        if opcao_editar_pt == "Atividades":
            
            plano_trabalho = (
                df_projeto["plano_trabalho"].values[0]
                if "plano_trabalho" in df_projeto.columns else {}
            )
            
            # Lista de componentes
            opcoes_componentes = [
                c for c in componentes
            ]

            nomes_componentes = [
                c.get("componente") for c in componentes
            ]

            if not nomes_componentes:
                st.write("")
                st.caption("Nenhum objetivo específico cadastrado. Cadastre objetivos específicos antes de adicionar atividades.")
                st.stop()
                
            componente_nome = st.selectbox(
                "Selecione o objetivo específico",
                [""] + nomes_componentes
            )

            # Recupera o componente selecionado
            componente_sel = next(
                (c for c in componentes if c.get("componente") == componente_nome),
                None
            )
            
            if not componente_sel:
                st.caption("Selecione um objetivo específico.")
                st.stop()

            # ============================================================
            # Carregar atividades existentes
            # ============================================================

            atividades_exist = componente_sel.get("atividades", [])

            lista_atividades = []
            for a in atividades_exist:
                # Agora as datas não serão convertidas aqui.
                lista_atividades.append({
                    "atividade": a.get("atividade", ""),
                    "data_inicio": a.get("data_inicio", ""),  # mantém string
                    "data_fim": a.get("data_fim", ""),        # mantém string
                })

            df_atividades = pd.DataFrame(lista_atividades)

            # Se estiver vazio, cria colunas vazias
            if df_atividades.empty:
                df_atividades = pd.DataFrame({
                    "atividade": pd.Series(dtype="str"),
                    "data_inicio": pd.Series(dtype="str"),
                    "data_fim": pd.Series(dtype="str"),
                })


            # ============================================================
            # Data Editor 
            # ============================================================

            # Converte para datetime (se houver valores)
            if not df_atividades.empty:

                df_atividades["data_inicio"] = pd.to_datetime(
                    df_atividades["data_inicio"],
                    format="%d/%m/%Y",
                    errors="coerce"
                )

                df_atividades["data_fim"] = pd.to_datetime(
                    df_atividades["data_fim"],
                    format="%d/%m/%Y",
                    errors="coerce"
                )


            df_editado = st.data_editor(
                df_atividades,
                num_rows="dynamic",
                hide_index=True,
                key="editor_atividades",
                column_config={

                    "atividade": st.column_config.TextColumn(
                        label="Atividade",
                        width=700
                    ),

                    "data_inicio": st.column_config.DateColumn(
                        label="Data de início",
                        width=120,
                        format="DD/MM/YYYY"
                    ),

                    "data_fim": st.column_config.DateColumn(
                        label="Data de fim",
                        width=120,
                        format="DD/MM/YYYY"
                    ),
                }
            )

            # ============================================================
            # Botão salvar
            # ============================================================

            salvar_ativ = st.button(
                "Salvar atividades",
                icon=":material/save:",
                type="secondary",
                key="btn_salvar_atividades"
            )

            # ============================================================
            # Validação + Salvamento
            # ============================================================

            if salvar_ativ:

                erros = []
                atividades_final = []

                # ----------------------------------------------------------
                # Função de validação de data
                # ----------------------------------------------------------
                def valida_data(valor, linha, campo):

                    if pd.isna(valor):
                        erros.append(f"Linha {linha}: {campo} é obrigatória.")
                        return None

                    return valor

                # ----------------------------------------------------------
                # Validação linha a linha
                # ----------------------------------------------------------
                # Remove linhas completamente vazias
                df_editado = remover_linhas_vazias(df_editado)

                for idx, row in df_editado.iterrows():

                    atividade = str(row["atividade"]).strip()

                    # Aqui NÃO converte para string ainda — mantém tipo original
                    data_inicio = row["data_inicio"]
                    data_fim = row["data_fim"]

                    # ----------------------------------------------------------
                    # Detecta linha parcialmente preenchida
                    # ----------------------------------------------------------
                    campos_preenchidos = [
                        atividade != "",
                        not pd.isna(data_inicio),
                        not pd.isna(data_fim)
                    ]

                    # Se pelo menos 1 campo foi preenchido mas não todos → erro
                    if any(campos_preenchidos) and not all(campos_preenchidos):
                        erros.append(
                            f"Linha {idx + 1}: preencha todos os campos antes de salvar."
                        )
                        continue

                    # ----------------------------------------------------------
                    # Linha válida → adiciona
                    # ----------------------------------------------------------
                    if all(campos_preenchidos):

                        atividades_final.append({
                            "atividade": atividade,
                            "data_inicio": pd.to_datetime(data_inicio).strftime("%d/%m/%Y"),
                            "data_fim": pd.to_datetime(data_fim).strftime("%d/%m/%Y"),
                        })

                # ----------------------------------------------------------
                # Se houver erros → apenas exibe
                # ----------------------------------------------------------
                if erros:

                    for e in erros:
                        st.error(e)

                else:

                    atividades_antigas = {
                        a["atividade"]: a for a in atividades_exist
                    }

                    # ------------------------------------------------------
                    # Cria nova lista de atividades (sempre novos IDs)
                    # ------------------------------------------------------

                    nova_lista = []

                    for a in atividades_final:

                        atividade_antiga = atividades_antigas.get(a["atividade"])

                        if atividade_antiga:
                            # Já existia → preserva dados
                            nova_lista.append({
                                "id": atividade_antiga.get("id"),
                                "atividade": a["atividade"],
                                "data_inicio": a["data_inicio"],
                                "data_fim": a["data_fim"],

                                # preservados
                                "porcentagem_atv": atividade_antiga.get("porcentagem_atv", 0),
                                "status_atividade": atividade_antiga.get("status_atividade"),
                                "relatos": atividade_antiga.get("relatos", [])
                            })

                        else:
                            # Nova atividade
                            nova_lista.append({
                                "id": str(bson.ObjectId()),
                                "atividade": a["atividade"],
                                "data_inicio": a["data_inicio"],
                                "data_fim": a["data_fim"],

                                # padrão inicial
                                "porcentagem_atv": 0,
                                "relatos": []
                            })

                    # ------------------------------------------------------
                    # Atualiza apenas o componente correspondente
                    # ------------------------------------------------------
                    componentes_atualizados = []

                    for c in componentes:
                        if c["id"] == componente_sel["id"]:
                            componentes_atualizados.append({
                                **c,
                                "atividades": nova_lista
                            })
                        else:
                            componentes_atualizados.append(c)

                    # ------------------------------------------------------
                    # Persistência no MongoDB
                    # ------------------------------------------------------
                    resultado = col_projetos.update_one(
                        {"codigo": codigo_projeto_atual},
                        {"$set": {"plano_trabalho.componentes": componentes_atualizados}}
                    )

                    if resultado.matched_count == 1:
                        st.success("Atividades atualizadas com sucesso!", icon=":material/check:")
                        time.sleep(3)
                        st.rerun()
                    else:
                        st.error("Erro ao atualizar atividades.")

        # ===========================================================================================
        # EDIÇÃO DE OBJETIVOS ESPECÍFICOS
        # ===========================================================================================

        if opcao_editar_pt == "Objetivos Específicos":

            st.write("")

            # Monta DataFrame apenas com nomes



            if componentes:
                df_componentes = pd.DataFrame({
                    "componente": [c.get("componente", "") for c in componentes]
                })
            else:
                # Força tipo string quando não houver componentes
                df_componentes = pd.DataFrame({
                    "componente": pd.Series(dtype="str")
                })

            # Garante que a coluna seja string
            df_componentes["componente"] = df_componentes["componente"].astype(str)


            df_editado = st.data_editor(
                df_componentes,
                num_rows="dynamic",
                hide_index=True,
                key="editor_componentes",
                column_config={
                    "componente": st.column_config.TextColumn(
                        label="Objetivos Específicos"  # <-- nome exibido
                    )
                }
            )

            salvar = st.button(
                "Salvar componentes",
                icon=":material/save:",
                type="secondary"
            )

            if salvar:

                # Limpa nomes vazios
                remover_linhas_vazias(df_editado)

                novos_componentes = []

                componentes_existentes = componentes
                
                # Remove linhas completamente vazias
                df_editado = remover_linhas_vazias(df_editado)
                for idx, row in df_editado.iterrows():

                    nome_componente = row["componente"]

                    # --------------------------------------------------
                    # Se já existia componente → preserva entregas
                    # --------------------------------------------------
                    if idx < len(componentes_existentes):

                        comp_antigo = componentes_existentes[idx]

                        novos_componentes.append({
                            **comp_antigo,
                            "componente": nome_componente
                        })

                    # --------------------------------------------------
                    # Novo componente
                    # --------------------------------------------------
                    else:

                        novos_componentes.append({
                            "id": str(bson.ObjectId()),
                            "componente": nome_componente,
                            "atividades": []
                        })

                col_projetos.update_one(
                    {"codigo": codigo_projeto_atual},
                    {"$set": {"plano_trabalho.componentes": novos_componentes}}
                )

                st.success("Objetivos específicos atualizados com sucesso!", icon=":material/check:")
                time.sleep(3)
                st.rerun()


# ###################################################################################################
# IMPACTOS
# ###################################################################################################

# with impactos:

#     # ============================================================
#     # CONTROLE DE MODO DE EDIÇÃO
#     # ============================================================

#     if st.session_state.tipo_usuario in ["admin", "equipe"]:
#         with st.container(horizontal=True, horizontal_alignment="right"):
#             modo_edicao = st.toggle("Modo de edição", key="editar_impactos")
#     else:
#         modo_edicao = False


#     # ============================================================
#     # COLUNAS
#     # ============================================================

#     col_lp, col_cp = st.columns(2, gap="large")

#     # ============================================================
#     # IMPACTOS DE LONGO PRAZO
#     # ============================================================

#     with col_lp:
#         st.subheader("Impactos de longo prazo")
#         st.write("*Entre 3 a 5 anos após o final do projeto*")

#         impactos_lp = (
#             df_projeto["impactos_longo_prazo"].values[0]
#             if "impactos_longo_prazo" in df_projeto.columns
#             else []
#         )

#         # ========================
#         # MODO VISUALIZAÇÃO
#         # ========================
#         if not modo_edicao:

#             if not impactos_lp:
#                 st.caption("Não há impactos de longo prazo cadastrados")
                

#             else:
#                 for i, impacto in enumerate(impactos_lp, 1):
#                     st.write(f"**{i}.** {impacto['texto']}")

#         # ========================
#         # MODO EDIÇÃO
#         # ========================
#         else:
#             df_lp = pd.DataFrame(
#                 [{"texto": i["texto"]} for i in impactos_lp] or [{"texto": ""}]
#             )

#             # df_lp = pd.DataFrame(impactos_lp or [{"texto": ""}])

#             df_editado_lp = st.data_editor(
#                 df_lp,
#                 num_rows="dynamic",
#                 hide_index=True,
#                 key="editor_lp",
#                 column_config={
#                     "texto": st.column_config.TextColumn(
#                         "Impacto de longo prazo",
#                         width=600
#                     )
#                 }
#             )

#             if st.button("Salvar", key="save_lp", icon=":material/save:"):
#                 impactos_salvar = []

#                 for i, row in df_editado_lp.iterrows():
#                     texto = str(row["texto"]).strip()
#                     if texto:
#                         impacto_id = (
#                             impactos_lp[i]["id"]
#                             if i < len(impactos_lp)
#                             else str(bson.ObjectId())
#                         )

#                         impactos_salvar.append({
#                             "id": impacto_id,
#                             "texto": texto
#                         })

#                 if salvar_impactos("impactos_longo_prazo", impactos_salvar, st.session_state.projeto_atual):
#                     st.success("Impactos de longo prazo salvos com sucesso!", icon=":material/check:")
#                     time.sleep(3)
#                     st.rerun()
#                 else:
#                     st.error("Erro ao salvar impactos.")


#     # ============================================================
#     # IMPACTOS DE CURTO PRAZO
#     # ============================================================

#     with col_cp:
#         st.subheader("Impactos de curto prazo")
#         st.write("*Durante o projeto ou até o final da subvenção*")

#         impactos_cp = (
#             df_projeto["impactos_curto_prazo"].values[0]
#             if "impactos_curto_prazo" in df_projeto.columns
#             else []
#         )

#         # ========================
#         # MODO VISUALIZAÇÃO
#         # ========================
#         if not modo_edicao:

#             if not impactos_cp:
#                 st.caption("Não há impactos de curto prazo cadastrados")

#             else:
#                 for i, impacto in enumerate(impactos_cp, 1):
#                     st.write(f"**{i}.** {impacto['texto']}")

#         # ========================
#         # MODO EDIÇÃO
#         # ========================
#         else:

#             df_cp = pd.DataFrame(
#                 [{"texto": i["texto"]} for i in impactos_cp] or [{"texto": ""}]
#             )

#             # df_cp = pd.DataFrame(impactos_cp or [{"texto": ""}])

#             df_editado_cp = st.data_editor(
#                 df_cp,
#                 num_rows="dynamic",
#                 hide_index=True,
#                 key="editor_cp",
#                 column_config={
#                     "texto": st.column_config.TextColumn(
#                         "Impacto de curto prazo",
#                         width=600
#                     )
#                 }
#             )

#             if st.button("Salvar", key="save_cp", icon=":material/save:"):
#                 impactos_salvar = []

#                 for i, row in df_editado_cp.iterrows():
#                     texto = str(row["texto"]).strip()
#                     if texto:
#                         impacto_id = (
#                             impactos_cp[i]["id"]
#                             if i < len(impactos_cp)
#                             else str(bson.ObjectId())
#                         )

#                         impactos_salvar.append({
#                             "id": impacto_id,
#                             "texto": texto
#                         })

#                 if salvar_impactos("impactos_curto_prazo", impactos_salvar, st.session_state.projeto_atual):
#                     st.success("Impactos de curto prazo salvos com sucesso!", icon=":material/check:")
#                     time.sleep(3)
#                     st.rerun()
#                 else:
#                     st.error("Erro ao salvar impactos.")







###########################################################################################################
# ABA INDICADORES
###########################################################################################################

with indicadores:

    # --------------------------------------------------
    # PERMISSÃO
    # --------------------------------------------------
    usuario_interno = st.session_state.tipo_usuario in ["admin", "equipe"]
    modo_edicao = False

    if usuario_interno:
        with st.container(horizontal=True, horizontal_alignment="right"):
            modo_edicao = st.toggle(
                "Modo de edição",
                key="editar_indicadores"
            )

    st.subheader("Indicadores de Portifólio")

    #######################################################################################################
    # MODO VISUALIZAÇÃO
    #######################################################################################################
    if not modo_edicao:

        indicadores_projeto = (
            df_projeto["indicadores"].values[0]
            if "indicadores" in df_projeto.columns
            else []
        )

        if not indicadores_projeto:
            st.caption("Nenhum indicador associado a este projeto.")
        else:

            # Mapeia codigo_indicador para nome do indicador
            mapa_indicadores = {
                ind["codigo_indicador"]: ind["indicador"]
                for ind in indicadores_edital
            }


            dados_tabela = []

            for item in indicadores_projeto:
                dados_tabela.append({
                    "Indicadores": mapa_indicadores.get(
                        item.get("id_indicador"),
                        "Indicador não encontrado"
                    ),
                    "Contribuição esperada": item.get("valor"),
                    "Descrição da contribuição": item.get(
                        "descricao_contribuicao", ""
                    ),
                    "Resultado intermediário": item.get(
                        "resultado_intermediario", ""
                    ),
                    "Resultado final": item.get(
                        "resultado_final", ""
                    )
                })

            df_visualizacao = pd.DataFrame(dados_tabela)
            ui.table(df_visualizacao)

    #######################################################################################################
    # MODO EDIÇÃO
    #######################################################################################################
    else:


        # Texto introdutório da seção
        st.write("*Selecione os indicadores que serão acompanhados no projeto.*")

        # Aviso para o usuário lembrar de salvar
        st.markdown(
            "<span style='color:#2F5AA1;'>***Lembre-se de salvar cada indicador após editar.***</span>",
            unsafe_allow_html=True
        )

        st.write("")


        # --------------------------------------------------
        # INICIALIZA / NORMALIZA ESTADO
        # --------------------------------------------------
        # Cria o estado na sessão para armazenar os valores
        # dos indicadores já salvos no projeto

        if "valores_indicadores" not in st.session_state:

            indicadores_salvos = (
                df_projeto["indicadores"].values[0]
                if "indicadores" in df_projeto.columns
                else []
            )

            estado = {}

            for item in indicadores_salvos:
                estado[item["id_indicador"]] = {
                    "valor": item.get("valor", 0),
                    "descricao": item.get("descricao_contribuicao", ""),
                    "resultado_intermediario": item.get("resultado_intermediario", ""),
                    "resultado_final": item.get("resultado_final", "")
                }

            st.session_state.valores_indicadores = estado


        # --------------------------------------------------
        # GARANTIA DE DADOS
        # --------------------------------------------------
        # Verifica se existem indicadores cadastrados no edital

        if not indicadores_edital:
            st.caption("Não há indicadores cadastrados neste edital.")

        else:

            # Configuração fixa das colunas da tabela
            colunas_indicadores = [5, 2, 4, 2, 2]

            # Cabeçalho da tabela
            col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns(colunas_indicadores)

            with col_h1:
                st.markdown("**Indicadores do CEPF**")

            with col_h2:
                st.markdown("**Contribuição esperada**")

            with col_h3:
                st.markdown("**Descrição da contribuição esperada**")

            with col_h4:
                st.markdown("**Resultado intermediário**")

            with col_h5:
                st.markdown("**Resultado final**")

            st.write("")
            st.write("")


            # --------------------------------------------------
            # LISTAGEM DOS INDICADORES
            # --------------------------------------------------
            # Cada indicador será renderizado em uma linha

            for ind in sorted(indicadores_edital, key=lambda x: x["indicador"]):

                id_indicador = ind["codigo_indicador"]
                nome_indicador = ind["indicador"]

                # Recupera dados existentes do indicador no estado
                dados_atual = st.session_state.valores_indicadores.get(
                    id_indicador,
                    {
                        "valor": 0,
                        "descricao": "",
                        "resultado_intermediario": "",
                        "resultado_final": ""
                    }
                )

                # Criação das colunas de inputs
                col_check, col_valor, col_desc, col_res_int, col_res_final = st.columns(colunas_indicadores)


                # --------------------------------------------------
                # CHECKBOX DO INDICADOR
                # --------------------------------------------------
                with col_check:

                    marcado = st.checkbox(
                        nome_indicador,
                        key=f"chk_{id_indicador}",
                        value=id_indicador in st.session_state.valores_indicadores
                    )


                # --------------------------------------------------
                # VALOR NUMÉRICO DA CONTRIBUIÇÃO
                # --------------------------------------------------
                with col_valor:

                    if marcado:

                        valor = st.number_input(
                            "Label",
                            step=1,
                            value=dados_atual["valor"],
                            key=f"num_{id_indicador}",
                            label_visibility="hidden"
                        )


                # --------------------------------------------------
                # DESCRIÇÃO DA CONTRIBUIÇÃO
                # --------------------------------------------------
                with col_desc:

                    if marcado:

                        descricao = st.text_area(
                            "Label",
                            value=dados_atual["descricao"],
                            key=f"desc_{id_indicador}",
                            height=80,
                            label_visibility="hidden"
                        )


                # --------------------------------------------------
                # RESULTADO INTERMEDIÁRIO
                # --------------------------------------------------
                with col_res_int:

                    if marcado:

                        resultado_intermediario = st.number_input(
                            "Label",
                            step=1,
                            value=(
                                dados_atual.get("resultado_intermediario")
                                if isinstance(
                                    dados_atual.get("resultado_intermediario"), (int, float)
                                )
                                else 0
                            ),
                            key=f"res_int_{id_indicador}",
                            label_visibility="hidden"
                        )


                # --------------------------------------------------
                # RESULTADO FINAL
                # --------------------------------------------------
                with col_res_final:

                    if marcado:

                        resultado_final = st.number_input(
                            "Label",
                            step=1,
                            value=(
                                dados_atual.get("resultado_final")
                                if isinstance(
                                    dados_atual.get("resultado_final"), (int, float)
                                )
                                else 0
                            ),
                            key=f"res_fin_{id_indicador}",
                            label_visibility="hidden"
                        )


                # --------------------------------------------------
                # ATUALIZA ESTADO DA SESSÃO
                # --------------------------------------------------
                # Mantém os valores no estado enquanto o usuário edita

                if marcado:

                    st.session_state.valores_indicadores[id_indicador] = {
                        "valor": valor,
                        "descricao": descricao,
                        "resultado_intermediario": resultado_intermediario,
                        "resultado_final": resultado_final
                    }

                else:

                    st.session_state.valores_indicadores.pop(id_indicador, None)


                # --------------------------------------------------
                # BOTÃO DE SALVAR INDIVIDUAL
                # --------------------------------------------------
                # Cada indicador possui seu próprio botão


                with st.container(horizontal=True, horizontal_alignment="right"):

                    salvar_indicador = st.button(
                        "Salvar",
                        icon=":material/save:",
                        type="secondary",
                        key=f"save_{id_indicador}",
                        width=200
                    )


                # --------------------------------------------------
                # VALIDAÇÃO E SALVAMENTO DO INDICADOR
                # --------------------------------------------------
                if salvar_indicador:

                    if not marcado:

                        st.warning("Selecione o indicador antes de salvar.")

                    elif valor <= 0:

                        st.error("O valor deve ser maior que zero.")

                    elif not descricao.strip():

                        st.error("A descrição da contribuição esperada não pode estar vazia.")

                    else:

                        indicador_para_salvar = {
                            "id_indicador": id_indicador,
                            "valor": valor,
                            "descricao_contribuicao": descricao.strip(),
                            "resultado_intermediario": resultado_intermediario,
                            "resultado_final": resultado_final
                        }

                        # Busca projeto atual
                        projeto = col_projetos.find_one({"codigo": codigo_projeto_atual})

                        indicadores_existentes = projeto.get("indicadores", [])

                        # Remove indicador antigo se existir
                        indicadores_filtrados = [
                            i for i in indicadores_existentes
                            if i["id_indicador"] != id_indicador
                        ]

                        # Adiciona o indicador atualizado
                        indicadores_filtrados.append(indicador_para_salvar)

                        # Atualiza no banco
                        resultado = col_projetos.update_one(
                            {"codigo": codigo_projeto_atual},
                            {"$set": {"indicadores": indicadores_filtrados}}
                        )

                        # Mensagem de retorno
                        if resultado.matched_count == 1:

                            st.success("Indicador atualizado com sucesso!", icon=":material/check:")

                            time.sleep(3)

                            st.rerun()

                        else:

                            st.error("Erro ao salvar indicador.")


                # Separador visual entre indicadores
                st.divider()


# ###################################################################################################
# SALVAGUARDAS
# ###################################################################################################

# with salvaguardas:



#     # ===============================================================================================
#     # PERMISSÃO - SALVAGUARDAS
#     # -----------------------------------------------------------------------------------------------
#     # Apenas admin/equipe podem editar. Usuários externos apenas visualizam.
#     # ===============================================================================================

#     usuario_interno = st.session_state.tipo_usuario in ["admin", "equipe"]

#     # Usuários internos podem editar, externos apenas visualizar
#     modo_edicao = usuario_interno


#     st.subheader("Avaliação de risco")
#     st.write('')

#     # Recupera o documento do projeto como dicionário
#     projeto = df_projeto.iloc[0].to_dict()

#     # Recupera o objeto salvaguardas do documento do projeto
#     # Caso não exista, utiliza um dicionário vazio
#     salvaguardas_doc = projeto.get("salvaguardas", {})


#     # Extrai os subdocumentos de cada política
#     pol2 = salvaguardas_doc.get("pol_2_trabalho", {})
#     pol3 = salvaguardas_doc.get("pol_3_poluicao", {})
#     pol4 = salvaguardas_doc.get("pol_4_comunidade", {})
#     pol5 = salvaguardas_doc.get("pol_5_reassentamento", {})
#     pol6 = salvaguardas_doc.get("pol_6_biodiversidade", {})
#     pol7 = salvaguardas_doc.get("pol_7_indigenas", {})
#     pol8 = salvaguardas_doc.get("pol_8_patrimonio", {})
#     pol9 = salvaguardas_doc.get("pol_9_genero", {})


#     # Carrega valores existentes no session_state
#     # Isso faz com que os widgets apareçam já preenchidos ao abrir a página


#     if "salv_2_aplicavel" not in st.session_state:
#         st.session_state["salv_2_aplicavel"] = pol2.get("aplicavel")

#     if "salv_2_detalhes" not in st.session_state:
#         st.session_state["salv_2_detalhes"] = pol2.get("detalhes")

#     if "salv_2_categoria_risco" not in st.session_state:
#         st.session_state["salv_2_categoria_risco"] = pol2.get("categoria")


#     if "salv_3_aplicavel" not in st.session_state:
#         st.session_state["salv_3_aplicavel"] = pol3.get("aplicavel")

#     if "salv_3_pesticidas_detalhes" not in st.session_state:
#         st.session_state["salv_3_pesticidas_detalhes"] = pol3.get("detalhes_pesticidas")

#     if "salv_3_poluicao_detalhes" not in st.session_state:
#         st.session_state["salv_3_poluicao_detalhes"] = pol3.get("detalhes_poluicao")

#     if "salv_3_categoria_risco" not in st.session_state:
#         st.session_state["salv_3_categoria_risco"] = pol3.get("categoria")


#     if "salv_4_aplicavel" not in st.session_state:
#         st.session_state["salv_4_aplicavel"] = pol4.get("aplicavel")

#     if "salv_4_detalhes" not in st.session_state:
#         st.session_state["salv_4_detalhes"] = pol4.get("detalhes")

#     if "salv_4_categoria_risco" not in st.session_state:
#         st.session_state["salv_4_categoria_risco"] = pol4.get("categoria")


#     if "salv_5_aplicavel" not in st.session_state:
#         st.session_state["salv_5_aplicavel"] = pol5.get("aplicavel")

#     if "salv_5_detalhes" not in st.session_state:
#         st.session_state["salv_5_detalhes"] = pol5.get("detalhes")

#     if "salv_5_categoria_risco" not in st.session_state:
#         st.session_state["salv_5_categoria_risco"] = pol5.get("categoria")


#     if "salv_6_aplicavel" not in st.session_state:
#         st.session_state["salv_6_aplicavel"] = pol6.get("aplicavel")

#     if "salv_6_detalhes" not in st.session_state:
#         st.session_state["salv_6_detalhes"] = pol6.get("detalhes")

#     if "salv_6_categoria_risco" not in st.session_state:
#         st.session_state["salv_6_categoria_risco"] = pol6.get("categoria")


#     if "salv_7_aplicavel" not in st.session_state:
#         st.session_state["salv_7_aplicavel"] = pol7.get("aplicavel")

#     if "salv_7_detalhes" not in st.session_state:
#         st.session_state["salv_7_detalhes"] = pol7.get("detalhes")

#     if "salv_7_categoria_risco" not in st.session_state:
#         st.session_state["salv_7_categoria_risco"] = pol7.get("categoria")


#     if "salv_8_aplicavel" not in st.session_state:
#         st.session_state["salv_8_aplicavel"] = pol8.get("aplicavel")

#     if "salv_8_detalhes" not in st.session_state:
#         st.session_state["salv_8_detalhes"] = pol8.get("detalhes")

#     if "salv_8_categoria_risco" not in st.session_state:
#         st.session_state["salv_8_categoria_risco"] = pol8.get("categoria")


#     if "salv_9_detalhes" not in st.session_state:
#         st.session_state["salv_9_detalhes"] = pol9.get("detalhes")

#     if "salv_9_categoria_risco" not in st.session_state:
#         st.session_state["salv_9_categoria_risco"] = pol9.get("categoria")
    
#     if "salv_fortalecimento_capacidades" not in st.session_state:
#         st.session_state["salv_fortalecimento_capacidades"] = salvaguardas_doc.get("fortalecimento_capacidades")
    
    
    
#     # COMEÇO DO FORMULÁRIO COM AS POLÍTICAS DE SALVAGUARDAS ###########################################################
    

#     # Duas colunas para o nome do avaliador e data da última atualização.
#     col1, col2 = st.columns(2)

    
#     # Recupera o nome do usuário logado no session_state
#     nome_avaliador = st.session_state.get("nome")

#     # Mostra o nome na tela

#     # Recupera o nome da pessoa que fez a última avaliação
#     nome_avaliador = salvaguardas_doc.get("nome_avaliador_risco")

#     # Mostra apenas se existir informação no banco
#     if nome_avaliador:
#         col1.write(f"**Nome da pessoa que completa a avaliação de risco:** {nome_avaliador}")




#     # Recupera a data da última avaliação salva
#     data_aval_risco = salvaguardas_doc.get("data_aval_risco")

#     # Mostra a data apenas se existir no banco
#     if data_aval_risco:
#         col2.write(f"**Data da última atualização:** {data_aval_risco}")


#     st.write("")
#     st.write("")
#     st.write("")


#     # Define a largura padrão das colunas que será reutilizada na tabela de salvaguardas
#     largura_colunas = [2, 2, 3, 2, 3]

#     # Cria a primeira linha de colunas (cabeçalho)
#     cab1, cab2, cab3, cab4, cab5 = st.columns(largura_colunas)

#     # Cabeçalhos em negrito
#     cab1.markdown("**Política de Salvaguardas**")
#     cab2.markdown("**Aplicável?**")
#     cab3.markdown("**Avaliação de Risco**")
#     cab4.markdown("**Categoria de Risco**")
#     cab5.markdown("**Notas (os exemplos abaixo são indicativos e não prevêem todas as eventualidades)**")

#     st.divider()


#     # colunas das linhas de pergutnas e respostas
#     col1, col2, col3, col4, col5 = st.columns(largura_colunas, gap="medium")


#     # 1. Avaliação Ambiental e Social ------------------------------------------------------------------------------------------------

#     # Coluna 1 — nome da política
#     col1.write("**1. Avaliação Ambiental e Social**")

#     # Coluna 2 — política sempre aplicável
#     with col2:

#         # Mostra o valor fixo para o usuário
#         st.write("Sim")

#         # Observação da política
#         st.caption("Aplica-se a todos os projetos")

#         # Define o valor no session_state para garantir que seja salvo
#         st.session_state["salv_1_aplicavel"] = "Sim"

#     # Coluna 3 — avaliação de risco
#     col3.write("N/A")

#     # Coluna 4 — categoria de risco
#     col4.write("N/A")

#     # Coluna 5 — observação
#     col5.write("Não é necessário atribuir uma categoria de risco individual a esta política.")


#     st.divider()




#     # 2. Condições de Trabalho e Trabalhistas -------------------------------------------------------------

#     # colunas da segunda linha de perguntas e respostas
#     col1, col2, col3, col4, col5 = st.columns(largura_colunas, gap="medium")


#     # Coluna 1 — nome da política
#     col1.write("**2. Condições de Trabalho e Trabalhistas**")

#     # Coluna 2 — pergunta se a política é aplicável
#     with col2:
#         st.radio(
#             "Aplicável?",
#             ["Sim", "Não"],
#             key="salv_2_aplicavel",
#             horizontal=True,
#             disabled=not modo_edicao
#         )

#     # Coluna 3 — pergunta de avaliação de risco e campo para detalhes
#     with col3:
#         st.write("O projeto proposto apresenta riscos significativos em relação às condições de trabalho e trabalhistas?")
#         st.text_area(
#             "Detalhes:",
#             key="salv_2_detalhes",
#             height=120,
#             disabled=not modo_edicao
#         )

#     # Coluna 4 — categoria de risco
#     with col4:
#         st.radio(
#             "Categoria de risco",
#             ["Categoria A", "Categoria B", "Categoria C"],
#             key="salv_2_categoria_risco",
#             disabled=not modo_edicao
#         )

#     # Coluna 5 — observação explicativa
#     col5.write(
#         "Projetos geralmente serão atribuídos à Categoria C para esta política, "
#         "a menos que existam riscos elevados relacionados à saúde e segurança "
#         "ocupacional, como mergulho ou trabalho como guardas ecológicos."
#     )

#     st.divider()




#     # 3. Eficiência de Recursos e Prevenção de Poluição --------------------------------------------------


#     # colunas da terceira linha de perguntas e respostas
#     col1, col2, col3, col4, col5 = st.columns(largura_colunas, gap="medium")


#     # Coluna 1 — nome da política
#     col1.write("**3. Eficiência de Recursos e Prevenção de Poluição**")

#     # Coluna 2 — pergunta se a política é aplicável
#     with col2:
#         st.radio(
#             "Aplicável?",
#             ["Sim", "Não"],
#             key="salv_3_aplicavel",
#             horizontal=True,
#             disabled=not modo_edicao
#         )

#     # Coluna 3 — perguntas de avaliação de risco com campos de detalhe
#     with col3:

#         st.write("O projeto proposto apresenta riscos significativos relacionados a pesticidas?")

#         st.text_area(
#             "Detalhes:",
#             key="salv_3_pesticidas_detalhes",
#             height=100,
#             disabled=not modo_edicao
#         )

#         st.write("O projeto proposto apresenta riscos significativos relacionados ao uso insustentável de recursos e/ou formas de poluição que não sejam pesticidas?")

#         st.text_area(
#             "Detalhes:",
#             key="salv_3_poluicao_detalhes",
#             height=100,
#             disabled=not modo_edicao
#         )

#     # Coluna 4 — categoria de risco
#     with col4:
#         st.radio(
#             "Categoria de risco",
#             ["Categoria A", "Categoria B", "Categoria C"],
#             key="salv_3_categoria_risco",
#             disabled=not modo_edicao
#         )

#     # Coluna 5 — observações explicativas
#     with col5:
#         st.write(
#             "Projetos que envolvem a aquisição ou uso de pesticidas químicos serão atribuídos à Categoria B."
#         )

#         st.write(
#             "Os projetos com potencial de exposição da comunidade a materiais e substâncias perigosos "
#             "liberados por suas atividades serão classificados na Categoria A ou B."
#         )

#     st.divider()





#     # 4. Saúde, Segurança e Proteção da Comunidade -------------------------------------------------------

#     # colunas da quarta linha de perguntas e respostas
#     col1, col2, col3, col4, col5 = st.columns(largura_colunas, gap="medium")



#     # Coluna 1 — nome da política
#     col1.write("**4. Saúde, Segurança e Proteção da Comunidade**")

#     # Coluna 2 — pergunta se a política é aplicável
#     with col2:
#         st.radio(
#             "Aplicável?",
#             ["Sim", "Não"],
#             key="salv_4_aplicavel",
#             horizontal=True,
#             disabled=not modo_edicao
#         )

#     # Coluna 3 — pergunta de avaliação de risco com campo para detalhes
#     with col3:

#         st.write(
#             "O projeto proposto apresenta riscos significativos relacionados "
#             "à saúde, segurança e proteção da comunidade?"
#         )

#         st.text_area(
#             "Detalhes:",
#             key="salv_4_detalhes",
#             height=120,
#             disabled=not modo_edicao
#         )

#     # Coluna 4 — categoria de risco
#     with col4:
#         st.radio(
#             "Categoria de risco",
#             ["Categoria A", "Categoria B", "Categoria C"],
#             key="salv_4_categoria_risco",
#             disabled=not modo_edicao
#         )

#     # Coluna 5 — observações explicativas
#     with col5:

#         st.markdown(
#             "Projetos que financiam salários e/ou operações de guardas florestais, "
#             "guardas ecológicos ou pessoal de segurança similar (armado ou desarmado) "
#             "serão classificados como Categoria B<sup>1</sup>.",
#             unsafe_allow_html=True
#         )


#         st.markdown(
#             "Projetos que envolvem atividades de pesquisa<sup>2</sup> com seres humanos<sup>2</sup> "
#             "serão classificados como Categoria B.",
#             unsafe_allow_html=True
#         )

#     st.write('')
    
#     # Nota de rodapé 1
#     st.caption(
#         "<sup>1</sup> Esta disposição aplica-se independentemente de o pessoal de segurança ser empregado "
#         "ou contratado pela entidade beneficiária, por uma agência governamental ou por um terceiro.",
#         unsafe_allow_html=True
#     )

#     # Nota de rodapé 2
#     st.caption(
#         "<sup>2</sup> Pesquisa com Seres Humanos refere-se a qualquer forma de investigação disciplinada "
#         "que visa contribuir para um corpo de conhecimento ou teoria que envolva a obtenção de "
#         "(a) dados de indivíduos vivos por meio de intervenção ou interação com o indivíduo ou "
#         "(b) informações pessoais identificáveis. Projetos de demonstração de campo de conservação "
#         "e/ou desenvolvimento geralmente não são considerados pesquisa, nem métodos participativos "
#         "padrão usados para monitorar os impactos desses projetos no bem-estar humano "
#         "(por exemplo, discussões em grupos focais).",
#         unsafe_allow_html=True
#     )

#     st.divider()








#     # 5. Restrições de Uso da Terra e Reassentamento Involuntário ----------------------------------------

#     col1, col2, col3, col4, col5 = st.columns(largura_colunas, gap="medium")

#     col1.write("**5. Restrições de Uso da Terra e Reassentamento Involuntário**")

#     with col2:
#         st.radio(
#             "Aplicável?",
#             ["Sim", "Não"],
#             key="salv_5_aplicavel",
#             horizontal=True,
#             disabled=not modo_edicao
#         )

#     with col3:
#         st.write(
#             "O projeto proposto apresenta riscos significativos relacionados a restrições "
#             "de acesso associadas a impactos negativos nos meios de subsistência?"
#         )

#         st.text_area(
#             "Detalhes:",
#             key="salv_5_detalhes",
#             height=120,
#             disabled=not modo_edicao
#         )

#     with col4:
#         st.radio(
#             "Categoria de risco",
#             ["Categoria A", "Categoria B", "Categoria C"],
#             key="salv_5_categoria_risco",
#             disabled=not modo_edicao
#         )

#     with col5:
#         st.write(
#             "Projetos que envolvem a criação ou expansão de áreas protegidas "
#             "serão classificados como Categoria B."
#         )

#     st.divider()


#     # 6. Conservação da Biodiversidade e Gestão Sustentável de Recursos Naturais Vivos -------------------

#     col1, col2, col3, col4, col5 = st.columns(largura_colunas, gap="medium")

#     col1.write("**6. Conservação da Biodiversidade e Gestão Sustentável de Recursos Naturais Vivos**")

#     with col2:
#         st.radio(
#             "Aplicável?",
#             ["Sim", "Não"],
#             key="salv_6_aplicavel",
#             horizontal=True,
#             disabled=not modo_edicao
#         )

#     with col3:
#         st.write(
#             "O projeto proposto apresenta riscos significativos relacionados à "
#             "degradação ou perda de habitat crítico ou outros habitats naturais?"
#         )

#         st.text_area(
#             "Detalhes:",
#             key="salv_6_detalhes",
#             height=120,
#             disabled=not modo_edicao
#         )

#     with col4:
#         st.radio(
#             "Categoria de risco",
#             ["Categoria A", "Categoria B", "Categoria C"],
#             key="salv_6_categoria_risco",
#             disabled=not modo_edicao
#         )

#     with col5:
        
#         st.markdown(
#             "Projetos que envolvem impactos adversos em habitats críticos<sup>3</sup> "
#             "serão classificados como Categoria A.",
#             unsafe_allow_html=True
#         )

#         st.write(
#             "Projetos que envolvem a aquisição de commodities de recursos naturais "
#             "(por exemplo, madeira) que possam contribuir para a conversão ou "
#             "degradação significativa de habitats naturais serão classificados como Categoria B."
#         )

#         st.write(
#             "Projetos que envolvem a produção ou colheita de recursos naturais vivos "
#             "de populações selvagens de espécies ameaçadas globalmente serão classificados como Categoria B."
#         )

#     # Nota de rodapé 3
#     st.caption(
#         "<sup>3</sup> Habitats críticos incluem, entre outros, áreas protegidas existentes "
#         "e propostas, áreas reconhecidas como protegidas por comunidades locais tradicionais, "
#         "bem como áreas identificadas como importantes para a conservação, como Áreas-Chave "
#         "de Biodiversidade (KBAs), Sítios da Aliança para Extinção Zero (AZE), Áreas "
#         "Importantes para Aves e Biodiversidade (IBAs), sítios Ramsar, etc.",
#         unsafe_allow_html=True
#     )
    
#     st.divider()


#     # 7. Povos Indígenas ----------------------------------------------------------------------------------

#     col1, col2, col3, col4, col5 = st.columns(largura_colunas, gap="medium")

#     col1.write("**7. Povos Indígenas**")

#     with col2:
#         st.radio(
#             "Aplicável?",
#             ["Sim", "Não"],
#             key="salv_7_aplicavel",
#             horizontal=True,
#             disabled=not modo_edicao
#         )

#     with col3:
#         st.write(
#             "O projeto proposto apresenta riscos significativos relacionados "
#             "aos impactos sobre Povos Indígenas?"
#         )

#         st.text_area(
#             "Detalhes:",
#             key="salv_7_detalhes",
#             height=120,
#             disabled=not modo_edicao
#         )

#     with col4:
#         st.radio(
#             "Categoria de risco",
#             ["Categoria A", "Categoria B", "Categoria C"],
#             key="salv_7_categoria_risco",
#             disabled=not modo_edicao
#         )

#     with col5:
#         st.write(
#             "Projetos que possam afetar Povos Indígenas em isolamento voluntário "
#             "ou grupos remotos com contato externo limitado serão classificados como Categoria A."
#         )

#         st.write(
#             "Projetos que envolvam o uso de ou restrições de acesso a recursos naturais "
#             "que sejam centrais para a identidade, cultura e subsistência dos Povos Indígenas "
#             "serão classificados como Categoria B."
#         )

#         st.write(
#             "Projetos que envolvam o desenvolvimento comercial de terras e recursos naturais "
#             "centrais para a identidade e subsistência dos Povos Indígenas ou o uso comercial "
#             "de seu patrimônio cultural serão classificados como Categoria B."
#         )


#     st.divider()


#     # 8. Patrimônio Cultural -------------------------------------------------------------------------------

#     col1, col2, col3, col4, col5 = st.columns(largura_colunas, gap="medium")

#     col1.write("**8. Patrimônio Cultural**")

#     with col2:
#         st.radio(
#             "Aplicável?",
#             ["Sim", "Não"],
#             key="salv_8_aplicavel",
#             horizontal=True,
#             disabled=not modo_edicao
#         )

#     with col3:
#         st.write(
#             "O projeto proposto apresenta riscos significativos relacionados "
#             "aos impactos sobre o patrimônio cultural tangível e/ou intangível?"
#         )

#         st.text_area(
#             "Detalhes:",
#             key="salv_8_detalhes",
#             height=120,
#             disabled=not modo_edicao
#         )

#     with col4:
#         st.radio(
#             "Categoria de risco",
#             ["Categoria A", "Categoria B", "Categoria C"],
#             key="salv_8_categoria_risco",
#             disabled=not modo_edicao
#         )

#     with col5:
#         st.write(
#             "Projetos que introduzam restrições ao acesso das partes interessadas "
#             "ao patrimônio cultural serão classificados como Categoria B."
#         )

#         st.write(
#             "Projetos que envolvam o uso comercial de patrimônio cultural "
#             "serão classificados como Categoria B."
#         )

#     st.divider()


#     # 9. Igualdade de Gênero -------------------------------------------------------------------------------

#     col1, col2, col3, col4, col5 = st.columns(largura_colunas, gap="medium")

#     col1.write("**9. Igualdade de Gênero**")

#     # Coluna 2 — política sempre aplicável
#     with col2:

#         st.write("Sim")
#         st.caption("Aplica-se a todos os projetos")

#         # Mantém o valor consistente para o salvamento
#         st.session_state["salv_9_aplicavel"] = "Sim"



#     with col3:
#         st.write(
#             "O projeto proposto apresenta riscos significativos relacionados "
#             "a impactos na promoção, proteção e respeito à igualdade de gênero?"
#         )

#         st.text_area(
#             "Detalhes:",
#             key="salv_9_detalhes",
#             height=120,
#             disabled=not modo_edicao
#         )

#     with col4:
#         st.radio(
#             "Categoria de risco",
#             ["Categoria A", "Categoria B", "Categoria C"],
#             key="salv_9_categoria_risco",
#             disabled=not modo_edicao
#         )

#     with col5:
#         st.write(
#             "Projetos serão tipicamente atribuídos à Categoria C para esta política, "
#             "a menos que existam riscos elevados de agravamento de desigualdades "
#             "existentes relacionadas ao gênero."
#         )

#     st.divider()


#     # 10. Engajamento de Partes Interessadas ---------------------------------------------------------------

#     col1, col2, col3, col4, col5 = st.columns(largura_colunas, gap="medium")

#     col1.write("**10. Engajamento de Partes Interessadas**")

#     with col2:
#         st.write("Sim")
#         st.caption("Aplica-se a todos os projetos")

#         # Mantém o valor consistente para o salvamento
#         st.session_state["salv_10_aplicavel"] = "Sim"

#     col3.write("N/A")
#     col4.write("N/A")

#     col5.write(
#         "Não é necessário atribuir uma categoria de risco individual a esta política."
#     )

#     st.divider()









#     # CATEGORIA GERAL DE RISCO ---------------------------------------------------------------------------

#     col1, col2, col3, col4, col5 = st.columns(largura_colunas, gap="medium")

#     # Coluna 1
#     col1.write("**CATEGORIA GERAL DE RISCO**")

#     # Coluna 2
#     col2.write("N/A")

#     # Coluna 3
#     col3.write("N/A")


#     # Lê as categorias escolhidas nas perguntas 2 a 9

#     categorias_filtradas = []

#     for i in range(2, 10):  # perguntas 2 a 9

#         aplicavel = st.session_state.get(f"salv_{i}_aplicavel")
#         categoria = st.session_state.get(f"salv_{i}_categoria_risco")

#         if aplicavel == "Sim" and categoria:
#             categorias_filtradas.append(categoria)

#     # Determina automaticamente a categoria geral
#     # prioridade: A > B > C
    
#     if not categorias_filtradas:
#         categoria_geral = "Não avaliado"
#     elif "Categoria A" in categorias_filtradas:
#         categoria_geral = "Categoria A"
#     elif "Categoria B" in categorias_filtradas:
#         categoria_geral = "Categoria B"
#     else:
#         categoria_geral = "Categoria C"

#     # Coluna 4 — mostra o resultado calculado
#     col4.write('Resultado final:')
#     col4.write(f"**{categoria_geral}**")


#     # Coluna 5
#     col5.write(
#         "A categoria geral de risco para o projeto é equivalente à categoria mais alta "
#         "atribuída às políticas individuais de salvaguarda."
#     )

#     st.divider()



#     # FORTALECIMENTO DE CAPACIDADE ---------------------------------------------------------------------------

#     largura_colunas = [2, 2, 3, 2, 3]

#     col1, col2 = st.columns([2, 11], gap="medium")


#     col1.write("**FORTALECIMENTO DE CAPACIDADE**")

#     col2.write("O solicitante necessita de fortalecimento de capacidade para gerenciar os riscos ambientais e sociais identificados aqui?")

#     col2.write("Se sim, descreva as atividades de fortalecimento de capacidade que precisam ser integradas ao desenho do projeto:")

#     col2.text_area(
#         "Detalhes:",
#         key="salv_fortalecimento_capacidades",
#         height=120,
#         disabled=not modo_edicao
#     )

#     st.divider()








#     st.write("")


#     # Botão somente para equipe e adimn

#     if st.session_state.get("tipo_usuario") in ["equipe", "admin"]:
        

#         # Botão para salvar as respostas no banco
#         if st.button("Salvar", icon=":material/save:", width=200, type="primary"):

#             # Data da avaliação
#             data_avaliacao = datetime.datetime.today().strftime("%d/%m/%Y")

#             # Estrutura organizada das respostas de salvaguardas
#             dados_salvaguardas = {

#                 "nome_avaliador_risco": nome_avaliador,
#                 "data_aval_risco": data_avaliacao,
#                 "categoria_geral_risco": categoria_geral,

#                 "pol_2_trabalho": {
#                     "aplicavel": st.session_state.get("salv_2_aplicavel"),
#                     "detalhes": st.session_state.get("salv_2_detalhes"),
#                     "categoria": st.session_state.get("salv_2_categoria_risco")
#                 },

#                 "pol_3_poluicao": {
#                     "aplicavel": st.session_state.get("salv_3_aplicavel"),
#                     "detalhes_pesticidas": st.session_state.get("salv_3_pesticidas_detalhes"),
#                     "detalhes_poluicao": st.session_state.get("salv_3_poluicao_detalhes"),
#                     "categoria": st.session_state.get("salv_3_categoria_risco")
#                 },

#                 "pol_4_comunidade": {
#                     "aplicavel": st.session_state.get("salv_4_aplicavel"),
#                     "detalhes": st.session_state.get("salv_4_detalhes"),
#                     "categoria": st.session_state.get("salv_4_categoria_risco")
#                 },

#                 "pol_5_reassentamento": {
#                     "aplicavel": st.session_state.get("salv_5_aplicavel"),
#                     "detalhes": st.session_state.get("salv_5_detalhes"),
#                     "categoria": st.session_state.get("salv_5_categoria_risco")
#                 },

#                 "pol_6_biodiversidade": {
#                     "aplicavel": st.session_state.get("salv_6_aplicavel"),
#                     "detalhes": st.session_state.get("salv_6_detalhes"),
#                     "categoria": st.session_state.get("salv_6_categoria_risco")
#                 },

#                 "pol_7_indigenas": {
#                     "aplicavel": st.session_state.get("salv_7_aplicavel"),
#                     "detalhes": st.session_state.get("salv_7_detalhes"),
#                     "categoria": st.session_state.get("salv_7_categoria_risco")
#                 },

#                 "pol_8_patrimonio": {
#                     "aplicavel": st.session_state.get("salv_8_aplicavel"),
#                     "detalhes": st.session_state.get("salv_8_detalhes"),
#                     "categoria": st.session_state.get("salv_8_categoria_risco")
#                 },

#                 "pol_9_genero": {
#                     "aplicavel": st.session_state.get("salv_9_aplicavel"),
#                     "detalhes": st.session_state.get("salv_9_detalhes"),
#                     "categoria": st.session_state.get("salv_9_categoria_risco")
#                 },

#                 "fortalecimento_capacidades": st.session_state.get("salv_fortalecimento_capacidades"),
#             }

#             # Atualiza o documento do projeto no MongoDB
#             resultado = col_projetos.update_one(
#                 {"codigo": codigo_projeto_atual},
#                 {
#                     "$set": {
#                         "salvaguardas": dados_salvaguardas
#                     }
#                 }
#             )

#             # Mostra mensagem de sucesso
#             if resultado.modified_count >= 0:
#                 st.success("Respostas salvas com sucesso!", icon=":material/check:")
#                 time.sleep(3)
#                 st.rerun()






# ###################################################################################################
# REMANEJAMENTOS
# ###################################################################################################
with remanejamentos:


    if "modo_remanejamento" not in st.session_state:
        st.session_state["modo_remanejamento"] = "lista"


    # ===============================================================================================
    # PERMISSÃO
    # -----------------------------------------------------------------------------------------------
    # Apenas usuários beneficiários podem solicitar remanejamentos
    # ===============================================================================================

    usuario_beneficiario = st.session_state.tipo_usuario == "beneficiario"

    st.write("")


    # ===============================================================================================
    # CARREGA O PLANO DE TRABALHO
    # ===============================================================================================


    # Recupera o plano de trabalho do projeto
    # Se não existir no documento, retorna um dicionário vazio
    plano_trabalho_dict = projeto_dict.get("plano_trabalho", {}) or {}



    # Função para renderizar a interface no modo lista
    def interface_lista_atividades(atividades):

        for atividade in atividades:

            nome_atividade = atividade.get("atividade")
            id_atividade = atividade.get("id")

            data_inicio = atividade.get("data_inicio") or "-"
            data_fim = atividade.get("data_fim") or "-"

            label_botao = f"{nome_atividade} - {data_inicio} a {data_fim}"

            if st.button(
                label_botao,
                key=f"remanej_atv_{id_atividade}",
                type="tertiary",
            ):
                st.session_state["atividade_remanejamento"] = atividade
                st.session_state["modo_remanejamento"] = "editar"
                st.rerun() 



    # Função para renderizar a interface no modo edição de atividade
    def interface_editar_atividade():

        with st.container(border=True):

            atividade = st.session_state.get("atividade_remanejamento")

            if not atividade:
                return

            st.markdown("##### Alterar atividade")

            st.write("")

            # --------------------------------------------------------------
            # Valores originais da atividade
            # --------------------------------------------------------------

            descricao_original = atividade.get("atividade")
            data_inicio_str = atividade.get("data_inicio")
            data_fim_str = atividade.get("data_fim")

            data_inicio_original = None
            data_fim_original = None

            if data_inicio_str:
                data_inicio_original = datetime.datetime.strptime(data_inicio_str, "%d/%m/%Y").date()

            if data_fim_str:
                data_fim_original = datetime.datetime.strptime(data_fim_str, "%d/%m/%Y").date()

            # --------------------------------------------------------------
            # Inputs
            # --------------------------------------------------------------

            descricao_atividade = st.text_area(
                "Descrição da atividade",
                value=descricao_original,
                key="remanej_desc_atividade",
                height=120
            )

            col1, col2 = st.columns(2)

            with col1:

                nova_data_inicio = st.date_input(
                    "Data de início",
                    value=data_inicio_original,
                    format="DD/MM/YYYY",
                    key="remanej_data_inicio"
                )

            with col2:

                nova_data_fim = st.date_input(
                    "Data de fim",
                    value=data_fim_original,
                    format="DD/MM/YYYY",
                    key="remanej_data_fim"
                )

            st.write("")

            justificativa = st.text_area(
                "Justificativa",
                key="remanej_justificativa",
                height=120
            )

            st.write("")
            st.write("")

            # --------------------------------------------------------------
            # Botões
            # --------------------------------------------------------------


            with st.container(horizontal=True):

                # Botão de cancelar e voltar
                if st.button(
                    "Cancelar",
                    icon=":material/close:",
                    type="secondary",
                    width=200
                ):

                    st.session_state["modo_remanejamento"] = "lista"
                    st.session_state.pop("atividade_remanejamento", None)

                    st.rerun()


                # Botão de enviar solicitação de remanejamento
                if st.button(
                    "Enviar solicitação de remanejamento",
                    icon=":material/outgoing_mail:",
                    type="primary"
                ):

                    # --------------------------------------------------
                    # Justificativa obrigatória
                    # --------------------------------------------------

                    if not justificativa.strip():
                        st.warning("Informe a justificativa da solicitação.")
                        return

                    antes = {}
                    depois = {}

                    # --------------------------------------------------
                    # Verifica alterações
                    # --------------------------------------------------

                    if descricao_atividade != descricao_original:

                        antes["atividade"] = descricao_original
                        depois["atividade"] = descricao_atividade

                    if nova_data_inicio != data_inicio_original:

                        antes["data_inicio"] = data_inicio_str
                        depois["data_inicio"] = nova_data_inicio.strftime("%d/%m/%Y")

                    if nova_data_fim != data_fim_original:

                        antes["data_fim"] = data_fim_str
                        depois["data_fim"] = nova_data_fim.strftime("%d/%m/%Y")

                    # --------------------------------------------------
                    # Só registra se houve alteração
                    # --------------------------------------------------

                    if not depois:
                        st.warning("Nenhuma alteração foi realizada.")
                        return



                    # --------------------------------------------------
                    # Só registra se houve alteração
                    # --------------------------------------------------

                    if depois:

                        with st.spinner("Salvando alterações..."):

                            novo_remanejamento = {

                                "tipo_remanejamento": "alterar_atividade",

                                "data_solicit_remanej": datetime.datetime.today().strftime("%d/%m/%Y"),

                                "status_remanejamento": "em_analise",

                                "atividade_id": atividade.get("id"),

                                "antes": antes,

                                "depois": depois,

                                "justificativa": justificativa,

                                "autor": st.session_state.get("nome")
                            }

                            col_projetos.update_one(
                                {"codigo": codigo_projeto_atual},
                                {
                                    "$push": {
                                        "plano_trabalho.remanejamentos_atividades": novo_remanejamento
                                    }
                                }
                            )



                            # Enviando email para os padrinhos
                            projeto_atualizado = col_projetos.find_one({"codigo": codigo_projeto_atual})

                            enviar_email_remanejamento_atividade(
                                projeto_atualizado,
                                novo_remanejamento
                            )

                            st.success("Solicitação enviada com sucesso!", icon=":material/check:")

                            time.sleep(3)

                            st.session_state["modo_remanejamento"] = "lista"
                            st.session_state.pop("atividade_remanejamento", None)

                            # Esconde o container de nova solicitação
                            st.session_state["mostrar_remanejamento"] = False

                            st.rerun()

                    else:

                        st.warning("Nenhuma alteração foi realizada.")






    # ===============================================================================================
    # FRAGMENTO: NOVA SOLICITAÇÃO DE REMANEJAMENTO
    # ===============================================================================================

    @st.fragment
    def fragmento_remanejamento(plano_trabalho):

        with st.container(border=True):

            st.markdown("##### Nova solicitação de remanejamento")

            st.write("")

            # ------------------------------------------------------------------
            # Tipo de remanejamento
            # ------------------------------------------------------------------

            tipo_remanejamento = st.radio(
                "O que deseja fazer?",
                [
                    "Alterar atividade",
                    "Adicionar atividade",
                    "Remover atividade"
                ],
                key="tipo_remanejamento_atividade",
                horizontal=True
            )

            st.write("")


















            # ------------------------------------------------------------------
            # ALTERAÇÃO DE ATIVIDADE
            # ------------------------------------------------------------------

            if tipo_remanejamento == "Alterar atividade":

                # Recupera componentes do plano de trabalho
                componentes = plano_trabalho.get("componentes", [])

                nomes_componentes = [
                    c.get("componente")
                    for c in componentes
                ]

                # opção vazia
                opcoes_componentes = [""] + nomes_componentes

                componente_selecionado = st.selectbox(
                    "Selecione o objetivo específico",
                    opcoes_componentes,
                    key="remanej_componente"
                )

                # --------------------------------------------------------------
                # Controle de mudança de componente
                # --------------------------------------------------------------

                if "componente_atual" not in st.session_state:
                    st.session_state["componente_atual"] = ""

                if componente_selecionado != st.session_state["componente_atual"]:
                    st.session_state["modo_remanejamento"] = "lista"
                    st.session_state.pop("atividade_remanejamento", None)
                    st.session_state["componente_atual"] = componente_selecionado


                if componente_selecionado:
    
                    st.write("")


                    componente_obj = next(
                        (
                            c for c in componentes
                            if c.get("componente") == componente_selecionado
                        ),
                        None
                    )

                    if componente_obj:

                        atividades = componente_obj.get("atividades", [])

                        if st.session_state["modo_remanejamento"] == "lista":
                            interface_lista_atividades(atividades)
                        else:
                            interface_editar_atividade()

            # ------------------------------------------------------------------
            # ADICIONAR ATIVIDADE
            # ------------------------------------------------------------------

            elif tipo_remanejamento == "Adicionar atividade":

                componentes = plano_trabalho.get("componentes", [])

                nomes_componentes = [c.get("componente") for c in componentes]
                opcoes_componentes = [""] + nomes_componentes

                componente_sel = st.selectbox(
                    "Selecione o objetivo específico",
                    opcoes_componentes,
                    key="add_componente"
                )

                if componente_sel:

                    comp_obj = next(
                        (c for c in componentes if c.get("componente") == componente_sel),
                        None
                    )

                    if comp_obj:

                        st.write("")

                        descricao = st.text_area("Descrição da atividade", key="add_desc")

                        col1, col2 = st.columns(2)

                        with col1:
                            data_inicio = st.date_input(
                                "Data de início",
                                format="DD/MM/YYYY",
                                key="add_data_inicio"
                            )

                        with col2:
                            data_fim = st.date_input(
                                "Data de fim",
                                format="DD/MM/YYYY",
                                key="add_data_fim"
                            )

                        justificativa = st.text_area("Justificativa", key="add_justificativa")

                        st.write("")

                        # BOTÕES
                        with st.container(horizontal=True):

                        
                            if st.button("Cancelar", key="cancel_add", icon=":material/close:", width=200):
                                st.session_state["mostrar_remanejamento"] = False
                                st.rerun()

                        
                            if st.button(
                                "Enviar solicitação de remanejamento",
                                icon=":material/outgoing_mail:",
                                type="primary",
                                key="submit_add"
                            ):

                                if not descricao.strip():
                                    st.warning("Informe a descrição da atividade.")
                                    return

                                if not justificativa.strip():
                                    st.warning("Informe a justificativa.")
                                    return
                                
                                with st.spinner("Salvando alterações..."):
                                    
                                    novo_remanejamento = {

                                        "tipo_remanejamento": "adicionar_atividade",

                                        "data_solicit_remanej": datetime.datetime.today().strftime("%d/%m/%Y"),

                                        "status_remanejamento": "em_analise",

                                        "componente": componente_sel,
                                        "add_atividade": descricao,
                                        "data_inicio": data_inicio.strftime("%d/%m/%Y"),
                                        "data_fim": data_fim.strftime("%d/%m/%Y"),

                                        "justificativa": justificativa,
                                        "autor": st.session_state.get("nome")
                                    }

                                    col_projetos.update_one(
                                        {"codigo": codigo_projeto_atual},
                                        {
                                            "$push": {
                                                "plano_trabalho.remanejamentos_atividades": novo_remanejamento
                                            }
                                        }
                                    )

                                    projeto_atualizado = col_projetos.find_one(
                                        {"codigo": codigo_projeto_atual}
                                    )

                                    enviar_email_nova_atividade(
                                        codigo_projeto_atual,
                                        projeto_atualizado
                                    )
                                    
                                    st.session_state["modo_remanejamento"] = "lista"
                                    st.session_state.pop("atividade_remanejamento", None)

                                    # Esconde o container de nova solicitação
                                    st.session_state["mostrar_remanejamento"] = False

                                    st.success("Solicitação enviada com sucesso!")
                                    time.sleep(2)
                                    st.rerun()


            # ------------------------------------------------------------------
            # REMOVER ATIVIDADE
            # ------------------------------------------------------------------

            elif tipo_remanejamento == "Remover atividade":

                componentes = plano_trabalho.get("componentes", [])

                nomes_componentes = [c.get("componente") for c in componentes]
                opcoes_componentes = [""] + nomes_componentes

                componente_sel = st.selectbox(
                    "Selecione o objetivo específico",
                    opcoes_componentes,
                    key="del_componente"
                )

                if componente_sel:

                    comp_obj = next(
                        (c for c in componentes if c.get("componente") == componente_sel),
                        None
                    )

                    if comp_obj:

                        atividades = comp_obj.get("atividades", [])

                        nomes_atividades = [""] + [a.get("atividade") for a in atividades]

                        atividade_sel = st.selectbox(
                            "Selecione a atividade",
                            nomes_atividades,
                            key="del_atividade_sel"
                        )

                        if atividade_sel:

                            atividade_obj = next(
                                (a for a in atividades if a.get("atividade") == atividade_sel),
                                None
                            )

                            justificativa = st.text_area(
                                "Justificativa",
                                key="del_justificativa"
                            )

                            st.write("")

                            # BOTÕES
                            with st.container(horizontal=True):

                         
                                if st.button("Cancelar", key="cancel_del", icon=":material/close:", width=200):
                                    st.session_state["mostrar_remanejamento"] = False
                                    st.rerun()

                       
                                if st.button(
                                    "Enviar solicitação de remanejamento",
                                    icon=":material/outgoing_mail:",
                                    type="primary",
                                    key="submit_del"
                                ):

                                    if not justificativa.strip():
                                        st.warning("Informe a justificativa.")
                                        return

                                    # ==================================================
                                    # VERIFICA SE JÁ EXISTE SOLICITAÇÃO DE REMOÇÃO
                                    # ==================================================

                                    lista_remanejamentos = plano_trabalho.get("remanejamentos_atividades", []) or []

                                    ja_existe = any(
                                        r.get("tipo_remanejamento") == "remover_atividade"
                                        and r.get("atividade_id") == atividade_obj.get("id")
                                        and r.get("status_remanejamento") == "em_analise"
                                        for r in lista_remanejamentos
                                    )

                                    if ja_existe:
                                        st.warning("Já existe uma solicitação de remoção em análise para esta atividade.")
                                        return

                                    # ==================================================
                                    # CRIA REMANEJAMENTO
                                    # ==================================================
                                    
                                    with st.spinner("Salvando alterações..."):
                                        
                                        novo_remanejamento = {

                                            "tipo_remanejamento": "remover_atividade",

                                            "data_solicit_remanej": datetime.datetime.today().strftime("%d/%m/%Y"),

                                            "status_remanejamento": "em_analise",

                                            "componente": componente_sel,
                                            "atividade_id": atividade_obj.get("id"),
                                            "del_atividade": atividade_sel,

                                            "justificativa": justificativa,
                                            "autor": st.session_state.get("nome")
                                        }

                                        col_projetos.update_one(
                                            {"codigo": codigo_projeto_atual},
                                            {
                                                "$push": {
                                                    "plano_trabalho.remanejamentos_atividades": novo_remanejamento
                                                }
                                            }
                                        )

                                        projeto_atualizado = col_projetos.find_one(
                                            {"codigo": codigo_projeto_atual}
                                        )

                                        enviar_email_remocao_atividade_solicitada(
                                            codigo_projeto_atual,
                                            projeto_atualizado
                                        )
                                        
                                        st.session_state["modo_remanejamento"] = "lista"
                                        st.session_state.pop("atividade_remanejamento", None)

                                        # Esconde o container de nova solicitação
                                        st.session_state["mostrar_remanejamento"] = False

                                        st.success("Solicitação enviada com sucesso!")
                                        time.sleep(2)
                                        st.rerun()


    # --------------------------------------------------
    # Inicializa controle de exibição do formulário
    # --------------------------------------------------
    if "mostrar_remanejamento" not in st.session_state:
        st.session_state["mostrar_remanejamento"] = False


    # --------------------------------------------------
    # Botão só para beneficiário
    # --------------------------------------------------
    if usuario_beneficiario:

        st.write("")

        # Verifica se já existe remanejamento em análise
        lista_remanejamentos = plano_trabalho_dict.get("remanejamentos_atividades", []) or []
        
        tem_pendente = any(
            r.get("status_remanejamento") == "em_analise"
            for r in lista_remanejamentos
        )

        if st.button(
            "Solicitar remanejamento",
            icon=":material/compare_arrows:",
        ):

            st.session_state["mostrar_remanejamento"] = not st.session_state["mostrar_remanejamento"]


    # --------------------------------------------------
    # Fragmento (formulário)
    # --------------------------------------------------
    if st.session_state["mostrar_remanejamento"]:
        fragmento_remanejamento(plano_trabalho_dict)





    # --------------------------------------------------
    # Histórico de remanejamentos de atividades
    # --------------------------------------------------

    st.write("")
    st.write("")
    st.write("#### Histórico de solicitações de remanejamento")


    lista_remanej = plano_trabalho_dict.get("remanejamentos_atividades", [])


    if not lista_remanej:
        st.caption("Nenhuma solicitação de remanejamento até o momento.")
    else:

        # RENDERIZA CADA CARD DE REMANEJAMENTO, CONDICIONALMENTE

        for idx in range(len(lista_remanej) - 1, -1, -1):

            item = lista_remanej[idx]

            with st.container(border=True):

                tipo_rem = item.get("tipo_remanejamento")

                if tipo_rem == "alterar_atividade":
                    renderizar_card_alteracao(item, idx, plano_trabalho_dict)

                elif tipo_rem == "adicionar_atividade":
                    renderizar_card_add(item)

                elif tipo_rem == "remover_atividade":
                    renderizar_card_del(item, idx)


