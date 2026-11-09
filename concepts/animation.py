"""원리 탭의 단면 애니메이션 (Plotly 프레임).

화면 구성
  왼쪽  : 고정자 N/S 극, 자속선, 회전자, 코일 변(⊙/⊗), 힘 화살표, 정류자·브러시
  오른쪽: 전압 분배 막대 (V = Ia·R + L·dIa/dt + E), 속도와 전류의 시간 변화

회전자는 실제 속도로 그리면 너무 빨라서 눈에 보이지 않으므로
"표시 각속도 ∝ 실제 ω" 로 줄여서 그린다. 실제 값은 숫자로 표시한다.
"""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from concepts.commutation import conductor_sign

R_ROTOR, R_COND, R_COMM = 0.95, 0.78, 0.22
COL_N, COL_S = "#d9534f", "#3b7dd8"
COL_A, COL_B = "#f0a020", "#20a39e"


def _arc(r, a0, a1, n=40):
    a = np.linspace(a0, a1, n)
    return r * np.cos(a), r * np.sin(a)


def _pole(side):
    """side=-1: 왼쪽(N), +1: 오른쪽(S) 극 다각형."""
    half = np.deg2rad(42)
    c = 0.0 if side > 0 else np.pi
    ax, ay = _arc(1.05, c - half, c + half)
    xo = side * 1.75
    xs = list(ax) + [xo, xo, ax[0]]
    ys = list(ay) + [ay[-1], ay[0], ay[0]]
    return xs, ys


def _arrow(x0, y0, dx, dy, head=0.09):
    """화살대(선)와 머리(삼각형) 좌표."""
    L = np.hypot(dx, dy)
    if L < 1e-6:
        return [None], [None], [None], [None]
    ux, uy = dx / L, dy / L
    x1, y1 = x0 + dx, y0 + dy
    px, py = -uy, ux
    hx = [x1, x1 - head * ux + 0.6 * head * px, x1 - head * ux - 0.6 * head * px, x1, None]
    hy = [y1, y1 - head * uy + 0.6 * head * py, y1 - head * uy - 0.6 * head * py, y1, None]
    return [x0, x1 - 0.5 * head * ux, None], [y0, y1 - 0.5 * head * uy, None], hx, hy


def _dynamic_traces(theta, ia, kphi, if_ratio, force_ref):
    """한 프레임에서 바뀌는 단면 요소들."""
    phis = np.array([theta, theta + np.pi])
    s = conductor_sign(phis) * np.sign(ia) if abs(ia) > 1e-3 else np.zeros(2)
    cx, cy = R_COND * np.cos(phis), R_COND * np.sin(phis)
    symbols = ["circle-dot" if v > 0 else ("circle-x" if v < 0 else "circle") for v in s]

    # 힘: F = I·L × B, B = +x, ⊙(+z) → +y 방향
    f_len = 0.55 * min(abs(kphi * ia) / force_ref, 1.6) if force_ref > 0 else 0.0
    shx, shy, hdx, hdy = [], [], [], []
    for j in range(2):
        if s[j] != 0 and f_len > 0.02:
            a, b, c, d = _arrow(cx[j], cy[j] + 0.1 * s[j], 0.0, s[j] * f_len)
            shx += a; shy += b; hdx += c; hdy += d
    shx, shy, hdx, hdy = ([None if v is None else round(float(v), 3) for v in arr]
                          for arr in (shx, shy, hdx, hdy))

    # 정류자편 A(코일변 1 쪽, 주황) / B(코일변 2 쪽, 청록)
    gap = np.deg2rad(8)
    ax_, ay_ = (np.round(v, 3) for v in _arc(R_COMM, theta - np.pi / 2 + gap,
                                              theta + np.pi / 2 - gap, 16))
    bx_, by_ = (np.round(v, 3) for v in _arc(R_COMM, theta + np.pi / 2 + gap,
                                              theta + 3 * np.pi / 2 - gap, 16))
    cx, cy = np.round(cx, 3), np.round(cy, 3)
    # 코일 결선 (정류자편 → 코일변)
    lx = [round(R_COMM * np.cos(theta), 3), cx[0], None,
          round(R_COMM * np.cos(theta + np.pi), 3), cx[1]]
    ly = [round(R_COMM * np.sin(theta), 3), cy[0], None,
          round(R_COMM * np.sin(theta + np.pi), 3), cy[1]]

    alpha = float(np.clip(0.15 + 0.55 * if_ratio, 0.05, 0.8))
    return [
        go.Scatter(x=lx, y=ly, mode="lines", line=dict(color="#666", width=1.5, dash="dot")),
        go.Scatter(x=ax_, y=ay_, mode="lines", line=dict(color=COL_A, width=9)),
        go.Scatter(x=bx_, y=by_, mode="lines", line=dict(color=COL_B, width=9)),
        go.Scatter(x=cx, y=cy, mode="markers",
                   marker=dict(symbol=symbols, size=26, color="white",
                               line=dict(color=[COL_A, COL_B], width=3))),
        go.Scatter(x=shx or [None], y=shy or [None], mode="lines",
                   line=dict(color="#2a9d3a", width=4)),
        go.Scatter(x=hdx or [None], y=hdy or [None], mode="lines", fill="toself",
                   fillcolor="#2a9d3a", line=dict(color="#2a9d3a", width=1)),
        # 자속선 (계자 세기에 따라 진하기 변화)
        go.Scatter(x=[-1.0, 1.0, None] * 3, y=[0.55, 0.55, None, 0.0, 0.0, None, -0.55, -0.55,
                                                None],
                   mode="lines", line=dict(color=f"rgba(120,80,200,{alpha})", width=2)),
    ]


def build_principle_figure(res, theta0, w_scale, force_ref, if_nom, n_frames=80,
                           frame_ms=70, t_offset=0.0):
    """res: core.simulate.SimResult. 반환: (figure, 마지막 표시 각도)"""
    t = res.t
    idx = np.linspace(0, len(t) - 1, n_frames).astype(int)
    ia, if_, w = res["ia"], res["if"], res["omega"]
    kphi, E, vR, vL, V = res["kphi"], res["E"], res["v_R"], res["v_L"], res["V"]
    rpm = res["rpm"]
    tt = t + t_offset
    # 시간 그래프용으로 줄인 이력 (프레임 데이터 크기를 줄이기 위해)
    hist = np.linspace(0, len(t) - 1, min(len(t), 4 * n_frames)).astype(int)

    # 표시 각도: 프레임당 최대 약 28° 로 줄여서 회전
    thetas = [theta0]
    for k in range(1, n_frames):
        thetas.append(thetas[-1] + np.deg2rad(28.0) * np.clip(w[idx[k]] / w_scale, -1.4, 1.4))

    fig = make_subplots(rows=3, cols=2, column_widths=[0.5, 0.5],
                        specs=[[{"rowspan": 3}, {}], [None, {}], [None, {}]],
                        vertical_spacing=0.12, horizontal_spacing=0.08,
                        subplot_titles=("단면 (코일 1개로 단순화)",
                                        "전압 분배  V = Ia·R + La·dIa/dt + E  [V]",
                                        "속도 [rpm]", "전기자 전류 Ia [A]"))
    # --- 고정 요소 ---------------------------------------------------------
    for side, col, txt in ((-1, COL_N, "N"), (1, COL_S, "S")):
        xs, ys = _pole(side)
        fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", fillcolor=col, mode="lines",
                                 line=dict(color=col)), 1, 1)
        fig.add_annotation(x=side * 1.45, y=0, text=f"<b>{txt}</b>", showarrow=False,
                           font=dict(size=22, color="white"), row=1, col=1)
    rx, ry = _arc(R_ROTOR, 0, 2 * np.pi, 90)
    fig.add_trace(go.Scatter(x=rx, y=ry, fill="toself", fillcolor="rgba(160,160,160,0.25)",
                             mode="lines", line=dict(color="#888")), 1, 1)
    # 브러시 (+ 오른쪽, − 왼쪽)
    for side, txt in ((1, "+"), (-1, "−")):
        x0 = side * (R_COMM + 0.01)
        x1 = side * (R_COMM + 0.16)
        fig.add_trace(go.Scatter(x=[x0, x1, x1, x0, x0], y=[-0.06, -0.06, 0.06, 0.06, -0.06],
                                 fill="toself", fillcolor="#333", mode="lines",
                                 line=dict(color="#333")), 1, 1)
        fig.add_annotation(x=side * (R_COMM + 0.27), y=0.0, text=f"<b>{txt}</b>",
                           showarrow=False, font=dict(size=16), row=1, col=1)
    n_static = len(fig.data)

    # --- 변하는 요소 (프레임으로 갱신) -----------------------------------------
    def frame_traces(k):
        j = idx[k]
        tr = _dynamic_traces(thetas[k], ia[j], kphi[j], if_[j] / if_nom if if_nom else 1.0,
                             force_ref)
        tr.append(go.Scatter(x=[0], y=[1.32], mode="text",
                             text=[f"ω = {rpm[j]:.0f} rpm   Ia = {ia[j]:.1f} A   "
                                   f"t = {tt[j]:.3f} s"],
                             textfont=dict(size=14)))
        bars = [
            go.Bar(y=["V"], x=[vR[j]], orientation="h", name="Ia·R (저항 강하)",
                   marker_color="#e76f51", text=[f"{vR[j]:.0f}"], textposition="inside"),
            go.Bar(y=["V"], x=[vL[j]], orientation="h", name="La·dIa/dt",
                   marker_color="#aaaaaa", text=[f"{vL[j]:.0f}"], textposition="inside"),
            go.Bar(y=["V"], x=[E[j]], orientation="h", name="E (역기전력)",
                   marker_color="#2a9d8f", text=[f"{E[j]:.0f}"], textposition="inside"),
        ]
        h = np.append(hist[hist < j], j)
        lines = [
            go.Scatter(x=np.round(tt[h], 4), y=np.round(rpm[h], 2), mode="lines",
                       line=dict(color="#264653")),
            go.Scatter(x=np.round(tt[h], 4), y=np.round(ia[h], 3), mode="lines",
                       line=dict(color="#e76f51")),
        ]
        return tr, bars, lines

    tr, bars, lines = frame_traces(0)
    for g in tr:
        fig.add_trace(g, 1, 1)
    for g in bars:
        fig.add_trace(g, 1, 2)
    fig.add_trace(lines[0], 2, 2)
    fig.add_trace(lines[1], 3, 2)
    dyn_idx = list(range(n_static, len(fig.data)))

    frames = []
    for k in range(n_frames):
        tr, bars, lines = frame_traces(k)
        frames.append(go.Frame(data=tr + bars + lines, traces=dyn_idx, name=str(k)))
    fig.frames = frames

    # --- 축과 레이아웃 -----------------------------------------------------
    fig.update_xaxes(range=[-1.9, 1.9], visible=False, row=1, col=1)
    fig.update_yaxes(range=[-1.45, 1.45], visible=False, scaleanchor="x", row=1, col=1)
    vmax = max(np.max(np.abs(V)), np.max(vR + np.maximum(vL, 0) + np.maximum(E, 0))) * 1.08
    vmin = min(0.0, np.min(np.minimum(vL, 0) + np.minimum(E, 0) + np.minimum(vR, 0))) * 1.08
    fig.update_xaxes(range=[vmin, vmax], row=1, col=2)
    for r_, y in ((2, rpm), (3, ia)):
        lo, hi = float(np.min(y)), float(np.max(y))
        pad = 0.08 * max(hi - lo, 1.0)
        fig.update_yaxes(range=[min(lo, 0) - pad, hi + pad], row=r_, col=2)
        fig.update_xaxes(range=[tt[0], tt[-1]], row=r_, col=2)
    fig.update_xaxes(title_text="시간 [s]", row=3, col=2)
    fig.add_vline(x=float(V[0]), line=dict(color="black", dash="dash"), row=1, col=2)

    fig.update_layout(
        height=600, barmode="relative", showlegend=True,
        legend=dict(orientation="h", x=0.52, y=-0.14, xanchor="left", yanchor="top",
                    font=dict(size=11)),
        margin=dict(l=10, r=10, t=40, b=85), plot_bgcolor="white",
        updatemenus=[dict(type="buttons", showactive=False, x=0.0, y=-0.02,
                          xanchor="left", yanchor="top", direction="left",
                          buttons=[
                              dict(label="▶ 재생", method="animate",
                                   args=[None, dict(frame=dict(duration=frame_ms, redraw=True),
                                                    transition=dict(duration=0),
                                                    fromcurrent=True, mode="immediate")]),
                              dict(label="⏸ 정지", method="animate",
                                   args=[[None], dict(frame=dict(duration=0, redraw=False),
                                                      mode="immediate")]),
                          ])],
        sliders=[dict(active=0, x=0.15, y=-0.02, len=0.33, pad=dict(t=0),
                      currentvalue=dict(visible=False),
                      steps=[dict(method="animate", label="",
                                  args=[[str(k)], dict(mode="immediate",
                                                       frame=dict(duration=0, redraw=True),
                                                       transition=dict(duration=0))])
                             for k in range(n_frames)])],
    )
    # 고정 요소의 범례는 숨기고 막대만 범례에 표시
    for i, d in enumerate(fig.data):
        d.showlegend = isinstance(d, go.Bar)
    for fr in fig.frames:
        for d in fr.data:
            d.showlegend = isinstance(d, go.Bar)
    return fig, thetas[-1]
