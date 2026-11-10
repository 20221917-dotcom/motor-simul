"""권선 전개도와 결선도 (2D Plotly)."""
import plotly.graph_objects as go

from motors.winding import Winding
from ui.diagrams import Sketch

PCOL = ["#d62828", "#2a9d3a", "#1d4ed8"]
PN = ["A", "B", "C"]


def _arrow(fig, x, y0, y1, col):
    fig.add_annotation(x=x, y=y1, ax=x, ay=y0, xref="x", yref="y", axref="x", ayref="y", showarrow=True,
                       arrowhead=2, arrowsize=1, arrowwidth=1.6, arrowcolor=col, text="")


def development(w: Winding, height=430):
    """슬롯을 펼친 권선 전개도. 상전류가 모두 + 일 때의 도체 전류 방향(위 ↑ = ⊙ 로 봄)을 화살표로 표시."""
    S, fig = w.slots, go.Figure()
    xs = {0: ([], []), 1: ([], []), 2: ([], [])}

    def add(ph, pts):
        X, Y = xs[ph]
        X.extend([p[0] for p in pts] + [None]); Y.extend([p[1] for p in pts] + [None])

    conc = w.kind == "concentrated"
    off = 0.18
    # 코일: 위층(왼쪽) 변 → 위쪽 코일 끝 → 아래층(오른쪽) 변 → 아래쪽 코일 끝
    for c in w.coils:
        if conc:
            xa, xb = c.slot_a + 1 + off, c.slot_b + 1 - off
            if xb < xa:                      # 마지막 이빨 코일: 오른쪽 끝에서 1번 슬롯으로 이어짐
                xb += S
        else:
            xa, xb = c.slot_a + 1 - off, c.slot_b + 1 + off
            if xb < xa:
                xb += S
        mid = (xa + xb) / 2
        h = 0.25 if conc else 0.55
        add(c.phase, [(xa, 0), (xa, 1), (mid, 1 + h), (xb, 1), (xb, 0), (mid, -h), (xa, 0)])
    for ph in range(3):
        X, Y = xs[ph]
        fig.add_trace(go.Scatter(x=X, y=Y, mode="lines", line=dict(color=PCOL[ph], width=2), name=f"{PN[ph]}상 코일",
                                 hoverinfo="skip"))
    # 도체 전류 방향 (상전류 > 0 기준): ⊙ → 위 화살표
    for cd in w.conductors:
        x = cd.slot + 1 + ((off if cd.layer == 1 else -off) if not conc else (-off if cd.layer == 0 else off))
        y0, y1 = (0.25, 0.75) if cd.sign > 0 else (0.75, 0.25)
        _arrow(fig, x, y0, y1, PCOL[cd.phase])
    # 슬롯 번호와 상대
    for k in range(S):
        fig.add_shape(type="rect", x0=k + 0.62, x1=k + 1.38, y0=-0.02, y1=1.02, line=dict(color="#ccc", width=1), layer="below")
        fig.add_annotation(x=k + 1, y=-0.75 if not conc else -0.45, text=str(k + 1), showarrow=False, font=dict(size=10, color="#555"))
        top = [c for c in w.conductors if c.slot == k and c.layer == 0][0]
        fig.add_annotation(x=k + 1, y=1.75 if not conc else 1.45, text=f"{PN[top.phase]}{'+' if top.sign > 0 else '−'}",
                           showarrow=False, font=dict(size=10, color=PCOL[top.phase]))
    # 극 피치
    tau = S / w.poles
    for j in range(w.poles):
        x0, x1 = 0.5 + j * tau, 0.5 + (j + 1) * tau
        fig.add_shape(type="line", x0=x0 + 0.05, x1=x1 - 0.05, y0=-1.1, y1=-1.1, line=dict(color="#888", width=1))
        fig.add_annotation(x=(x0 + x1) / 2, y=-1.3, text=f"{'N' if j % 2 == 0 else 'S'}극 피치", showarrow=False,
                           font=dict(size=10, color="#888"))
    kind = "분포권" if not conc else "집중권"
    title = (f"{kind} · {w.poles}극 · 슬롯 {S} · q = {w.q:g} · 코일 피치 {w.pitch} 슬롯 (극피치 {tau:g}) · "
             f"분포계수 {w.kd:.3f} × 피치계수 {w.kp:.3f} = 권선계수 {w.kw:.3f}")
    fig.update_layout(height=height, plot_bgcolor="white", margin=dict(l=10, r=10, t=40, b=10), hovermode=False,
                      title=dict(text=title, x=0, font=dict(size=13)),
                      legend=dict(orientation="h", y=1.08, x=1, xanchor="right"))
    fig.update_xaxes(visible=False, range=[0.2, S + 0.8 + (tau if not conc else 0)])
    fig.update_yaxes(visible=False, range=[-1.45, 2.0])
    return fig


def connection(w: Winding, conn="Y"):
    """상별 코일 그룹 직렬 연결 + Y / Δ 결선."""
    s = Sketch()
    groups = w.poles if w.kind == "distributed" else w.slots // 3
    n_show = min(groups, 4)
    if conn == "Y":
        s.text(4.6, 3.2, "Y 결선 (성형): 세 상의 끝을 한 점(중성점 N)에 모음 · 선간 전압 = √3 × 상전압", size=12, color="#555")
        ys = [2.2, 1.0, -0.2]
        for ph in range(3):
            y = ys[ph]
            s.text(-0.35, y, ["U", "V", "W"][ph], size=14, color=PCOL[ph])
            s.wire((0, y), (0.6, y))
            x = 0.6
            for g in range(n_show):
                s.inductor((x, y), (x + 1.1, y), "", loops=3)
                s.text(x + 0.55, y + 0.38, f"{PN[ph]}{g + 1}", size=10, color=PCOL[ph])
                x += 1.1
                if g < n_show - 1:
                    s.wire((x, y), (x + 0.25, y)); x += 0.25
            if groups > n_show:
                s.text(x + 0.35, y, "…", size=14); x += 0.7
            s.wire((x, y), (7.6, y), (7.6, 1.0))
        s.text(7.95, 1.0, "N", size=14)
        s.text(4.0, -0.95, f"한 상 = 코일 그룹 {groups}개 직렬 (그룹마다 극 하나{'' if w.kind == 'distributed' else ' = 이빨 코일'})",
               size=11, color="#555")
        return s.done([-0.8, 8.6], [-1.3, 3.5], height=300)
    # Δ
    s.text(3.0, 3.6, "Δ 결선 (환상): 세 상을 고리로 이음 · 상전압 = 선간 전압", size=12, color="#555")
    pts = [(3.0, 3.0), (5.4, -0.6), (0.6, -0.6)]
    for ph in range(3):
        a, b = pts[ph], pts[(ph + 1) % 3]
        s.inductor(a, b, f"{PN[ph]}상 ({groups} 그룹 직렬)", label_side=1 if ph != 2 else -1, loops=6)
        s.wire(a, (a[0] + (0.0 if ph else 0.0), a[1]))
    for ph, (x, y) in enumerate(pts):
        lx, ly = (x, y + 0.45) if ph == 0 else ((x + 0.55, y - 0.3) if ph == 1 else (x - 0.55, y - 0.3))
        s.text(lx, ly, ["U", "V", "W"][ph], size=14, color=PCOL[ph])
    return s.done([-0.8, 6.8], [-1.2, 4.0], height=300)


def terminal_box(conn="Y"):
    """6 단자 단자함: 위 U1 V1 W1, 아래 W2 U2 V2 와 연결판."""
    fig = go.Figure()
    top = [("U1", 0, 0), ("V1", 1, 1), ("W1", 2, 2)]
    bot = [("W2", 0, 2), ("U2", 1, 0), ("V2", 2, 1)]
    for row, y in ((top, 1.0), (bot, 0.0)):
        for name, x, ph in row:
            fig.add_shape(type="circle", x0=x - 0.18, x1=x + 0.18, y0=y - 0.18, y1=y + 0.18,
                          line=dict(color=PCOL[ph], width=2), fillcolor="white")
            fig.add_annotation(x=x, y=y, text=f"<b>{name}</b>", showarrow=False, font=dict(size=12, color=PCOL[ph]))
    # 권선 (U1–U2, V1–V2, W1–W2) 을 점선으로
    for ph, (x1, x2) in enumerate(((0, 1), (1, 2), (2, 0))):
        fig.add_shape(type="line", x0=x1, y0=0.82, x1=x2, y1=0.18, line=dict(color=PCOL[ph], width=1.5, dash="dot"))
    if conn == "Y":
        fig.add_shape(type="rect", x0=-0.25, x1=2.25, y0=-0.1, y1=0.1, line=dict(color="#555"), fillcolor="rgba(160,160,160,0.5)")
        note = "Y: 아래 세 단자(W2·U2·V2)를 가로 연결판 하나로 묶음 → 중성점"
    else:
        for x in (0, 1, 2):
            fig.add_shape(type="rect", x0=x - 0.08, x1=x + 0.08, y0=0.0, y1=1.0, line=dict(color="#555"),
                          fillcolor="rgba(160,160,160,0.5)", layer="below")
        note = "Δ: 세로 연결판 3개 (U1–W2, V1–U2, W1–V2) → 고리"
    for x, t in zip((0, 1, 2), ("L1", "L2", "L3")):
        fig.add_annotation(x=x, y=1.55, ax=x, ay=1.9, xref="x", yref="y", axref="x", ayref="y", showarrow=True,
                           arrowhead=2, arrowcolor="#333", text="")
        fig.add_annotation(x=x, y=2.02, text=f"전원 {t}", showarrow=False, font=dict(size=11))
    fig.add_annotation(x=1, y=-0.55, text=note, showarrow=False, font=dict(size=11, color="#555"))
    fig.update_xaxes(visible=False, range=[-0.8, 2.8]); fig.update_yaxes(visible=False, range=[-0.8, 2.2], scaleanchor="x")
    fig.update_layout(height=300, plot_bgcolor="white", margin=dict(l=5, r=5, t=5, b=5), dragmode=False)
    return fig


def bldc_connection():
    """BLDC: Y 결선 권선 + 3상 인버터 + 홀 센서."""
    s = Sketch()
    s.text(4.0, 3.5, "BLDC 결선: Y 결선 권선 ↔ 3상 인버터 (스위치 6개) ↔ 홀 센서 신호", size=12, color="#555")
    s.wire((0.3, 3.0), (5.0, 3.0)); s.wire((0.3, -0.8), (5.0, -0.8))
    s.text(0.0, 3.0, "+Vdc", size=12); s.text(0.0, -0.8, "0 V", size=12)
    for k, x in enumerate((1.2, 2.6, 4.0)):
        s.box(x, 2.2, 0.6, 0.5, ["Q1", "Q3", "Q5"][k]); s.box(x, 0.0, 0.6, 0.5, ["Q4", "Q6", "Q2"][k])
        s.wire((x, 3.0), (x, 2.45)); s.wire((x, 1.95), (x, 0.25)); s.wire((x, -0.25), (x, -0.8))
        s.wire((x, 1.1), (5.6, 1.1 + (1 - k) * 0.6))
        s.text(x + 0.35, 1.25, ["U", "V", "W"][k], size=12, color=PCOL[k])
    for k in range(3):                      # Y 결선: 각 상 코일 → 중성점
        y = 1.1 + (1 - k) * 0.6
        s.inductor((5.6, y), (7.0, y), "", loops=3)
        s.text(6.3, y + 0.25, f"{PN[k]}상", size=10, color=PCOL[k])
        s.wire((7.0, y), (7.4, y))
    s.wire((7.4, 1.7), (7.4, 0.5))
    s.box(6.5, -0.2, 2.0, 0.55, "홀 센서 Ha·Hb·Hc")
    s.arrow((5.5, -0.2), (4.6, -0.2), color="#2f855a")
    s.text(3.4, -0.45, "회전자 위치 → 켤 스위치 결정", size=10, color="#2f855a")
    return s.done([-0.6, 8.6], [-1.2, 3.8], height=320)


def dc_armature(poles: int, slots: int = 12, kind="lap", height=360):
    """DC 전기자 권선 전개도 (중권 / 파권): 코일 양 끝이 정류자편에 연결."""
    fig = go.Figure()
    S = slots
    y = S // poles
    if kind == "wave":
        yc = (S - 1) // (poles // 2) if poles > 2 else 1
        a = 2
    else:
        yc, a = 1, poles
    X, Y = [], []
    for k in range(S):
        xa, xb = k + 1 - 0.15, k + 1 + y + 0.15
        seg_a, seg_b = k + 1, k + 1 + yc
        X += [seg_a, xa, xa, (xa + xb) / 2, xb, xb, seg_b, None]
        Y += [-0.9, -0.2, 1.0, 1.5, 1.0, -0.2, -0.9, None]
    fig.add_trace(go.Scatter(x=X, y=Y, mode="lines", line=dict(color="#d97706", width=1.8), name="전기자 코일", hoverinfo="skip"))
    for k in range(S):
        fig.add_shape(type="rect", x0=k + 0.6, x1=k + 1.4, y0=-1.25, y1=-0.9, line=dict(color="#7a4a1f"), fillcolor="#e0a35f")
        fig.add_annotation(x=k + 1, y=-1.08, text=str(k + 1), showarrow=False, font=dict(size=9))
        fig.add_annotation(x=k + 1, y=-0.05, text="", showarrow=False)
    for j in range(poles):           # 브러시 (극 사이 중성축)
        xb = 1 + (j + 0.5) * S / poles
        fig.add_shape(type="rect", x0=xb - 0.3, x1=xb + 0.3, y0=-1.75, y1=-1.3, fillcolor="#333", line=dict(color="#111"))
        fig.add_annotation(x=xb, y=-1.95, text="+" if j % 2 == 0 else "−", showarrow=False, font=dict(size=14))
    for j in range(poles):
        x0 = 0.5 + j * S / poles
        fig.add_annotation(x=x0 + S / poles / 2, y=2.0, text=f"{'N' if j % 2 == 0 else 'S'}극 아래", showarrow=False,
                           font=dict(size=11, color="#d62828" if j % 2 == 0 else "#1d4ed8"))
    title = (f"{'중권 (lap)' if kind == 'lap' else '파권 (wave)'} · {poles}극 · 슬롯·정류자편 {S}개 · 코일 피치 {y} · "
             f"정류자 피치 {yc} · 병렬 회로 수 a = {a}")
    fig.update_layout(height=height, plot_bgcolor="white", margin=dict(l=10, r=10, t=40, b=10), hovermode=False,
                      title=dict(text=title, x=0, font=dict(size=13)), showlegend=False)
    fig.update_xaxes(visible=False, range=[0.2, S + y + 1.5]); fig.update_yaxes(visible=False, range=[-2.2, 2.3])
    return fig
