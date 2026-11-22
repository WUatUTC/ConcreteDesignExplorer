import math
import pytest
from concrete.aci318 import Materials, REBAR, effective_depth, clear_bar_spacing, minimum_beam_steel, strength_reduction_factor
from concrete.flexure import Section, analyze
from concrete.design import candidates_for_section, preliminary_size


def test_beta1_and_strain_limits():
    assert Materials(fc=4).beta1 == pytest.approx(.85)
    assert Materials(fc=6).beta1 == pytest.approx(.75)
    assert Materials(fc=8).beta1 == pytest.approx(.65)
    assert Materials(fc=10).beta1 == pytest.approx(.65)
    m = Materials()
    assert strength_reduction_factor(m.yield_strain+.003,m)[0] == pytest.approx(.9)
    assert strength_reduction_factor(m.yield_strain,m)[0] == pytest.approx(.65)
    assert strength_reduction_factor(m.yield_strain+.0015,m)[0] == pytest.approx(.775)


def test_yielding_rectangular_closed_form():
    m=Materials(fc=4,fy=60)
    sec=Section(b=12,h=24,d=21.5,as_t=2.37)
    r=analyze(sec,m)
    a=sec.as_t*m.fy/(.85*m.fc*sec.b)
    exact_mn=sec.as_t*m.fy*(sec.d-a/2)/12
    assert r.a==pytest.approx(a,rel=1e-10)
    assert r.mn_kft==pytest.approx(exact_mn,rel=1e-10)
    assert r.stress_t==pytest.approx(60)
    assert r.control=="Tension-controlled"
    assert r.equilibrium_error<1e-8


def test_overreinforced_reduces_phi_and_stress():
    m=Materials()
    r=analyze(Section(as_t=8.0),m)
    assert r.stress_t<m.fy
    assert r.control=="Compression-controlled"
    assert r.phi==pytest.approx(.65)


def test_tbeam_both_stress_block_cases():
    m=Materials()
    a=analyze(Section(kind="T-beam (+M)",b=12,bf=36,hf=4,h=24,d=21.5,as_t=3),m)
    assert "Case 1" in a.case and a.a<=4
    assert a.cc==pytest.approx(3*60)
    b=analyze(Section(kind="T-beam (+M)",b=12,bf=36,hf=4,h=24,d=21.5,as_t=10),m)
    assert "Case 2" in b.case and b.a>4
    assert b.equilibrium_error<1e-7
    # For case 2, equivalent flange + web concrete compression sum
    assert b.cc==pytest.approx(.85*4*(12*b.a+(36-12)*4))


def test_doubly_reinforced_equilibrium_and_force_reduction():
    m=Materials()
    s=Section(as_t=4.0,as_c=2.0,dp=2.375)
    r=analyze(s,m)
    assert r.strain_c_steel>0
    assert r.cs_net==pytest.approx(s.as_c*(r.stress_c_steel-.85*m.fc))
    assert r.tension==pytest.approx(r.cc+r.cs_net)
    assert r.equilibrium_error<1e-7
    r_singly=analyze(Section(as_t=4.0),m)
    assert r.strain_t>r_singly.strain_t


def test_aci_min_steel_ksi_units():
    m=Materials(fc=4,fy=60)
    d=21.5; bw=12
    assert minimum_beam_steel(bw,d,m)==pytest.approx(max(3*math.sqrt(4000)/60000,200/60000)*bw*d)


def test_effective_depth_spacing():
    d=effective_depth(24,1.5,REBAR['#3'][0],REBAR['#8'][0])
    assert d==pytest.approx(21.625)
    clear=clear_bar_spacing(12,3,1,1.5,.375)
    assert clear==pytest.approx((12-2*(1.5+.375)-3)/2)


def test_fixed_and_unknown_design_find_limited_solutions():
    m=Materials()
    cs=candidates_for_section(220,12,24,m,1.5,.375)
    assert cs
    assert all(c.result.control=="Tension-controlled" for c in cs)
    assert all(c.result.phi_mn_kft>=220 for c in cs)
    assert all(c.as_t>=c.result.as_min for c in cs)
    p=preliminary_size(250,m)
    assert p.candidate is not None
    assert p.candidate.result.phi_mn_kft>=250
    assert p.rho_trial==pytest.approx(.85*m.fc*m.beta1*(.003/(.003+.0075))/m.fy)


def test_validation():
    with pytest.raises(ValueError):
        Section(b=12,h=20,d=22,as_t=1)
    with pytest.raises(ValueError):
        Section(kind='T-beam (+M)',b=12,bf=10,hf=4)
    with pytest.raises(ValueError):
        preliminary_size(200,Materials(),strain_target=.003)
