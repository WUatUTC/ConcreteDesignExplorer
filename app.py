"""ENCE 3680 • Concrete Design Explorer
A lightweight pedagogical Streamlit app based on instructor's Chapters 4–5
sequence and selected ACI 318-19 provisions. Original code/visuals only.
"""
from dataclasses import replace
import pandas as pd
import streamlit as st
from concrete.aci318 import (Materials, REBAR, effective_depth, clear_bar_spacing,
                              required_horizontal_clear_spacing)
from concrete.flexure import Section, analyze
from concrete.design import candidates_for_section, preliminary_size
from concrete.visuals import section_figure, interaction_charts

st.set_page_config(page_title="Concrete Design Explorer | ENCE 3680", page_icon="🏗️",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
.block-container {padding-top:1.8rem; max-width:1280px}
.small-note {color:#5c6f7f; font-size:0.93rem}
.headline {font-size:1.14rem;font-weight:650;color:#236fa1}
</style>""", unsafe_allow_html=True)

MODULES = ["Start here", "Flexural analysis", "Beam design: dimensions known",
           "Preliminary member sizing", "What-if design studio", "Code & module roadmap"]
with st.sidebar:
    st.title("🏗️ Concrete Design Explorer")
    st.caption("ENCE 3680 · Teaching prototype · ACI 318-19")
    page = st.radio("Explore", MODULES, label_visibility="collapsed")
    st.divider()
    st.markdown("**Material properties**")
    fc = st.number_input("Concrete strength f'c (ksi)", min_value=2.5, max_value=12.0,
                         value=4.0, step=0.5, key="common_fc")
    fy = st.selectbox("Reinforcement yield fy (ksi)", [40.0, 60.0, 80.0], index=1)
    es = st.number_input("Steel modulus Es (ksi)", min_value=27000.0, max_value=30000.0,
                         value=29000.0, step=500.0)
    m = Materials(fc=fc, fy=fy, es=es)
    st.caption(f"β₁ = {m.beta1:.3f} · εty = {m.yield_strain:.5f}")
    st.divider()
    st.caption("**Teaching / verification use only.** This program does not perform complete ACI 318-19 member design or verify all applicable provisions.")

st.title("Concrete Design Explorer")
st.caption("Interactive reinforced-concrete flexure · Based on ENCE 3680 Chapters 4–5, James K. Wight (8th ed.), and selected ACI 318-19 provisions")


def section_metrics(s, r, mu=None):
    a, b, c, d = st.columns(4)
    a.metric("Nominal strength, Mn", f"{r.mn_kft:,.1f} kip-ft")
    b.metric("Design strength, φMn", f"{r.phi_mn_kft:,.1f} kip-ft")
    c.metric("Extreme steel strain, εt", f"{r.strain_t:.5f}")
    d.metric("Reduction factor, φ", f"{r.phi:.3f}")
    if r.control == "Tension-controlled":
        st.success(f"**{r.control}:** εt ≥ εty + 0.003 = {m.yield_strain+.003:.5f} (ACI 318-19, Table 21.2.2).")
    else:
        st.warning(f"**{r.control}:** Analyzed for understanding; this does not satisfy the tension-controlled beam requirement in §9.3.3.1.")
    if s.as_t + 1e-8 < r.as_min:
        st.warning(f"Provided As = {s.as_t:.3f} in² is below the calculated minimum beam steel As,min = {r.as_min:.3f} in² (ACI §9.6.1.2; §9.6.1.3 exception not assessed).")
    if r.strain_c_steel < 0 and s.as_c:
        st.warning("Upper steel is in tension at nominal strength under this model; it is not acting as compression reinforcement.")
    if mu is not None:
        if r.phi_mn_kft >= mu and r.control == "Tension-controlled" and s.as_t >= r.as_min:
            st.info(f"**Limited flexural check satisfied:** φMn = {r.phi_mn_kft:.1f} ≥ Mu = {mu:.1f} kip-ft. Other design checks remain outstanding.")
        else:
            st.error("**Limited flexural check NOT satisfied:** review strength, minimum reinforcement, or tension-control requirement.")


def detail_panel(s, r):
    with st.expander("Show the equilibrium, strains, and governing provisions", expanded=False):
        st.latex(r"\varepsilon_t=0.003\frac{d-c}{c},\qquad a=\beta_1c")
        st.latex(r"T=A_s f_s,\quad C_c=0.85f'_c\times (\text{equivalent stress-block area})")
        st.latex(r"\sum F=0:\quad T=C_c+C'_s;\qquad \phi M_n\geq M_u")
        st.write("The solver uses bisection on strain-compatible axial equilibrium. Tension and upper-steel stresses are capped at ±fy; displaced concrete within the equivalent stress block is accounted for when upper steel is present.")
        vals = {
            "Neutral-axis depth c (in)": r.c,
            "Whitney block depth a (in)": r.a,
            "Equivalent concrete compression Cc (kip)": r.cc,
            "Net upper-steel compression C's (kip)": r.cs_net,
            "Tension steel force T (kip)": r.tension,
            "Tension steel stress fs (ksi)": r.stress_t,
            "Upper steel stress f's (ksi)": r.stress_c_steel,
            "As,min (in²)": r.as_min,
            "Equilibrium residual (kip)": r.equilibrium_error,
        }
        st.dataframe(pd.DataFrame([{"Quantity":k,"Result":round(v,6)} for k,v in vals.items()]),
                     use_container_width=True, hide_index=True)
        st.write("**Model result:**", r.case)
        st.caption("Code cross-references: ACI 318-19 §9.3.3.1, §9.6.1.2, Table 21.2.2, §22.2.2 and Table 22.2.2.4.3. Details and official text should be checked in the licensed ACI code.")


def show_diagrams(s,r):
    lc,rc=st.columns([1,1.15])
    with lc:
        st.plotly_chart(section_figure(s,r),use_container_width=True)
        st.caption("Schematic section; symbolic bar count, compression block shaded. The detailed spacing checker is in the design module.")
    with rc:
        st.subheader("What changes as As increases?")
        f1,f2 = interaction_charts(s,m,r)
        st.plotly_chart(f1,use_container_width=True)
        st.plotly_chart(f2,use_container_width=True)


if page == "Start here":
    st.subheader("A structural design laboratory, not a quiz system")
    st.write("Change section parameters, predict the outcome, examine the stress block and steel strain, and verify a solution using ACI 318-19 procedures. The deterministic calculation engine is independent from any AI model.")
    cols=st.columns(3)
    with cols[0]:
        st.markdown("#### 1 · Analyze")
        st.write("Singly reinforced, doubly reinforced, and positive-moment flanged sections; see c, a, εt, Mn and φMn.")
    with cols[1]:
        st.markdown("#### 2 · Design")
        st.write("Size tension reinforcement for given beam dimensions, or estimate a preliminary section when dimensions are unknown.")
    with cols[2]:
        st.markdown("#### 3 · Explain")
        st.write("Use live parameter sweeps to discuss capacity, ductility, tension control, and reinforcement economy.")
    st.info("**Suggested classroom activity:** predict whether increasing As always increases φMn. Then open **What-if design studio**, move the slider beyond the tension-controlled limit, and explain what the graph shows.")
    st.markdown("#### Alignment with your lecture notes")
    st.markdown("""- **Ch4L1–L2:** flexural behavior, strain compatibility, Whitney stress block and moment–curvature intuition.
- **Ch4L3–L4:** singly reinforced flexural strength; balanced, transition and tension-controlled response.
- **Ch4L5–L6:** doubly reinforced analysis and the two positive-moment flanged-section cases.
- **Ch5L2–L4:** effective depth, constructability, design with known and initially unknown dimensions.
- **Next:** Ch5L5 doubly reinforced design; Ch5L6 one-way slab design; later shear and columns.""")
    st.caption("References: instructor-supplied ENCE 3680 slides and design flowcharts, Wight, *Reinforced Concrete: Mechanics and Design*, 8th ed. The code and figures are original; no textbook/ACI pages are redistributed.")

elif page == "Flexural analysis":
    st.subheader("Chapter 4 · Flexural analysis of a given section")
    st.write("**Analysis problem:** section geometry and reinforcement are known; compute nominal strength and interpret ductility.")
    inp, = st.columns(1)
    section_kind=st.radio("Compression section geometry",["Rectangular","T-beam (+M)"],horizontal=True)
    doubly=st.checkbox("Include upper reinforcement (doubly reinforced analysis)",value=False)
    z1,z2,z3=st.columns(3)
    with z1:
        b=st.number_input("Beam width b / web width bw (in)",min_value=6.0,max_value=60.0,value=12.0,step=1.0)
        h=st.number_input("Overall height h (in)",min_value=10.0,max_value=72.0,value=24.0,step=1.0)
    with z2:
        cover=st.number_input("Clear cover to outside stirrup (in)",min_value=0.75,max_value=4.0,value=1.5,step=.25)
        stirrup_db=st.selectbox("Stirrup bar size",["#3","#4"],index=0)
    with z3:
        as_mode=st.radio("Tension reinforcement input",["Bar selection","Enter As"],horizontal=True)
        if as_mode=="Bar selection":
            n=st.slider("Number of tension bars (one layer)",2,10,3)
            bar_size=st.selectbox("Tension bar size",list(REBAR)[1:],index=4)
            as_t=n*REBAR[bar_size][1]
            d=effective_depth(h,cover,REBAR[stirrup_db][0],REBAR[bar_size][0])
            st.caption(f"As = {as_t:.3f} in²; d = {d:.3f} in")
        else:
            as_t=st.number_input("Tension steel area As (in²)",min_value=0.1,max_value=45.0,value=3.0,step=0.1)
            d=st.number_input("Effective depth d (in)",min_value=1.0,max_value=h-0.1,value=min(21.5,h-0.2),step=.25)
    bf=hf=0.0
    if section_kind=="T-beam (+M)":
        t1,t2=st.columns(2)
        with t1: bf=st.number_input("Effective flange width bf (in)",min_value=b,max_value=180.0,value=max(36.0,b),step=2.0)
        with t2: hf=st.number_input("Flange thickness hf (in)",min_value=2.0,max_value=max(2.1,h-0.5),value=min(5.0,h-1),step=.5)
        st.caption("Use positive bending with flange in compression. Enter an effective bf already verified using ACI §6.3.2; the application does not calculate flange width or cover negative-moment T-beams.")
    as_c=0.0
    dp=2.375
    if doubly:
        cc1,cc2,cc3=st.columns(3)
        with cc1: cn=st.slider("Upper bar count",2,6,2)
        with cc2: csize=st.selectbox("Upper bar size",list(REBAR)[1:],index=3)
        with cc3: dp=st.number_input("Upper steel centroid d' (in)",min_value=0.5,max_value=max(.6,d-0.01),value=min(2.375,d-.1),step=.125)
        as_c=cn*REBAR[csize][1]
    mu=st.number_input("Optional factored demand Mu for comparison (kip-ft)",min_value=0.0,max_value=3000.0,value=200.0,step=10.0)
    try:
        s=Section(b=b,h=h,d=d,as_t=as_t,kind=section_kind,bf=bf,hf=hf,as_c=as_c,dp=dp)
        r=analyze(s,m)
        section_metrics(s,r,mu if mu>0 else None)
        if as_mode=="Bar selection":
            clear=clear_bar_spacing(b,n,REBAR[bar_size][0],cover,REBAR[stirrup_db][0])
            req=required_horizontal_clear_spacing(REBAR[bar_size][0],.75)
            if clear < req:
                st.warning(f"Bar-fit alert: actual one-layer horizontal clear spacing {clear:.2f} in < approximate minimum {req:.2f} in (assumed 3/4-in aggregate).")
        show_diagrams(s,r)
        detail_panel(s,r)
    except ValueError as ex:
        st.error(f"Check your inputs: {ex}")

elif page == "Beam design: dimensions known":
    st.subheader("Chapter 5 · Reinforcement selection with known section dimensions")
    st.write("Find tension rebar combinations in **one layer** that satisfy the limited beam flexural checks. Each combination is independently analyzed using its actual bar diameter and effective depth.")
    c1,c2,c3=st.columns(3)
    with c1:
        b=st.number_input("Beam width b (in)",8.0,40.0,12.0,step=1.0,key="design_b")
        h=st.number_input("Beam height h (in)",12.0,60.0,24.0,step=1.0,key="design_h")
    with c2:
        mu=st.number_input("Factored moment Mu (kip-ft)",10.0,2500.0,220.0,step=10.0,key="design_mu")
        cover=st.number_input("Clear cover to stirrup (in)",.75,4.0,1.5,step=.25,key="design_cover")
    with c3:
        agg=st.number_input("Nominal max aggregate size (in)",.375,1.5,.75,step=.125,key="design_agg")
        stirrup=st.selectbox("Stirrup size",["#3","#4"],index=0,key="design_stirrup")
    mode=st.radio("Reinforcement model",["Singly reinforced","Doubly reinforced (fixed upper steel)"],horizontal=True)
    as_c=0.0; dp=2.375
    if mode.startswith("Doubly"):
        x1,x2,x3=st.columns(3)
        with x1: nc=st.slider("Upper bars",2,6,2,key="design_cn")
        with x2: cs=st.selectbox("Upper bar size",list(REBAR)[1:],index=4,key="design_cs")
        with x3: dp=st.number_input("Upper reinforcement centroid d' (in)",.5,h-3.0,2.375,step=.125,key="design_dp")
        as_c=nc*REBAR[cs][1]
        st.caption(f"Fixed compression reinforcement A's = {as_c:.2f} in². Search changes only tension bars.")
    try:
        options=candidates_for_section(mu,b,h,m,cover,REBAR[stirrup][0],agg,as_c,dp)
        st.metric("Acceptable one-layer choices found",len(options))
        if options:
            rows=[{"Option":c.label,"As (in²)":round(c.as_t,2),
                   "d (in)":round(c.d,2),"Clear spacing (in)":round(c.clear,2),
                   "εt":round(c.result.strain_t,5),"φMn (kip-ft)":round(c.result.phi_mn_kft,1)} for c in options[:12]]
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
            st.download_button("Export candidate table (CSV)",data=pd.DataFrame(rows).to_csv(index=False).encode(),
                               file_name="beam_flexure_candidates.csv",mime="text/csv")
            selected=st.selectbox("Inspect a reinforcement alternative",range(min(12,len(options))),
                                  format_func=lambda i: f"{options[i].label} · φMn {options[i].result.phi_mn_kft:.1f} kip-ft")
            c=options[selected]
            sec=Section(b=b,h=h,d=c.d,as_t=c.as_t,as_c=as_c,dp=dp)
            section_metrics(sec,c.result,mu)
            st.plotly_chart(section_figure(sec,c.result),use_container_width=True)
            st.caption(f"Clear spacing = {c.clear:.2f} in, minimum checked = {required_horizontal_clear_spacing(REBAR[c.designation][0],agg):.2f} in. One-layer fit only; cover, development, curtailment, spacing under service loads, shear and serviceability must still be checked.")
            detail_panel(sec,c.result)
        else:
            st.warning("No acceptable **one-layer** reinforcement combination found within 2–12 bars, #4–#11. Increase the beam dimensions, revise demand, or use a manually engineered multilayer layout (not supported yet).")
    except ValueError as ex:
        st.error(f"Check inputs: {ex}")

elif page == "Preliminary member sizing":
    st.subheader("Chapter 5 · Preliminary design when dimensions are unknown")
    st.write("This follows the educational initial-strain method in your Ch5L4 handout, then searches real nominal one-layer reinforcement options and rechecks the chosen dimensions.")
    c1,c2,c3=st.columns(3)
    with c1:
        mu=st.number_input("Factored design moment Mu (kip-ft)",10.0,2500.0,250.0,step=10.0,key="pre_mu")
        alpha=st.slider("Trial width-to-effective-depth ratio b/d",.35,1.0,.6,step=.05)
    with c2:
        eps=st.number_input("Target tension strain εt",min_value=float(m.yield_strain+.003),max_value=.02,
                            value=max(.0075,m.yield_strain+.003),step=.0005,format="%.4f")
        cover=st.number_input("Cover (in)",.75,4.0,1.5,step=.25,key="pre_cover")
    with c3:
        stirrup=st.selectbox("Stirrup size",["#3","#4"],key="pre_stirrup")
        agg=st.number_input("Aggregate size (in)",.375,1.5,.75,step=.125,key="pre_agg")
    try:
        p=preliminary_size(mu,m,alpha,eps,cover,REBAR[stirrup][0],agg)
        st.markdown("#### Estimate → select → verify")
        c1,c2,c3=st.columns(3)
        c1.metric("Initial steel ratio ρ",f"{p.rho_trial:.4f}")
        c2.metric("Calculated trial d",f"{p.d_trial:.2f} in")
        c3.metric("Calculated trial b",f"{p.b_trial:.2f} in")
        st.latex(r"\rho_\mathrm{trial}=0.85\,\beta_1\frac{f'_c}{f_y}\frac{0.003}{0.003+\varepsilon_t}")
        st.latex(r"M_u\approx 0.90\,\rho f_y\,\alpha d^3 \left(1-\frac{\beta_1}{2}\frac{0.003}{0.003+\varepsilon_t}\right),\qquad b\approx\alpha d")
        if p.candidate:
            st.success(f"Trial size verified for this model: **b = {p.b_selected:g} in, h = {p.h_selected:g} in**, with **{p.candidate.label}** (one layer).")
            s=Section(b=p.b_selected,h=p.h_selected,d=p.candidate.d,as_t=p.candidate.as_t)
            section_metrics(s,p.candidate.result,mu)
            st.plotly_chart(section_figure(s,p.candidate.result),use_container_width=True)
            detail_panel(s,p.candidate.result)
        else:
            st.warning("Initial sizing is computed, but an acceptable one-layer reinforcement layout was not found in the limited automated search. Try a different b/d ratio or design manually.")
        st.caption("The initial strain target 0.0075 is used in the instructor's Ch5L4 procedure. Selection of preliminary depth/width is heuristic; no deflection, shear, load-combination or comprehensive detailing verification is performed.")
    except ValueError as ex:
        st.error(f"Input error: {ex}")

elif page == "What-if design studio":
    st.subheader("Chapter 4 · Predict, explore, and explain")
    st.write("**Central question:** Does adding tension reinforcement always produce a safer, more ductile beam?")
    prediction=st.radio("Make a prediction before moving the slider:",[
        "Adding more As always increases the design strength φMn.",
        "Adding more As generally increases Mn, but may reduce φ and ductility.",
        "Adding more As increases the tension strain εt."],index=None)
    c1,c2=st.columns([2,1])
    with c1:
        as_t=st.slider("Tension steel area As (in²)",.25,11.0,2.5,step=.25,key="studio_as")
    with c2:
        b=st.slider("Section width b (in)",8,24,12,step=2,key="studio_b")
        d=st.slider("Effective depth d (in)",12.0,34.0,21.0,step=1.0,key="studio_d")
    s=Section(b=float(b),h=float(d)+2.5,d=float(d),as_t=float(as_t))
    r=analyze(s,m)
    section_metrics(s,r)
    show_diagrams(s,r)
    if prediction:
        st.markdown("**After experimenting:** The nominal capacity usually rises with As over the range shown, but φ and steel tensile strain can drop as reinforcement increases. The code's tension-control requirement matters when judging an acceptable beam design; even a higher Mn is not sufficient by itself.")
    st.markdown("#### Discussion prompts for pairs / small groups")
    st.write("1. Keep b and d fixed. Find the As value at which the section stops being tension-controlled. What changes near this boundary?")
    st.write("2. Increase b while holding As and d constant. What happens to the neutral-axis depth, εt and φMn? Explain using force equilibrium.")
    st.write("3. Compare two sections with similar φMn but different reinforcement amounts. Which would you prefer and why? Identify checks the simulation does not address.")
    st.caption("No student logins or scores are collected in this version. For an AI Socratic tutor, a future optional API integration can ask questions and discuss student explanations without performing structural calculations itself.")

else:
    st.subheader("References, code scope and next modules")
    st.markdown("""**Calculation basis (selected ACI 318-19):**
- §9.3.3.1: tension-controlled requirement for nonprestressed beams.
- §9.6.1.2: minimum longitudinal flexural beam reinforcement, except §9.6.1.3 not evaluated.
- Table 21.2.2: strain-dependent φ factors for nonprestressed tied cross sections.
- §22.2.2 and Table 22.2.2.4.3: strain compatibility and equivalent rectangular stress block / β₁.
- §25.2.1: selected one-layer horizontal clear spacing checks; §6.3.2 flange effectiveness **not** automated.

**Not included or not verified:** continuous-beam load effects and factored combinations, shear, torsion, development/anchorage, flexural crack-control spacing under service loads, seismic detailing, deflections, fire, exposure/cover compliance, multilayer bars, slab reinforcement, negative-moment flanged sections, and column interaction. **Never use the prototype to approve a real-world structural design.**

**Next modular additions:**
1. **Doubly reinforced design** with selectable compression reinforcement and improved two-layer bar placement.
2. **T-beam and one-way slab design**: effective flange width, required As and slab detailing.
3. **Beam shear** (ACI 318-19 Ch. 22 and related beam provisions): Vc, Vs, stirrup spacing, shear capacity.
4. **Column P–M interaction**: strain-compatible interaction curves, bar arrangements and tied/spiral behavior.
5. **Optional AI Socratic tutor**: student explains observations, AI challenges reasoning, core numerical results remain verified Python computations.

**Reference alignment:** Wight, *Reinforced Concrete: Mechanics and Design*, 8th ed.; the instructor-provided ENCE 3680 Ch4L1–L6 and Ch5L1–L6 lectures and chapter flowcharts. This application does not redistribute the copyrighted textbook, code, or lecture images.""")

st.divider()
st.caption("UTC · ENCE 3680 | Original instructional prototype · ACI 318-19 reference edition | Verify all results independently before engineering application")
