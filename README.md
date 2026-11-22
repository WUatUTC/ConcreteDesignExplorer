# Concrete Design Explorer

An open, lightweight **Streamlit application for interactive learning and exploration** of reinforced-concrete beam flexure. Its educational topics align with James K. Wight's *Reinforced Concrete: Mechanics and Design*, 8th edition, and it implements **selected ACI 318-19 provisions** in a separate, testable Python calculation engine.

**Not a code-complete design tool. Do not use for real-world structural design, permitting, or professional signoff.** No external AI service, database, payment method, or student login is needed.

## Included now

- **Flexural analysis:** singly and doubly reinforced rectangular beams; positive-moment flanged T-beams, with both Whitney-block cases; general strain-compatible steel stress calculation and φ classification.
- **Interactive cross sections and what-if plots:** experiment with steel area, neutral axis, strength factor, strength and extreme tension strain.
- **Design with known b and h:** automated selection of nominal tension bars (#4 through #11, 2–12 bars) for one-layer rectangular beams. It checks nominal flexural strength, tension control, minimum beam steel, horizontal bar spacing, and effective depth based on chosen bars.
- **Preliminary beam dimensions unknown:** initial strain method (default εt=0.0075) and b/d heuristic, followed by detailed rebar selection/verification for a one-layer section.
- **Doubly reinforced design:** selection is available with **fixed upper reinforcement** and searches for tension bars. This is not a complete unconstrained doubly reinforced section design algorithm.
- Self-contained prediction prompts and explanation of intermediate calculations. No scores are collected.
- Icon-labeled sidebar page links, a public overview page, and clearly grouped input, result, and visualization cards.

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
5. Share the URL directly or link it from a learning-management system. Test simultaneous usage before using it in a classroom.

Community Cloud offers free hosting for small apps, subject to resource limits, sleep after inactivity, and applicable policies. This prototype stores no student names or grades. No textbook or lecture files are included or needed for deployment.

## Selected engineering assumptions and boundaries

- US customary: **in, ksi, kips, kip-ft**; normalweight nonprestressed concrete, positive bending, symmetric top/bottom reinforcement centroid in 1 layer, εcu=0.003, steel stress ±fy, Es default 29,000 ksi. Strength is computed by **bisection of force equilibrium**.
- β₁ per ACI 318-19 Table 22.2.2.4.3.
- φ per ACI Table 21.2.2, tension-controlled when εt ≥ εty + 0.003 (also the nonprestressed beam design condition in §9.3.3.1). Transitional/compression-control results are shown for pedagogical analysis, **not as acceptable beam designs**.
- As,min per §9.6.1.2; the §9.6.1.3 possible exception is **not** evaluated.
- One-layer horizontal clear spacing checked by a simplified interpretation of §25.2.1, using bar diameter, 1 in, and 4/3 nominal maximum aggregate size. Aggregate input matters.
- For T-beams, the user provides a previously verified effective bf; §6.3.2.1 is **not implemented**. Positive moment and flange in compression only.
- Simplified treatment of compression steel accounts for net compression within the Whitney block. If top bars enter tension, the analysis flags it; the designer must reconsider modeling.
- Not checked: load combinations/analysis and live-load patterns, anchorage/development, stirrups and shear, deflection and serviceability, service-load crack-control steel spacing, exposure/cover compliance, seismic provisions, full 3D geometry, bar curtailment, multilayer placements, beam stability, detailing of fixed upper bars, or code edition updates.
- Notation and simplified instructional assumptions may differ from practice-specific requirements. Always consult the official code.

## File structure

```
app.py                     Public Streamlit user interface and multipage navigation
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

## References

- James K. Wight, *Reinforced Concrete: Mechanics and Design*, 8th edition, Pearson.
- ACI, *Building Code Requirements for Structural Concrete (ACI 318-19)*. Consult a properly licensed copy of the code for complete requirements.

The application provides original instructional diagrams and simplified workflows; no copyrighted textbook or code pages are redistributed. It does not implement every topic, example, or requirement from either reference.