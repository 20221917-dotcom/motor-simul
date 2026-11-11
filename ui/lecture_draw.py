"""강의 실습 페이지의 회로도·페이저도 (Plotly 도형). 켜진 스위치·도통 경로를 색으로 표시."""
import math

import numpy as np
import plotly.graph_objects as go

from ui.diagrams import Sketch

ON, OFF, LINE = "#4ade80", "#ffffff", "#333"
POS, NEG, FLT = "#d62828", "#1d4ed8", "#9ca3af"


def _switch(s, x, y, on, label, w=0.5, h=0.7):
    s.fig.add_shape(type="rect", x0=x - w / 2, x1=x + w / 2, y0=y - h / 2, y1=y + h / 2,
                    fillcolor=ON if on else OFF, line=dict(color=LINE, width=1.6))
    s.text(x, y, f"<b>{label}</b>", size=12)
    # 역병렬 다이오드 (오른쪽 작은 삼각형)
    dx = w / 2 + 0.22
    s.wire((x + w / 2, y + h / 2 - 0.05), (x + dx, y + h / 2 - 0.05), (x + dx, y - h / 2 + 0.05), (x + w / 2, y - h / 2 + 0.05))
    s.fig.add_shape(type="path", path=f"M {x + dx - 0.12},{y - 0.1} L {x + dx + 0.12},{y - 0.1} L {x + dx},{y + 0.1} Z",
                    fillcolor=LINE, line=dict(color=LINE, width=1))
    s.wire((x + dx - 0.12, y + 0.1), (x + dx + 0.12, y + 0.1))


def hbridge(states, i_dir=0, va_label="", title=""):
    """H-브리지 (T1 A상 위, T2 A상 아래, T3 B상 위, T4 B상 아래). states: dict T1..T4 → bool. i_dir: 전기자 전류 방향(+1 A→B)."""
    s = Sketch()
    xA, xB, yT, yB, yM = 2.0, 6.0, 3.0, -1.0, 1.0
    s.wire((0, yT), (xB + 0.8, yT)); s.wire((0, yB), (xB + 0.8, yB))
    s.wire((0, yT), (0, 1.6)); s.wire((0, yB), (0, 0.4))
    s.source(0, 1.0, "Vdc", r=0.55)
    for x, (u, d) in ((xA, ("T1", "T2")), (xB, ("T3", "T4"))):
        s.wire((x, yT), (x, yT - 0.45)); s.wire((x, yM + 0.85), (x, yM)); s.wire((x, yM), (x, yM - 0.85)); s.wire((x, yB + 0.45), (x, yB))
        _switch(s, x, yT - 0.8, states.get(u, False), u)
        _switch(s, x, yB + 0.8, states.get(d, False), d)
    # 전기자 (가운데)
    s.wire((xA, yM), (3.2, yM)); s.wire((4.8, yM), (xB, yM))
    s.resistor((3.2, yM), (3.7, yM)); s.inductor((3.7, yM), (4.2, yM))
    a = np.linspace(0, 2 * np.pi, 40); s._seg(4.5 + 0.3 * np.cos(a), yM + 0.3 * np.sin(a)); s.text(4.5, yM, "<b>E</b>", size=12)
    s.text(xA - 0.35, yM + 0.25, "A", size=12); s.text(xB + 0.35, yM + 0.25, "B", size=12)
    if va_label:
        s.text(4.0, yM - 0.6, va_label, size=12, color=POS)
    if i_dir:
        p0, p1 = ((3.0, yM + 0.45), (4.9, yM + 0.45)) if i_dir > 0 else ((4.9, yM + 0.45), (3.0, yM + 0.45))
        s.arrow(p0, p1, color=POS, text="")
        s.text(3.95, yM + 0.75, "ia", color=POS)
    if title:
        s.text(4.0, yT + 0.55, title, size=13)
    return s.done((-1.3, 7.5), (-1.6, 3.9), height=300)


def bldc_inverter(sw, roles, title=""):
    """3상 인버터 + Y 결선 BLDC. sw: dict 'a+','a-',... → bool. roles: dict 상 → '+', '−', '개방'."""
    s = Sketch()
    xs = {"a": 2.0, "b": 4.2, "c": 6.4}
    yT, yB, yM = 3.2, -1.2, 1.0
    s.wire((0, yT), (7.0, yT)); s.wire((0, yB), (7.0, yB))
    s.wire((0, yT), (0, 1.55)); s.wire((0, yB), (0, 0.45)); s.source(0, 1.0, "Vdc", r=0.55)
    for p, x in xs.items():
        s.wire((x, yT), (x, yT - 0.45)); s.wire((x, yM + 0.85), (x, yB + 0.85)); s.wire((x, yB + 0.45), (x, yB))
        _switch(s, x, yT - 0.8, sw.get(p + "+", False), p.upper() + "+")
        _switch(s, x, yB + 0.8, sw.get(p + "-", False), p.upper() + "−")
    # 전동기 Y 결선 (오른쪽)
    cx, cy = 9.6, 1.0
    ends = {"a": (cx, cy + 1.3), "b": (cx - 1.1, cy - 0.7), "c": (cx + 1.1, cy - 0.7)}
    for p, x in xs.items():
        ex, ey = ends[p]
        col = {"+": POS, "−": NEG}.get(roles.get(p), FLT)
        s.fig.add_trace(go.Scatter(x=[x, 7.8, 7.8, ex],
                                   y=[yM, yM, ey, ey], mode="lines", line=dict(color=col, width=3 if roles.get(p) in "+−" else 2,
                                   dash=None if roles.get(p) in ("+", "−") else "dot"), hoverinfo="skip"))
        s.fig.add_trace(go.Scatter(x=[ex, cx], y=[ey, cy], mode="lines", line=dict(color=col, width=3), hoverinfo="skip"))
        s.text(ex + (0.25 if p != "b" else -0.25), ey + 0.25, f"<b>{p}</b> ({roles.get(p, '')})", size=12, color=col)
    s.fig.add_trace(go.Scatter(x=[cx], y=[cy], mode="markers", marker=dict(size=8, color=LINE), hoverinfo="skip"))
    s.text(cx + 0.3, cy - 0.05, "n", size=12)
    if title:
        s.text(4.5, yT + 0.55, title, size=13)
    return s.done((-1.3, 11.6), (-1.8, 4.0), height=320)


def im_equivalent(vals):
    """유도 전동기 상당 등가회로. vals: 표시할 문자열 dict (Rs, Xls, Xm, Rc, Xlr, Rr_s, I1, I2, Im)."""
    s = Sketch()
    yT, yB = 2.0, 0.0
    s.wire((0, yT), (0.3, yT))
    s.resistor((0.3, yT), (1.5, yT), f"Rs {vals.get('Rs', '')}")
    s.inductor((1.5, yT), (2.8, yT), f"jXls {vals.get('Xls', '')}")
    s.wire((2.8, yT), (4.2, yT))
    s.inductor((4.2, yT), (5.5, yT), f"jXlr′ {vals.get('Xlr', '')}")
    s.wire((5.5, yT), (5.8, yT))
    s.resistor((5.8, yT), (5.8, yB), vals.get("Rr_s", "Rr′/s"), label_side=-1)
    s.wire((0, yB), (5.8, yB))
    s.inductor((3.3, yT), (3.3, yB), f"jXm {vals.get('Xm', '')}", label_side=1)
    s.fig.add_shape(type="circle", x0=-0.15, x1=0.15, y0=yT - 0.15, y1=yT + 0.15, line=dict(color=LINE))
    s.fig.add_shape(type="circle", x0=-0.15, x1=0.15, y0=yB - 0.15, y1=yB + 0.15, line=dict(color=LINE))
    s.text(-0.35, 1.0, "Vs", size=13)
    if vals.get("I1"):
        s.current((0.4, yT + 0.85), (1.3, yT + 0.85), vals["I1"])
    if vals.get("I2"):
        s.current((4.3, yT + 0.85), (5.3, yT + 0.85), vals["I2"])
    if vals.get("Im"):
        s.current((3.75, 1.6), (3.75, 0.6), vals["Im"])
    return s.done((-0.9, 7.6), (-0.7, 3.5), height=280)


def phasors(items, title="", height=380):
    """페이저도. items: [(복소수 끝점, 시작점, 이름, 색)]."""
    fig = go.Figure()
    lim = 0.0
    for z, z0, name, col in items:
        fig.add_annotation(x=z.real, y=z.imag, ax=z0.real, ay=z0.imag, xref="x", yref="y", axref="x", ayref="y",
                           showarrow=True, arrowhead=2, arrowsize=1.3, arrowwidth=2.4, arrowcolor=col, text="")
        fig.add_annotation(x=z.real, y=z.imag, text=f"<b>{name}</b>", showarrow=False, font=dict(color=col, size=13),
                           xshift=14 if z.real >= z0.real else -14, yshift=-14 if "I" in name else 10)
        lim = max(lim, abs(z), abs(z0))
    lim = lim * 1.2 or 1
    fig.update_xaxes(range=[-lim, lim], zeroline=True, zerolinecolor="#ccc", showgrid=False, showticklabels=False)
    fig.update_yaxes(range=[-lim, lim], zeroline=True, zerolinecolor="#ccc", showgrid=False, showticklabels=False,
                     scaleanchor="x")
    fig.update_layout(height=height, plot_bgcolor="white", margin=dict(l=5, r=5, t=30 if title else 5, b=5),
                      title=dict(text=title, x=0.02, font=dict(size=13)), showlegend=False, dragmode=False)
    return fig


def blocks(chain, feedback=None, height=200):
    """간단한 가로 블록도. chain: [(라벨, 색)], feedback: (from_index, to_index, 라벨)."""
    s = Sketch()
    w, gap = 1.7, 0.6
    xs = []
    for k, (lab, fill) in enumerate(chain):
        x = k * (w + gap)
        s.box(x, 0, w, 0.9, lab, fill=fill)
        xs.append(x)
        if k:
            s.arrow((xs[k - 1] + w / 2, 0), (x - w / 2, 0))
    if feedback:
        a, b, lab = feedback
        s.wire((xs[a], -0.45), (xs[a], -1.1), (xs[b], -1.1))
        s.arrow((xs[b], -1.1), (xs[b], -0.47))
        s.text((xs[a] + xs[b]) / 2, -1.35, lab, size=11)
    return s.done((-1.2, xs[-1] + 1.2), (-1.7, 0.8), height=height)
