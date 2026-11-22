# Instructor activity guide — ENCE 3680

This guide uses **Prediction → Exploration → Explanation → Verification**. Canvas remains the LMS; the Streamlit app provides the interactive visualization and deterministic computations.

## Activity A · Reinforcement, strength and ductility (15–20 min)

**Aligns with:** Ch4L1, Ch4L3, Ch4L4 (behavior, Mn, controlled sections).

1. **Predict (2 min):** Given the same concrete section, is more tensile reinforcement always better? Ask students to identify possible changes in flexural strength and ductility.
2. **Explore (5 min):** Open **What-if design studio**; hold b and d fixed while increasing As. Observe Mn, φMn, strain, and transition into non-tension-controlled behavior.
3. **Explain (5 min):** In pairs, explain why adding As shifts the neutral axis and changes the strain distribution. A group should explain how a lower φ can change the preferred design.
4. **Verify (5 min):** Select one point that remains tension-controlled and check by hand using T = As fy, a = T/(0.85 f'c b), εt = .003(d-c)/c, and Mn = T(d-a/2). Discuss when the yield assumption fails.
5. **Exit prompt:** Describe why the highest nominal moment capacity is not automatically the most appropriate member design.

**Assessment suggestion:** Score the explanation and verification in Canvas as short formative work, not automatically in the Streamlit app.

## Activity B · Doubly reinforced sections (15–20 min)

**Aligns with:** Ch4L5; later Ch5L5.

1. In **Flexural analysis**, start with a singly reinforced beam and note εt, c, Mn and φ.
2. Toggle **Include upper reinforcement** with the same bottom steel and geometry.
3. Compare the upper steel strain/stress, compression force, neutral axis, and strength. Discuss why upper bars may not yield.
4. Examine force equilibrium when the steel's occupied area displaces part of the idealized Whitney stress block. Ask which assumptions require checking.
5. Sketch how adding compression reinforcement could change ductility and long-term serviceability; emphasize that this app does **not** calculate deflection.

**Instructor note:** The fixed-upper-steel design search is illustrative. Full compression-reinforcement optimization and upper-bar constructability will be part of a later release.

## Activity C · Design with known dimensions (20–25 min)

**Aligns with:** Ch5L2, Ch5L3 and your design flowchart.

1. Supply b, h, Mu, fc, fy, cover, and stirrup size; ask students to estimate effective depth and As from a simplified lever arm before opening the app.
2. Use **Beam design: dimensions known** to display acceptable one-layer choices.
3. Compare 2–3 choices: steel area, actual d (depends on bar diameter), clear bar spacing and φMn.
4. Require each team to select an arrangement and explain tradeoffs in material use, construction, and available safety margin.
5. Verify their chosen design by hand; list additional ACI checks that prevent calling the output a completed member design.

## Activity D · Preliminary sizing with unknown dimensions (15–20 min)

**Aligns with:** Ch5L4, initial strain εt = 0.0075 method.

1. Assign a factored design moment Mu.
2. Predict a suitable b/d ratio, trial reinforcement ratio, and section dimensions.
3. Run **Preliminary member sizing**; students compare their predictions with the nominal sizes and bars returned by the program.
4. Change the strain target and b/d ratio and explain why different proportions lead to different reinforcement demands.
5. Compare two designs by strength, ductility, and constructability; identify unmodeled shear and deflection limitations.

## Where AI fits later

For an optional AI tutor, use a narrowly scoped service that receives **only** relevant summary outputs and the student's written explanation. It should ask probing questions and request verification instead of computing capacity or certifying code compliance. No API key is required for this first release, and no student data is saved.

**Compliance note:** All numerical results should be treated as formative and instructor-supervised. The app intentionally does not provide a full design certification.
