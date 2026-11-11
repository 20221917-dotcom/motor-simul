"""강의 실습(1~4장) 계산 검증: 해석해·교재 수치와 비교."""
import math

import numpy as np
import pytest

from lectures import ch1, ch2, ch3, ch4


# ---------------- 1장
def test_lambda_i_linear_region_matches_inductance_and_saturates():
    N, A, g, lc, mur = 200, 4e-4, 1e-3, 0.3, 4000.0
    L = N * N * ch1.MU0 * A / (g + lc / mur)
    assert ch1.lambda_i(0.5, N=N, A=A, g=g) == pytest.approx(L * 0.5, rel=2e-3)
    assert ch1.lambda_i(200, N=N, A=A, g=g) == pytest.approx(N * A * 1.6, rel=1e-3)     # 포화: λ → N·A·Bs


def test_force_matches_linear_formula_and_pulls_gap_closed():
    F = ch1.gap_force(1.0, 1e-3)
    assert F < 0
    assert F == pytest.approx(ch1.gap_force_linear(1.0, 1e-3), rel=5e-3)


def test_reluctance_average_torque_only_at_synchronous_speed():
    ws = 2 * math.pi * 10
    sync = ch1.reluctance_avg(10, ws, ws, 0.4, 0.01, cycles=100)
    assert sync == pytest.approx(ch1.reluctance_avg_sync(10, 0.01, 0.4), rel=1e-3)
    assert abs(ch1.reluctance_avg(10, ws, 0.8 * ws, 0.4, 0.01, cycles=100)) < 0.01 * abs(sync)


def test_double_excited_average_torque_conditions():
    # 유도: ωm = ωs − ωr 에서만 평균 토크, 조금 벗어나면 0
    on = ch1.double_excited_avg(1, 1, 1, 10, 3, 7, theta0=-1, T=200, n=2000000)
    off = ch1.double_excited_avg(1, 1, 1, 10, 3, 6, theta0=-1, T=200, n=2000000)
    assert abs(on) == pytest.approx(0.25 * math.sin(1), rel=1e-2) and abs(off) < 0.01 * abs(on)


def test_load_operating_point_and_elevator_quadrants():
    w = ch1.operating_point(ch1.LOADS[0], 140, 0.4058, 0.5, 5, 100)
    assert w == pytest.approx((140 - 0.5 * 5 / 0.4058) / 0.4058, rel=1e-6)
    assert ch1.elevator(800, 600, 1100, 1, 0.25)[3] == 1      # 사람 탄 카 상승
    assert ch1.elevator(800, 0, 1100, 1, 0.25)[3] == 2        # 빈 카 상승
    assert ch1.elevator(800, 0, 1100, -1, 0.25)[3] == 3       # 빈 카 하강
    assert ch1.elevator(800, 600, 1100, -1, 0.25)[3] == 4     # 사람 탄 카 하강
    assert ch1.reflect_gear(0.01, 0.5, 0, 0, 50, 5)[0] == pytest.approx(0.01 + 0.5 / 25)


# ---------------- 2장
def test_textbook_motor_matches_rating_and_damping():
    P = ch2.TEXTBOOK
    _, _, poles, zeta, *_ = ch2.voltage_to_speed(P)
    assert zeta == pytest.approx(0.37, abs=0.005)                       # 교재: 감쇠비 0.37 (부족감쇠)
    assert np.all(np.abs(poles.imag) > 0)
    t, V, ia, w = ch2.voltage_step(P, [(0.05, 140.0)], 0.2)
    assert w[-1] == pytest.approx((140 * P["K"]) / (P["Ra"] * P["B"] + P["K"] ** 2), rel=1e-3)
    assert w.max() > 1.2 * w[-1]                                         # 오버슈트 (진동 응답)


def test_current_pi_pole_zero_cancellation_first_order():
    P = ch2.TEXTBOOK
    wcc = 2 * math.pi * 500
    r = ch2.simulate(P, 0.02, 1e-6, i_ref=lambda t: 5.0 if t >= 0.005 else 0.0, fixed_speed=0.0, wcc=wcc)   # 전압 포화 없는 크기
    k = np.searchsorted(r["t"], 0.005 + 1 / wcc)
    assert r["ia"][k] == pytest.approx(5 * (1 - math.exp(-1)), rel=0.02)   # 시정수 1/ωcc 의 1차 응답
    os_, _ = ch2.step_metrics(r["t"], r["ia"], 5, 0.005)
    assert os_ < 0.5
    _, _, wc, pm = ch2.loop_bode(P, *ch2.current_gains(P, wcc), np.logspace(1, 6, 2000))
    assert wc == pytest.approx(wcc, rel=0.01) and pm == pytest.approx(90, abs=1)


def test_p_control_steady_state_error():
    P = ch2.TEXTBOOK
    t, i, v = ch2.rl_controller_demo(P, "P", 5.0, 0.0, i_ref=20, t_end=0.05)
    assert 20 - i[-1] == pytest.approx(20 * P["Ra"] / (P["Ra"] + 5.0), rel=1e-3)


def test_ip_controller_removes_overshoot():
    P = ch2.TEXTBOOK
    kw = dict(w_ref=lambda t: 1000 / ch2.RPM if t >= 0.01 else 0.0, wcs=2 * math.pi * 50, wcc=2 * math.pi * 1000)
    pi = ch2.simulate(P, 0.2, 2e-5, alpha=1.0, **kw)
    ip = ch2.simulate(P, 0.2, 2e-5, alpha=0.0, **kw)
    os_pi, _ = ch2.step_metrics(pi["t"], pi["w"], 1000 / ch2.RPM, 0.01)
    os_ip, _ = ch2.step_metrics(ip["t"], ip["w"], 1000 / ch2.RPM, 0.01)
    assert os_pi > 5 and os_ip < 0.5
    assert pi["w"][-1] == pytest.approx(1000 / ch2.RPM, rel=1e-3) and ip["w"][-1] == pytest.approx(1000 / ch2.RPM, rel=1e-3)


def test_antiwindup_recovers_faster():
    P = ch2.TEXTBOOK
    kw = dict(i_ref=lambda t: 40.0 if 0.005 <= t < 0.02 else 0.0, fixed_speed=1500 / ch2.RPM, Vlim=80.0)
    on = ch2.simulate(P, 0.04, 2e-6, antiwindup=True, **kw)
    off = ch2.simulate(P, 0.04, 2e-6, antiwindup=False, **kw)
    k = np.searchsorted(on["t"], 0.024)
    assert abs(on["ia"][k]) < abs(off["ia"][k])


def test_chopper_average_voltage_and_unipolar_ripple():
    for mode in ("바이폴라", "유니폴라"):
        w = ch2.chopper_waveforms(mode, 140, 70, 5000, 0.5, 5e-3, 60)
        assert np.mean(w["v"]) == pytest.approx(70, abs=1.5)
        assert np.mean(w["i"]) == pytest.approx((70 - 60) / 0.5, rel=0.05)
    b = ch2.chopper_waveforms("바이폴라", 140, 0, 5000, 0.5, 5e-3, 0)
    u = ch2.chopper_waveforms("유니폴라", 140, 70, 5000, 0.5, 5e-3, 70)
    assert np.ptp(u["i"]) < 0.5 * np.ptp(b["i"])


# ---------------- 3장
def test_bldc_ideal_shapes_give_flat_torque():
    assert ch3.ripple_percent(ch3.torque_from_shapes("사다리꼴", "120° 사각파")[3]) < 1e-6
    assert ch3.ripple_percent(ch3.torque_from_shapes("정현파", "정현파")[3]) < 1e-6
    assert ch3.ripple_percent(ch3.torque_from_shapes("정현파", "120° 사각파")[3]) > 10


def test_hall_sectors_cover_six_steps():
    codes = {tuple(int(h) for h in ch3.hall(math.radians(60 + 60 * k))) for k in range(6)}
    assert len(codes) == 6 and (0, 0, 0) not in codes and (1, 1, 1) not in codes
    for k in range(6):
        hi, lo, fl = ch3.step_info(k)
        th = math.radians(60 + 60 * k)
        assert ch3.trap(th - ch3.SHIFT["abc".index(hi)]) == pytest.approx(1)     # + 상은 역기전력 평탄부(+)
        assert ch3.trap(th - ch3.SHIFT["abc".index(lo)]) == pytest.approx(-1)


def test_bldc_switching_sim_current_balance_and_torque():
    r = ch3.simulate_bldc(1500, 0.6, "hpwm")
    assert np.max(np.abs(r["i"].sum(axis=0))) < 1e-6                 # Σi = 0
    assert np.mean(r["Te"]) > 0
    rb = ch3.simulate_bldc(1500, 0.6, "bipolar")
    assert np.mean(rb["Te"]) < np.mean(r["Te"])                        # 같은 듀티면 바이폴라 평균 전압이 낮음


def test_sensorless_zero_crossing_detection():
    r = ch3.simulate_bldc(1500, 0.6, "hpwm")
    det, true = ch3.zero_crossings(r, 0)
    assert true and det
    we = r["wm"] * r["P"]["poles"] / 2
    assert min(abs(d - t) for d in det for t in true) * we < math.radians(3)


# ---------------- 4장
def test_rotating_mmf_constant_magnitude_and_speed():
    phi = np.linspace(0, 2 * math.pi, 721)
    amps, peaks = [], []
    for t in np.linspace(0, 1 / 60, 9)[:-1]:
        _, Fs, _ = ch4.mmf(phi, t, 60, 2)
        amps.append(Fs.max()); peaks.append(phi[np.argmax(Fs)])
    assert np.allclose(amps, 1.5, atol=1e-3)
    step = np.unwrap(peaks)
    assert np.diff(step) == pytest.approx(np.full(len(step) - 1, 2 * math.pi / 8), abs=0.02)
    _, Fs1, _ = ch4.mmf(phi, 0.002, 60, 2, mode="단상 (a상만)")
    _, Fs2, _ = ch4.mmf(phi, 0.004, 60, 2, mode="단상 (a상만)")
    assert phi[np.argmax(np.abs(Fs1))] == pytest.approx(phi[np.argmax(np.abs(Fs2))], abs=0.01)   # 단상: 자리에서 교번


def test_im_circuit_matches_existing_model_and_power_balance():
    from motors.ac.induction import InductionMotor
    m = InductionMotor({s.key: s.default * (s.scale or 1) for s in InductionMotor.param_specs()})
    u = m.default_inputs()
    for s in (0.02, 0.1, 1.0):
        assert float(ch4.im_circuit(s)["T"]) == pytest.approx(float(m.torque(s, u)), rel=1e-9)
    assert ch4.max_torque() == pytest.approx(m.max_torque(u), rel=1e-9)
    r = ch4.im_circuit(0.03)
    assert float(r["Pin"]) == pytest.approx(float(r["Pcu1"] + r["Pag"]), rel=1e-9)
    assert float(r["Pag"]) == pytest.approx(float(r["Pcu2"] + r["Pmech"]), rel=1e-9)


def test_parameter_tests_recover_motor():
    est = ch4.estimate_params(ch4.run_tests())
    assert est["Rs"] == pytest.approx(ch4.IM["Rs"])
    assert est["Rr"] == pytest.approx(ch4.IM["Rr"], rel=0.1)
    assert est["Xls"] + est["Xlr"] == pytest.approx(ch4.IM["Xls"] + ch4.IM["Xlr"], rel=0.03)
    assert est["Xm"] == pytest.approx(ch4.IM["Xm"], rel=0.02)


def test_sync_motor_power_and_torque_formula():
    Vs, Ef, Xs, d = 220, 250, 5.0, math.radians(30)
    r = ch4.sync_phasor(Vs, Ef, d, Xs)
    assert r["P"] == pytest.approx(3 * Vs * Ef / Xs * math.sin(d), rel=1e-9)
    ws = 2 * math.pi * 60 / 2
    r2 = ch4.sync_phasor(Vs, Ef, d, 5.0, 3.0)
    Tf, Tr = ch4.sync_torque(d, Vs, Ef, 5.0, 3.0, ws)
    assert r2["P"] == pytest.approx((Tf + Tr) * ws, rel=1e-9)
    # 과여자 → 진상(Q < 0), 부족여자 → 지상(Q > 0)
    assert ch4.sync_phasor(Vs, 300, d, Xs)["Q"] < 0 < ch4.sync_phasor(Vs, 150, d, Xs)["Q"]


def test_speed_regions_constant_torque_then_power():
    R = ch4.speed_regions(npts=24)
    ns = 1800
    low = R["T"][(R["n"] > 0.3 * ns) & (R["n"] < 0.9 * ns)]
    assert np.ptp(low) / np.mean(low) < 0.05                           # 기저 속도 이하: 토크 일정
    assert R["T"][-1] < 0.5 * np.mean(low)                             # 고속: 토크 감소


# ---------------- 슬라이드 그림 보강분
def test_textbook_values_from_mfile_and_example2():
    assert ch2.TEXTBOOK["K"] == pytest.approx(3336 / (3000 * 2 * math.pi / 60) / 25)
    _, _, poles, zeta, *_ = ch2.voltage_to_speed(ch2.EXAMPLE2)
    assert poles[0].real == pytest.approx(-75.2941, abs=1e-3) and abs(poles[0].imag) == pytest.approx(281.63, abs=0.05)
    assert zeta == pytest.approx(0.2583, abs=1e-3)
    _, _, z, _ = ch2.pi_speed_decomposition(ch2.TEXTBOOK, 2 * math.pi * 50, np.linspace(0, 0.05, 50))
    assert z == pytest.approx(math.sqrt(5) / 2)                       # 교재: ζ = √5/2


def test_linear_machine_energy_paths_linear_region():
    # 선형 영역에서 느린 이동의 기계적 에너지 = ½ i² ΔL, 빠른 이동은 그보다 작음
    p = ch1.linear_machine_paths(0.5, 2e-3, 1e-3)
    L1 = p["A"][1] / 0.5; L2 = p["B"][1] / 0.5
    assert p["W_slow"] == pytest.approx(0.5 * 0.25 * (L2 - L1), rel=1e-2)
    assert 0 < p["W_fast"] < p["W_slow"]


def test_stability_margins_and_closed_loop():
    w = np.logspace(-2, 3, 3000)
    *_, num_s, den_s = ch2.generic_loop(2.0, 2, 10, w)
    *_, num_u, den_u = ch2.generic_loop(30.0, 2, 10, w)
    t = np.linspace(0, 20, 2000)
    assert abs(ch2.closed_loop_step(num_s, den_s, t)[-1] - 1) < 0.02
    assert np.max(np.abs(ch2.closed_loop_step(num_u, den_u, t))) > 5   # 이득이 너무 크면 발산
    _, _, wc, pm, w180, gm, *_ = ch2.generic_loop(2.0, 2, 10, w)
    assert pm > 0 and gm > 0


def test_chopper_drive_reaches_speed_with_ripple():
    d = ch2.simulate_chopper_drive(ch2.TEXTBOOK, t_end=0.2)
    assert d["w"][-1] * ch2.RPM == pytest.approx(2500, rel=0.01)
    assert np.max(d["Te"][(d["t"] > 0.06) & (d["t"] < 0.09)]) == pytest.approx(ch2.TEXTBOOK["K"] * 25, rel=0.15)   # 토크 제한


def test_bldc_drive_current_control_limits_current():
    a = ch3.simulate_bldc_drive(2000, "전류 제어")
    b = ch3.simulate_bldc_drive(2000, "전압(듀티) 제어")
    assert a["rpm"][-1] == pytest.approx(2000, rel=0.05) and b["rpm"][-1] == pytest.approx(2000, rel=0.05)
    assert np.max(np.abs(a["i"])) < 0.5 * np.max(np.abs(b["i"]))      # 전류 제어는 기동 과전류가 작음


def test_winding_factor_and_deep_bar():
    th = np.linspace(0, 2 * math.pi, 1440, endpoint=False)
    for q in (1, 2, 3):
        _, _, kd, _ = ch4.winding_mmf(th, q, "3상")
        g = math.pi / (3 * q)
        assert kd == pytest.approx(math.sin(q * g / 2) / (q * math.sin(g / 2)))
    thd = [ch4.winding_mmf(th, q, "3상")[3] for q in (1, 2, 3)]
    assert thd[0] > thd[1] > thd[2]
    assert float(ch4.deep_bar_ratio(1.0)) == pytest.approx(1.0, abs=0.01) and float(ch4.deep_bar_ratio(60.0)) > 2


def test_vf_closed_loop_tracks_with_load():
    r = ch4.vf_closed_loop([(0, 0), (0.2, 1200)], [(0, 0), (2.0, 40)])
    assert r["n"][-1] == pytest.approx(1200, abs=2)
    assert 0 < r["fr"][-1] <= 3.0 and r["fs"][-1] == pytest.approx(1200 * 2 / 60 + r["fr"][-1], abs=0.05)
