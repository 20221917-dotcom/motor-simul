"""그래프 공통 스타일."""
import plotly.graph_objects as go

PALETTE = {
    "speed": "#264653", "ref": "#e9c46a", "ia": "#e76f51", "if": "#8e44ad",
    "Te": "#2a9d8f", "TL": "#6c757d", "V": "#1d3557", "E": "#2a9d8f",
    "ol": "#adb5bd", "lim": "#d62828",
}


def style(fig: go.Figure, height=400, side_legend=False, **kw):
    """side_legend=True: 범례를 오른쪽 세로로 (여러 줄 서브플롯에서 제목과 겹치지 않게)."""
    if side_legend:
        legend = dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.01)
        margin = dict(l=10, r=10, t=40, b=10)
    else:
        legend = dict(orientation="h", yanchor="bottom", y=1.02, x=0)
        margin = dict(l=10, r=10, t=85 if "title" in kw else 40, b=10)
    if "title" in kw:
        kw["title"] = dict(kw["title"], y=0.98, yanchor="top", yref="container")
    layout = dict(height=height, plot_bgcolor="white", hovermode="x unified",
                  margin=margin, legend=legend)
    layout.update(kw)
    fig.update_layout(**layout)
    fig.update_xaxes(showgrid=True, gridcolor="#eee", zeroline=True, zerolinecolor="#ccc")
    fig.update_yaxes(showgrid=True, gridcolor="#eee", zeroline=True, zerolinecolor="#ccc")
    return fig


def mark_events(fig, events, rows):
    for ev in events:
        for r in rows:
            fig.add_vline(x=ev.t, line=dict(color="#999", dash="dot", width=1), row=r, col=1)
        fig.add_annotation(x=ev.t, y=1.0, yref="paper", text=ev.label, showarrow=False,
                           font=dict(size=11, color="#666"), yanchor="bottom")


def info_metric(col, label, value, sub=None, help=None):
    """화살표·색 없이 보조 설명을 다는 metric (증감이 아닌 정보 표시용)."""
    try:
        col.metric(label, value, sub, delta_color="off", delta_arrow="off", help=help)
    except TypeError:   # delta_arrow 가 없는 구버전 Streamlit
        col.metric(label, value, sub, delta_color="off", help=help)
