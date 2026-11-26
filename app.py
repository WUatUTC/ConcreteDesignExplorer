"""Concrete Design Explorer — public interactive reinforced-concrete flexure lab.

Selected ACI 318-19 calculations; original figures and deterministic Python engine.
The teaching UI and verified calculation functions are kept separate.
"""

import pandas as pd
import streamlit as st

from concrete.aci318 import (
    Materials,
    REBAR,
    clear_bar_spacing,
    effective_depth,
    required_horizontal_clear_spacing,
)
from concrete.design import candidates_for_section, preliminary_size
from concrete.flexure import Section, analyze
from concrete.visuals import interaction_charts, section_figure
from concrete.layout import BarGroup, BarLayout, build_layout, bar_depths_from_compression

st.set_page_config(
    page_title="Concrete Design Explorer",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """<style>
    .block-container {padding-top: 1.55rem; padding-bottom: 2.5rem; max-width: 1280px;}
    [data-testid="stSidebar"] [data-testid="stPageLink"] a {font-weight: 500;}
    [data-testid="stVerticalBlockBorderWrapper"] {border-radius: 0.75rem;}
    h1, h2, h3 {letter-spacing: -0.02em;}
    </style>""",
    unsafe_allow_html=True,
)


def page_header(title: str, description: str) -> None:
    st.title(title)
    st.caption(description)


def section_metrics(s: Section, r, mu=None, layout_valid=True) -> None:
    """Present the limited flexural results and their important qualifications."""
    a, b, c, d = st.columns(4)
    a.metric("Nominal strength, Mn", f"{r.mn_kft:,.1f} kip-ft")
    b.metric("Design strength, φMn", f"{r.phi_mn_kft:,.1f} kip-ft")
    c.metric("Extreme steel strain, εt", f"{r.strain_t:.5f}")
    d.metric("Reduction factor, φ", f"{r.phi:.3f}")

    if r.control == "Tension-controlled":
        st.success(
            f"**{r.control}:** εt ≥ εty + 0.003 = "
            f"{m.yield_strain + .003:.5f} (ACI 318-19, Table 21.2.2)."
        )
    else:
        st.warning(
            f"**{r.control}:** Shown to explore behavior; this does not satisfy "
            "the tension-controlled beam requirement in ACI 318-19 §9.3.3.1."
        )
    if s.as_t + 1e-8 < r.as_min:
        st.warning(
            f"Provided As = {s.as_t:.3f} in² is below the calculated minimum "
            f"As,min = {r.as_min:.3f} in² (ACI §9.6.1.2; the §9.6.1.3 "
            "exception is not assessed)."
        )
    if r.strain_c_steel < 0 and s.as_c:
        st.warning("Compression-face steel is in tension at nominal strength; it is not acting as compression reinforcement.")

    if mu is not None:
        if r.phi_mn_kft >= mu and r.control == "Tension-controlled" and s.as_t >= r.as_min and layout_valid:
            st.info(
                f"**Limited flexural check satisfied:** φMn = {r.phi_mn_kft:.1f} ≥ "
                f"Mu = {mu:.1f} kip-ft. Other design checks remain outstanding."
            )
        else:
            st.error(
                "**Limited flexural check not satisfied:** review strength, "
                "minimum reinforcement, tension-control, or reinforcement spacing requirements."
            )


def detail_panel(r) -> None:
    with st.expander("View equations, equilibrium forces, and ACI references"):
        st.latex(r"\varepsilon_t=0.003\frac{d-c}{c},\qquad a=\beta_1c")
        st.latex(r"T=A_s f_s,\quad C_c=0.85f'_c\times (\text{equivalent stress-block area})")
        st.latex(r"\sum F=0:\quad T=C_c+C'_s;\qquad \phi M_n\geq M_u")
        st.write(
            "The solver uses strain-compatible axial equilibrium, with bisection "
            "for neutral-axis depth. Longitudinal-steel stresses are limited "
            "to ±fy, and displaced concrete is considered when upper steel "
            "lies inside the equivalent compression block."
        )
        vals = {
            "Neutral-axis depth c (in)": r.c,
            "Whitney block depth a (in)": r.a,
            "Concrete compression Cc (kip)": r.cc,
            "Net upper-steel compression C's (kip)": r.cs_net,
            "Tension steel force T (kip)": r.tension,
            "Extreme tension steel stress fs (ksi)": r.stress_t,
            "Compression-side steel stress f's (ksi)": r.stress_c_steel,
            "As,min (in²)": r.as_min,
            "Equilibrium residual (kip)": r.equilibrium_error,
        }
        st.dataframe(
            pd.DataFrame([{"Quantity": key, "Result": round(val, 6)} for key, val in vals.items()]),
            use_container_width=True,
            hide_index=True,
        )
        st.write("**Analysis case:**", r.case)
        st.caption(
            "Selected references: ACI 318-19 §9.3.3.1, §9.6.1.2, "
            "Table 21.2.2, §22.2.2, Table 22.2.2.4.3. "
            "Consult the official ACI code for full requirements."
        )


def show_diagrams(s: Section, r, layout=None) -> None:
    left, right = st.columns([1, 1.12], gap="large")
    with left:
        st.markdown("#### Section and stress block")
        st.plotly_chart(section_figure(s, r, layout=layout), use_container_width=True)
        st.caption("Dark circles: tension steel. Blue shading: compression block. Dashed line: neutral axis. Reinforcement layout is schematic; verify all constructability and detailing requirements.")
    with right:
        st.markdown("#### Reinforcement sensitivity")
        f1, f2 = interaction_charts(s, m, r)
        st.plotly_chart(f1, use_container_width=True)
        st.plotly_chart(f2, use_container_width=True)
        if layout is not None:
            st.caption("Sensitivity curves hold the bar depths fixed and scale steel areas continuously for teaching; intermediate points are not discrete constructible bar arrangements.")




def bending_selector(key: str) -> str:
    return st.radio("Bending direction", ["Positive", "Negative"], horizontal=True,
                    key=key, help="Positive (+M): bottom steel in tension. Negative (−M): TOP steel in tension; compression is at the bottom.")


def reinforcement_editor(prefix: str, b: float, h: float, cover: float,
                         stirrup_db: float, aggregate: float,
                         bending: str) -> BarLayout:
    """Two bar-size groups per row, one or two physically detailed layers."""
    st.markdown(f"**Tension reinforcement — {'bottom' if bending == 'Positive' else 'TOP'} face**")
    two = st.toggle("Use two layers", value=False, key=f"{prefix}_two")
    groups = []
    for layer in range(1, 3 if two else 2):
        st.caption(f"Layer {layer} · {'nearest tension face' if layer == 1 else 'toward compression face'}")
        a,b1,c,d = st.columns([1,1,1,1])
        with a:
            count1 = st.number_input("Bar count A", 1, 10, 3 if layer == 1 else 2,
                                     key=f"{prefix}_L{layer}_n1")
        with b1:
            size1 = st.selectbox("Bar size A", list(REBAR)[1:], index=4 if layer == 1 else 3,
                                 key=f"{prefix}_L{layer}_s1")
        with c:
            count2 = st.number_input("Bar count B (optional)", 0, 10, 0,
                                     key=f"{prefix}_L{layer}_n2")
        with d:
            size2 = st.selectbox("Bar size B", list(REBAR)[1:], index=3,
                                 key=f"{prefix}_L{layer}_s2")
        groups.append([BarGroup(size1,int(count1))]+([BarGroup(size2,int(count2))] if count2 else []))
    user_gap = None
    if two:
        maximum = max(REBAR[g.designation][0] for row in groups for g in row)
        required = max(1.0, maximum)
        col1,col2=st.columns([1,2])
        with col1:
            user_gap = st.number_input("Clear distance between layers (in)",0.0,10.0,
                                       float(round(required,3)),step=0.125,key=f"{prefix}_gap")
        with col2:
            st.caption(f"Minimum used in this tool: max(1 in, largest bar diameter) = {required:.3f} in. ACI 318-19 §25.2.2 specifies at least 1 in and vertical alignment; the diameter-based minimum here is deliberately more conservative.")
    return build_layout(b,h,cover,stirrup_db,groups,bending,aggregate,user_gap)


def layout_summary(layout: BarLayout) -> None:
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Total As",f"{layout.as_t:.3f} in²")
    c2.metric("Steel centroid from top",f"{layout.centroid_y:.3f} in")
    c3.metric("Effective depth d",f"{layout.d:.3f} in")
    c4.metric("Extreme steel depth",f"{layout.d_extreme:.3f} in")
    if len(layout.layers)==2:
        st.caption(f"Actual clear spacing between reinforcement layers: {layout.vertical_clear:.3f} in; specified minimum: {layout.required_vertical_clear:.3f} in.")
    st.dataframe(pd.DataFrame([{"Row":x.number,"Bars":x.count,"Center from top (in)":round(x.y,3),
                              "As (in²)":round(x.total_area,3),"Horizontal clear (in)":round(x.clear_horizontal,3),
                              "Minimum (in)":round(x.minimum_horizontal,3)} for x in layout.layers]),
                 hide_index=True,use_container_width=True)
    if layout.issues:
        for issue in layout.issues:
            st.error("Detailing alert: "+issue)
        st.warning("Strength may be calculated for exploration, but a nonconforming layout cannot be accepted as a beam design.")
    else:
        st.success("Selected horizontal and vertical bar-spacing/fit checks satisfied (other ACI detailing checks still required).")


def compression_steel_editor(prefix: str, b: float, cover: float, stirrup_db: float,
                             aggregate: float, bending: str):
    st.markdown(f"**Additional reinforcement on the compression side ({'top' if bending == 'Positive' else 'bottom'})**")
    a,b1,c,d=st.columns(4)
    with a: n1=st.number_input("Compression bars A",2,8,2,key=f"{prefix}_cn1")
    with b1: size1=st.selectbox("Compression size A",list(REBAR)[1:],index=3,key=f"{prefix}_cs1")
    with c: n2=st.number_input("Compression bars B",0,8,0,key=f"{prefix}_cn2")
    with d: size2=st.selectbox("Compression size B",list(REBAR)[1:],index=2,key=f"{prefix}_cs2")
    sizes=[size1]*n1 + ([size2]*n2 if n2 else [])
    area=sum(REBAR[size][1] for size in sizes)
    dp=cover+stirrup_db+max(REBAR[size][0] for size in sizes)/2
    inside=b-2*(cover+stirrup_db)
    clear=(inside-sum(REBAR[size][0] for size in sizes))/(len(sizes)-1)
    req=max(required_horizontal_clear_spacing(REBAR[size][0],aggregate) for size in sizes)
    valid=clear+1e-9>=req
    st.caption(f"Compression-side As′ = {area:.3f} in²; d′ = {dp:.3f} in from compression face; clear spacing = {clear:.3f} in (required ≥ {req:.3f} in).")
    if not valid: st.error("Compression-side reinforcement does not satisfy the horizontal spacing check.")
    return area,dp,valid


def section_from_layout(b: float,h: float,layout: BarLayout,kind: str="Rectangular",
                        bf: float=0.0,hf: float=0.0,as_c: float=0.0,dp: float=2.375):
    return Section(b=b,h=h,d=layout.d,as_t=layout.as_t,kind=kind,bf=bf,hf=hf,
                   as_c=as_c,dp=dp,bending=layout.bending,
                   tension_bars=bar_depths_from_compression(layout,h))


def home() -> None:
    page_header(
        "Concrete Design Explorer",
        "Interactive reinforced-concrete flexure · ACI 318-19 · US customary units",
    )
    st.write(
        "Explore how section geometry, material strengths, and reinforcement "
        "affect beam behavior and flexural design. Adjust parameters, interpret "
        "the visualizations, and inspect the underlying engineering equations."
    )

    st.markdown("### Explore the tools")
    first = st.columns(3, gap="medium")
    with first[0]:
        with st.container(border=True):
            st.markdown("#### 📊 Flexural analysis")
            st.write("Analyze rectangular beams under positive or negative bending and T-beams under positive bending.")
            st.page_link(PAGES["analysis"], label="Open analysis", icon=":material/arrow_forward:")
    with first[1]:
        with st.container(border=True):
            st.markdown("#### 📐 Beam design")
            st.write("Compare mixed-size bars and one- or two-layer arrangements for known dimensions and moment demand.")
            st.page_link(PAGES["design"], label="Design reinforcement", icon=":material/arrow_forward:")
    with first[2]:
        with st.container(border=True):
            st.markdown("#### 📏 Preliminary sizing")
            st.write("Estimate practical section dimensions, then check candidate reinforcement.")
            st.page_link(PAGES["sizing"], label="Start sizing", icon=":material/arrow_forward:")

    with st.container(border=True):
        l, r = st.columns([2, 1], gap="large")
        with l:
            st.markdown("#### 🎛️ What-if design studio")
            st.write(
                "Move reinforcement and geometry sliders to test a key question: "
                "**Does more tension steel always increase design strength and ductility?**"
            )
        with r:
            st.page_link(PAGES["studio"], label="Open design studio", icon=":material/arrow_forward:")

    lower = st.columns([1.2, 1], gap="medium")
    with lower[0]:
        with st.container(border=True):
            st.markdown("#### Suggested learning sequence")
            st.write("**1. Predict** what will change before adjusting a parameter.")
            st.write("**2. Explore** the strain diagram, nominal strength, and design strength.")
            st.write("**3. Explain** the behavior using equilibrium, compatibility, and ACI provisions.")
    with lower[1]:
        with st.container(border=True):
            st.markdown("#### Scope and reference")
            st.write("Based on selected ACI 318-19 flexural provisions and topics from James K. Wight, *Reinforced Concrete: Mechanics and Design*, 8th ed.")
            st.caption("An educational exploration tool, not a complete code-compliant member-design program.")
            st.page_link(PAGES["scope"], label="View limitations and roadmap", icon=":material/info:")


def flexural_analysis() -> None:
    page_header("Flexural analysis", "Analyze an existing beam section with mixed bar sizes, one or two layers, and either bending direction.")
    with st.container(border=True):
        st.markdown("### 1 · Define the section and bending direction")
        bending=bending_selector("analysis_bending")
        kind=st.radio("Section geometry",["Rectangular","T-beam (+M)"] if bending=="Positive" else ["Rectangular"], horizontal=True,key="analysis_kind")
        c1,c2,c3=st.columns(3)
        with c1:
            b=st.number_input("Beam width b / web width bw (in)",6.0,60.0,12.0,step=1.0,key="analysis_b")
            h=st.number_input("Overall beam height h (in)",10.0,72.0,24.0,step=1.0,key="analysis_h")
        with c2:
            cover=st.number_input("Clear cover to outer stirrup (in)",.75,4.0,1.5,step=.25,key="analysis_cover")
            stirrup=st.selectbox("Stirrup bar size",["#3","#4"],key="analysis_stirrup")
        with c3:
            agg=st.number_input("Max coarse aggregate size (in)",.375,1.5,.75,step=.125,key="analysis_agg")
            as_mode=st.radio("Tension steel representation",["Select rebars (1–2 layers)","Enter As and d"],key="analysis_mode")
        bf=hf=0.0
        if kind=="T-beam (+M)":
            t1,t2=st.columns(2)
            with t1: bf=st.number_input("Effective flange width bf (in)",b,180.0,max(36.0,b),step=2.0,key="analysis_bf")
            with t2: hf=st.number_input("Flange thickness hf (in)",2.0,max(2.1,h-.5),min(5.0,h-1),step=.5,key="analysis_hf")
            st.caption("The compression flange is modeled for positive bending only; enter bf after verifying ACI §6.3.2.")
        layout=None
        if as_mode.startswith("Select"):
            layout=reinforcement_editor("analysis",b,h,cover,REBAR[stirrup][0],agg,bending)
            layout_summary(layout)
        else:
            x1,x2=st.columns(2)
            with x1: as_t=st.number_input("Total tensile steel As (in²)",.1,45.0,3.0,step=.1,key="analysis_as")
            with x2: d=st.number_input("Steel centroid depth d from compression face (in)",1.0,h-.1,min(21.5,h-.2),step=.25,key="analysis_d")
            st.info("This option does not validate rebar spacing or determine extreme-layer steel strain; enter discrete bars for two-layer analysis.")
        doubly=st.checkbox("Include reinforcement on compression side",value=False,key="analysis_doubly")
        as_c,dp,comp_valid=0.0,2.375,True
        if doubly:
            as_c,dp,comp_valid=compression_steel_editor("analysis",b,cover,REBAR[stirrup][0],agg,bending)
    with st.container(border=True):
        st.markdown("### 2 · Factored moment demand")
        mu=st.number_input("Optional |Mu| (kip-ft)",0.0,3000.0,200.0,step=10.0,key="analysis_mu")
    try:
        s=section_from_layout(b,h,layout,kind,bf,hf,as_c,dp) if layout else Section(
            b=b,h=h,d=d,as_t=as_t,kind=kind,bf=bf,hf=hf,as_c=as_c,dp=dp,bending=bending)
        r=analyze(s,m)
        with st.container(border=True):
            st.markdown("### 3 · Strength, strain, and detailing checks")
            section_metrics(s,r,mu if mu>0 else None,layout_valid=(layout.valid if layout else True) and comp_valid)
        with st.container(border=True):
            st.markdown("### 4 · Visual interpretation")
            show_diagrams(s,r,layout=layout)
            detail_panel(r)
    except ValueError as ex:
        st.error(f"Check your inputs: {ex}")


def beam_design() -> None:
    page_header("Beam design · Known dimensions", "Evaluate mixed-size, one- or two-layer reinforcement and compare with single-layer design alternatives.")
    with st.container(border=True):
        st.markdown("### 1 · Design inputs")
        bending=bending_selector("design_bending")
        c1,c2,c3=st.columns(3,gap="large")
        with c1:
            b=st.number_input("Beam width b (in)",8.0,40.0,12.0,step=1.0,key="design_b")
            h=st.number_input("Beam height h (in)",12.0,60.0,24.0,step=1.0,key="design_h")
        with c2:
            mu=st.number_input("Factored |Mu| (kip-ft)",10.0,2500.0,220.0,step=10.0,key="design_mu")
            cover=st.number_input("Clear cover to outer stirrup (in)",.75,4.0,1.5,step=.25,key="design_cover")
        with c3:
            agg=st.number_input("Max aggregate size (in)",.375,1.5,.75,step=.125,key="design_agg")
            stirrup=st.selectbox("Stirrup bar size",["#3","#4"],key="design_stirrup")
        doubly=st.checkbox("Include compression-side steel",value=False,key="design_doubly")
        as_c,dp,comp_valid=0.0,2.375,True
        if doubly:
            as_c,dp,comp_valid=compression_steel_editor("design",b,cover,REBAR[stirrup][0],agg,bending)
    tab_manual,tab_options=st.tabs(["Manual layout · mixed bars / 1–2 layers","Single-layer design suggestions"])
    with tab_manual:
        with st.container(border=True):
            st.markdown("### 2 · Build and check reinforcement")
            layout=reinforcement_editor("design",b,h,cover,REBAR[stirrup][0],agg,bending)
            layout_summary(layout)
            try:
                s=section_from_layout(b,h,layout,as_c=as_c,dp=dp)
                r=analyze(s,m)
                section_metrics(s,r,mu,layout_valid=layout.valid and comp_valid)
                st.plotly_chart(section_figure(s,r,layout=layout),use_container_width=True)
                detail_panel(r)
            except ValueError as ex:
                st.error(f"Check your reinforcement inputs: {ex}")
    with tab_options:
        with st.container(border=True):
            st.markdown("### 2 · Automatic single-layer suggestions")
            st.caption("Suggestions use one size per row. Use the Manual layout tab for mixed sizes and two-layer detailing.")
            try:
                options=candidates_for_section(mu,b,h,m,cover,REBAR[stirrup][0],agg,as_c,dp,bending=bending)
                st.metric("Candidates satisfying limited checks",len(options))
                if options:
                    rows=[{"Option":c.label,"As (in²)":round(c.as_t,2),"d (in)":round(c.d,2),
                           "Clear spacing (in)":round(c.clear,2),"εt":round(c.result.strain_t,5),
                           "φMn (kip-ft)":round(c.result.phi_mn_kft,1)} for c in options[:12]]
                    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
                    st.download_button("Export table (CSV)",data=pd.DataFrame(rows).to_csv(index=False).encode(),
                                       file_name="beam_flexure_candidates.csv",mime="text/csv",icon=":material/download:")
                    selected=st.selectbox("Inspect alternative",range(min(12,len(options))),
                                          format_func=lambda i:f"{options[i].label} · φMn {options[i].result.phi_mn_kft:.1f} kip-ft",
                                          key="design_selected")
                    c=options[selected]
                    sec=Section(b=b,h=h,d=c.d,as_t=c.as_t,as_c=as_c,dp=dp,bending=bending)
                    section_metrics(sec,c.result,mu,layout_valid=comp_valid)
                    st.plotly_chart(section_figure(sec,c.result),use_container_width=True)
                    detail_panel(c.result)
                else:
                    st.warning("No one-layer candidate found in the current limited search. Try a mixed-size or two-layer arrangement in the Manual layout tab.")
            except ValueError as ex:
                st.error(f"Check your design inputs: {ex}")


def preliminary_sizing() -> None:
    page_header(
        "Preliminary member sizing",
        "Estimate rectangular beam dimensions for positive or negative moment, then verify a trial layout.",
    )
    with st.container(border=True):
        st.markdown("### 1 · Choose design assumptions")
        bending=bending_selector("pre_bending")
        c1, c2, c3 = st.columns(3, gap="large")
        with c1:
            mu = st.number_input("Factored design moment Mu (kip-ft)", 10.0, 2500.0, 250.0, step=10.0, key="pre_mu")
            alpha = st.slider("Trial b/d ratio", .35, 1.0, .6, step=.05)
        with c2:
            eps = st.number_input(
                "Target tensile strain εt", min_value=float(m.yield_strain + .003), max_value=.02,
                value=max(.0075, m.yield_strain + .003), step=.0005, format="%.4f"
            )
            cover = st.number_input("Clear cover (in)", .75, 4.0, 1.5, step=.25, key="pre_cover")
        with c3:
            stirrup = st.selectbox("Stirrup bar size", ["#3", "#4"], key="pre_stirrup")
            agg = st.number_input("Aggregate size (in)", .375, 1.5, .75, step=.125, key="pre_agg")

    try:
        p = preliminary_size(mu, m, alpha, eps, cover, REBAR[stirrup][0], agg, bending=bending)
        with st.container(border=True):
            st.markdown("### 2 · Initial section estimates")
            a, b, c = st.columns(3)
            a.metric("Initial steel ratio ρ", f"{p.rho_trial:.4f}")
            b.metric("Trial effective depth d", f"{p.d_trial:.2f} in")
            c.metric("Trial width b", f"{p.b_trial:.2f} in")
            with st.expander("Show the preliminary sizing equations"):
                st.latex(r"\rho_\mathrm{trial}=0.85\,\beta_1\frac{f'_c}{f_y}\frac{0.003}{0.003+\varepsilon_t}")
                st.latex(r"M_u\approx 0.90\,\rho f_y\,\alpha d^3 \left(1-\frac{\beta_1}{2}\frac{0.003}{0.003+\varepsilon_t}\right),\qquad b\approx\alpha d")
        with st.container(border=True):
            st.markdown("### 3 · Select and verify a trial design")
            if p.candidate:
                st.success(
                    f"Trial section: **b = {p.b_selected:g} in, "
                    f"h = {p.h_selected:g} in**, with **{p.candidate.label}** (one layer)."
                )
                s = Section(b=p.b_selected, h=p.h_selected, d=p.candidate.d, as_t=p.candidate.as_t, bending=bending)
                section_metrics(s, p.candidate.result, mu)
                st.plotly_chart(section_figure(s, p.candidate.result), use_container_width=True)
                detail_panel(p.candidate.result)
            else:
                st.warning(
                    "The initial dimensions were estimated, but the limited one-layer "
                    "reinforcement search did not find an acceptable layout. Try another b/d ratio."
                )
            st.caption(
                "The default target εt = 0.0075 is a preliminary ductility heuristic. "
                "This procedure suggests single-layer bars only and does not verify deflection, shear, loading, or complete detailing requirements."
            )
    except ValueError as ex:
        st.error(f"Check your inputs: {ex}")


def design_studio() -> None:
    page_header(
        "What-if design studio",
        "Explore how reinforcement and section dimensions influence nominal and design strength.",
    )
    with st.container(border=True):
        st.markdown("### 1 · Predict")
        st.write("**Question:** Does adding tension reinforcement always produce a safer, more ductile beam?")
        prediction = st.radio(
            "Choose a prediction before moving the sliders",
            [
                "Increasing As always increases design strength φMn.",
                "Increasing As generally raises Mn, but may reduce φ and ductility.",
                "Increasing As raises tensile strain εt.",
            ],
            index=None,
        )
    with st.container(border=True):
        st.markdown("### 2 · Explore")
        c1, c2 = st.columns([2, 1], gap="large")
        with c1:
            as_t = st.slider("Tension reinforcement As (in²)", .25, 11.0, 2.5, step=.25, key="studio_as")
        with c2:
            b = st.slider("Section width b (in)", 8, 24, 12, step=2, key="studio_b")
            d = st.slider("Effective depth d (in)", 12.0, 34.0, 21.0, step=1.0, key="studio_d")
        s = Section(b=float(b), h=float(d) + 2.5, d=float(d), as_t=float(as_t))
        r = analyze(s, m)
        section_metrics(s, r)
    with st.container(border=True):
        st.markdown("### 3 · Interpret")
        show_diagrams(s, r)
        with st.expander("Reveal the engineering explanation", expanded=False):
            st.write(
                "Within the studied range, nominal moment capacity usually increases as As "
                "increases, while the tensile strain decreases. Outside the tension-controlled "
                "range the strength-reduction factor may decrease, and the higher nominal "
                "strength does not alone make the section an acceptable beam design."
            )
    with st.container(border=True):
        st.markdown("### Investigation prompts")
        st.markdown(
            "1. Hold b and d constant. Find the As at which the section stops being tension-controlled.\n"
            "2. Increase b at fixed As and d. Explain changes in neutral-axis depth, εt, and φMn.\n"
            "3. Compare two sections of similar φMn but different steel quantities. Discuss which you would choose and what additional checks are needed."
        )
        if prediction is not None:
            st.caption("Return to your original prediction after completing the investigation.")


def scope_roadmap() -> None:
    page_header(
        "Reference, limitations & roadmap",
        "The code basis, checks currently implemented, and modules planned for future releases.",
    )
    with st.container(border=True):
        st.markdown("### Selected ACI 318-19 provisions")
        st.markdown(
            "- **§9.3.3.1:** tension-control requirement for nonprestressed beams.\n"
            "- **§9.6.1.2:** minimum longitudinal beam reinforcement (§9.6.1.3 exception not assessed).\n"
            "- **Table 21.2.2:** strain-dependent strength-reduction factors for nonprestressed tied sections.\n"
            "- **§22.2.2 and Table 22.2.2.4.3:** strain compatibility and equivalent rectangular concrete stress block.\n"
            "- **§25.2.1:** selected horizontal clear-spacing checks for mixed bar sizes.\n"
            "- **§25.2.2:** vertical layer alignment and clear spacing (using additional conservative db-based limit).\n"
            "- **§6.3.2:** effective flange width is a user-provided, preverified input—not automatically determined."
        )
    with st.container(border=True):
        st.markdown("### Checks not yet provided")
        st.write(
            "The current application does **not** establish load combinations or member demand, "
            "or complete checks for shear, torsion, development/anchorage, crack-control spacing "
            "under service loads, deflection, seismic detailing, fire, exposure-related cover, "
            "slabs, negative-moment flanged sections, or column interaction. "
            "Mixed-size and two-layer detailing is limited to selected spacing, width and alignment checks."
        )
        st.warning("Do not use this instructional prototype to approve or certify a real structural design.")
    with st.container(border=True):
        st.markdown("### Upcoming modules")
        st.markdown(
            "- **Doubly reinforced beam design:** expanded compression-steel selection and layering.\n"
            "- **T-beams and one-way slabs:** flange width, steel design, and detailing.\n"
            "- **Beam shear:** concrete and stirrup contributions, shear strength, and spacing.\n"
            "- **Column design:** axial-load–moment interaction diagrams and reinforcement layouts.\n"
            "- **Optional guided tutor:** AI-led reflection, with numerical calculations remaining in verified Python routines."
        )
    st.caption(
        "Reference topics: James K. Wight, *Reinforced Concrete: Mechanics and Design*, 8th ed.; "
        "ACI 318-19. All application figures are original; copyrighted textbook and code pages are not redistributed."
    )


PAGES = {
    "home": st.Page(home, title="Overview", icon=":material/home:", default=True),
    "analysis": st.Page(flexural_analysis, title="Flexural analysis", icon=":material/analytics:", url_path="flexural-analysis"),
    "design": st.Page(beam_design, title="Beam design", icon=":material/architecture:", url_path="beam-design"),
    "sizing": st.Page(preliminary_sizing, title="Preliminary sizing", icon=":material/straighten:", url_path="preliminary-sizing"),
    "studio": st.Page(design_studio, title="What-if design studio", icon=":material/tune:", url_path="design-studio"),
    "scope": st.Page(scope_roadmap, title="Reference & roadmap", icon=":material/menu_book:", url_path="reference-and-roadmap"),
}
selected_page = st.navigation(list(PAGES.values()), position="hidden")

with st.sidebar:
    # The app name doubles as a home link; no redundant "Start here" menu entry.
    st.page_link(PAGES["home"], label="**Concrete Design Explorer**", icon="🏗️")
    st.caption("ACI 318-19 · Interactive flexure")
    st.markdown("**EXPLORE**")
    for key in ["analysis", "design", "sizing", "studio", "scope"]:
        st.page_link(PAGES[key])
    st.divider()
    st.markdown("**MATERIAL PROPERTIES**")
    fc = st.number_input("Concrete strength f'c (ksi)", 2.5, 12.0, 4.0, step=.5, key="common_fc")
    fy = st.selectbox("Reinforcement yield fy (ksi)", [40.0, 60.0, 80.0], index=1, key="common_fy")
    es = st.number_input("Steel modulus Es (ksi)", 27000.0, 30000.0, 29000.0, step=500.0, key="common_es")
    m = Materials(fc=fc, fy=fy, es=es)
    st.caption(f"β₁ = {m.beta1:.3f} · εty = {m.yield_strain:.5f}")
    st.divider()
    st.caption("Educational exploration only. Not a complete ACI 318-19 design or detailing check.")

selected_page.run()
st.divider()
st.caption(
    "Concrete Design Explorer · ACI 318-19 reference edition · "
    "Verify all engineering results independently before practical application. "
    "Developed by Dr. Wu @ UT Chattanooga."
)