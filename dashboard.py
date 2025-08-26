import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata, re

st.set_page_config(page_title="Dashboard Processos", layout="wide")
# Cabeçalho com logo + título
col_logo, col_texto = st.columns([1, 5])  # proporção 1:5

with col_logo:
    st.image("tjpi.png", width=120)  # ajuste width se quiser maior/menor

with col_texto:
    st.markdown(
        """
        <h1 style='margin-bottom:0; color:#2C3E50;'>
            Dados da Violência Doméstica
        </h1>
        <h3 style='margin-top:0; color:#34495E;'>
            Comarca de Inhuma - PI
        </h3>
        """,
        unsafe_allow_html=True
    )

st.title("📊 Dashboard Interativo de Processos")

# =========================
# Helpers de normalização
# =========================
def norm_text(s: str) -> str:
    if s is None: return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii","ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def rename_columns_safely(df: pd.DataFrame, targets: dict) -> pd.DataFrame:
    """
    Mapeia colunas do arquivo para nomes canônicos.
    Ex.: "bairro localidade" -> "bairro_localidade"
    """
    current_map = {norm_text(c): c for c in df.columns}
    renames = {}
    for canonical, aliases in targets.items():
        for alias in aliases:
            n = norm_text(alias)
            base = n.replace("_", " ")
            if n in current_map and canonical not in df.columns:
                renames[current_map[n]] = canonical
                break
            if base in current_map and canonical not in df.columns:
                renames[current_map[base]] = canonical
                break
    if renames:
        df = df.rename(columns=renames)
    return df

# Paletas
PALETA = px.colors.qualitative.Set3
PALETA2 = px.colors.qualitative.Pastel

# Mês PT-BR (para exibição e ordenação)
MESES_PT = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
            "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
MAP_MES_NUM = {m: i+1 for i, m in enumerate(MESES_PT)}

# =========================
# Funções de gráficos/contagens
# =========================
def donut_fig(df_counts, nome_cat, nome_val, titulo, paleta=PALETA):
    fig = px.pie(
        df_counts, names=nome_cat, values=nome_val, hole=0.55,
        color=nome_cat, color_discrete_sequence=paleta
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Total: %{value}<br>%{percent}",
        sort=True
    )
    fig.update_layout(
        title=titulo,
        template="plotly_white",
        showlegend=True,
        legend_title_text="",
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, xanchor="center", x=0.5),
        margin=dict(t=60, r=20, b=30, l=20)
    )
    return fig

def barras_totais(df_counts, x, y, titulo, paleta=PALETA2):
    fig = px.bar(
        df_counts, x=x, y=y, text=y, color=x, color_discrete_sequence=paleta
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        title=titulo,
        template="plotly_white",
        showlegend=False,
        uniformtext_minsize=10,
        margin=dict(t=60, r=20, b=30, l=20),
        yaxis_title="Total",
        xaxis_title=x
    )
    return fig

def preparar_contagem(df: pd.DataFrame, coluna: str, rotulo: str):
    """
    Retorna DataFrame com colunas padronizadas: [rotulo, 'Total'].
    Usa value_counts, ignora NaN e ordena por Total desc.
    """
    if coluna not in df.columns:
        return None
    s = df[coluna].dropna()
    if s.empty:
        return None
    out = s.value_counts().reset_index()
    # após reset_index(), colunas se tornam ['index', '<coluna>'] — padronizamos:
    out.columns = [rotulo, "Total"]
    out = out.sort_values("Total", ascending=False)
    return out

def preparar_barras_ano(df: pd.DataFrame):
    if "Ano Processo" not in df.columns or df.empty:
        return None
    out = df["Ano Processo"].dropna().value_counts().reset_index()
    out.columns = ["Ano", "Total"]
    # ordenar numericamente, se possível
    try:
        out["AnoInt"] = out["Ano"].astype(int)
        out = out.sort_values("AnoInt").drop(columns=["AnoInt"])
    except:
        out = out.sort_values("Ano")
    return out

# =========================
# Carregamento e preparo
# =========================
@st.cache_data
def carregar_dados(caminho: str) -> pd.DataFrame:
    df = pd.read_excel(caminho, sheet_name="Lista")

    df = rename_columns_safely(df, {
        "nr_processo":      ["nr_processo","numero do processo","nº do processo","nro_processo"],
        "etiquetas":        ["etiquetas","etiqueta"],
        "prioridades":      ["prioridades","prioridade"],
        "dt_distribuicao":  ["dt_distribuicao","data de distribuicao","data autuacao","data de autuacao"],
        "local_ocorrencia": ["local_ocorrencia","local ocorrencia","local de ocorrencia"],
        "bairro_localidade":["bairro_localidade","bairro localidade","bairro","localidade","bairro/localidade"],
    })

    # Unicidade por número do processo
    if "nr_processo" in df.columns:
        df = df.drop_duplicates(subset=["nr_processo"]).copy()

    # Ano do processo (a partir do número)
    if "nr_processo" in df.columns:
        df["Ano Processo"] = df["nr_processo"].astype(str).str[11:15]
    else:
        df["Ano Processo"] = None

    # Datas
    if "dt_distribuicao" in df.columns:
        df["Data Autuação"] = pd.to_datetime(df["dt_distribuicao"], dayfirst=True, errors="coerce")
    else:
        df["Data Autuação"] = pd.NaT

    # Mês Autuação, com chaves de ordenação
    df["Mes Nome"] = df["Data Autuação"].dt.month.apply(lambda m: MESES_PT[m-1] if pd.notnull(m) else None)
    df["Ano Num"] = df["Data Autuação"].dt.year
    df["Mês Autuação"] = df.apply(lambda r: f"{r['Mes Nome']}/{int(r['Ano Num'])}" if pd.notnull(r["Ano Num"]) and r["Mes Nome"] else None, axis=1)
    df["MesNum"] = df["Mes Nome"].map(MAP_MES_NUM)

    # Zona / Município a partir de local_ocorrencia: "Zona Urbana - Inhuma"
    if "local_ocorrencia" in df.columns:
        def extrair_zona(loc):
            if pd.isna(loc): return None
            parts = [p.strip() for p in str(loc).split("-")]
            return parts[0] if parts else None
        def extrair_mun(loc):
            if pd.isna(loc): return None
            parts = [p.strip() for p in str(loc).split("-")]
            return parts[-1] if len(parts) >= 2 else None
        df["Zona"] = df["local_ocorrencia"].apply(extrair_zona)
        df["Município"] = df["local_ocorrencia"].apply(extrair_mun)
    else:
        df["Zona"] = None
        df["Município"] = None

    # Limpezas leves
    for col in ["prioridades","local_ocorrencia","bairro_localidade","Zona","Município","Mês Autuação","Ano Processo","Mes Nome"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace({"nan": None, "None": None})

    return df

df = carregar_dados("Datacor_processos.xlsx")

# =========================
# Filtros (sem Órgão Julgador)
# =========================
st.sidebar.header("🔍 Filtros")

anos = st.sidebar.multiselect(
    "Ano do Processo",
    sorted(df["Ano Processo"].dropna().unique()) if "Ano Processo" in df.columns else []
)

# ordenar meses por Ano e número do mês
if "Mês Autuação" in df.columns:
    meses_opcoes = (
        pd.Series(df["Mês Autuação"])
        .dropna()
        .drop_duplicates()
        .to_frame("Mês Autuação")
        .assign(
            Ano=lambda d: d["Mês Autuação"].str.split("/").str[1].astype(int),
            Mes=lambda d: d["Mês Autuação"].str.split("/").str[0],
            MesNum=lambda d: d["Mes"].map(MAP_MES_NUM)
        )
        .sort_values(["Ano","MesNum"])
        ["Mês Autuação"]
        .tolist()
    )
else:
    meses_opcoes = []

meses = st.sidebar.multiselect("Mês de Autuação", meses_opcoes)

prioridades = st.sidebar.multiselect(
    "Prioridades",
    sorted(df["prioridades"].dropna().unique()) if "prioridades" in df.columns else []
)

municipios_opcoes = sorted(df["Município"].dropna().unique()) if "Município" in df.columns else []
municipios = st.sidebar.multiselect("Município (Local de Ocorrência)", municipios_opcoes)

# Bairro depende do(s) município(s) selecionado(s)
if municipios and "Município" in df.columns:
    base_bairros = df[df["Município"].isin(municipios)]
else:
    base_bairros = df
bairros_opcoes = sorted(base_bairros["bairro_localidade"].dropna().unique()) if "bairro_localidade" in base_bairros.columns else []
bairros = st.sidebar.multiselect("Bairro/Localidade", bairros_opcoes)

zonas_opcoes = sorted(df["Zona"].dropna().unique()) if "Zona" in df.columns else []
zonas = st.sidebar.multiselect("Zona", zonas_opcoes)

# =========================
# Aplicar filtros
# =========================
df_filtrado = df.copy()

if anos and "Ano Processo" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["Ano Processo"].isin(anos)]
if meses and "Mês Autuação" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["Mês Autuação"].isin(meses)]
if prioridades and "prioridades" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["prioridades"].isin(prioridades)]
if municipios and "Município" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["Município"].isin(municipios)]
if bairros and "bairro_localidade" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["bairro_localidade"].isin(bairros)]
if zonas and "Zona" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["Zona"].isin(zonas)]

# =========================
# KPI principal
# =========================
st.metric("📁 Total de Processos", len(df_filtrado))

# =========================
# Gráficos (com helpers padronizados)
# =========================
col1, col2 = st.columns(2)

# Donut: Prioridade
with col1:
    pizza_prioridade = preparar_contagem(df_filtrado, "prioridades", "Prioridade")
    if pizza_prioridade is not None:
        st.plotly_chart(
            donut_fig(pizza_prioridade, "Prioridade", "Total", "Distribuição por Prioridade"),
            use_container_width=True
        )
    else:
        st.info("Sem dados para Prioridade nos filtros atuais.")

# Donut: Município
with col2:
    pizza_mun = preparar_contagem(df_filtrado, "Município", "Município")
    if pizza_mun is not None:
        st.plotly_chart(
            donut_fig(pizza_mun, "Município", "Total", "Distribuição por Município"),
            use_container_width=True
        )
    else:
        st.info("Sem dados de Município nos filtros atuais.")

# Donut: Zona
st.subheader("🧭 Distribuição por Zona")
pizza_zona = preparar_contagem(df_filtrado, "Zona", "Zona")
if pizza_zona is not None:
    st.plotly_chart(
        donut_fig(pizza_zona, "Zona", "Total", "Distribuição por Zona"),
        use_container_width=True
    )
else:
    st.info("Sem dados de Zona nos filtros atuais.")

# Sunburst Município → Bairro
st.subheader("🌳 Hierarquia Município → Bairro")
if "Município" in df_filtrado.columns and "bairro_localidade" in df_filtrado.columns:
    base_sb = df_filtrado.dropna(subset=["Município", "bairro_localidade"])
    if not base_sb.empty:
        fig_sun = px.sunburst(
            base_sb, path=["Município", "bairro_localidade"],
            color="Município",
            color_discrete_sequence=PALETA,
            title="Distribuição por Município e Bairro"
        )
        fig_sun.update_layout(
            template="plotly_white",
            margin=dict(t=60, r=20, b=30, l=20),
            legend_title_text="",
        )
        fig_sun.update_traces(hovertemplate="<b>%{label}</b><br>Contagem: %{value}")
        st.plotly_chart(fig_sun, use_container_width=True)
    else:
        st.info("Sem dados para o gráfico hierárquico.")

# Barras: Ano do Processo
st.subheader("📅 Processos por Ano")
ano_data = preparar_barras_ano(df_filtrado)
if ano_data is not None:
    st.plotly_chart(
        barras_totais(ano_data, "Ano", "Total", "Distribuição Anual de Processos"),
        use_container_width=True
    )
else:
    st.info("Sem dados para o gráfico anual nos filtros atuais.")

# =========================
# Tabela (resumo)
# =========================
st.subheader("📄 Lista de Processos (Resumo)")
colunas_visiveis = [
    "Mês Autuação", "Data Autuação", "Ano Processo",
    "prioridades",
    "Zona", "Município", "bairro_localidade", "local_ocorrencia"
]
colunas_visiveis = [c for c in colunas_visiveis if c in df_filtrado.columns]
st.dataframe(df_filtrado[colunas_visiveis], use_container_width=True)
