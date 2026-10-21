# Knowledge base: verification and change log

Every check of a claim against its source, and every change to a rule, its premises or its CF. Starting point: the rules in `docs/catcare_plan.md` (Oct 21, 2026).

## Source verification (Oct 22, 2026)

| Claim | Result | Source |
|---|---|---|
| Upper respiratory signs: eye/nose discharge, sneezing, coughing, conjunctivitis, mouth ulcers, lethargy, anorexia | Confirmed | Cornell, Respiratory infections |
| Mouth ulcers with calicivirus | Confirmed but "rare": R29 CF lowered 0.6 → 0.4 | Cornell, Respiratory infections |
| Herpes can cause fever | Confirmed (R31) | Cornell, Respiratory infections |
| Flu most common in young cats and where many cats are kept (shelters, catteries) | Confirmed (R30, R21 wording) | Cornell, Respiratory infections |
| Mild flare-ups often clear up on their own | Confirmed for herpes (R54: home care for mild flu) | Cornell, Respiratory infections |
| Resting breathing should not exceed 35 breaths a minute | Confirmed (breathing_trouble help text) | Cornell, Respiratory infections |
| Bladder signs: difficult/painful urination, frequency, crying, blood in urine, urinating outside the box, licking genitals | Confirmed | Cornell, Feline lower urinary tract disease |
| Male cats at greater risk of obstruction ("longer and narrower" urethra) | Confirmed (R39, R45) | Cornell, Feline lower urinary tract disease |
| Obstruction is "an absolute emergency"; death may follow in under 24–48 hours | Confirmed (R3, R47) | Cornell, Feline lower urinary tract disease |
| Parvo signs: lethargy, appetite loss, fever, vomiting, diarrhoea; kittens and unvaccinated cats most at risk; prompt vet care | Confirmed | WSU Veterinary Hospital |
| Bloody diarrhoea in parvo; sudden death in young kittens | Confirmed (R35, R48) | VCA Hospitals |
| No food for ~24 hours → vet the same day | **Secondary sources only** (vet hospital guidance; WebVet citing Cornell). Kept as R51, marked secondary | Sydney Animal Hospitals; WebVet |
| Normal temperature 100.5–102.5 °F (38.1–39.2 °C) | **Secondary sources only**; Merck's adult figure not found. Used as the band boundary | cats.com and others |
| Kitten = under 1 year | Common definition, not from the sources; used as the age band | — |

## Changes

| Date | Rule | Old | New | Reason |
|---|---|---|---|---|
| 2026-10-22 | R29 | CF 0.6 (plan) | 0.4 | Cornell says mouth ulcers with calicivirus are rare |
| 2026-10-22 | R5 | `breathing no AND collapsed no → danger_sign −0.6` | `breathing no AND collapsed no AND blood no AND urinary_signs no → −0.8`, plus new **R58** (same with `urine_blocked no`) | The old rule fired first and cancelled part of the blockage evidence: danger ended at +0.65 for a blocked cat. "No danger" must only count when every danger check is clear. Blocked male now reaches Emergency at 0.97 |
| 2026-10-22 | plan R24, R26 | not eating > 24 h → danger; kitten + gut signs + weak → danger | moved/dropped: not eating > 24 h → **vet today** (R51); kitten + parvo → Emergency (R48) | Keeps triage to the danger signs that need a vet now; avoids asking every owner about appetite and age up front |
| 2026-10-22 | plan R58 | "no condition and no danger → vet in 1–2 days" | the urgency group's `fallback: vet_soon` | Cannot be written as an ordinary rule (needs "none of the conditions") |
