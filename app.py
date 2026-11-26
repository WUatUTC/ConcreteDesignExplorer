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


def section_metrics(s: Section, r, mu=None) -> None:
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
        st.warning("Upper steel is in tension at nominal strength in this model; it is not acting as compression reinforcement.")

    if mu is not None:
        if r.phi_mn_kft >= mu and r.control == "Tension-controlled" and s.as_t >= r.as_min:
            st.info(
                f"**Limited flexural check satisfied:** φMn = {r.phi_mn_kft:.1f} ≥ "
                f"Mu = {mu:.1f} kip-ft. Other design checks remain outstanding."
            )
        else:
            st.error(
                "**Limited flexural check not satisfied:** review strength, "
                "minimum reinforcement, or tension-control requirement."
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
            "Tension steel stress fs (ksi)": r.stress_t,
            "Upper steel stress f's (ksi)": r.stress_c_steel,
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


def show_diagrams(s: Section, r) -> None:
    left, right = st.columns([1, 1.12], gap="large")
    with left:
        st.markdown("#### Section and stress block")
        st.plotly_chart(section_figure(s, r), use_container_width=True)
        st.caption("Schematic reinforcement; one-layer bar-fit checks are available in the design section.")
    with right:
        st.markdown("#### Reinforcement sensitivity")
        f1, f2 = interaction_charts(s, m, r)
        st.plotly_chart(f1, use_container_width=True)
        st.plotly_chart(f2, use_container_width=True)


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
            st.write("Analyze rectangular, doubly reinforced, and positive-moment T-beam sections.")
            st.page_link(PAGES["analysis"], label="Open analysis", icon=":material/arrow_forward:")
    with first[1]:
        with st.container(border=True):
            st.markdown("#### 📐 Beam design")
            st.write("Select a one-layer reinforcement layout for known section dimensions and moment demand.")
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
    page_header(
        "Flexural analysis",
        "Analyze an existing reinforced-concrete section and explore strength, strain, and ductility.",
    )
    with st.container(border=True):
        st.markdown("### 1 · Define the section")
        section_kind = st.radio(
            "Compression section geometry", ["Rectangular", "T-beam (+M)"], horizontal=True
        )
        doubly = st.checkbox("Include upper reinforcement (doubly reinforced analysis)", value=False)
        z1, z2, z3 = st.columns(3, gap="large")
        with z1:
            b = st.number_input("Beam width b / web width bw (in)", 6.0, 60.0, 12.0, step=1.0)
            h = st.number_input("Overall height h (in)", 10.0, 72.0, 24.0, step=1.0)
        with z2:
            cover = st.number_input("Clear cover to outside stirrup (in)", .75, 4.0, 1.5, step=.25)
            stirrup_db = st.selectbox("Stirrup bar size", ["#3", "#4"])
        with z3:
            as_mode = st.radio("Tension steel input", ["Bar selection", "Enter As"], horizontal=True)
            if as_mode == "Bar selection":
                n = st.slider("Tension bars (one layer)", 2, 10, 3)
                bar_size = st.selectbox("Tension bar size", list(REBAR)[1:], index=4)
                as_t = n * REBAR[bar_size][1]
                d = effective_depth(h, cover, REBAR[stirrup_db][0], REBAR[bar_size][0])
                st.caption(f"As = {as_t:.3f} in² · d = {d:.3f} in")
            else:
                as_t = st.number_input("Tension steel area As (in²)", .1, 45.0, 3.0, step=.1)
                d = st.number_input(
                    "Effective depth d (in)", 1.0, h - .1, min(21.5, h - .2), step=.25
                )

        bf = hf = 0.0
        if section_kind == "T-beam (+M)":
            st.markdown("**Compression flange (positive bending only)**")
            t1, t2 = st.columns(2)
            with t1:
                bf = st.number_input("Effective flange width bf (in)", b, 180.0, max(36.0, b), step=2.0)
            with t2:
                hf = st.number_input("Flange thickness hf (in)", 2.0, max(2.1, h - .5), min(5.0, h - 1), step=.5)
            st.caption("Enter an effective flange width already verified using ACI §6.3.2. This application does not calculate bf or analyze negative-moment T-beams.")

        as_c = 0.0
        dp = 2.375
        if doubly:
            st.markdown("**Upper reinforcement**")
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                cn = st.slider("Upper bar count", 2, 6, 2)
            with cc2:
                csize = st.selectbox("Upper bar size", list(REBAR)[1:], index=3)
            with cc3:
                dp = st.number_input(
                    "Upper steel centroid d' (in)", .5, max(.6, d - .01), min(2.375, d - .1), step=.125
                )
            as_c = cn * REBAR[csize][1]

    with st.container(border=True):
        st.markdown("### 2 · Set the applied moment")
        mu = st.number_input(
            "Optional factored moment demand Mu (kip-ft)", 0.0, 3000.0, 200.0, step=10.0
        )
        st.caption("Set Mu = 0 to explore capacity without checking a particular demand.")

    try:
        s = Section(b=b, h=h, d=d, as_t=as_t, kind=section_kind, bf=bf, hf=hf, as_c=as_c, dp=dp)
        r = analyze(s, m)
        with st.container(border=True):
            st.markdown("### 3 · Strength and strain results")
            section_metrics(s, r, mu if mu > 0 else None)
            if as_mode == "Bar selection":
                clear = clear_bar_spacing(b, n, REBAR[bar_size][0], cover, REBAR[stirrup_db][0])
                req = required_horizontal_clear_spacing(REBAR[bar_size][0], .75)
                if clear < req:
                    st.warning(
                        f"Bar-fit alert: one-layer clear spacing {clear:.2f} in is less "
                        f"than the approximate minimum {req:.2f} in (assumes 3/4-in aggregate)."
                    )
        with st.container(border=True):
            st.markdown("### 4 · Visual interpretation")
            show_diagrams(s, r)
            detail_panel(r)
    except ValueError as ex:
        st.error(f"Check your inputs: {ex}")


def beam_design() -> None:
    page_header(
        "Beam design · Known dimensions",
        "Find one-layer tension reinforcement layouts for a specified rectangular beam and moment demand.",
    )
    with st.container(border=True):
        st.markdown("### 1 · Design inputs")
        c1, c2, c3 = st.columns(3, gap="large")
        with c1:
            b = st.number_input("Beam width b (in)", 8.0, 40.0, 12.0, step=1.0, key="design_b")
            h = st.number_input("Beam height h (in)", 12.0, 60.0, 24.0, step=1.0, key="design_h")
        with c2:
            mu = st.number_input("Factored moment Mu (kip-ft)", 10.0, 2500.0, 220.0, step=10.0, key="design_mu")
            cover = st.number_input("Clear cover to stirrup (in)", .75, 4.0, 1.5, step=.25, key="design_cover")
        with c3:
            agg = st.number_input("Nominal max aggregate size (in)", .375, 1.5, .75, step=.125, key="design_agg")
            stirrup = st.selectbox("Stirrup bar size", ["#3", "#4"], key="design_stirrup")

        mode = st.radio(
            "Reinforcement model", ["Singly reinforced", "Doubly reinforced (fixed upper steel)"], horizontal=True
        )
        as_c, dp = 0.0, 2.375
        if mode.startswith("Doubly"):
            st.markdown("**Fixed upper reinforcement**")
            x1, x2, x3 = st.columns(3)
            with x1:
                nc = st.slider("Upper bars", 2, 6, 2, key="design_cn")
            with x2:
                cs = st.selectbox("Upper bar size", list(REBAR)[1:], index=4, key="design_cs")
            with x3:
                dp = st.number_input("Upper centroid d' (in)", .5, h - 3.0, 2.375, step=.125, key="design_dp")
            as_c = nc * REBAR[cs][1]
            st.caption(f"Fixed upper steel A's = {as_c:.2f} in². Only the tension reinforcement is varied.")

    try:
        options = candidates_for_section(mu, b, h, m, cover, REBAR[stirrup][0], agg, as_c, dp)
        with st.container(border=True):
            st.markdown("### 2 · Reinforcement alternatives")
            st.metric("Acceptable one-layer candidates", len(options))
            if options:
                rows = [
                    {
                        "Option": c.label,
                        "As (in²)": round(c.as_t, 2),
                        "d (in)": round(c.d, 2),
                        "Clear spacing (in)": round(c.clear, 2),
                        "εt": round(c.result.strain_t, 5),
                        "φMn (kip-ft)": round(c.result.phi_mn_kft, 1),
                    }
                    for c in options[:12]
                ]
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                st.download_button(
                    "Export table (CSV)",
                    data=pd.DataFrame(rows).to_csv(index=False).encode(),
                    file_name="beam_flexure_candidates.csv",
                    mime="text/csv",
                    icon=":material/download:",
                )
                selected = st.selectbox(
                    "Inspect an alternative",
                    range(min(12, len(options))),
                    format_func=lambda i: f"{options[i].label} · φMn {options[i].result.phi_mn_kft:.1f} kip-ft",
                )
            else:
                selected = None
                st.warning(
                    "No acceptable one-layer combination was found within 2–12 bars, "
                    "#4–#11. Increase dimensions, revise demand, or detail a multilayer arrangement manually."
                )
        if selected is not None:
            c = options[selected]
            sec = Section(b=b, h=h, d=c.d, as_t=c.as_t, as_c=as_c, dp=dp)
            with st.container(border=True):
                st.markdown("### 3 · Check the selected alternative")
                section_metrics(sec, c.result, mu)
                st.plotly_chart(section_figure(sec, c.result), use_container_width=True)
                st.caption(
                    f"Clear spacing = {c.clear:.2f} in; minimum checked = "
                    f"{required_horizontal_clear_spacing(REBAR[c.designation][0], agg):.2f} in. "
                    "Service-load crack control, anchorage, shear, deflection, and other checks remain outstanding."
                )
                detail_panel(c.result)
    except ValueError as ex:
        st.error(f"Check your inputs: {ex}")


def preliminary_sizing() -> None:
    page_header(
        "Preliminary member sizing",
        "Estimate rectangular beam dimensions using a target tensile strain, then verify the selected layout.",
    )
    with st.container(border=True):
        st.markdown("### 1 · Choose design assumptions")
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
        p = preliminary_size(mu, m, alpha, eps, cover, REBAR[stirrup][0], agg)
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
                s = Section(b=p.b_selected, h=p.h_selected, d=p.candidate.d, as_t=p.candidate.as_t)
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
                "This procedure does not verify deflection, shear, loading, or complete detailing requirements."
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
            "- **§25.2.1:** selected one-layer horizontal clear spacing checks.\n"
            "- **§6.3.2:** effective flange width is a user-provided, preverified input—not automatically determined."
        )
    with st.container(border=True):
        st.markdown("### Checks not yet provided")
        st.write(
            "The current application does **not** establish load combinations or member demand, "
            "or complete checks for shear, torsion, development/anchorage, crack-control spacing "
            "under service loads, deflection, seismic detailing, fire, exposure-related cover, "
            "multilayer reinforcement, slabs, negative-moment T-sections, or column interaction."
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
    "Concrete Design Explorer · ACI 318-19 reference edition · Developed by Dr. Wu @ UT Chattanooga "
    "Verify all engineering results independently before practical application."
)
