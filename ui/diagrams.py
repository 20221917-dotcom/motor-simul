"""결선도와 블록 다이어그램 (Plotly 도형으로 직접 그림, 외부 이미지 없음)."""
import numpy as np
import plotly.graph_objects as go

INK = "#222"


class Sketch:
    """간단한 회로도 그리기 도구."""

    def __init__(self):
        self.fig = go.Figure()
        self.xs, self.ys = [], []          # 선 묶음 (None 으로 구분)

    def _seg(self, xs, ys):
        self.xs += list(xs) + [None]
        self.ys += list(ys) + [None]

    def wire(self, *pts):
        self._seg([p[0] for p in pts], [p[1] for p in pts])

    def text(self, x, y, s, size=13, color=INK, **kw):
        self.fig.add_annotation(x=x, y=y, text=s, showarrow=False,
                                font=dict(size=size, color=color), **kw)

    def resistor(self, p0, p1, label="", variable=False, label_side=1):
        (x0, y0), (x1, y1) = p0, p1
        n = 6
        L = np.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        px, py = -uy, ux
        lead = 0.2 * L
        pts = [(x0, y0), (x0 + lead * ux, y0 + lead * uy)]
        body = L - 2 * lead
        for i in range(n):
            d = lead + body * (i + 0.5) / n
            a = 0.15 * (1 if i % 2 == 0 else -1)
            pts.append((x0 + d * ux + a * px, y0 + d * uy + a * py))
        pts += [(x1 - lead * ux, y1 - lead * uy), (x1, y1)]
        self.wire(*pts)
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        if variable:
            self.arrow((mx - 0.35 * ux - 0.3 * px, my - 0.35 * uy - 0.3 * py),
                       (mx + 0.35 * ux + 0.3 * px, my + 0.35 * uy + 0.3 * py))
        if label:
            self.text(mx + 0.45 * label_side * px, my + 0.45 * label_side * py, label)

    def inductor(self, p0, p1, label="", label_side=1, loops=4):
        (x0, y0), (x1, y1) = p0, p1
        L = np.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        px, py = -uy, ux
        lead = 0.15 * L
        body = L - 2 * lead
        r = body / loops / 2
        pts = [(x0, y0)]
        for i in range(loops):
            c = lead + r * (2 * i + 1)
            for a in np.linspace(np.pi, 0, 12):
                d = c + r * np.cos(a)
                h = r * np.sin(a) * 1.2
                pts.append((x0 + d * ux + h * px, y0 + d * uy + h * py))
        pts.append((x1, y1))
        self.wire(*pts)
        if label:
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            self.text(mx + 0.5 * label_side * px, my + 0.5 * label_side * py, label)

    def source(self, x, y, label, r=0.38):
        a = np.linspace(0, 2 * np.pi, 50)
        self._seg(x + r * np.cos(a), y + r * np.sin(a))
        self.text(x, y + 0.17, "+", size=14)
        self.text(x, y - 0.17, "−", size=14)
        self.text(x - r - 0.35, y, label, xanchor="right")
        return (x, y + r), (x, y - r)

    def armature(self, x, y, label="M", r=0.45):
        a = np.linspace(0, 2 * np.pi, 50)
        self._seg(x + r * np.cos(a), y + r * np.sin(a))
        for sgn in (1, -1):  # 브러시
            yb = y + sgn * r
            self.wire((x - 0.12, yb), (x + 0.12, yb), (x + 0.12, yb + sgn * 0.1),
                      (x - 0.12, yb + sgn * 0.1), (x - 0.12, yb))
        self.text(x, y, f"<b>{label}</b>", size=16)
        return (x, y + r + 0.1), (x, y - r - 0.1)

    def arrow(self, p0, p1, color=INK, text=""):
        self.fig.add_annotation(x=p1[0], y=p1[1], ax=p0[0], ay=p0[1], xref="x", yref="y",
                                axref="x", ayref="y", showarrow=True, arrowhead=2,
                                arrowsize=1.2, arrowwidth=1.6, arrowcolor=color, text=text)

    def current(self, p0, p1, label, color="#d62828"):
        self.arrow(p0, p1, color=color)
        vertical = abs(p1[0] - p0[0]) < abs(p1[1] - p0[1])
        dx, dy = (0.3, 0.0) if vertical else (0.0, 0.28)
        self.text((p0[0] + p1[0]) / 2 + dx, (p0[1] + p1[1]) / 2 + dy, label, color=color)

    def box(self, x, y, w, h, label, fill="#eef4fb", line="#3b6ea5"):
        self.fig.add_shape(type="rect", x0=x - w / 2, x1=x + w / 2, y0=y - h / 2, y1=y + h / 2,
                           fillcolor=fill, line=dict(color=line, width=1.6), layer="below")
        self.text(x, y, label, size=12)

    def summer(self, x, y, r=0.22, signs=("+", "−"), sign_pos=((-0.3, 0.28), (0.28, -0.32))):
        a = np.linspace(0, 2 * np.pi, 40)
        self._seg(x + r * np.cos(a), y + r * np.sin(a))
        self.text(x, y, "Σ", size=12)
        for s, (dx, dy) in zip(signs, sign_pos):
            self.text(x + dx, y + dy, s, size=12)

    def done(self, xr, yr, height=330):
        self.fig.add_trace(go.Scatter(x=self.xs, y=self.ys, mode="lines",
                                      line=dict(color=INK, width=2), hoverinfo="skip"))
        self.fig.update_xaxes(range=xr, visible=False)
        self.fig.update_yaxes(range=yr, visible=False, scaleanchor="x")
        self.fig.update_layout(height=height, showlegend=False, plot_bgcolor="white",
                               margin=dict(l=5, r=5, t=5, b=5), dragmode=False)
        return self.fig


# --------------------------------------------------------------------------
# 결선도
# --------------------------------------------------------------------------
def _armature_branch(s, x_left, x_right, top, bot, R_label="Ra", L_label="La"):
    """위쪽 선에 저항·인덕터, 오른쪽에 전기자(M)."""
    s.resistor((x_left, top), (x_left + 1.6, top), R_label, label_side=1)
    s.inductor((x_left + 1.6, top), (x_left + 3.0, top), L_label, label_side=1)
    s.wire((x_left + 3.0, top), (x_right, top))
    a_top, a_bot = s.armature(x_right, (top + bot) / 2)
    s.wire((x_right, top), a_top)
    s.wire(a_bot, (x_right, bot))
    s.text(x_right + 0.85, (top + bot) / 2, "E = Kφω", size=12)
    return a_top


def wiring_diagram(excitation: str):
    s = Sketch()
    top, bot = 2.0, -1.0
    if excitation == "separately":
        # 계자 회로 (왼쪽)
        st_, sb = s.source(0.0, 0.5, "Vf")
        s.wire(st_, (0, top), (0.6, top))
        s.resistor((0.6, top), (2.0, top), "Rfx", variable=True)
        s.wire((2.0, top), (2.6, top), (2.6, 1.7))
        s.inductor((2.6, 1.7), (2.6, 0.2), "Lf, Rf", label_side=-1)
        s.wire((2.6, 0.2), (2.6, bot), (0, bot), sb)
        s.current((2.95, 1.4), (2.95, 0.6), "If")
        s.text(1.3, -1.45, "계자 회로 (별도 전원)", size=12, color="#555")
        # 전기자 회로 (오른쪽)
        vt, vb = s.source(4.2, 0.5, "V")
        s.wire(vt, (4.2, top), (4.6, top))
        _armature_branch(s, 4.6, 8.6, top, bot)
        s.wire((8.6, bot), (4.2, bot), vb)
        s.current((7.7, top + 0.25), (8.3, top + 0.25), "Ia")
        s.text(6.4, -1.45, "전기자 회로", size=12, color="#555")
        return s.done([-1.0, 10.0], [-1.8, 2.8])
    raise NotImplementedError(excitation)


# --------------------------------------------------------------------------
# 제어 블록 다이어그램
# --------------------------------------------------------------------------
def control_block_diagram(emf_ff=True):
    s = Sketch()
    y = 0.0
    s.text(-0.1, y + 0.3, "ω*", size=14)
    s.arrow((-0.4, y), (0.38, y))
    s.summer(0.6, y)
    s.arrow((0.82, y), (1.3, y))
    s.box(2.0, y, 1.4, 0.8, "속도 PI<br>Kpω, Kiω")
    s.arrow((2.7, y), (3.1, y))
    s.box(3.8, y, 1.4, 0.8, "전류 제한<br>±I_lim")
    s.arrow((4.5, y), (5.18, y), text="")
    s.text(4.85, y + 0.32, "Ia*", size=13)
    s.summer(5.4, y)
    s.arrow((5.62, y), (6.0, y))
    s.box(6.7, y, 1.4, 0.8, "전류 PI<br>Kpi, Kii")
    s.arrow((7.4, y), (7.78, y))
    s.summer(8.0, y, signs=("+", "+"), sign_pos=((-0.3, 0.28), (0.3, 0.32)))
    s.arrow((8.22, y), (8.7, y))
    s.box(9.4, y, 1.4, 0.8, "초퍼<br>(평균값)")
    s.arrow((10.1, y), (10.7, y))
    s.text(10.4, y + 0.32, "va", size=13)
    s.box(11.6, y, 1.8, 1.0, "DC 전동기<br>(타여자)", fill="#fdf0e6", line="#c0692b")
    s.text(11.6, 1.25, "TL (부하)", size=12)
    s.arrow((11.6, 1.05), (11.6, 0.52))
    # 출력과 피드백
    s.wire((12.5, y), (13.3, y))
    s.text(13.6, y, "ω", size=14)
    s.wire((12.9, y), (12.9, -2.2), (0.6, -2.2))
    s.arrow((0.6, -2.2), (0.6, -0.22))
    s.text(6.7, -2.45, "속도 피드백 ω", size=12, color="#555")
    s.wire((12.2, -0.5), (12.2, -1.3), (5.4, -1.3))
    s.arrow((5.4, -1.3), (5.4, -0.22))
    s.text(8.8, -1.55, "전류 피드백 Ia", size=12, color="#555")
    if emf_ff:
        s.box(8.0, 1.35, 1.6, 0.6, "Kφ·ω (E 피드포워드)", fill="#eefaf0", line="#2a9d3a")
        s.arrow((8.0, 1.05), (8.0, 0.22))
    return s.done([-0.8, 14.0], [-2.8, 1.9], height=300)
