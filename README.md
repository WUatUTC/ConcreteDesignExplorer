# Concrete Design Explorer — ENCE 3680

An open, lightweight **Streamlit classroom exploration app** for reinforced-concrete beam flexure. It follows the subject order of the instructor's Chapter 4–5 course handouts and *Reinforced Concrete: Mechanics and Design*, James K. Wight, 8th edition. It implements a **selected instructional subset** of **ACI 318-19** in a separate, testable Python calculation engine.

**Not a code-complete design tool. Do not use for real-world structural design, permitting, or professional signoff.** No external AI service, database, payment method, or student login is needed.

## Included now

- **Flexural analysis:** singly and doubly reinforced rectangular beams; positive-moment flanged T-beams, with both Whitney-block cases; general strain-compatible steel stress calculation and φ classification.
- **Interactive cross sections and what-if plots:** experiment with steel area, neutral axis, strength factor, strength and extreme tension strain.
- **Design with known b and h:** automated selection of nominal tension bars (#4 through #11, 2–12 bars) for one-layer rectangular beams. It checks nominal flexural strength, tension control, minimum beam steel, horizontal bar spacing, and effective depth based on chosen bars.
- **Preliminary beam dimensions unknown:** instructor's selected initial strain method (default εt=0.0075) and b/d heuristic, followed by detailed rebar selection/verification for a one-layer section.
- **Doubly reinforced design:** selection is available with **fixed upper reinforcement** and searches for tension bars. This is not a complete unconstrained doubly reinforced section design algorithm.
- Self-contained classroom prediction prompts and explanation of intermediate calculations. No scores are collected.

## Run locally

Requires Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

To run numerical verification tests:

```bash
pip install pytest
python -m pytest -q
```

## Deploy for free using Streamlit Community Cloud

1. Create a **new GitHub repository** and push the **contents** of this project folder to it (do not upload student records, the instructor's copyrighted slides, or secrets).
2. Open https://share.streamlit.io/ and sign in with GitHub.
3. Select **Create app**, then your repository, branch (`main`), and entrypoint **`app.py`**.
4. Choose your app URL and deploy. Community Cloud installs `requirements.txt` automatically.
5. Add the URL as an external link in Canvas. Test it with several students simultaneously before using it in class.

The service is free for small apps, but subject to resource limits, sleep after inactivity, and its hosting/privacy policies. Use no names or grades in this prototype. An app hosted in a public repository is public code; the instructor's PDF/PPTX/DOCX materials are not required for deployment.

## Selected engineering assumptions and boundaries

- US customary: **in, ksi, kips, kip-ft**; normalweight nonprestressed concrete, positive bending, symmetric top/bottom reinforcement centroid in 1 layer, εcu=0.003, steel stress ±fy, Es default 29,000 ksi. Strength is computed by **bisection of force equilibrium**.
- β₁ per ACI 318-19 Table 22.2.2.4.3.
- φ per ACI Table 21.2.2, tension-controlled when εt ≥ εty + 0.003 (also the nonprestressed beam design condition in §9.3.3.1). Transitional/compression-control results are shown for pedagogical analysis, **not as acceptable beam designs**.
- As,min per §9.6.1.2; the §9.6.1.3 possible exception is **not** evaluated.
- One-layer horizontal clear spacing checked by a simplified interpretation of §25.2.1, using bar diameter, 1 in, and 4/3 nominal maximum aggregate size. Aggregate input matters.
- For T-beams, the user provides a previously verified effective bf; §6.3.2.1 is **not implemented**. Positive moment and flange in compression only.
- Simplified treatment of compression steel accounts for net compression within the Whitney block. If top bars enter tension, the analysis flags it; the designer must reconsider modeling.
- Not checked: load combinations/analysis and live-load patterns, anchorage/development, stirrups and shear, deflection and serviceability, service-load crack-control steel spacing, exposure/cover compliance, seismic provisions, full 3D geometry, bar curtailment, multilayer placements, beam stability, detailing of fixed upper bars, or code edition updates.
- Some textbook/classroom notation may differ from ACI due to course-specific conventions. Always verify with the official code and lecture source.

## File structure

```
app.py                     Streamlit classroom app
concrete/aci318.py         Material factors, nominal bars and selected code limits
concrete/flexure.py        Pure-Python strain-compatible flexural analysis
concrete/design.py         Trial sizing + one-layer rebar selections
concrete/visuals.py        Original, interactive Plotly drawings
tests/                     Numerical verification checks
.streamlit/config.toml     Basic theme
requirements.txt
```

## Expansion roadmap

- Complete doubly reinforced beam design including optimized upper bars and multilayer detailing.
- T-beam design, one-way slabs, effective flange width, serviceability and reinforcement detailing.
- Shear design (next module), then column P–M interaction.
- Optional **AI Socratic tutor** (separate configuration; must not be the design calculation authority).

## Sources / instructor alignment

- User-provided ENCE 3680 lectures: Ch4L1–Ch4L6 (beam behavior, Whitney block, rectangular analysis, tension control, doubly reinforced beams, flanged sections); Ch5L2–Ch5L4 (beam design considerations, fixed b/h, preliminary sizing), plus Ch5L1, Ch5L5, Ch5L6 for future expansions.
- James K. Wight, *Reinforced Concrete: Mechanics and Design*, 8th edition, Pearson. Publisher confirms its edition is aligned with ACI 318-19.
- ACI, *Building Code Requirements for Structural Concrete (ACI 318-19)*. Use a properly licensed copy for code requirements. No pages, illustrations or tables from copyrighted sources are reproduced in this app.

The source handouts were used for overall **instructional organization and selected initial sizing relationships**, not as an assertion that every page or every Wight example has been implemented or checked.
