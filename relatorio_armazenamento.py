import streamlit as st
from funcoes_auxiliares import conectar_mongo_coruja  # Função personalizada para conectar ao MongoDB
import plotly.graph_objects as go
import time



st.set_page_config(page_title="Armazenamento no BD", page_icon=":material/home_storage:")






###########################################################################################################
# CARREGAMENTO DO BANCO DE DADOS
###########################################################################################################


db = conectar_mongo_coruja()

# Pessoas
colaboradores = db["pessoas"]

col_projetos = db["projetos"]
# Carrega apenas os campos necessários
projetos_db = list(
    col_projetos.find(
        {},
        {
            "_id": 1,
            "codigo": 1
        }
    )
)

# ObjectId (string) -> código
mapa_id_para_codigo = {
    str(p["_id"]): p["codigo"]
    for p in projetos_db
}

# Códigos existentes (compatibilidade)
codigos_validos = {
    p["codigo"]
    for p in projetos_db
}

###########################################################################################################
# FUNÇÕES
###########################################################################################################


def renderizar_armazenamento():
   
    st.write("")
    
    st.header('Armazenamento do banco de dados')

    st.write('')

    col1, col2, col3 = st.columns(3)

    # Obtém estatísticas do banco
    stats = db.command("dbStats")

    # Extrai o tamanho total usado (em MB)
    usado_mb = stats.get("storageSize", 0) / (1024 * 1024)
    capacidade_total_mb = 500
    porcentagem_usada = (usado_mb / capacidade_total_mb) * 100

    if porcentagem_usada <= 50:
        cor = "green"
    elif porcentagem_usada <= 75:
        cor = "yellow"
    else:
        cor = "red"

    # Velocímetro
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(usado_mb, 1),
        number={'suffix': " MB", "font": {"size": 36}, "valueformat": ".1f"},
        gauge={
            'axis': {'range': [0, capacidade_total_mb]},
            'bar': {'color': cor},
            'steps': [
                {'range': [0, capacidade_total_mb*0.5], 'color': 'rgba(0,255,0,0.2)'},
                {'range': [capacidade_total_mb*0.5, capacidade_total_mb*0.75], 'color': 'rgba(255,255,0,0.2)'},
                {'range': [capacidade_total_mb*0.75, capacidade_total_mb], 'color': 'rgba(255,0,0,0.2)'},
            ],
            'threshold': {'line': {'color': cor, 'width': 6}, 'value': usado_mb}
        }
    ))


    fig_gauge.update_layout(
        height=400,
        margin=dict(l=30, r=30, t=60, b=30),
        title="Limite do plano gratuito da nuvem Mongo Atlas: 500 MB"
    )

    col1.plotly_chart(fig_gauge)

def converter_projetos_para_id(lista_projetos):
    """
    Recebe uma lista contendo códigos ou ObjectIds e
    devolve sempre uma lista de ObjectIds (string).
    """

    if not isinstance(lista_projetos, list):
        return []

    resultado = []

    for projeto in lista_projetos:

        projeto = str(projeto)

        # Já está no formato novo
        if projeto in mapa_id_para_codigo:
            resultado.append(projeto)

        # Está no formato antigo (código)
        elif projeto in codigos_validos:

            for p in projetos_db:
                if p["codigo"] == projeto:
                    resultado.append(str(p["_id"]))
                    break

    return resultado


###########################################################################################################
# INTERFACE
###########################################################################################################


# Logo do sidebar
st.logo("images/logo_fundo_ecos.png", size='large')

if st.session_state.get("tipo_usuario") == "admin":

    aba_armazenamento, aba_impersonar = st.tabs(["Banco de Dados", "Impersonar Usuário"])
    with aba_armazenamento:
        renderizar_armazenamento()
    with aba_impersonar:
        st.markdown("##### Impersonar usuário")
        st.write('')

        usuarios_ativos = list(colaboradores.find(
            {"status": "ativo"},
            {"nome_completo": 1, "e_mail": 1}
        ))

        mapa_usuarios = {
            u.get("nome_completo", "Sem nome"): u.get("e_mail", "")
            for u in usuarios_ativos
            if u.get("e_mail")
        }

        lista_nomes = sorted(mapa_usuarios.keys())
        opcoes = ["-- Selecione um usuário --"] + lista_nomes

        nome_selecionado = st.selectbox(
            "Selecione o usuário para impersonar",
            options=opcoes,
            index=0,
            width=400
        )

        email_impersonar = None if nome_selecionado == opcoes[0] else mapa_usuarios.get(nome_selecionado)

        if st.button("Impersonar usuário", icon=":material/skull:"):
            if not email_impersonar:
                st.warning("Selecione um usuário válido.")
                st.stop()

            usuario = colaboradores.find_one({"e_mail": email_impersonar})

            if usuario:
                # Guarda a sessão do admin para poder voltar depois
                st.session_state["_admin_backup"] = {
                    "id_usuario": st.session_state.get("id_usuario"),
                    "nome": st.session_state.get("nome"),
                    "email": st.session_state.get("email"),
                    "tipo_usuario": st.session_state.get("tipo_usuario"),
                    "projetos": st.session_state.get("projetos"),
                }

                # Mesmo padrão usado em login() e recuperar_senha_dialog()
                st.session_state["logged_in"] = True
                st.session_state["tipo_usuario"] = usuario.get("tipo_usuario", "")
                st.session_state["nome"] = usuario.get("nome_completo")
                st.session_state["id_usuario"] = usuario.get("_id")
                st.session_state["email"] = usuario.get("e_mail", "")
                st.session_state["projetos"] = converter_projetos_para_id(
                    usuario.get("projetos", [])
                )

                # Reset navegação
                st.session_state["pagina_atual"] = None
                st.session_state["projeto_atual"] = None

                st.success(f"Acessando como {st.session_state['nome']}")
                st.balloons()
                time.sleep(3)
                st.rerun()
            else:
                st.error("Usuário não encontrado.")

else:
    renderizar_armazenamento()


