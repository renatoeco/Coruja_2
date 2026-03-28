import streamlit as st
import time
import pandas as pd
import io
import folium
from streamlit_folium import st_folium

from funcoes_auxiliares import (
    conectar_mongo_cepf_gestao,
    sidebar_projeto,
    # ajustar_altura_data_editor,

    # Google Drive
    obter_servico_drive,
    obter_ou_criar_pasta,
    obter_pasta_locais,
    obter_pasta_projeto,
    enviar_arquivo_drive,
    gerar_link_drive
)


st.set_page_config(page_title="Locais", page_icon=":material/map:")




###########################################################################################################
# CONFIGURAÇÕES DO STREAMLIT
###########################################################################################################


# Traduzindo o texto do st.file_uploader
# Texto interno
st.markdown("""
<style>
/* Esconde o texto padrão */
[data-testid="stFileUploaderDropzone"] div div::before {
    content: "Arraste e solte os arquivos aqui";
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
db = conectar_mongo_cepf_gestao()

# Coleção de projetos
col_projetos = db["projetos"]

# Coleção de UFs e Municípios
col_ufs_munic = db["ufs_municipios"]

# Coleção de corredores
col_corredores = db["corredores"]

# Coleção de KBAs
col_kbas = db["kbas"]





###########################################################################################################
# CARREGAMENTO DE DADOS
###########################################################################################################


# Capturando o código do projeto e os dados do projeto
codigo_projeto_atual = st.session_state.get("projeto_atual")

if not codigo_projeto_atual:
    st.error("Nenhum projeto selecionado.")
    st.stop()


df_projeto = pd.DataFrame(
    list(
        col_projetos.find(
            {"codigo": codigo_projeto_atual}
        )
    )
)



projeto = col_projetos.find_one(
    {"codigo": codigo_projeto_atual},
    {"codigo": 1, "sigla": 1, "locais": 1}
) or {}



# --------------------------------------------------
# COLEÇÃO COM UFs E MUNICÍPIOS (IBGE)
# --------------------------------------------------

docs = list(col_ufs_munic.find({}))

lista_ufs = []
lista_municipios = []

for doc in docs:
    if "ufs" in doc:
        lista_ufs = doc["ufs"]
    elif "municipios" in doc:
        lista_municipios = doc["municipios"]

# --------------------------------------------------
# SIGLA DA UF (APENAS PARA FORMATAÇÃO)
# --------------------------------------------------
sigla_por_codigo_uf = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA",
    "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
    "41": "PR", "42": "SC", "43": "RS",
    "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}

locais = projeto.get("locais", {})


# Lista completa de corredores disponíveis
lista_corredores = list(
    col_corredores.find(
        {},
        {"_id": 0, "id_corredor": 1, "nome_corredor": 1}
    ).sort("nome_corredor", 1)
)


# Lista completa de KBAs disponíveis
lista_kbas = list(
    col_kbas.find(
        {},
        {"_id": 0, "id_kba": 1, "nome_kba": 1}
    ).sort("nome_kba", 1)
)




###########################################################################################################
# FUNÇÕES
###########################################################################################################



def extrair_lat_long_google_maps(link):
    try:
        # Extrai a parte após o "@"
        coordenadas = link.split("@")[1].split(",")
        latitude = coordenadas[0]
        longitude = coordenadas[1]
        return latitude, longitude
    except (IndexError, AttributeError):
        return None, None






# -------------------------------------------------------------------------------
# DIÁLOGO — EDITAR ESTADOS
# -------------------------------------------------------------------------------

@st.dialog("Editar Estados", width="medium")
def dialog_editar_estados():

    # st.write("Selecione os estados de atuação do projeto.")
    st.write("")

    nomes_estados = sorted(
        [uf["nome_uf"] for uf in lista_ufs],
        key=lambda x: x.lower()
    )

    estados_default = [
        e["nome_estado"]
        for e in locais.get("estados", [])
        if e.get("nome_estado") in nomes_estados
    ]

    estados_selecionados = st.multiselect(
        "Selecione os estados de atuação do projeto",
        options=nomes_estados,
        default=estados_default,
        placeholder="Selecione os estados"
    )

    st.write("")

    if st.button(
        "Salvar",
        icon=":material/save:",
        key="salvar_estados_dialogo"
    ):

        estados_para_salvar = [
            {
                "codigo_uf": int(uf["codigo_uf"]),
                "nome_estado": uf["nome_uf"]
            }
            for uf in lista_ufs
            if uf["nome_uf"] in estados_selecionados
        ]

        col_projetos.update_one(
            {"codigo": codigo_projeto_atual},
            {
                "$set": {
                    "locais.estados": estados_para_salvar
                }
            }
        )

        st.success("Estados atualizados com sucesso!", icon=":material/check:")
        time.sleep(3)
        st.rerun()





@st.dialog("Editar Municípios", width="medium")
def dialog_editar_municipios():

    st.write("")

    # --------------------------------------------------
    # LISTA DE MUNICÍPIOS DISPONÍVEIS (Nome - UF)
    # --------------------------------------------------
    nomes_municipios = sorted(
        [
            f"{m['nome_municipio']} - {sigla_por_codigo_uf.get(str(m['codigo_municipio'])[:2], '')}"
            for m in lista_municipios
        ],
        key=lambda x: x.lower()
    )

    municipios_default = [
        m["nome_municipio"]
        for m in locais.get("municipios", [])
        if m.get("nome_municipio") in nomes_municipios
    ]

    municipios_selecionados = st.multiselect(
        "Selecione os municípios de atuação do projeto",
        options=nomes_municipios,
        default=municipios_default,
        placeholder="Selecione os municípios"
    )

    st.write("")

    if st.button(
        "Salvar",
        icon=":material/save:",
        key="salvar_municipios_dialogo"
    ):

        municipios_para_salvar = []

        for m in lista_municipios:
            nome_formatado = (
                f"{m['nome_municipio']} - "
                f"{sigla_por_codigo_uf.get(str(m['codigo_municipio'])[:2], '')}"
            )

            if nome_formatado in municipios_selecionados:
                municipios_para_salvar.append({
                    "codigo_municipio": int(m["codigo_municipio"]),
                    "nome_municipio": nome_formatado
                })

        col_projetos.update_one(
            {"codigo": codigo_projeto_atual},
            {
                "$set": {
                    "locais.municipios": municipios_para_salvar
                }
            }
        )

        st.success("Municípios atualizados com sucesso!", icon=":material/check:")
        time.sleep(2)
        st.rerun()



@st.dialog("Localidades e Comunidades", width="medium")
def dialog_editar_localidades():

    abas = st.tabs(["Cadastrar", "Excluir"])

    # =============================================================================
    # ABA — CADASTRAR
    # =============================================================================
    with abas[0]:

        # --------------------------------------------------
        # MUNICÍPIOS DISPONÍVEIS (Nome - UF)
        # --------------------------------------------------
        municipios_opcoes = sorted(
            [
                f"{m['nome_municipio']} - {sigla_por_codigo_uf.get(str(m['codigo_municipio'])[:2], '')}"
                for m in lista_municipios
            ],
            key=lambda x: x.lower()
        )

        # --------------------------------------------------
        # CAMPOS BÁSICOS
        # --------------------------------------------------
        nome_localidade = st.text_input(
            "Nome da localidade ou comunidade",
            placeholder="Ex: Comunidade Novo Horizonte"
        )

        municipio = st.selectbox(
            "Município",
            options=municipios_opcoes,
            index=None,
            placeholder="Selecione o município"
        )

        st.write("")

        # --------------------------------------------------
        # ESCOLHA DO MODO DE COORDENADAS
        # --------------------------------------------------
        modo_coordenadas = st.radio(
            "Escolha uma opção",
            ["Link do Google Maps", "Latitude e Longitude"],
            horizontal=True
        )

        latitude = None
        longitude = None

        # --------------------------------------------------
        # OPÇÃO 1 — LINK GOOGLE MAPS
        # --------------------------------------------------
        if modo_coordenadas == "Link do Google Maps":

            link_maps = st.text_input(
                "Link do Google Maps",
                placeholder="Ex: https://www.google.com/maps/@-13.7975,-47.4589,15z"
            )

            if link_maps:
                lat_tmp, lon_tmp = extrair_lat_long_google_maps(link_maps)

                if lat_tmp and lon_tmp:
                    latitude = lat_tmp
                    longitude = lon_tmp
                else:
                    st.warning("Não foi possível extrair latitude e longitude do link.")

        # --------------------------------------------------
        # OPÇÃO 2 — LATITUDE / LONGITUDE MANUAL
        # --------------------------------------------------
        else:
            col1, col2 = st.columns(2)

            latitude = col1.text_input(
                "Latitude",
                placeholder="-13.797500"
            )

            longitude = col2.text_input(
                "Longitude",
                placeholder="-47.458900"
            )

        st.write("")

        # --------------------------------------------------
        # BOTÃO SALVAR
        # --------------------------------------------------
        if st.button(
            "Salvar",
            icon=":material/save:",
            key="salvar_localidade_dialogo"
        ):

            # -----------------------------
            # VALIDAÇÕES
            # -----------------------------
            if not nome_localidade.strip():
                st.error("Informe o nome da localidade.")
                return

            if not municipio:
                st.error("Selecione o município.")
                return

            try:
                lat = float(latitude)
                lon = float(longitude)
            except (TypeError, ValueError):
                st.error("Latitude e longitude inválidas.")
                return

            if not (-90 <= lat <= 90):
                st.error("Latitude deve estar entre -90 e 90.")
                return

            if not (-180 <= lon <= 180):
                st.error("Longitude deve estar entre -180 e 180.")
                return

            nova_localidade = {
                "nome_localidade": nome_localidade.strip(),
                "municipio": municipio,
                "latitude": lat,
                "longitude": lon
            }

            localidades_atual = locais.get("localidades", [])
            localidades_atual.append(nova_localidade)

            col_projetos.update_one(
                {"codigo": codigo_projeto_atual},
                {
                    "$set": {
                        "locais.localidades": localidades_atual
                    }
                }
            )

            st.success("Localidade / Comunidade cadastrada com sucesso!", icon=":material/check:")
            time.sleep(2)
            st.rerun()

    # =============================================================================
    # ABA — EXCLUIR
    # =============================================================================
    with abas[1]:

        localidades_cadastradas = locais.get("localidades", [])

        if not localidades_cadastradas:
            st.info("Não há localidades cadastradas.")
            return

        nomes_localidades = sorted(
            [l["nome_localidade"] for l in localidades_cadastradas],
            key=lambda x: x.lower()
        )

        localidade_para_excluir = st.selectbox(
            "Selecione a localidade",
            options=nomes_localidades,
            index=None,
            placeholder="Escolha uma localidade"
        )

        st.write("")

        if st.button(
            "Excluir",
            icon=":material/delete:",
            type="secondary",
            key="excluir_localidade_dialogo"
        ):

            if not localidade_para_excluir:
                st.error("Selecione uma localidade para excluir.")
                return

            novas_localidades = [
                l for l in localidades_cadastradas
                if l.get("nome_localidade") != localidade_para_excluir
            ]

            col_projetos.update_one(
                {"codigo": codigo_projeto_atual},
                {
                    "$set": {
                        "locais.localidades": novas_localidades
                    }
                }
            )

            st.success("Localidade excluída com sucesso!", icon=":material/check:")
            time.sleep(3)
            st.rerun()



@st.dialog("Áreas Protegidas", width="medium")
def dialog_editar_areas_protegidas():

    st.write("")

    abas = st.tabs(["Cadastrar", "Excluir"])

    # =============================================================================
    # ABA — CADASTRAR
    # =============================================================================
    with abas[0]:

        # --------------------------------------------------
        # MUNICÍPIOS DISPONÍVEIS (Nome - UF)
        # --------------------------------------------------
        municipios_opcoes = sorted(
            [
                f"{m['nome_municipio']} - {sigla_por_codigo_uf.get(str(m['codigo_municipio'])[:2], '')}"
                for m in lista_municipios
            ],
            key=lambda x: x.lower()
        )

        nome_area_protegida = st.text_input(
            "Nome da área protegida",
            placeholder="Ex: Parque Nacional da Chapada dos Veadeiros"
        )

        municipios_selecionados = st.multiselect(
            "Municípios",
            options=municipios_opcoes,
            placeholder="Selecione os municípios"
        )

        gerente_area_protegida = st.text_input(
            "Autoridade, gerente ou proprietário",
            placeholder="Ex: ICMBio / Secretaria Estadual / Associação Local"
        )

        st.write("")

        if st.button(
            "Salvar",
            icon=":material/save:",
            key="salvar_area_protegida"
        ):

            # -----------------------------
            # VALIDAÇÕES
            # -----------------------------
            if not nome_area_protegida.strip():
                st.error("Informe o nome da área protegida.")
                return

            if not municipios_selecionados:
                st.error("Selecione ao menos um município.")
                return

            if not gerente_area_protegida.strip():
                st.error("Informe o responsável pela área protegida.")
                return

            nova_area = {
                "nome_area_protegida": nome_area_protegida.strip(),
                "municipios": municipios_selecionados,
                "gerente_area_protegida": gerente_area_protegida.strip()
            }

            areas_atual = locais.get("areas_protegidas", [])
            areas_atual.append(nova_area)

            col_projetos.update_one(
                {"codigo": codigo_projeto_atual},
                {
                    "$set": {
                        "locais.areas_protegidas": areas_atual
                    }
                }
            )

            st.success("Área protegida cadastrada com sucesso!", icon=":material/check:")
            time.sleep(2)
            st.rerun()

    # =============================================================================
    # ABA — EXCLUIR
    # =============================================================================
    with abas[1]:

        areas_cadastradas = locais.get("areas_protegidas", [])

        if not areas_cadastradas:
            st.info("Não há áreas protegidas cadastradas.")
            return

        nomes_areas = sorted(
            [a["nome_area_protegida"] for a in areas_cadastradas],
            key=lambda x: x.lower()
        )

        area_para_excluir = st.selectbox(
            "Selecione a área protegida",
            options=nomes_areas,
            index=None,
            placeholder="Escolha uma área"
        )

        st.write("")

        if st.button(
            "Excluir",
            icon=":material/delete:",
            type="secondary",
            key="excluir_area_protegida"
        ):

            if not area_para_excluir:
                st.error("Selecione uma área protegida para excluir.")
                return

            novas_areas = [
                a for a in areas_cadastradas
                if a.get("nome_area_protegida") != area_para_excluir
            ]

            col_projetos.update_one(
                {"codigo": codigo_projeto_atual},
                {
                    "$set": {
                        "locais.areas_protegidas": novas_areas
                    }
                }
            )

            st.success("Área protegida excluída com sucesso!", icon=":material/check:")
            time.sleep(3)
            st.rerun()



@st.dialog("Editar Corredores Prioritários de Conservação", width="medium")
def dialog_editar_corredores():

    st.write("")

    # --------------------------------------------------
    # NOMES DISPONÍVEIS
    # --------------------------------------------------
    nomes_corredores = [
        c["nome_corredor"]
        for c in lista_corredores
    ]

    nomes_corredores = sorted(
        nomes_corredores,
        key=lambda x: x.lower()
    )

    corredores_default = [
        c["nome_corredor"]
        for c in locais.get("corredores", [])
        if c.get("nome_corredor") in nomes_corredores
    ]

    corredores_selecionados = st.multiselect(
        "Selecione os corredores prioritários de conservação",
        options=nomes_corredores,
        default=corredores_default,
        placeholder="Selecione os corredores"
    )

    st.write("")

    # --------------------------------------------------
    # SALVAR
    # --------------------------------------------------
    if st.button(
        "Salvar",
        icon=":material/save:",
        key="salvar_corredores_dialogo"
    ):

        corredores_para_salvar = [
            {
                "id_corredor": c["id_corredor"],
                "nome_corredor": c["nome_corredor"]
            }
            for c in lista_corredores
            if c["nome_corredor"] in corredores_selecionados
        ]

        col_projetos.update_one(
            {"codigo": codigo_projeto_atual},
            {
                "$set": {
                    "locais.corredores": corredores_para_salvar
                }
            }
        )

        st.success("Corredores atualizados com sucesso!", icon=":material/check:")
        time.sleep(3)
        st.rerun()



@st.dialog("Editar KBAs", width="medium")
def dialog_editar_kbas():

    st.write("")

    # --------------------------------------------------
    # NOMES DE KBAs DISPONÍVEIS
    # --------------------------------------------------
    nomes_kbas = sorted(
        [kba["nome_kba"] for kba in lista_kbas],
        key=lambda x: x.lower()
    )

    kbas_default = [
        kba["nome_kba"]
        for kba in locais.get("kbas", [])
        if kba.get("nome_kba") in nomes_kbas
    ]

    kbas_selecionadas = st.multiselect(
        "Selecione as KBAs associadas ao projeto",
        options=nomes_kbas,
        default=kbas_default,
        placeholder="Selecione as KBAs"
    )

    st.write("")

    # --------------------------------------------------
    # SALVAR
    # --------------------------------------------------
    if st.button(
        "Salvar",
        icon=":material/save:",
        key="salvar_kbas_dialogo"
    ):

        kbas_para_salvar = [
            {
                "id_kba": kba["id_kba"],
                "nome_kba": kba["nome_kba"]
            }
            for kba in lista_kbas
            if kba["nome_kba"] in kbas_selecionadas
        ]

        col_projetos.update_one(
            {"codigo": codigo_projeto_atual},
            {
                "$set": {
                    "locais.kbas": kbas_para_salvar
                }
            }
        )

        st.success("KBAs atualizadas com sucesso!", icon=":material/check:")
        time.sleep(3)
        st.rerun()





@st.dialog("Mapas do Projeto", width="large")
def dialog_mapas():

    abas = st.tabs(
        [":material/add: Adicionar mapas", ":material/delete: Remover mapas"]
    )

    # =========================================================
    # ABA — ADICIONAR MAPAS
    # =========================================================
    with abas[0]:
        st.write('')
        st.write('**Selecione os arquivos de mapa**')

        arquivos = st.file_uploader(
            "Tamanho máximo: 25MB. Formatos de arquivo aceitos: jpg, png, pdf, jpeg, webp, docx",
            accept_multiple_files=True,
            type=["jpg", "png", "pdf", "jpeg", "webp", "docx"]
        )

        if arquivos and st.button(":material/save: Enviar arquivos"):

            # Spinner exibido enquanto os arquivos são enviados
            with st.spinner("Enviando arquivos..."):
                
                # Conecta ao Google Drive SOMENTE quando necessário
                servico = obter_servico_drive()

                # Obtém ou reutiliza a pasta do projeto
                pasta_projeto = obter_pasta_projeto(
                    servico,
                    projeto["codigo"],
                    projeto["sigla"]
                )

                # Obtém ou cria a pasta "Locais"
                pasta_locais = obter_pasta_locais(
                    servico,
                    pasta_projeto
                )

                novos = []

                # Loop de upload dos arquivos
                for arq in arquivos:
                    id_drive = enviar_arquivo_drive(
                        servico,
                        pasta_locais,
                        arq
                    )

                    novos.append({
                        "nome": arq.name,
                        "url": gerar_link_drive(id_drive)
                    })

                # Salva os links no MongoDB
                col_projetos.update_one(
                    {"codigo": codigo_projeto_atual},
                    {"$push": {"locais.arquivos": {"$each": novos}}}
                )

            # Mensagem exibida após o spinner finalizar
            st.success("Arquivos cadastrados com sucesso!", icon=":material/check:")
            time.sleep(3)
            st.rerun()

    # =========================================================
    # ABA — REMOVER MAPAS
    # =========================================================
    with abas[1]:

        arquivos_bd = locais.get("arquivos", [])

        if not arquivos_bd:
            st.info("Nenhum mapa cadastrado.")
            return

        # Lista apenas os nomes dos mapas
        nomes_mapas = sorted(
            [a["nome"] for a in arquivos_bd],
            key=lambda x: x.lower()
        )

        mapa_selecionado = st.selectbox(
            "Selecione o mapa para remover",
            options=nomes_mapas,
            index=None,
            placeholder="Escolha um mapa"
        )

        st.write("")

        if st.button(
            "Remover arquivo",
            icon=":material/delete:",
        ):

            if not mapa_selecionado:
                st.error("Selecione um mapa para remover.")
                return

            # Spinner para a remoção (mesmo sendo rápida)
            with st.spinner("Removendo mapa..."):
                col_projetos.update_one(
                    {"codigo": codigo_projeto_atual},
                    {
                        "$pull": {
                            "locais.arquivos": {
                                "nome": mapa_selecionado
                            }
                        }
                    }
                )

            st.success("Arquivo removido com sucesso!", icon=":material/check:")
            time.sleep(3)
            st.rerun()









###########################################################################################################
# INTERFACE PRINCIPAL DA PÁGINA
###########################################################################################################



# Logo do sidebar
st.logo("images/ieb_logo.svg", size='large')

# Título da página e identificação
col_titulo, col_identificacao = st.columns([3, 2])

with col_titulo:
    st.header("Locais")

with col_identificacao:
    st.markdown(
        f"<div style='text-align: right; margin-top: 30px;'>{df_projeto['codigo'].values[0]} - {df_projeto['sigla'].values[0]}</div>",
        unsafe_allow_html=True
    )


st.write('')


aba_cadastro, aba_mapas = st.tabs(
    ["Cadastro", "Mapa"]
)


with aba_cadastro:

    st.write('')

    # Colunas para Estados e Municípios
    col_estados, col_municipios = st.columns(2)

    # -------------------------------------------------------------------------------
    # SEÇÃO — ESTADOS
    # -------------------------------------------------------------------------------
    with col_estados.container(border=True):


        col_botao, col_titulo = st.columns([1, 30])

        with col_botao:

            if st.button(
                "",
                icon=":material/edit:",
                key="editar_estados",
                type="tertiary"
            ):
                dialog_editar_estados()

        with col_titulo:


            st.markdown("#### Estados")

            # --------------------------------------------------
            # TABELA DE ESTADOS CADASTRADOS
            # --------------------------------------------------
            estados_cadastrados = locais.get("estados", [])

            if not estados_cadastrados:
                st.caption("Nenhum estado cadastrado para este projeto.")
            else:
                df_estados = pd.DataFrame(estados_cadastrados)

                for estado in df_estados["nome_estado"].sort_values():
                    st.write(f"{estado}")



    # -------------------------------------------------------------------------------
    # SEÇÃO — MUNICÍPIOS
    # -------------------------------------------------------------------------------

    with col_municipios.container(border=True):

        col_botao, col_titulo = st.columns([1, 30])

        with col_botao:
            if st.button(
                "",
                icon=":material/edit:",
                key="editar_municipios",
                type="tertiary"
            ):
                dialog_editar_municipios()

        with col_titulo:
            st.markdown("#### Municípios")

            municipios_cadastrados = locais.get("municipios", [])

            if not municipios_cadastrados:
                st.caption("Nenhum município cadastrado para este projeto.")
            else:
                for municipio in sorted(
                    [m["nome_municipio"] for m in municipios_cadastrados],
                    key=lambda x: x.lower()
                ):
                    st.write(municipio)





    # Colunas para Localidades e Áreas Protegidas
    col_localidade, col_area_protegida = st.columns(2)

    # -------------------------------------------------------------------------------
    # SEÇÃO — LOCALIDADES
    # -------------------------------------------------------------------------------

    with col_localidade.container(border=True):

        col_botao, col_titulo = st.columns([1, 30])

        with col_botao:
            if st.button(
                "",
                icon=":material/edit:",
                key="editar_localidades",
                type="tertiary"
            ):
                dialog_editar_localidades()

        with col_titulo:
            st.markdown("#### Localidades e Comunidades")

            localidades_cadastradas = locais.get("localidades", [])

            if not localidades_cadastradas:
                st.caption("Nenhuma localidade cadastrada para este projeto.")
            else:
                for loc in sorted(
                    localidades_cadastradas,
                    key=lambda x: x.get("nome_localidade", "").lower()
                ):
                    st.write(
                        f"**{loc.get('nome_localidade')}** - {loc.get('municipio')}"
                    )




    # -------------------------------------------------------------------------------
    # SEÇÃO - ÁREAS PROTEGIDAS
    # -------------------------------------------------------------------------------

    with col_area_protegida.container(border=True):

        col_botao, col_titulo = st.columns([1, 30])

        with col_botao:
            if st.button(
                "",
                icon=":material/edit:",
                key="editar_areas_protegidas",
                type="tertiary"
            ):
                dialog_editar_areas_protegidas()

        with col_titulo:
            st.markdown("#### Áreas protegidas")

            areas_cadastradas = locais.get("areas_protegidas", [])

            if not areas_cadastradas:
                st.caption("Nenhuma área protegida cadastrada para este projeto.")
            else:
                for area in sorted(
                    areas_cadastradas,
                    key=lambda x: x.get("nome_area_protegida", "").lower()
                ):
                    st.write(f"**{area.get('nome_area_protegida')}** - {', '.join(area.get('municipios', []))}")
                    st.caption(
                        f"Responsável: {area.get('gerente_area_protegida')}"
                    )





    # Colunas para Corredores e KBAs
    col_corredores, col_kbas = st.columns(2)


    # -------------------------------------------------------------------------------
    # SEÇÃO — CORREDORES
    # -------------------------------------------------------------------------------
    with col_corredores.container(border=True):

        col_botao, col_titulo = st.columns([1, 30])

        with col_botao:
            if st.button(
                "",
                icon=":material/edit:",
                key="editar_corredores",
                type="tertiary"
            ):
                dialog_editar_corredores()

        with col_titulo:
            st.markdown("#### Corredores Prioritários de Conservação")

            corredores_cadastrados = locais.get("corredores", [])

            if not corredores_cadastrados:
                st.caption("Nenhum corredor cadastrado para este projeto.")
            else:
                for corredor in sorted(
                    corredores_cadastrados,
                    key=lambda x: x.get("nome_corredor", "").lower()
                ):
                    st.write(corredor.get("nome_corredor", ""))


    # -------------------------------------------------------------------------------
    # SEÇÃO — KBAs
    # -------------------------------------------------------------------------------
    with col_kbas.container(border=True):

        col_botao, col_titulo = st.columns([1, 30])

        with col_botao:
            if st.button(
                "",
                icon=":material/edit:",
                key="editar_kbas",
                type="tertiary"
            ):
                dialog_editar_kbas()

        with col_titulo:
            st.markdown("#### KBAs (Áreas Chave de Biodiversidade)")

            kbas_cadastradas = locais.get("kbas", [])

            if not kbas_cadastradas:
                st.caption("Nenhuma KBA cadastrada para este projeto.")
            else:
                for kba in sorted(
                    kbas_cadastradas,
                    key=lambda x: x.get("nome_kba", "").lower()
                ):
                    st.write(kba.get("nome_kba", ""))


    # -------------------------------------------------------------------------------
    # SEÇÃO — MAPAS
    # -------------------------------------------------------------------------------
    with st.container(border=True):

        col_btn, col_title = st.columns([1, 30])

        with col_btn:
            if st.button("", icon=":material/edit:", type="tertiary"):
                dialog_mapas()

        with col_title:
            st.markdown("#### Mapas")

            arquivos = locais.get("arquivos", [])

            if not arquivos:
                st.caption("Nenhum mapa cadastrado para este projeto.")
            else:
                for arq in arquivos:
                    st.markdown(f"[{arq['nome']}]({arq['url']})")





# ABAS - MAPAS
with aba_mapas:
    st.write('')

    st.write("**Mapa de Localidades e Comunidades**")

    # Garantir que há dados
    if df_projeto.empty:
        st.info("Nenhum dado de projeto disponível.")

    else:
        projeto = df_projeto.iloc[0]

        locais = projeto.get("locais", {})
        localidades = locais.get("localidades", [])

        pontos_mapa = []

        for local in localidades:
            lat = local.get("latitude")
            lon = local.get("longitude")

            if lat is None or lon is None:
                continue

            pontos_mapa.append({
                "codigo": projeto.get("codigo"),
                "sigla": projeto.get("sigla"),
                "nome_projeto": projeto.get("nome_do_projeto"),
                "organizacao": projeto.get("organizacao"),
                "municipio": local.get("municipio"),
                "localidade": local.get("nome_localidade"),
                "latitude": lat,
                "longitude": lon
            })

        if not pontos_mapa:
            st.info("Este projeto não possui localidades com coordenadas cadastradas.")
        else:
            df_mapa = pd.DataFrame(pontos_mapa)

            # Centraliza o mapa
            centro_lat = df_mapa["latitude"].mean()
            centro_lon = df_mapa["longitude"].mean()

            mapa = folium.Map(
                location=[centro_lat, centro_lon],
                zoom_start=6,
                tiles="OpenStreetMap"
            )

            # Adiciona os marcadores
            for _, row in df_mapa.iterrows():

                popup_html = f"""
                <div style="width:300px">
                    <b>Organização:</b> {row['organizacao']}<br>
                    <b>Sigla:</b> {row['sigla']}<br>
                    <b>Código:</b> {row['codigo']}<br>
                    <b>Projeto:</b> {row['nome_projeto']}<br>
                    <b>Município:</b> {row['municipio']}<br>
                    <b>Localidade:</b> {row['localidade']}
                </div>
                """

                folium.Marker(
                    location=[row["latitude"], row["longitude"]],
                    popup=folium.Popup(popup_html, max_width=500),
                    icon=folium.Icon(
                        color="red",
                        prefix="fa"
                    ),
                ).add_to(mapa)

            # Renderiza o mapa ocupando toda a largura
            st_folium(mapa, width="100%", height=600)





# ###################################################################################################
# SIDEBAR DA PÁGINA DO PROJETO
# ###################################################################################################

sidebar_projeto()