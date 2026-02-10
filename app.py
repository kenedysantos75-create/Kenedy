import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ===============================
# CONFIGURAÇÃO E ESTILO RS (SHADOW + ROUNDED)
# ===============================
st.set_page_config(page_title="Projeto Aliança - RS", layout="wide")

st.markdown("""
    <style>
    .metric-card {
        background: #ffffff; padding: 25px; border-radius: 15px; 
        border-left: 15px solid #ccc; margin-bottom: 20px;
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    .metric-title { font-size: 32px !important; font-weight: bold; color: #1a1a1a; }
    .metric-label { font-size: 22px !important; color: #333; margin: 8px 0; }
    .metric-value { font-size: 52px !important; font-weight: 900; }
    
    .chart-box { 
        border: 1px solid #dee2e6; 
        border-radius: 18px; 
        padding: 0px; 
        margin-bottom: 30px; 
        background: #fff; 
        box-shadow: 0 8px 16px rgba(0,0,0,0.1); 
        overflow: hidden;
    }
    
    .chart-header {
        background-color: #001f3f; 
        color: white; 
        padding: 12px; 
        text-align: center; 
        font-size: 24px; 
        font-weight: bold;
        border-top-left-radius: 18px;
        border-top-right-radius: 18px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Projeto Aliança - RS")

NOMES_COMPLETOS = {
    "AH": "Aderência ao Horizonte de Programação",
    "AR": "Aderência à Eliminação de Restrições",
    "AE": "Aderência à Execução"
}

# ===============================
# CÁLCULO DE PONTOS POR INDICADOR
# ===============================
def processar_pontos_personalizados(df):
    def calcular_por_kpi(row):
        ah = pd.to_numeric(row.get("Horizonte de Programação", 0), errors='coerce') or 0
        ar = pd.to_numeric(row.get("Eliminação de Restrição", 0), errors='coerce') or 0
        ae = pd.to_numeric(row.get("Execução da Programação", 0), errors='coerce') or 0
        
        pts_ah = 4 if ah >= 90 else (2 if ah >= 60 else (1 if ah >= 50 else 0))
        pts_ar = 4 if ar >= 85 else (2 if ar >= 70 else (1 if ar >= 60 else 0))
        pts_ae = 4 if ae >= 85 else (2 if ae >= 70 else (1 if ae >= 60 else 0))
        
        return pd.Series([pts_ah, pts_ar, pts_ae, (pts_ah + pts_ar + pts_ae)])

    df[['pts_ah', 'pts_ar', 'pts_ae', 'PTS_TOTAL']] = df.apply(calcular_por_kpi, axis=1)
    return df

@st.cache_data
def carregar_dados():
    try:
        df = pd.read_excel("Alianca.xlsx")
    except:
        df = pd.read_csv("Alianca.xlsx - Export.csv")
    df.columns = [c.strip() for c in df.columns]
    for col in ["Semana", "Gerência", "Fornecedor", "Regional", "Profundidade", "Tipo_Registro"]:
        if col in df.columns:
            df[col] = df[col].fillna("N/A").astype(str).str.strip()
    return processar_pontos_personalizados(df)

df_raw = carregar_dados()

# ===============================
# SIDEBAR - FILTROS
# ===============================
st.sidebar.header("🔎 Parâmetros")
filtro_regional = st.sidebar.selectbox("Regional", sorted(df_raw["Regional"].unique()))
gerencias_opcoes = sorted([g for g in df_raw["Gerência"].unique() if g not in ["N/A", "Norte", "Sul"]])
filtro_gerencia = st.sidebar.selectbox("Gerência", ["Todas"] + gerencias_opcoes)

# Filtro lateral de fornecedores (apenas Detalhe para a sidebar)
df_sidebar = df_raw[df_raw["Tipo_Registro"] == "Detalhe"]
if filtro_gerencia != "Todas": df_sidebar = df_sidebar[df_sidebar["Gerência"] == filtro_gerencia]
filtro_fornecedor = st.sidebar.multiselect("Fornecedor", sorted(df_sidebar["Fornecedor"].unique()))

semanas_opcoes = sorted([s for s in df_raw["Semana"].unique() if "FECHAMENTO" not in s.upper()], reverse=True)
filtro_semana = st.sidebar.multiselect("Semana", semanas_opcoes)

# ===============================
# CARDS (MÊS ESTÁTICO)
# ===============================
def card_val(label, reg):
    base_m = df_raw[df_raw["Profundidade"].str.upper().isin(["MÊS", "CONSOLIDADO"])]
    target = base_m[base_m["Fornecedor"].str.upper() == label.upper()]
    if target.empty and label == "Geral": target = base_m[base_m["Fornecedor"].str.upper() == reg.upper()]
    if not target.empty:
        r = target.iloc[-1]
        return r["Horizonte de Programação"], r["Eliminação de Restrição"], r["Execução da Programação"], r["PTS_TOTAL"]
    return 0, 0, 0, 0

st.markdown(f"### 📊 Fechamento do Mês - {filtro_regional}")
c_cols = st.columns(3)
for ui, t in zip(c_cols, ["Manutenção", "Obras", "Geral"]):
    ah, ar, ae, pts = card_val(t, filtro_regional)
    color = "#2ecc71" if pts >= 10 else ("#f1c40f" if pts >= 7 else "#e74c3c")
    with ui:
        st.markdown(f'<div class="metric-card" style="border-left-color: {color}"><div class="metric-title">{t}</div>'
                    f'<div class="metric-label">{NOMES_COMPLETOS["AH"]}: {ah:.2f}%</div>'
                    f'<div class="metric-label">{NOMES_COMPLETOS["AR"]}: {ar:.2f}%</div>'
                    f'<div class="metric-label">{NOMES_COMPLETOS["AE"]}: {ae:.2f}%</div>'
                    f'<div class="metric-value" style="color:{color}">{pts:.0f} pts</div></div>', unsafe_allow_html=True)

# ===============================
# FUNÇÃO DE GRÁFICO (BLINDADA CONTRA ZEROS)
# ===============================
def plot_dispersao_v27(df_in, kpi, pts_col, meta, is_comp=False, x_range=None):
    if df_in.empty: return go.Figure()
    
    # Remove fechamento para o gráfico não poluir
    df_in = df_in[~df_in["Semana"].str.upper().str.contains("FECHAMENTO")]
    
    g_col = "Fornecedor" if is_comp else "Gerência"
    colunas_selecao = list(set([kpi, pts_col]))
    df_p = df_in.groupby(["Semana", g_col])[colunas_selecao].last().reset_index().sort_values("Semana")
    
    df_p['Delta'] = df_p.groupby(g_col)[kpi].transform(lambda x: x.diff().fillna(0))
    df_p['Evol'] = df_p['Delta'].apply(lambda x: "Progredindo" if x > 0.1 else ("Regredindo" if x < -0.1 else "Estável"))
    
    fig = go.Figure()
    texto_legenda = "🟢 Cumpre Meta Progredindo/Estável | 🔴 Fora Meta Regredindo/Estável | 🟡 Cumpre Meta Regredindo ou Fora Meta Progredindo"
    
    fig.add_vline(x=meta, line_dash="dash", line_color="#1565C0", line_width=3)
    fig.add_annotation(x=meta, y=1.06, yref="paper", text="Meta", showarrow=False, font=dict(size=18, color="#1565C0", weight="bold"))

    for i, name in enumerate(df_p[g_col].unique()):
        d = df_p[df_p[g_col] == name]
        def cor_logic(r):
            cumpre = r[kpi] >= meta
            if cumpre and r['Evol'] != "Regredindo": return "#2E7D32"
            if not cumpre and r['Evol'] != "Progredindo": return "#C62828"
            return "#F9A825"

        fig.add_trace(go.Scatter(
            x=d[kpi], y=d['Evol'], mode='markers', name=str(name),
            marker=dict(size=[25+(p*8) for p in d[pts_col]], color=d.apply(cor_logic, axis=1), symbol="circle" if i==0 else "diamond", line=dict(width=2, color="white")),
            text=d['Semana'], customdata=d[pts_col], showlegend=is_comp,
            hovertemplate="<b>%{text}</b><br>Apurado: %{x:.2f}%<br>Pontos: %{customdata} pts<extra></extra>"
        ))
        
        pos_counts = {}
        for idx, row in d.iterrows():
            pos_key = (row[kpi], row['Evol'])
            pos_counts[pos_key] = pos_counts.get(pos_key, 0) + 1
            off_y = 65 + (pos_counts[pos_key] * 28) if idx % 2 == 0 else -65 - (pos_counts[pos_key] * 28)
            fig.add_annotation(x=row[kpi], y=row['Evol'], text=row['Semana'], showarrow=True, ax=45, ay=off_y, font=dict(size=18, weight="bold"), bgcolor="rgba(255,255,255,0.9)", bordercolor="#aaa")

    fig.add_annotation(text=texto_legenda, xref="paper", yref="paper", x=0.5, y=-0.3, showarrow=False, font=dict(size=15, color="#444"))
    
    r_x = x_range if x_range else [-5, 115]
    fig.update_layout(xaxis=dict(range=r_x, tickfont=dict(size=18), title=dict(text="Aderência %" if not x_range else "Pontos", font=dict(size=18))),
                      yaxis=dict(tickfont=dict(size=18), categoryorder="array", categoryarray=["Regredindo", "Estável", "Progredindo"]),
                      height=600, plot_bgcolor="white", margin=dict(b=140, t=20),
                      legend=dict(font=dict(size=18), orientation="h", y=-0.4, x=0.5, xanchor="center"))
    return fig

# ===============================
# LÓGICA DE FILTRAGEM (O SEGREDO DO ZERO DE OBRAS)
# ===============================
if filtro_gerencia == "Todas":
    # Se não filtrou nada, mostra Detalhes dos fornecedores
    df_ind = df_raw[df_raw["Tipo_Registro"] == "Detalhe"]
else:
    # 🔴 Se filtrou Obras ou Manutenção, pega a linha mestre (onde Fornecedor == Gerência)
    # Isso garante que o valor consolidado (55%, etc) apareça e não fique zero.
    df_ind = df_raw[(df_raw["Fornecedor"] == filtro_gerencia) | (df_raw["Gerência"] == filtro_gerencia)]

if filtro_fornecedor: df_ind = df_ind[df_ind["Fornecedor"].isin(filtro_fornecedor)]
if filtro_semana: df_ind = df_ind[df_ind["Semana"].isin(filtro_semana)]

# --- GRID DE GRÁFICOS INDIVIDUAIS ---
st.divider()
st.markdown("#### 📈 Matriz de Dispersão Individual")
c1, c2 = st.columns(2)
with c1:
    st.markdown(f'<div class="chart-box"><div class="chart-header">{NOMES_COMPLETOS["AH"]}</div>', unsafe_allow_html=True)
    st.plotly_chart(plot_dispersao_v27(df_ind, "Horizonte de Programação", "pts_ah", 90), use_container_width=True, key="gr_ah_i")
    st.markdown('</div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="chart-box"><div class="chart-header">{NOMES_COMPLETOS["AR"]}</div>', unsafe_allow_html=True)
    st.plotly_chart(plot_dispersao_v27(df_ind, "Eliminação de Restrição", "pts_ar", 85), use_container_width=True, key="gr_ar_i")
    st.markdown('</div>', unsafe_allow_html=True)

c3, c4 = st.columns(2)
with c3:
    st.markdown(f'<div class="chart-box"><div class="chart-header">{NOMES_COMPLETOS["AE"]}</div>', unsafe_allow_html=True)
    st.plotly_chart(plot_dispersao_v27(df_ind, "Execução da Programação", "pts_ae", 85), use_container_width=True, key="gr_ae_i")
    st.markdown('</div>', unsafe_allow_html=True)

# --- COMPARATIVO OBRAS VS MANUTENÇÃO (CONSOLIDADO) ---
st.divider()
st.markdown("#### 🚀 Comparativo Obras vs Manutenção")
df_cmp = df_raw[df_raw["Fornecedor"].isin(["Obras", "Manutenção"])]
if filtro_semana: df_cmp = df_cmp[df_cmp["Semana"].isin(filtro_semana)]

c5, c6 = st.columns(2)
with c5:
    st.markdown(f'<div class="chart-box"><div class="chart-header">{NOMES_COMPLETOS["AH"]} (Comp)</div>', unsafe_allow_html=True)
    st.plotly_chart(plot_dispersao_v27(df_cmp, "Horizonte de Programação", "PTS_TOTAL", 90, True), use_container_width=True, key="gr_ah_c")
    st.markdown('</div>', unsafe_allow_html=True)
with c6:
    st.markdown(f'<div class="chart-box"><div class="chart-header">{NOMES_COMPLETOS["AR"]} (Comp)</div>', unsafe_allow_html=True)
    st.plotly_chart(plot_dispersao_v27(df_cmp, "Eliminação de Restrição", "PTS_TOTAL", 85, True), use_container_width=True, key="gr_ar_c")
    st.markdown('</div>', unsafe_allow_html=True)

c7, c8 = st.columns(2)
with c7:
    st.markdown(f'<div class="chart-box"><div class="chart-header">{NOMES_COMPLETOS["AE"]} (Comp)</div>', unsafe_allow_html=True)
    st.plotly_chart(plot_dispersao_v27(df_cmp, "Execução da Programação", "PTS_TOTAL", 85, True), use_container_width=True, key="gr_ae_c")
    st.markdown('</div>', unsafe_allow_html=True)
with c8:
    st.markdown(f'<div class="chart-box"><div class="chart-header">Soma Total Acumulada</div>', unsafe_allow_html=True)
    df_tot = df_raw[(df_raw["Tipo_Registro"].str.contains("Consolidado")) & (df_raw["Fornecedor"].str.upper() == filtro_regional.upper())]
    if not df_tot.empty:
        fig_pts = plot_dispersao_v27(df_tot, "PTS_TOTAL", "PTS_TOTAL", 10, x_range=[0, 15])
        st.plotly_chart(fig_pts, use_container_width=True, key="gr_pts_f")
    st.markdown('</div>', unsafe_allow_html=True)