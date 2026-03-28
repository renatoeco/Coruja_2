import streamlit as st
from funcoes_auxiliares import conectar_mongo_cepf_gestao, calcular_status_projetos  # Função personalizada para conectar ao MongoDB
import pandas as pd
import io
import datetime
import time


st.set_page_config(page_title="Relatórios", page_icon=":material/assignment:")




###########################################################################################################
# CONEXÃO COM O BANCO DE DADOS MONGODB E CARREGAMENTO DE DADOS
###########################################################################################################

# Conecta-se ao banco de dados MongoDB (usa cache automático para melhorar performance)
db = conectar_mongo_cepf_gestao()









# Carregamento de várias coleções cacheadas
@st.cache_data(ttl=600)  # 10 minutos
def carregar_dados_base():

    return {
        "publicos": list(db["publicos"].find()),
        "beneficios": list(db["beneficios"].find()),
        "categorias_despesa": list(db["categorias_despesa"].find()),
        "corredores": list(db["corredores"].find()),
        "kbas": list(db["kbas"].find()),
        "editais": list(db["editais"].find()),
        "ciclos": list(db["ciclos_investimento"].find()),
        "organizacoes": list(db["organizacoes"].find())
    }



dados_base = carregar_dados_base()

editais = dados_base["editais"]
ciclos = dados_base["ciclos"]
organizacoes = dados_base["organizacoes"]










###########################################################################################################
# FUNÇÕES
###########################################################################################################



# FUNÇÃO DE FILTRO DE EDITAIS

def filtro_editais():
    """
    Cria um selectbox para escolha de edital e retorna os projetos filtrados.
    """

    #######################################################################################################
    # FUNÇÃO INTERNA PARA MONTAR O LABEL DO SELECTBOX
    #######################################################################################################
    def montar_label_edital(edital):
        """
        Monta o texto exibido no selectbox combinando:
        codigo_edital | nome_edital | doadores | investidores | nome_ciclo
        """

        # Código e nome do edital
        codigo = edital.get("codigo_edital", "")
        nome = edital.get("nome_edital", "")

        # Código do ciclo associado ao edital
        codigo_ciclo = edital.get("ciclo_investimento")

        # Busca os dados do ciclo no mapa previamente carregado
        ciclo = mapa_ciclos.get(codigo_ciclo, {})

        # Listas de doadores e investidores
        doadores = ciclo.get("doadores", [])
        investidores = ciclo.get("investidores", [])

        # Nome do ciclo
        nome_ciclo = ciclo.get("nome_ciclo", "")

        # Converte listas em string separada por vírgula
        doadores_str = ", ".join(doadores) if doadores else ""
        investidores_str = ", ".join(investidores) if investidores else ""

        # Monta as partes do label
        partes = [codigo, nome]

        if doadores_str:
            partes.append(doadores_str)

        if investidores_str:
            partes.append(investidores_str)

        if nome_ciclo:
            partes.append(nome_ciclo)

        # Junta tudo com separador
        return " | ".join(partes)


    #######################################################################################################
    # SELECTBOX DE ESCOLHA DO EDITAL
    #######################################################################################################
    edital_selecionado_obj = st.selectbox(
        "Selecione o edital",
        options=[None] + editais,
        format_func=lambda x: "Selecione..." if x is None else montar_label_edital(x)
    )


    #######################################################################################################
    # EXTRAÇÃO DO CÓDIGO DO EDITAL
    #######################################################################################################
    codigo_edital = None

    if edital_selecionado_obj:
        codigo_edital = edital_selecionado_obj.get("codigo_edital")


    #######################################################################################################
    # BUSCA DOS PROJETOS FILTRADOS
    #######################################################################################################
    # Caso nenhum edital seja selecionado, retorna lista vazia
    if not codigo_edital:
        return [], None

    # Consulta projetos vinculados ao edital selecionado
    projetos = list(db["projetos"].find({
        "edital": codigo_edital
    }))


    #######################################################################################################
    # RETORNO DOS PROJETOS FILTRADOS
    #######################################################################################################
    return projetos, edital_selecionado_obj








###########################################################################################################
# TRATAMENTO DE DADOS
###########################################################################################################


# Mapa de ciclos de editais, pra ajudar no join de edital com ciclos_investimento, usado no selectbox do filtro
# que tem concatenado "nome_edital | doadores | investidores | nome_ciclo" 
mapa_ciclos = {
    c.get("codigo_ciclo"): c
    for c in ciclos
}


###########################################################################################################
# MAPA COMPLETO DE ORGANIZAÇÕES (NOME + SIGLA)
###########################################################################################################
mapa_organizacoes = {
    str(org.get("_id")): {
        "nome": org.get("nome_organizacao", ""),
        "sigla": org.get("sigla_organizacao", "")
    }
    for org in organizacoes
}









###########################################################################################################
# INTERFACE
###########################################################################################################


# Logo do sidebar
st.logo("images/ieb_logo.svg", size='large')

st.header('Relatórios')

st.write('')








###########################################################################################################
# ESCOLHA DO RELATÓRIO
###########################################################################################################


opcao_relatorio = st.radio(
    "Selecione o relatório que deseja gerar:",
    [
        "Relatório de salvaguardas",
        "Relatório de acompanhamento de desembolsos",
        "Relatório de acompanhamento de desembolsos por parcela",
        "Relatório de acompanhamento completo"
    ]
)

st.divider()














###########################################################################################################
# RELATÓRIO DE SALVAGUARDAS
###########################################################################################################

# Inicializa session_state
if "arquivo_salvaguardas" not in st.session_state:
    st.session_state.arquivo_salvaguardas = None



if opcao_relatorio == "Relatório de salvaguardas":

    st.subheader("Relatório de salvaguardas")

    # Filtro de editais
    # projetos = filtro_editais()
    projetos, edital_selecionado_obj = filtro_editais()

    st.write(f"{len(projetos)} projetos")

    st.write('')

    #######################################################################################################
    # BOTÕES (EM CONTAINER HORIZONTAL)
    #######################################################################################################
    with st.container(horizontal=True):

        ###################################################################################################
        # BOTÃO GERAR
        ###################################################################################################
        if st.button("Gerar relatório", icon=":material/list_alt_add:"):

            ###################################################################################################
            # VALIDAÇÃO DE PROJETOS
            ###################################################################################################
            if not projetos:
                st.warning("Nenhum projeto encontrado para o edital selecionado.", icon=":material/warning:")
                st.session_state.arquivo_salvaguardas = None
                time.sleep(3)

            else:

                with st.spinner("Gerando relatório..."):

                    ###################################################################################################
                    # MONTAGEM DOS DADOS DO RELATÓRIO
                    ###################################################################################################
                    dados = []

                    for p in projetos:

                        # Recupera o id da organização
                        id_org = p.get("id_organizacao")

                        # Busca nome no mapa (já cacheado)
                        nome_org = mapa_organizacoes.get(str(id_org), "") if id_org else ""


                        # Recupera dados de salvaguardas
                        salvaguardas = p.get("salvaguardas", {})

                        # POLÍTICA 2
                        pol2 = salvaguardas.get("pol_2_trabalho", {})
                        aplicavel2 = pol2.get("aplicavel", "")
                        detalhes2 = pol2.get("detalhes", "")
                        categoria2 = pol2.get("categoria", "")

                        # POLÍTICA 3
                        pol3 = salvaguardas.get("pol_3_poluicao", {})
                        aplicavel3 = pol3.get("aplicavel", "")
                        detalhes_pesticidas = pol3.get("detalhes_pesticidas", "")
                        detalhes_poluicao = pol3.get("detalhes_poluicao", "")
                        categoria3 = pol3.get("categoria", "")

                        # POLÍTICA 4
                        pol4 = salvaguardas.get("pol_4_comunidade", {})
                        aplicavel4 = pol4.get("aplicavel", "")
                        detalhes4 = pol4.get("detalhes", "")
                        categoria4 = pol4.get("categoria", "")

                        # POLÍTICA 5
                        pol5 = salvaguardas.get("pol_5_reassentamento", {})
                        aplicavel5 = pol5.get("aplicavel", "")
                        detalhes5 = pol5.get("detalhes", "")
                        categoria5 = pol5.get("categoria", "")

                        # POLÍTICA 6
                        pol6 = salvaguardas.get("pol_6_biodiversidade", {})
                        aplicavel6 = pol6.get("aplicavel", "")
                        detalhes6 = pol6.get("detalhes", "")
                        categoria6 = pol6.get("categoria", "")

                        # POLÍTICA 7
                        pol7 = salvaguardas.get("pol_7_indigenas", {})
                        aplicavel7 = pol7.get("aplicavel", "")
                        detalhes7 = pol7.get("detalhes", "")
                        categoria7 = pol7.get("categoria", "")

                        # POLÍTICA 8
                        pol8 = salvaguardas.get("pol_8_patrimonio", {})
                        aplicavel8 = pol8.get("aplicavel", "")
                        detalhes8 = pol8.get("detalhes", "")
                        categoria8 = pol8.get("categoria", "")

                        # POLÍTICA 9
                        pol9 = salvaguardas.get("pol_9_genero", {})
                        detalhes9 = pol9.get("detalhes", "")
                        categoria9 = pol9.get("categoria", "")

                        # CAMPOS GERAIS DE SALVAGUARDAS
                        categoria_geral_risco = salvaguardas.get("categoria_geral_risco", "")
                        fortalecimento_capacidades = salvaguardas.get("fortalecimento_capacidades", "")


                        # Criando as colunas na tabela
                        dados.append({
                            "Código do projeto": p.get("codigo"),
                            "Nome da organização": nome_org,
                            "Nome do projeto": p.get("nome_do_projeto"),

                            ###################################################################################################
                            # POLÍTICA 1
                            ###################################################################################################
                            "1. Avaliação Ambiental e Social": "",
                            "1. Aplicável?": "Sim",
                            "1. Avaliação de Risco": "N/A",
                            "1. Categoria de Risco": "N/A",

                            ###################################################################################################
                            # POLÍTICA 2
                            ###################################################################################################
                            "2. Condições de Trabalho e Trabalhistas": "",
                            "2. Aplicável?": aplicavel2,
                            "2. Avaliação de Risco": f"O projeto proposto apresenta riscos significativos em relação às condições de trabalho e trabalhistas?\nDetalhes: {detalhes2}" if detalhes2 else "",
                            "2. Categoria de Risco": categoria2,

                            ###################################################################################################
                            # POLÍTICA 3
                            ###################################################################################################
                            "3. Eficiência de Recursos e Prevenção de Poluição": "",
                            "3. Aplicável?": aplicavel3,
                            "3. Avaliação de Risco": (
                                f"O projeto proposto apresenta riscos significativos relacionados a pesticidas?\n"
                                f"Detalhes: {detalhes_pesticidas}\n\n"
                                f"O projeto proposto apresenta riscos significativos relacionados ao uso insustentável de recursos e/ou formas de poluição que não sejam pesticidas?\n"
                                f"Detalhes: {detalhes_poluicao}"
                                if detalhes_pesticidas or detalhes_poluicao else ""
                            ),
                            "3. Categoria de Risco": categoria3,

                            ###################################################################################################
                            # POLÍTICA 4
                            ###################################################################################################
                            "4. Saúde, Segurança e Proteção da Comunidade": "",
                            "4. Aplicável?": aplicavel4,
                            "4. Avaliação de Risco": f"O projeto proposto apresenta riscos significativos relacionados à saúde, segurança e proteção da comunidade?\nDetalhes: {detalhes4}" if detalhes4 else "",
                            "4. Categoria de Risco": categoria4,

                            ###################################################################################################
                            # POLÍTICA 5
                            ###################################################################################################
                            "5. Restrições de Uso da Terra e Reassentamento Involuntário": "",
                            "5. Aplicável?": aplicavel5,
                            "5. Avaliação de Risco": f"O projeto proposto apresenta riscos significativos relacionados a restrições de acesso associadas a impactos negativos nos meios de subsistência?\nDetalhes: {detalhes5}" if detalhes5 else "",
                            "5. Categoria de Risco": categoria5,

                            ###################################################################################################
                            # POLÍTICA 6
                            ###################################################################################################
                            "6. Conservação da Biodiversidade e Gestão Sustentável de Recursos Naturais Vivos": "",
                            "6. Aplicável?": aplicavel6,
                            "6. Avaliação de Risco": f"O projeto proposto apresenta riscos significativos relacionados à degradação ou perda de habitat crítico ou outros habitats naturais?\nDetalhes: {detalhes6}" if detalhes6 else "",
                            "6. Categoria de Risco": categoria6,

                            ###################################################################################################
                            # POLÍTICA 7
                            ###################################################################################################
                            "7. Povos Indígenas": "",
                            "7. Aplicável?": aplicavel7,
                            "7. Avaliação de Risco": f"O projeto proposto apresenta riscos significativos relacionados aos impactos sobre Povos Indígenas?\nDetalhes: {detalhes7}" if detalhes7 else "",
                            "7. Categoria de Risco": categoria7,                        

                            ###################################################################################################
                            # POLÍTICA 8
                            ###################################################################################################
                            "8. Patrimônio Cultural": "",
                            "8. Aplicável?": aplicavel8,
                            "8. Avaliação de Risco": f"O projeto proposto apresenta riscos significativos relacionados aos impactos sobre o patrimônio cultural tangível e/ou intangível?\nDetalhes: {detalhes8}" if detalhes8 else "",
                            "8. Categoria de Risco": categoria8,

                            ###################################################################################################
                            # POLÍTICA 9
                            ###################################################################################################
                            "9. Igualdade de Gênero": "",
                            "9. Aplicável?": "Sim",
                            "9. Avaliação de Risco": f"O projeto proposto apresenta riscos significativos relacionados a impactos na promoção, proteção e respeito à igualdade de gênero?\nDetalhes: {detalhes9}" if detalhes9 else "",
                            "9. Categoria de Risco": categoria9,

                            ###################################################################################################
                            # POLÍTICA 10
                            ###################################################################################################
                            "10. Engajamento de Partes Interessadas": "",
                            "10. Aplicável?": "Sim",
                            "10. Avaliação de Risco": "N/A",
                            "10. Categoria de Risco": "N/A",

                            ###################################################################################################
                            # CAMPOS FINAIS
                            ###################################################################################################
                            "CATEGORIA GERAL DE RISCO": categoria_geral_risco,
                            "FORTALECIMENTO DE CAPACIDADE": fortalecimento_capacidades,

                        })



                    ###################################################################################################
                    # CRIAÇÃO DO EXCEL
                    ###################################################################################################
                    df = pd.DataFrame(dados)

                    buffer = io.BytesIO()

                    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                        df.to_excel(writer, index=False, sheet_name="Salvaguardas")

                    buffer.seek(0)

                    ###################################################################################################
                    # SALVAR NO SESSION STATE
                    ###################################################################################################
                    st.session_state.arquivo_salvaguardas = buffer

                    st.rerun()



        ###################################################################################################
        # BOTÃO DOWNLOAD
        ###################################################################################################


        if st.session_state.arquivo_salvaguardas:

            # Nome do edital (seguro para arquivo)
            nome_edital = edital_selecionado_obj.get("nome_edital", "") if edital_selecionado_obj else ""
            nome_edital_arquivo = nome_edital.replace(" ", "_")

            download_clicado = st.download_button(
                label="Baixar relatório",
                icon=":material/download:",
                data=st.session_state.arquivo_salvaguardas,
                file_name=f"Relatorio_de_salvaguardas_{nome_edital_arquivo}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            ###################################################################################################
            # SE CLICOU NO DOWNLOAD, LIMPA O ESTADO
            ###################################################################################################
            if download_clicado:
                st.session_state.arquivo_salvaguardas = None
                st.rerun()




    #######################################################################################################
    # MENSAGEM ABAIXO DOS BOTÕES
    #######################################################################################################
    if st.session_state.arquivo_salvaguardas:
        st.caption("Relatório gerado. Clique para baixar.")


















###########################################################################################################
# RELATÓRIO DE ACOMPANHAMENTO DE DESEMBOLSOS
###########################################################################################################

elif opcao_relatorio == "Relatório de acompanhamento de desembolsos":

    st.subheader("Relatório de acompanhamento de desembolsos")


    # Renderiza o filtro de editais 
    projetos, edital_selecionado_obj = filtro_editais()


    st.write(f"{len(projetos)} projetos")

    st.write('')
    st.write('')


    # Gerar lista de anos
    # EXTRAIR ANOS ÚNICOS DAS PARCELAS ############################################
    anos_set = set()

    for p in projetos:

        financeiro = p.get("financeiro", {})
        parcelas = financeiro.get("parcelas", [])

        for parcela in parcelas:

            data_realizada = parcela.get("data_realizada")

            if data_realizada:
                try:
                    ano = datetime.datetime.strptime(data_realizada, "%Y-%m-%d").year
                    anos_set.add(ano)
                except:
                    pass

    # ordenar anos
    anos = [""] + sorted(list(anos_set))

    # SELECTBOX DE ANO ############################################
    ano_selecionado = st.selectbox(
        "Selecione o ano",
        anos,
        width=250,
    )




    ###################################################################################################
    # INPUTS DE CÂMBIO POR MÊS (USANDO DATA_EDITOR)
    ###################################################################################################
    st.write('')

    st.markdown("##### Câmbio US\\$ por mês")

    # lista de meses completa
    meses_completos = [
        "Janeiro", "Fevereiro", "Março",
        "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro",
        "Outubro", "Novembro", "Dezembro"
    ]

    ###################################################################################################
    # CRIA DATAFRAME BASE (MESES FIXOS + COTAÇÃO VAZIA)
    ###################################################################################################
    df_cambio = pd.DataFrame({
        "Mês": meses_completos,
        "Cotação": [None] * 12  # inicia vazio
    })




    ###################################################################################################
    # DATA EDITOR
    ###################################################################################################
    df_editado = st.data_editor(
        df_cambio,
        width=400,  # define largura fixa de 400px
        height="content",
        hide_index=True,  # esconde o índice
        num_rows="fixed",  # não permite adicionar/remover linhas
        column_config={
            "Mês": st.column_config.TextColumn(
                "Mês",
                disabled=True  # usuário não pode alterar
            ),
            "Cotação": st.column_config.NumberColumn(
                "Cotação",
                min_value=0.0,
                step=0.01,
                format="%.2f"
            )
        },
        key="data_editor_cambio"
    )




    ###################################################################################################
    # CONVERTE PARA DICIONÁRIO
    ###################################################################################################
    cambio_meses = {
        row["Mês"]: (row["Cotação"] if pd.notna(row["Cotação"]) else 0)
        for _, row in df_editado.iterrows()
    }




    meses = [
        "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
        "Jul", "Ago", "Set", "Out", "Nov", "Dez"
    ]

    # session state
    if "relatorio_desembolsos_pronto" not in st.session_state:
        st.session_state.relatorio_desembolsos_pronto = False

    if "arquivo_desembolsos" not in st.session_state:
        st.session_state.arquivo_desembolsos = None





    ###################################################################################################
    # BOTÕES 
    ###################################################################################################
    st.write('')

    with st.container(horizontal=True):

        ###################################################################################################
        # BOTÃO GERAR
        ###################################################################################################
        if st.button("Gerar relatório", icon=":material/list_alt_add:"):


            ###################################################################################################
            # VALIDAÇÕES
            ###################################################################################################

            # valida ano
            if ano_selecionado == "":
                st.warning("Selecione um ano.")
                time.sleep(3)

            # valida câmbio (pelo menos um mês preenchido)
            elif not any(valor and valor > 0 for valor in cambio_meses.values()):
            # elif not any(valor > 0 for valor in cambio_meses.values()):
                st.warning("Informe a cotação de pelo menos um mês.")
                time.sleep(3)



            else:

                # Gerando relatório
                with st.spinner("Gerando relatório..."):



                    ###################################################################################################
                    # CALCULAR STATUS DOS PROJETOS
                    ###################################################################################################
                    df_projetos = pd.DataFrame(projetos)

                    df_projetos_status = calcular_status_projetos(df_projetos)

                    # cria mapa: codigo -> status
                    mapa_status = {
                        row["codigo"]: row.get("status")
                        for _, row in df_projetos_status.iterrows()
                    }





                    ###################################################################################################
                    # CRIAÇÃO DO EXCEL
                    ###################################################################################################
                    buffer = io.BytesIO()

                    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:

                        ###################################################################################################
                        # CRIA PLANILHA
                        ###################################################################################################
                        workbook = writer.book
                        worksheet = workbook.create_sheet(title="Desembolsos")

                        writer.sheets["Desembolsos"] = worksheet


                        ###################################################################################################
                        # TÍTULO DO CÂMBIO (LINHA 1)
                        ###################################################################################################
                        worksheet.cell(
                            row=1,
                            column=1,
                            value=f"Taxas de câmbio de {ano_selecionado}"
                        )


                        ###################################################################################################
                        # 1. ESCREVER CÂMBIO (A1:H3)
                        ###################################################################################################
                        meses_completos = [
                            "Janeiro", "Fevereiro", "Março",
                            "Abril", "Maio", "Junho",
                            "Julho", "Agosto", "Setembro",
                            "Outubro", "Novembro", "Dezembro"
                        ]

                        trimestres = [
                            meses_completos[0:3],
                            meses_completos[3:6],
                            meses_completos[6:9],
                            meses_completos[9:12]
                        ]

                        col_offset = 1

                        for trimestre in trimestres:

                            col_mes = col_offset
                            col_valor = col_offset + 1

                            for i, mes in enumerate(trimestre):

                                linha_excel = i + 2
                                # linha_excel = i + 1

                                worksheet.cell(row=linha_excel, column=col_mes, value=mes)
                                worksheet.cell(
                                    row=linha_excel,
                                    column=col_valor,
                                    value=cambio_meses.get(mes, "")
                                )

                            col_offset += 2

                        ###################################################################################################
                        # 2. ESCREVER CABEÇALHO (LINHA 5)
                        ###################################################################################################


                        # COLUNAS (COM R$ E US$)
                        colunas = [
                            "Código",
                            "Sigla",
                            "Valor do contrato (R$)",
                            "Valor do contrato (US$)",
                        ]

                        # colunas mensais
                        for mes in meses:
                            colunas.append(f"{mes} R$")
                            colunas.append(f"{mes} US$")

                        colunas.append("Já Pago")
                        colunas.append("Remanescente a receber")
                        colunas.append("Data de Encerramento")
                        colunas.append("Status do projeto")



                        for col_idx, col_nome in enumerate(colunas, start=1):
                            worksheet.cell(row=6, column=col_idx, value=col_nome)

                        ###################################################################################################
                        # 3. ESCREVER DADOS (A PARTIR DA LINHA 6)
                        ###################################################################################################
                        linha_excel = 7

                        for p in projetos:

                            financeiro = p.get("financeiro", {})
                            parcelas = financeiro.get("parcelas", [])

                            valor_total = financeiro.get("valor_total", 0)

                            linha = {
                                "Código": p.get("codigo"),
                                "Sigla": p.get("sigla"),
                                "Valor do contrato (R$)": valor_total,
                                "Valor do contrato (US$)": 0  # temporário (sem cotação global)
                            }



                            # inicializar meses
                            for mes in meses:
                                linha[f"{mes} R$"] = 0
                                linha[f"{mes} US$"] = ""

                            # inicializa já pago
                            ja_pago = 0

                            # preencher parcelas
                            for parcela in parcelas:

                                data_realizada = parcela.get("data_realizada")

                                if not data_realizada:
                                    continue

                                valor_parcela = parcela.get("valor", 0)

                                # soma no já pago (todas com data_realizada)
                                ja_pago += valor_parcela

                                data = datetime.datetime.strptime(data_realizada, "%Y-%m-%d")

                                if data.year == int(ano_selecionado):

                                    mes_nome = meses[data.month - 1]
                                    linha[f"{mes_nome} R$"] += valor_parcela


                            #  CALCULAR DATA DE ENCERRAMENTO
                            data_encerramento = ""

                            # verifica se existem parcelas
                            if parcelas:

                                # pega apenas parcelas com data_realizada
                                parcelas_com_data = [
                                    parcela for parcela in parcelas
                                    if parcela.get("data_realizada")
                                ]

                                # se TODAS têm data_realizada
                                if len(parcelas_com_data) == len(parcelas):

                                    # converte datas para datetime
                                    datas = [
                                        datetime.datetime.strptime(p["data_realizada"], "%Y-%m-%d")
                                        for p in parcelas_com_data
                                    ]

                                    # pega a mais recente
                                    ultima_data = max(datas)

                                    # formata
                                    data_encerramento = ultima_data.strftime("%d/%m/%Y")


                            ###################################################################################################
                            # STATUS DO PROJETO
                            ###################################################################################################
                            codigo_projeto = p.get("codigo")

                            status_projeto = mapa_status.get(codigo_projeto, "")

                            linha["Status do projeto"] = status_projeto





                            # preencher já pago e remanescente a receber
                            linha["Já Pago"] = ja_pago
                            linha["Remanescente a receber"] = ""  # será fórmula
                            linha["Data de Encerramento"] = data_encerramento
                            linha["Status do projeto"] = status_projeto


                            # escrever linha no excel
                            for col_idx, col_nome in enumerate(colunas, start=1):
                                
                                
                                valor = linha.get(col_nome, "")


                                # coluna "Remanescente a receber" -> fórmula
                                if col_nome == "Remanescente a receber":

                                    # coluna C = Valor do contrato (R$)
                                    celula_contrato = f"C{linha_excel}"

                                    # coluna AC = Já Pago
                                    celula_ja_pago = f"AC{linha_excel}"

                                    formula = f"={celula_contrato}-{celula_ja_pago}"

                                    worksheet.cell(
                                        row=linha_excel,
                                        column=col_idx,
                                        value=formula
                                    )

                                    continue


                                # se for coluna US$ (dos meses)
                                if "US$" in col_nome and "Valor do contrato" not in col_nome:

                                    mes = col_nome.split()[0]  # Jan, Fev...

                                    ###################################################################################################
                                    # MAPA DE CÂMBIO (ONDE ESTÃO AS CÉLULAS)
                                    ###################################################################################################
                                    mapa_cambio = {
                                        "Jan": "B2", "Fev": "B3", "Mar": "B4",
                                        "Abr": "D2", "Mai": "D3", "Jun": "D4",
                                        "Jul": "F2", "Ago": "F3", "Set": "F4",
                                        "Out": "H2", "Nov": "H3", "Dez": "H4"
                                    }

                                    # coluna do R$ (coluna anterior)
                                    col_rs_letra = worksheet.cell(row=6, column=col_idx - 1).column_letter

                                    # linha atual
                                    celula_rs = f"{col_rs_letra}{linha_excel}"
                                    celula_cambio = mapa_cambio.get(mes)

                                    formula = f'=IF({celula_rs}="","",{celula_rs}/{celula_cambio})'



                                    worksheet.cell(
                                        row=linha_excel,
                                        column=col_idx,
                                        value=formula
                                    )

                                else:

                                    ###################################################################################################
                                    # ESCREVER VALORES (SUBSTITUIR 0 POR VAZIO)
                                    ###################################################################################################
                                    if valor == 0:
                                        valor = ""

                                    worksheet.cell(
                                        row=linha_excel,
                                        column=col_idx,
                                        value=valor
                                    )


                            linha_excel += 1


                    buffer.seek(0)

                    st.session_state.arquivo_desembolsos = buffer

                    st.rerun()

        ###################################################################################################
        # BOTÃO DOWNLOAD
        ###################################################################################################
        if st.session_state.arquivo_desembolsos:

            # Nome do edital (seguro para arquivo)
            nome_edital = edital_selecionado_obj.get("nome_edital", "") if edital_selecionado_obj else ""
            nome_edital_arquivo = nome_edital.replace(" ", "_")

            download_clicado = st.download_button(
                label="Baixar relatório",
                icon=":material/download:",
                data=st.session_state.arquivo_desembolsos,
                file_name=f"Relatorio_acompanhamento_desembolsos_{nome_edital_arquivo}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            ###################################################################################################
            # SE CLICOU NO DOWNLOAD, LIMPA O ESTADO
            ###################################################################################################
            if download_clicado:
                st.session_state.arquivo_desembolsos = None
                st.rerun()



    ###################################################################################################
    # MENSAGEM ABAIXO DOS BOTÕES
    ###################################################################################################
    if st.session_state.arquivo_desembolsos:
        st.caption("Relatório gerado. Clique para baixar.")











elif opcao_relatorio == "Relatório de acompanhamento de desembolsos por parcela":
    
    st.subheader("Relatório de acompanhamento de desembolsos por parcela")

    
    # Renderiza o filtro de editais 
    # projetos = filtro_editais()
    projetos, edital_selecionado_obj = filtro_editais()


    st.write(f"{len(projetos)} projetos")

    st.write('')
    st.write('')











elif opcao_relatorio == "Relatório de acompanhamento completo":

    st.subheader("Relatório de acompanhamento completo")

    # Renderiza o filtro de editais 
    # projetos = filtro_editais()
    projetos, edital_selecionado_obj = filtro_editais()


    st.write(f"{len(projetos)} projetos")

    st.write('')
    st.write('')



    ###################################################################################################
    # SESSION STATE
    ###################################################################################################
    if "arquivo_acompanhamento_completo" not in st.session_state:
        st.session_state.arquivo_acompanhamento_completo = None


    ###################################################################################################
    # BOTÕES
    ###################################################################################################
    with st.container(horizontal=True):

        ###################################################################################################
        # BOTÃO GERAR RELATÓRIO
        ###################################################################################################
        if st.button("Gerar relatório", icon=":material/list_alt_add:"):

            ###################################################################################################
            # VALIDAÇÃO DE PROJETOS
            ###################################################################################################
            if not projetos:
                st.warning("Nenhum projeto encontrado para o edital selecionado.", icon=":material/warning:")
                st.session_state.arquivo_acompanhamento_completo = None
                time.sleep(3)

            else:

                with st.spinner("Gerando relatório..."):

                    ###################################################################################################
                    # MONTAGEM DOS DADOS
                    ###################################################################################################
                    dados = []


                    for p in projetos:

                        ###################################################################################################
                        # CONTRATO
                        ###################################################################################################
                        contrato_nome = p.get("contrato_nome", "")


                        ###################################################################################################
                        # DIREÇÕES ESTRATÉGICAS
                        ###################################################################################################
                        direcoes = p.get("direcoes_estrategicas", [])

                        lista_direcoes_formatadas = []

                        for direcao in direcoes:

                            tema = direcao.get("tema", "")
                            subcategorias = direcao.get("subcategorias", [])

                            subcategorias_limpo = [
                                sub.strip().replace("\n", " ")
                                for sub in subcategorias
                                if sub
                            ]

                            if subcategorias_limpo:
                                sub_str = ", ".join(subcategorias_limpo)
                                direcao_formatada = f"{tema} ({sub_str})"
                            else:
                                direcao_formatada = tema

                            lista_direcoes_formatadas.append(direcao_formatada)

                        direcoes_str = ", ".join(lista_direcoes_formatadas)


                        ###################################################################################################
                        # NOME DA PROPOSTA
                        ###################################################################################################
                        nome_projeto = p.get("nome_do_projeto", "")


                        ###################################################################################################
                        # ORGANIZAÇÃO (NOME + SIGLA)
                        ###################################################################################################
                        id_org = p.get("id_organizacao")

                        org_info = mapa_organizacoes.get(str(id_org), {}) if id_org else {}

                        nome_organizacao = org_info.get("nome", "")
                        sigla_organizacao = org_info.get("sigla", "")


                        ###################################################################################################
                        # UF (ESTADOS DO PROJETO)
                        ###################################################################################################
                        estados = p.get("locais", {}).get("estados", [])

                        nomes_estados = [
                            estado.get("nome_estado", "")
                            for estado in estados
                            if estado.get("nome_estado")
                        ]

                        uf_str = ", ".join(nomes_estados)




                        ###################################################################################################
                        # CONTATOS DO PROJETO
                        ###################################################################################################
                        contatos = p.get("contatos", [])


                        ###################################################################################################
                        # RESPONSÁVEIS LEGAIS (ASSINAM DOCUMENTOS)
                        ###################################################################################################
                        nomes_responsaveis = [
                            contato.get("nome", "")
                            for contato in contatos
                            if contato.get("assina_docs") is True and contato.get("nome")
                        ]

                        responsaveis_str = ", ".join(nomes_responsaveis)


                        ###################################################################################################
                        # E-MAIL RESPONSÁVEL LEGAL
                        ###################################################################################################
                        emails_responsaveis = [
                            contato.get("email", "")
                            for contato in contatos
                            if contato.get("assina_docs") is True and contato.get("email")
                        ]

                        emails_responsaveis_str = "; ".join(emails_responsaveis)


                        ###################################################################################################
                        # E-MAILS DA EQUIPE (TODOS OS CONTATOS)
                        ###################################################################################################
                        emails_equipe = [
                            contato.get("email", "")
                            for contato in contatos
                            if contato.get("email")
                        ]

                        emails_equipe_str = "; ".join(emails_equipe)


                        ###################################################################################################
                        # TELEFONES (TODOS OS CONTATOS)
                        ###################################################################################################
                        telefones = [
                            contato.get("telefone", "")
                            for contato in contatos
                            if contato.get("telefone")
                        ]

                        telefones_str = "; ".join(telefones)






                        ###################################################################################################
                        # LINHA DA TABELA
                        ###################################################################################################

                        dados.append({
                            "Contrato": contrato_nome,
                            "Direções estratégicas": direcoes_str,
                            "Nome da proposta": nome_projeto,
                            "Organização": nome_organizacao,
                            "Sigla": sigla_organizacao,
                            "UF": uf_str,
                            "Nome Responsável Legal (Quem vai assinar o contrato e os recibos)": responsaveis_str,
                            "E-mail responsável legal": emails_responsaveis_str,
                            "E-mails da equipe": emails_equipe_str,
                            "Telefone": telefones_str
                        })








                    ###################################################################################################
                    # CRIA DATAFRAME
                    ###################################################################################################
                    df = pd.DataFrame(dados)


                    ###################################################################################################
                    # CRIAÇÃO DO EXCEL
                    ###################################################################################################
                    buffer = io.BytesIO()

                    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                        df.to_excel(
                            writer,
                            index=False,
                            sheet_name="Acompanhamento Completo"
                        )

                    buffer.seek(0)


                    ###################################################################################################
                    # SALVA NO SESSION STATE
                    ###################################################################################################
                    st.session_state.arquivo_acompanhamento_completo = buffer

                    st.rerun()


        ###################################################################################################
        # BOTÃO DOWNLOAD
        ###################################################################################################
        if st.session_state.arquivo_acompanhamento_completo:

            # Nome do edital (seguro para arquivo)
            nome_edital = edital_selecionado_obj.get("nome_edital", "") if edital_selecionado_obj else ""
            nome_edital_arquivo = nome_edital.replace(" ", "_")

            download_clicado = st.download_button(
                label="Baixar relatório",
                icon=":material/download:",
                data=st.session_state.arquivo_acompanhamento_completo,
                file_name=f"Relatorio_acompanhamento_completo_{nome_edital_arquivo}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            ###################################################################################################
            # LIMPA SESSION STATE APÓS DOWNLOAD
            ###################################################################################################
            if download_clicado:
                st.session_state.arquivo_acompanhamento_completo = None
                st.rerun()


    ###################################################################################################
    # MENSAGEM FINAL
    ###################################################################################################
    if st.session_state.arquivo_acompanhamento_completo:
        st.caption("Relatório gerado. Clique para baixar.")