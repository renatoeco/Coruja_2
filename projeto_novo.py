import streamlit as st
from funcoes_auxiliares import conectar_mongo_coruja
import pandas as pd
import bson
import time


st.set_page_config(page_title="Novo Projeto", page_icon=":material/add_circle:")



###########################################################################################################
# CONEXÃO COM O BANCO
###########################################################################################################

db = conectar_mongo_coruja()

col_projetos = db["projetos"]
col_pessoas = db["pessoas"]
col_organizacoes = db["organizacoes"]
col_editais = db["editais"]
col_publicos = db["publicos"]

df_pessoas = pd.DataFrame(list(col_pessoas.find()))
df_publicos = pd.DataFrame(list(col_publicos.find()))

###########################################################################################################
# SESSION STATE
###########################################################################################################

# Controle do formulário
if "form_key" not in st.session_state:
    st.session_state.form_key = 0

# Dados do formulário
if "form_projeto" not in st.session_state:
    st.session_state.form_projeto = {
        "edital": "",
        "id_organizacao": "",
        "codigo": "",
        "sigla": "",
        "nome": "",
        "duracao": 1,
        "data_inicio": None,
        "data_fim": None,
        "responsavel": [],
        # "direcoes": [],
        "publicos": [],
        "objetivo": ""
    }

###########################################################################################################
# INTERFACE
###########################################################################################################

st.logo("images/logo_fundo_ecos.png", size="large")
st.header("Novo projeto")

st.write(
    "*Antes de cadastrar o **projeto**, cadastre a **Organização** e as **Pessoas** envolvidas.*"
)















###########################################################################################################
# DADOS AUXILIARES (PESSOAS RESPONSÁVEIS)
###########################################################################################################

# apenas beneficiários
pessoas_benef = df_pessoas[
    df_pessoas["tipo_usuario"].str.contains("beneficiario", na=False)
][["_id", "nome_completo"]]

# mapa id -> nome (para exibição)
mapa_id_nome = {
    row["_id"]: row["nome_completo"]
    for _, row in pessoas_benef.iterrows()
}

lista_ids = list(mapa_id_nome.keys())




###########################################################################################################
# DADOS AUXILIARES (ORGANIZAÇÕES)
###########################################################################################################

orgs = list(col_organizacoes.find().sort("nome_organizacao", 1))

# mapa id -> nome da organização (para exibição no selectbox)
mapa_org_id_nome = {
    org["_id"]: org["nome_organizacao"]
    for org in orgs
}

# lista de ids das organizações (será usada no selectbox)
lista_org_ids = list(mapa_org_id_nome.keys())


st.write('')

col1, col2, col3 = st.columns(3)



###########################################################################################################
# EDITAL (FORA DO FORM)
###########################################################################################################

editais = list(col_editais.find().sort("data_lancamento", -1))
lista_editais = [e["codigo_edital"] for e in editais]

edital = col1.selectbox(
    "Edital",
    lista_editais,
    index=lista_editais.index(st.session_state.form_projeto["edital"])
    if st.session_state.form_projeto["edital"] in lista_editais else 0,
)

# pega o documento do edital selecionado
edital_doc = next((e for e in editais if e["codigo_edital"] == edital), {})




###########################################################################################################
# FORMULÁRIO
###########################################################################################################

with st.form(key=f"form_novo_projeto_{st.session_state.form_key}", border=False):


    codigo_projeto = col2.text_input(
        "Código do Projeto",
        value=st.session_state.form_projeto["codigo"]
    )

    sigla_projeto = col3.text_input(
        "Sigla do Projeto",
        value=st.session_state.form_projeto["sigla"]
    )

    organizacao_id = st.selectbox(
        "Organização",
        lista_org_ids,
        index=0,
        format_func=lambda x: mapa_org_id_nome[x],  # exibe nome da organização
    )


    nome_projeto = st.text_input(
        "Nome do Projeto",
        value=st.session_state.form_projeto["nome"]
    )



    col1, col2, col3 = st.columns(3)
    
    duracao = col1.number_input(
        "Duração do Projeto (meses)",
        min_value=1,
        step=1,
        value=st.session_state.form_projeto["duracao"]
    )

    data_inicio = col2.date_input(
        "Data de Início",
        value=st.session_state.form_projeto["data_inicio"],
        format="DD/MM/YYYY"
    )

    data_fim = col3.date_input(
        "Data de Fim",
        value=st.session_state.form_projeto["data_fim"],
        format="DD/MM/YYYY"
    )


    col1, col2 = st.columns([2, 1])

    responsaveis_ids = col1.multiselect(
        "Responsáveis pelo projeto",
        lista_ids,
        default=st.session_state.form_projeto["responsavel"],
        format_func=lambda x: "" if x is None else mapa_id_nome[x]
    )

    publicos = col2.multiselect(
        "Públicos",
        df_publicos["publico"].tolist(),
        default=st.session_state.form_projeto["publicos"]
    )

    objetivo = st.text_area(
        "Objetivo geral",
        value=st.session_state.form_projeto["objetivo"]
    )

    submit = st.form_submit_button("Cadastrar projeto", type="primary")










###########################################################################################################
# PROCESSAMENTO
###########################################################################################################

if submit:

    #######################################################################################################
    # SALVA NO SESSION STATE
    #######################################################################################################

    st.session_state.form_projeto.update({
        "edital": edital,
        "organizacao": organizacao_id,
        "codigo": codigo_projeto,
        "sigla": sigla_projeto,
        "nome": nome_projeto,
        "duracao": duracao,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "responsavel": responsaveis_ids,  # lista de _id
        # "direcoes": direcoes,
        "publicos": publicos,
        "objetivo": objetivo
    })


    #######################################################################################################
    # VALIDAÇÃO
    #######################################################################################################

    obrigatorios = {
        "Edital": edital,
        "Código": codigo_projeto,
        "Sigla": sigla_projeto,
        "Nome": nome_projeto,
        "Objetivo": objetivo,
        "Data início": data_inicio,
        "Data fim": data_fim,
        # "Direções": direcoes,
        "Públicos": publicos
    }

    faltando = [k for k, v in obrigatorios.items() if not v]

    if faltando:
        st.error(f"Preencha os campos obrigatórios: {', '.join(faltando)}")

    elif col_projetos.find_one({"codigo": codigo_projeto}):
        st.warning(f":material/warning: Já existe um projeto com o código {codigo_projeto}.")

    elif col_projetos.find_one({"sigla": sigla_projeto}):
        st.warning(f":material/warning: Já existe um projeto com a sigla {sigla_projeto}.")

    else:

        ###################################################################################################
        # INSERE PROJETO
        ###################################################################################################

        col_projetos.insert_one({
            "_id": bson.ObjectId(),
            "edital": edital,
            "codigo": codigo_projeto,
            "sigla": sigla_projeto,
            "id_organizacao": organizacao_id,
            "nome_do_projeto": nome_projeto,
            "objetivo_geral": objetivo,
            "duracao": duracao,
            "data_inicio_contrato": data_inicio.strftime("%d/%m/%Y"),
            "data_fim_contrato": data_fim.strftime("%d/%m/%Y"),
            # "direcoes_estrategicas": direcoes,
            "publicos": publicos,
            "status": "Em dia"
        })

        ###################################################################################################
        # ATUALIZA PESSOA (ADICIONA CÓDIGO DO PROJETO)
        ###################################################################################################


        if responsaveis_ids:

            col_pessoas.update_many(
                {"_id": {"$in": responsaveis_ids}},
                {
                    "$addToSet": {
                        "projetos": codigo_projeto
                    }
                }
            )


        st.success("Projeto cadastrado com sucesso!", icon=":material/check:")

        ###################################################################################################
        # RESET FORMULÁRIO 
        ###################################################################################################

        st.session_state.form_projeto = {
            "edital": "",
            "id_organizacao": None,
            "codigo": "",
            "sigla": "",
            "nome": "",
            "duracao": 1,
            "data_inicio": None,
            "data_fim": None,
            "responsavel": [],
            # "direcoes": [],
            "publicos": [],
            "objetivo": ""
        }

        st.session_state.form_key += 1
        time.sleep(3)
        st.rerun()












