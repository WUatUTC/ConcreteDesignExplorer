"""Mixed-bar geometry, exact strain compatibility and bending-direction regression."""
import pytest
from concrete.aci318 import REBAR, Materials
from concrete.layout import BarGroup, build_layout, bar_depths_from_compression
from concrete.flexure import Section, analyze
from concrete.design import candidates_for_section


def layout(bending="Positive", second=True, gap=None):
    groups=[[BarGroup("#8",3),BarGroup("#6",1)]]
    if second:
        groups.append([BarGroup("#7",2)])
    return build_layout(14,26,1.5,REBAR["#3"][0],groups,bending,0.75,gap)


def section_from_layout(l):
    return Section(b=14,h=26,d=l.d,as_t=l.as_t,bending=l.bending,
                   tension_bars=bar_depths_from_compression(l,26))


def test_one_layer_reproduces_standard_effective_depth():
    l=build_layout(12,24,1.5,.375,[[BarGroup("#8",3)]])
    assert l.valid
    assert l.d==pytest.approx(21.625)
    assert l.d_extreme==pytest.approx(21.625)
    assert l.as_t==pytest.approx(2.37)
    s=Section(b=12,h=24,d=l.d,as_t=l.as_t,tension_bars=bar_depths_from_compression(l,24))
    older=Section(b=12,h=24,d=l.d,as_t=l.as_t)
    assert analyze(s,Materials()).mn_kft==pytest.approx(analyze(older,Materials()).mn_kft)


def test_mixed_sizes_two_layers_centroid_and_extreme_depth():
    l=layout()
    assert l.valid and len(l.layers)==2 and len(l.bars)==6
    expected_area=3*.79+.44+2*.60
    assert l.as_t==pytest.approx(expected_area)
    y1=26-(1.5+.375+.5)
    y2=y1-(.5+1+.875/2)  # conservative gap: max(1, db)
    expected_centroid=((3*.79+.44)*y1+(2*.60)*y2)/expected_area
    assert l.centroid_y==pytest.approx(expected_centroid)
    assert l.d==pytest.approx(expected_centroid)
    assert l.d_extreme==pytest.approx(y1)
    assert l.vertical_clear==pytest.approx(1)
    assert all(abs(x.x-y.x)<1e-9 for x in l.bars[4:] for y in l.bars[:4] if abs(x.x-y.x)<1e-9)
    assert all(any(abs(upper.x-lower.x)<1e-9 for lower in l.bars[:4]) for upper in l.bars[4:])


def test_negative_bending_mirrors_positions_not_capacity():
    pos=layout("Positive")
    neg=layout("Negative")
    assert pos.valid and neg.valid
    assert neg.d==pytest.approx(pos.d)
    assert neg.centroid_y==pytest.approx(26-pos.centroid_y)
    assert sorted(b.y for b in neg.bars)==pytest.approx(sorted(26-b.y for b in pos.bars))
    rp=analyze(section_from_layout(pos),Materials())
    rn=analyze(section_from_layout(neg),Materials())
    assert rp.mn_kft==pytest.approx(rn.mn_kft)
    assert rp.phi_mn_kft==pytest.approx(rn.phi_mn_kft)
    assert rp.strain_t==pytest.approx(rn.strain_t)
    assert rp.equilibrium_error<1e-7 and rn.equilibrium_error<1e-7


def test_layered_analysis_uses_extreme_strain_not_centroid():
    l=layout()
    r=analyze(section_from_layout(l),Materials())
    assert r.strain_t==pytest.approx(.003*(l.d_extreme-r.c)/r.c)
    assert r.strain_t>.003*(l.d-r.c)/r.c
    assert r.tension==pytest.approx(r.cc+r.cs_net,abs=1e-8)


def test_conservative_vertical_clear_limit_and_horizontal_clear_limit():
    two_big=[[BarGroup("#11",2)],[BarGroup("#11",2)]]
    too_close=build_layout(18,30,1.5,.375,two_big,vertical_clear=1.0)
    assert too_close.required_vertical_clear==pytest.approx(1.410)
    assert not too_close.valid and any("Vertical clear spacing" in x for x in too_close.issues)
    okay=build_layout(18,30,1.5,.375,two_big,vertical_clear=1.41)
    assert okay.valid
    narrow=build_layout(8,24,1.5,.375,[[BarGroup("#8",5)]])
    assert not narrow.valid and any("horizontal clear" in x for x in narrow.issues)


def test_too_many_second_layer_bars_produces_alignment_flag():
    l=build_layout(20,30,1.5,.375,[[BarGroup("#6",2)],[BarGroup("#6",3)]])
    assert not l.valid and any("directly above" in i for i in l.issues)


def test_no_false_tbeam_negative_compression_flange():
    with pytest.raises(ValueError,match="positive bending"):
        Section(kind="T-beam (+M)",b=12,bf=36,hf=4,bending="Negative")


def test_invalid_bar_area_centroid_mismatch_rejected():
    with pytest.raises(ValueError,match="match"):
        Section(b=12,h=24,d=21.5,as_t=3,tension_bars=((1.,21.5),(1.,21.5)))
    with pytest.raises(ValueError,match="match"):
        Section(b=12,h=24,d=21.5,as_t=2.,tension_bars=((1.,20),(1.,21)))


def test_negative_auto_candidates():
    m=Materials()
    positive=candidates_for_section(220,12,24,m,1.5,.375)
    negative=candidates_for_section(220,12,24,m,1.5,.375,bending="Negative")
    assert positive and negative
    assert [c.label for c in positive]==[c.label for c in negative]
    assert [c.result.phi_mn_kft for c in positive]==pytest.approx([c.result.phi_mn_kft for c in negative])


def test_diagram_compression_block_flips_to_bottom_for_negative_moment():
    from concrete.visuals import section_figure, interaction_charts
    for bending in ("Positive","Negative"):
        lay=layout(bending)
        sec=section_from_layout(lay)
        result=analyze(sec,Materials())
        figure=section_figure(sec,result,lay)
        compression_shape=figure.layout.shapes[1]
        if bending=="Positive":
            assert compression_shape.y0==pytest.approx(0)
            assert compression_shape.y1==pytest.approx(result.a)
        else:
            assert compression_shape.y0==pytest.approx(26-result.a)
            assert compression_shape.y1==pytest.approx(26)
        assert len(figure.data[0].x)==len(lay.bars)
        sensitivity=interaction_charts(sec,Materials(),result)
        assert len(sensitivity)==2