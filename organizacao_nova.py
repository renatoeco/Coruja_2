
import streamlit as st
from funcoes_auxiliares import conectar_mongo_coruja, limpar_e_validar_cep  # Funções personalizadas
import pandas as pd
import locale
import re
import time
import uuid


st.set_page_config(page_title="Nova Organização", page_icon=":material/add_business:")




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

col_organizacoes = db["organizacoes"]
df_organizacoes = pd.DataFrame(list(col_organizacoes.find()))

col_temas = db["temas_projetos"]
df_temas = pd.DataFrame(list(col_temas.find()))

col_publicos = db["publicos"]
df_publicos = pd.DataFrame(list(col_publicos.find()))


# -------------------------------------------------------------------------------------------------
# COLEÇÃO UF_MUNICIPIOS - DOCUMENTO DE UFs
# -------------------------------------------------------------------------------------------------

col_uf_municipios = db["ufs_municipios"]

# Busca especificamente o documento que possui a chave 'ufs'
doc_ufs = col_uf_municipios.find_one({"ufs": {"$exists": True}})

if doc_ufs and "ufs" in doc_ufs:
    df_ufs = pd.DataFrame(doc_ufs["ufs"])
else:
    st.warning("Dados de UFs não encontrados.")
    df_ufs = pd.DataFrame(columns=["sigla_uf", "nome_uf", "codigo_uf"])




# -------------------------------------------------------------------------------------------------
# COLEÇÃO UF_MUNICIPIOS - DOCUMENTO DE MUNICÍPIOS
# -------------------------------------------------------------------------------------------------

# Busca especificamente o documento que possui a chave 'municipios'
doc_municipios = col_uf_municipios.find_one({"municipios": {"$exists": True}})

if doc_municipios and "municipios" in doc_municipios:
    df_municipios = pd.DataFrame(doc_municipios["municipios"])
else:
    st.warning("Dados de municípios não encontrados.")
    df_municipios = pd.DataFrame(columns=["nome_municipio", "codigo_municipio"])






###########################################################################################################
# TRATAMENTO DOS DADOS
###########################################################################################################



# -------------------------------------------------------------------------------------------------
# PREPARAÇÃO DE LISTAS PARA INTERFACE
# -------------------------------------------------------------------------------------------------

# Lista de UFs com opção vazia no topo
lista_ufs = [""] + (
    sorted(df_ufs["sigla_uf"].dropna().tolist())
    if "sigla_uf" in df_ufs.columns else []
)

# Lista de municípios com opção vazia

lista_municipios = [""] + (
    sorted(df_municipios["nome_municipio"].dropna().tolist())
    if "nome_municipio" in df_municipios.columns else []
)






###########################################################################################################
# CONFIGURAÇÃO DE LOCALE
###########################################################################################################

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil')
    except locale.Error:
        print("Aviso: Não foi possível definir a localidade para Português. Usando a localidade padrão.")

###########################################################################################################
# FUNÇÕES AUXILIARES
###########################################################################################################





def validar_cnpj(cnpj_str):
    """
    Valida apenas o formato do CNPJ.

    Aceita:
    - 99.999.999/9999-99
    - 99999999999999
    """

    cnpj_str = str(cnpj_str).strip()

    padrao_mascarado = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")
    padrao_puro = re.compile(r"^\d{14}$")

    return bool(padrao_mascarado.match(cnpj_str) or padrao_puro.match(cnpj_str))


def formatar_cnpj(cnpj_str):
    """
    Converte qualquer CNPJ válido para o formato padrão.
    """

    cnpj_limpo = re.sub(r"\D", "", str(cnpj_str))

    return f"{cnpj_limpo[0:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:14]}"


def df_index1(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ajusta o índice do dataframe para iniciar em 1.
    """

    df2 = df.copy()
    df2.index = range(1, len(df2) + 1)
    return df2




###########################################################################################################
# CONTROLE DE LIMPEZA DO FORMULÁRIO
###########################################################################################################

# Inicializa flag de limpeza do formulário
if "limpar_form_organizacao" not in st.session_state:
    st.session_state.limpar_form_organizacao = False

# Caso a flag esteja ativa, limpa os campos antes dos widgets serem renderizados
if st.session_state.limpar_form_organizacao:

    st.session_state.sigla_organizacao_input = ""
    st.session_state.nome_organizacao_input = ""
    st.session_state.cnpj_input = ""

    # Desativa a flag após limpar
    st.session_state.limpar_form_organizacao = False




###########################################################################################################
# INTERFACE PRINCIPAL DA PÁGINA
###########################################################################################################

# Logo do sidebar
st.logo("images/logo_fundo_ecos.png", size='large')

# Título da página
st.header("Nova Organização")

st.write("")
st.write("Preencha os dados diretamente na tabela abaixo:")

# ---------------------------------------------------------------------------------------------
# DATAFRAME INICIAL (VAZIO)
# ---------------------------------------------------------------------------------------------
df_base = pd.DataFrame({
    "sigla_organizacao": [""],
    "nome_organizacao": [""],
    "cnpj": [""],
    "endereco": [""],
    "uf": [""],
    "municipio": [""],
    "cep": [""]
})

# ---------------------------------------------------------------------------------------------
# LISTAS PARA SELECTBOX
# ---------------------------------------------------------------------------------------------
lista_ufs = [""] + sorted(df_ufs["sigla_uf"].tolist())
lista_municipios = [""] + df_municipios["nome_municipio"].sort_values().tolist()

# ---------------------------------------------------------------------------------------------
# DATA EDITOR
# ---------------------------------------------------------------------------------------------
df_editado = st.data_editor(
    df_base,
    num_rows="dynamic",
    width="stretch",
    column_config={
        "sigla_organizacao": st.column_config.TextColumn("Sigla", width=1),
        "nome_organizacao": st.column_config.TextColumn("Nome da Organização", width=200),
        "cnpj": st.column_config.TextColumn("CNPJ", width=1),
        "endereco": st.column_config.TextColumn("Endereço", width=200),
        "uf": st.column_config.SelectboxColumn("UF", options=lista_ufs, width=1),
        "municipio": st.column_config.SelectboxColumn("Município", options=lista_municipios, width=1),
        "cep": st.column_config.TextColumn("CEP", width=1),
    }
)

st.write("")

# ---------------------------------------------------------------------------------------------
# BOTÃO DE SALVAR
# ---------------------------------------------------------------------------------------------
if st.button(":material/save: Cadastrar organizações", type="primary"):

    df = df_editado.copy()

    # Remove linhas completamente vazias
    df = df.dropna(how="all")

    # Remove linhas onde todos os campos são vazios
    df = df[
        df.astype(str).apply(lambda x: "".join(x).strip() != "", axis=1)
    ]

    if df.empty:
        st.error("Nenhum dado válido para cadastro.")
        st.stop()

    # -----------------------------------------------------------------------------------------
    # VALIDAÇÕES
    # -----------------------------------------------------------------------------------------

    registros_validos = []
    erros = []

    for idx, row in df.iterrows():

        linha_num = idx + 1

        sigla = str(row["sigla_organizacao"]).strip()
        nome = str(row["nome_organizacao"]).strip()
        cnpj = str(row["cnpj"]).strip()
        endereco = str(row["endereco"]).strip()
        uf = str(row["uf"]).strip()
        municipio_nome = str(row["municipio"]).strip()
        cep_raw = str(row["cep"]).strip()



        # IDENTIFICADOR DA LINHA PARA MENSAGENS DE ERRO (SIGLA → NOME → VAZIO)
        nome_org = str(row["nome_organizacao"]).strip()
        identificador_ref = sigla if sigla else nome_org if nome_org else ""
        identificador = f"Linha {linha_num} ({identificador_ref})"

        # -----------------------------
        # Validação obrigatórios
        # -----------------------------
        if not sigla or not nome or not cnpj or not endereco or not uf or not municipio_nome or not cep_raw:
            erros.append(f"{identificador}: Campos obrigatórios não preenchidos.")
            continue

        # -----------------------------
        # CNPJ
        # -----------------------------
        if not validar_cnpj(cnpj):
            erros.append(f"{identificador}: CNPJ inválido.")
            continue

        cnpj = formatar_cnpj(cnpj)

        # -----------------------------
        # CEP
        # -----------------------------
        cep_limpo, cep_valido = limpar_e_validar_cep(cep_raw)

        if not cep_valido:
            erros.append(f"{identificador}: CEP inválido.")
            continue

        # -----------------------------
        # UF
        # -----------------------------
        uf_match = df_ufs[df_ufs["sigla_uf"] == uf] if "sigla_uf" in df_ufs.columns else pd.DataFrame()

        if uf_match.empty:
            erros.append(f"{identificador}: UF inválida.")
            continue

        uf_doc = uf_match.iloc[0]

        # -----------------------------
        # MUNICÍPIO
        # -----------------------------
        mun_match = (
            df_municipios[df_municipios["nome_municipio"] == municipio_nome]
            if "nome_municipio" in df_municipios.columns else pd.DataFrame()
        )

        if mun_match.empty:
            erros.append(f"{identificador}: Município inválido.")
            continue

        municipio_doc = mun_match.iloc[0]

        # -----------------------------
        # DUPLICIDADE NO BANCO
        # -----------------------------
        if col_organizacoes.find_one({"sigla_organizacao": sigla}):
            erros.append(f"{identificador}: Sigla já existe.")
            continue

        if col_organizacoes.find_one({"cnpj": cnpj}):
            erros.append(f"{identificador}: CNPJ já existe.")
            continue

        # -----------------------------
        # DOCUMENTO FINAL
        # -----------------------------
        doc = {
            "sigla_organizacao": sigla,
            "nome_organizacao": nome,
            "cnpj": cnpj,
            "endereco": endereco,
            "uf": {
                "sigla": uf_doc["sigla_uf"],
                "nome": uf_doc["nome_uf"],
                "codigo_uf": int(uf_doc["codigo_uf"])
            },
            "municipio": {
                "nome": municipio_doc["nome_municipio"],
                "codigo_municipio": int(municipio_doc["codigo_municipio"])
            },
            "cep": cep_limpo
        }

        registros_validos.append(doc)

    # -----------------------------------------------------------------------------------------
    # EXIBIÇÃO DE ERROS
    # -----------------------------------------------------------------------------------------
    if erros:
        st.error("Alguns dados estão vazios ou precisam ser corrigidos:")
        for e in erros:
            st.write(f"- {e}")
        st.stop()

    # -----------------------------------------------------------------------------------------
    # INSERÇÃO EM MASSA
    # -----------------------------------------------------------------------------------------
    if registros_validos:
        resultado = col_organizacoes.insert_many(registros_validos)

        st.success(f"{len(resultado.inserted_ids)} organizações cadastradas com sucesso!", icon=":material/check:")

        time.sleep(3)
        st.rerun()



