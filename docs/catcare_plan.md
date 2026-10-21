# CatCare: Cat Health Expert System — Design Plan

Draft for review, Oct 21, 2026. Nothing here is built yet. The engine (certainty factors, backward chaining, explanations, KB checker, test harness) comes from the earlier network-fault version of this project; this plan covers the new knowledge base and the features the instructor's brief adds.

**Status: waiting for the instructor to approve a veterinary domain.** If he wants human medicine instead, the same plan works with dengue, typhoid and malaria.

> **Update Oct 22, 2026:** steps 1–4 are built (knowledge base, engine changes, normaliser, tests). The rules as built are in `kb/rules.json` (58 rules); differences from section 6 below and the results of checking every ⚠️ claim are in `docs/kb_changes.md`.

## 1. What the system does

An owner describes their cat's problem. CatCare asks only the questions it needs, then gives:

1. **Urgency** (decision making, always given): Emergency, go now / See a vet today / See a vet in 1–2 days / Home care and watch.
2. **Most likely condition** with a certainty word: Cat Flu, Cat Parvo or Blocked Bladder, or "not one of the three, see a vet".
3. **Options with pros and cons** (decision support): the owner chooses what to do.
4. **Explanations**: Why? (during questions), How? and Why not X? (at the result).

Every result says it is not a substitute for a vet. Danger signs always lead to "Emergency", even when the cause is not one of the three conditions.

## 2. Scope

| Easy name | Medical name | Typical urgency | Main source |
|---|---|---|---|
| **Cat Flu** | Feline upper respiratory infection | Home care to vet in 1–2 days | Cornell Feline Health Center: Respiratory infections |
| **Cat Parvo** | Feline panleukopenia | Vet today (emergency for weak kittens) | WSU Veterinary Hospital; VCA; ASPCApro |
| **Blocked Bladder** | Urethral obstruction | Emergency | Cornell Feline Health Center: Feline lower urinary tract disease |

Out of scope: other diseases, medicine names and doses (CatCare never prescribes), dogs and other pets.

## 3. How a session runs

1. **Free-text start.** "My cat is sneezing & has runny eyes, not eating since yesterday." The normaliser extracts known facts (sneezing = yes, eye discharge = yes, not eating for ~24 h) and shows "I understood: … Is this right?" so the owner can correct it.
2. **Triage first.** The engine establishes `danger_sign` before anything else (declared in the KB as `start_with`). If a danger sign is present, an Emergency banner shows immediately; diagnosis continues so the owner can tell the vet what is likely.
3. **Diagnosis.** Backward chaining over the three conditions: highest belief first, ties broken by rank, one question at a time, forward pass after every answer.
4. **Urgency decision.** A second goal group, evaluated after the conditions. Its rules may use the conditions' beliefs as premises. Policy (declared in the KB): pick the **most severe** level whose CF is above 0.2. When in doubt, be more urgent.
5. **Result and decision support.** Condition + certainty word, urgency, options with pros and cons, explanations, disclaimer.

## 4. Inputs (askable parameters)

About 25 inputs; a typical session asks 6–10 because backward chaining skips what isn't needed and the free-text start pre-fills some.

Numeric inputs are typed freely and converted to categories by **bands stored in the KB**, so rules stay simple and the cut-offs are data, not code.

| ID | Question | Values / bands | Flexible input examples |
|---|---|---|---|
| A1 | How old is your cat? | kitten (< 12 months), adult, senior (> 10 years) ⚠️ verify cut-offs | "6 months", "6 mo", "half a year", "2 yrs", "two years", "kitten" |
| A2 | Is your cat male or female? | male / female | "male", "tom", "boy", "billa"; "female", "girl", "billi" |
| A3 | Has your cat had its vaccinations (FVRCP)? | yes / no | "yes", "vaccinated", "all shots", "FVRCP done", "no", "never" |
| A4 | Has your cat been near other cats recently (new cat, outdoors, cattery, shelter)? | yes / no | |
| S1 | Is your cat sneezing? | yes / no | "sneezing", "chheenk" |
| S2 | Is there discharge from the eyes? | yes / no | "runny eyes", "watery eyes", "eye gunk" |
| S3 | Is there discharge from the nose? | yes / no | "runny nose", "snotty nose" |
| S4 | Are the eyes red or swollen around the edges? | yes / no | |
| S5 | Are there sores in the mouth, or is your cat drooling? | yes / no | "mouth ulcers", "drooling", "ulcers" |
| S6 | What is your cat's temperature? (optional) | normal / high (> 102.5 °F / 39.2 °C ⚠️ verify) | "102", "a hundred and two", "102°F", "39.5 C", "39.5°c", "feels hot" |
| S7 | Is your cat eating? | normal / less / not at all | "not eating", "khana nahi kha rahi" |
| S8 | How long since it last ate? | under 24 h / over 24 h ⚠️ verify cut-off | "since yesterday", "2 days", "36 hrs", "a day and a half" |
| S9 | Is your cat unusually tired, weak or hiding? | yes / no | "lethargic", "sleepy", "weak", "hiding" |
| S10 | Is your cat vomiting? | yes / no | "vomiting", "throwing up", "ulti", "being sick" |
| S11 | Is there diarrhoea? | yes / no | "diarrhea", "diarrhoea", "loose stool", "dast" |
| S12 | Is there blood in the stool or vomit? | yes / no | |
| S13 | Is your cat straining in the litter box? | yes / no | "straining", "pushing", "trying to pee" |
| S14 | Is it going to the litter box much more often than usual? | yes / no | |
| S15 | Is it passing only a little urine, or none at all? | yes / no | "no pee", "only drops", "nothing comes out" |
| S16 | Does it cry or yowl when trying to urinate? | yes / no | |
| S17 | Is there blood in the urine? | yes / no | "red pee", "pink urine" |
| S18 | Is it licking its genital area a lot? | yes / no | |
| D1 | Is your cat breathing with its mouth open or struggling to breathe? | yes / no | Help: at rest, more than 35 breaths a minute is a concern (Cornell) |
| D2 | Has your cat collapsed, or can it not stand up? | yes / no | |

Every input has a `help` line (how to check, in plain words) and a `why` line. Answer certainty works as before: Yes / Probably / Not sure / Probably not / No, typed or tapped.

## 5. Intermediate facts (derived)

| Fact | Meaning | Concluded from |
|---|---|---|
| `respiratory_signs` | Cat has upper-airway signs | S1, S2, S3 |
| `gi_signs` | Cat has stomach/gut signs | S10, S11 |
| `urinary_signs` | Cat has trouble urinating | S13, S14, S16 |
| `urine_blocked` | Urine can't get out | `urinary_signs` + S15 |
| `parvo_risk` | Cat is in the parvo risk group | A1, A3, A4 |
| `systemic_illness` | Cat is generally unwell | S6, S7, S9 |
| `danger_sign` | Needs a vet immediately, whatever the cause | D1, D2, `urine_blocked`, S8, S12, kitten + gut signs + weakness |

These are shared between conditions and urgency, which is what makes it a reasoning network rather than one question per answer.

## 6. Rules (58)

Starting CFs follow this scale: "absolute emergency" / "this means" 0.9–0.95, "usually" 0.7–0.8, "often / can indicate" 0.5–0.6, "may" 0.3–0.4. Scenario tests then check every clean path reaches ≥ 0.85, and every CF change goes in the change log.

Sources: **CR** Cornell respiratory infections · **CU** Cornell lower urinary tract disease · **WSU** WSU panleukopenia page · **VCA** VCA panleukopenia page · **ASP** ASPCApro panleukopenia · **S** safety rule (errs towards the vet; justified in the report).

### Layer 1: evidence → intermediate facts (27)

| Rule | IF | THEN | CF | Src |
|---|---|---|---|---|
| R1 | S1 sneezing | respiratory_signs | +0.8 | CR |
| R2 | S2 eye discharge | respiratory_signs | +0.8 | CR |
| R3 | S3 nose discharge | respiratory_signs | +0.8 | CR |
| R4 | S1 no AND S2 no AND S3 no | respiratory_signs | −0.9 | CR |
| R5 | S10 vomiting | gi_signs | +0.7 | WSU |
| R6 | S11 diarrhoea | gi_signs | +0.8 | WSU |
| R7 | S10 no AND S11 no | gi_signs | −0.9 | WSU |
| R8 | S13 straining | urinary_signs | +0.85 | CU |
| R9 | S14 litter box often | urinary_signs | +0.7 | CU |
| R10 | S16 cries when urinating | urinary_signs | +0.6 | CU |
| R11 | S13 no AND S14 no | urinary_signs | −0.9 | CU |
| R12 | urinary_signs AND S15 little/no urine | urine_blocked | +0.95 | CU |
| R13 | S15 no | urine_blocked | −0.9 | CU |
| R14 | A1 kitten | parvo_risk | +0.6 | WSU |
| R15 | A3 not vaccinated | parvo_risk | +0.8 | WSU |
| R16 | A3 vaccinated | parvo_risk | −0.8 | WSU |
| R17 | A4 near other cats | parvo_risk | +0.4 | ASP |
| R18 | S6 temperature high | systemic_illness | +0.6 | WSU, CR |
| R19 | S9 tired/weak/hiding | systemic_illness | +0.6 | WSU, CR |
| R20 | S7 not eating | systemic_illness | +0.6 | WSU, CR |
| R21 | D1 breathing difficulty | danger_sign | +0.95 | CR |
| R22 | D2 collapsed | danger_sign | +0.95 | WSU |
| R23 | urine_blocked | danger_sign | +0.95 | CU |
| R24 | S8 not eaten > 24 h | danger_sign | +0.7 | S ⚠️ find source |
| R25 | S12 blood in stool/vomit | danger_sign | +0.8 | VCA |
| R26 | A1 kitten AND gi_signs AND S9 weak | danger_sign | +0.8 | VCA (young kittens can die suddenly) |
| R27 | D1 no AND D2 no | danger_sign | −0.6 | S |

### Layer 2: conditions (19)

| Rule | IF | THEN | CF | Src |
|---|---|---|---|---|
| R28 | respiratory_signs | Cat Flu | +0.8 | CR |
| R29 | respiratory_signs AND S5 mouth sores/drooling | Cat Flu | +0.6 | CR |
| R30 | S2 eye discharge AND S4 red/swollen eyes | Cat Flu | +0.5 | CR |
| R31 | respiratory_signs AND A4 near other cats | Cat Flu | +0.4 | CR ⚠️ verify wording |
| R32 | respiratory_signs no | Cat Flu | −0.8 | CR |
| R33 | gi_signs AND respiratory_signs no | Cat Flu | −0.4 | CR |
| R34 | gi_signs AND parvo_risk | Cat Parvo | +0.8 | WSU, VCA |
| R35 | S11 diarrhoea AND S12 blood AND parvo_risk | Cat Parvo | +0.6 | VCA |
| R36 | gi_signs AND systemic_illness | Cat Parvo | +0.5 | WSU |
| R37 | parvo_risk no | Cat Parvo | −0.7 | WSU |
| R38 | gi_signs no | Cat Parvo | −0.8 | WSU |
| R39 | respiratory_signs AND gi_signs no | Cat Parvo | −0.4 | WSU |
| R40 | urine_blocked | Blocked Bladder | +0.95 | CU |
| R41 | urinary_signs AND A2 male | Blocked Bladder | +0.6 | CU ⚠️ verify "mostly males" |
| R42 | urinary_signs AND S17 blood in urine | Blocked Bladder | +0.3 | CU |
| R43 | urinary_signs AND S18 licking genitals | Blocked Bladder | +0.3 | CU |
| R44 | urinary_signs no | Blocked Bladder | −0.9 | CU |
| R45 | urinary_signs AND S15 no (passing normal urine) | Blocked Bladder | −0.6 | CU (bladder inflammation, not a blockage) |
| R46 | A2 female | Blocked Bladder | −0.4 | CU ⚠️ verify |

### Layer 3: urgency (12)

| Rule | IF | THEN | CF | Src |
|---|---|---|---|---|
| R47 | danger_sign | Emergency | +0.95 | S |
| R48 | Blocked Bladder | Emergency | +0.95 | CU ("absolute emergency") |
| R49 | Cat Parvo AND A1 kitten | Emergency | +0.7 | VCA |
| R50 | Cat Parvo | Vet today | +0.9 | WSU ("seen promptly") |
| R51 | urinary_signs AND urine_blocked no | Vet today | +0.7 | CU |
| R52 | systemic_illness AND S7 not eating | Vet today | +0.6 | S |
| R53 | Cat Flu AND S7 not eating | Vet today | +0.7 | CR |
| R54 | Cat Flu AND systemic_illness no | Vet in 1–2 days | +0.6 | CR |
| R55 | Cat Flu AND danger_sign no AND S7 eating normally | Home care | +0.7 | CR ⚠️ verify mild cases |
| R56 | danger_sign | Home care | −0.95 | S |
| R57 | danger_sign | Vet in 1–2 days | −0.9 | S |
| R58 | danger_sign no AND no condition above 0.2 | Vet in 1–2 days | +0.5 | S ("not one of the three": still see a vet) |

**Total: 58 rules** (27 + 19 + 12), every one tied to a source or a stated safety principle. ⚠️ marks claims to check against the source before writing `rules.json`.

## 7. Output wording

**Certainty words** (bands stored in the KB):

| CF | Word |
|---|---|
| ≥ 0.85 | definitely |
| 0.60 – 0.85 | quite possible |
| 0.40 – 0.60 | maybe |
| 0.20 – 0.40 | not sure |
| ≤ 0.20 | not shown (shown as "unlikely" in Why not?) |

Example result:

> **Urgency: Emergency, go now.**
> **Blocked Bladder: definitely.** Cat Parvo: unlikely. Cat Flu: unlikely.
> Your male cat is straining with little or no urine. Cornell calls a urinary blockage an absolute emergency.
> This is not a diagnosis by a vet; please see one.

"Definitely" still comes with "see a vet", so the system never claims certainty on its own.

## 8. Decision support (options with pros and cons)

Stored in the KB (`options.json`), shown for the decided urgency level. The owner picks; CatCare doesn't decide for them, though Emergency never offers "wait at home".

| Urgency | Option | Pros | Cons |
|---|---|---|---|
| Emergency | Nearest vet clinic now | Fastest treatment | May not have night staff or equipment |
| Emergency | 24-hour / emergency clinic | Equipped for emergencies, open at night | Costs more, may be far away |
| Emergency | Call a vet while travelling | Advice on the way, clinic can prepare | Needs a number; can't treat by phone |
| Vet today | Regular vet appointment today | Proper tests (e.g. parvo test), treatment early | Cost and travel |
| Vet today | Call the vet first | Cheap, vet decides how urgent | Risk of waiting too long |
| Vet in 1–2 days | Book a visit | Vet checks before it worsens | Cost; cat may recover anyway |
| Vet in 1–2 days | Home care, vet if worse | Free, less stress for the cat | Must watch closely for warning signs |
| Home care | Care at home (warm, quiet, clean eyes and nose, encourage eating) | Free, comfortable for the cat | Must watch for the warning signs listed |
| Home care | Vet visit for peace of mind | Certainty | Cost, travel stress for the cat |

Every option list ends with the warning signs that move the cat up a level ("If your cat stops eating for a day or struggles to breathe, go to a vet now").

## 9. Flexible input and robustness

New module `engine/normalize.py`, driven by synonym and unit data in the KB (no domain words in code):

- **Yes/no**: "yes", "y", "yeah", "haan", "ji", "han"; "no", "n", "nope", "nahi"; certainty words "probably", "maybe", "not sure", "dunno".
- **Numbers**: digits and words ("102", "one hundred and two", "a hundred and two", "half a year").
- **Units and conversion**: °F / °C / "degrees" / "F" / "c"; months / weeks / years / "mo" / "yrs"; hours / days.
- **Lists**: "and", "&", ",", "+" split a free-text description into facts.
- **Negation**: "no sneezing", "not vomiting", "isn't eating" are detected, so a mentioned symptom isn't automatically "yes".
- **Synonyms**: per parameter in the KB, including Roman Urdu.
- **Incomplete data**: "Not sure" / skipped answers give CF 0; the engine tries other rules and, if needed, ends with a differential or "see a vet".
- **Redundant data**: facts given twice are stored once; **contradictions** ("sneezing" in the description, then "no" to the sneezing question) are shown and the owner picks.
- **Bad input**: unrecognised or empty input asks again with examples; out-of-range values ("temperature 500") are rejected with a reason. Nothing reaches the engine unvalidated.
- **"Must not fail"**: fuzz tests throw thousands of random strings, emojis, huge numbers, empty input and SQL-looking text at the normaliser and the app logic; the test passes only if nothing crashes.

## 10. Engine changes (all generic: no cat-specific code)

| Change | Why |
|---|---|
| Goal groups in the KB, evaluated in order: conditions, then urgency | Urgency is a separate decision that uses the diagnosis |
| `start_with: ["danger_sign"]` in the KB | Triage before diagnosis |
| Rule premises may refer to goals of an earlier group | Urgency rules use the conditions' beliefs |
| Group policy in the KB: conditions = "highest CF", urgency = "most severe above 0.2" | Safety: when unsure, more urgent |
| Bands for numeric inputs | "6 months" → kitten, "39.5 C" → high |
| Certainty word bands | Sir's not sure → maybe → quite possible → definitely |
| `options.json` | Decision support |
| Fix-and-verify not used | You don't "try a fix and see" on a sick animal; `failed_fixes` stays in the engine, unused |

~~Keep the earlier network-fault knowledge base as a second example~~ (dropped: the old code was removed from the project).

## 11. Decision tree (for the instructor's "you are building a decision tree")

`tools/draw_tree.py` runs the engine on every combination of answers and draws the tree of questions it actually asks, with the result at each leaf. The tree is an **output** of the rules, not hand-written: change a rule and the tree redraws. It goes in the report, explained branch by branch.

## 12. Interface and deployment

- **Streamlit, text-only**: no images or charts, so it loads on 3G.
- **Screens**: describe the problem → confirm what was understood → questions (typed answer box + quick buttons) → result (urgency, condition, certainty word, options, Why/How/Why not) → Back / Start again at any point.
- **Emergency banner** appears as soon as a danger sign is established.
- **Deploy**: GitHub repo → Streamlit Community Cloud (free). `requirements.txt` for deployment holds only `streamlit` and `pydantic`; graphviz and pytest stay in a dev requirements file.
- **Before demo day**: test with Chrome DevTools "Slow 3G"; open the app before your slot (free apps sleep when unused).

## 13. Testing and evaluation

- **Scenario tests**: clean path for each condition reaches ≥ 0.85; danger sign with no condition → Emergency + "not one of the three"; uncertain answers → differential; mixed signs (flu + gut); bladder inflammation (straining but passing urine) → not Blocked Bladder, Vet today; triage asks danger signs first.
- **Normaliser tests**: a table of input → expected value for every flexible form above.
- **Fuzz tests**: nothing crashes.
- **KB checker**: unreachable goals, unused questions, cycles, contradictions, plus bands and options.
- **Evaluation**: 15+ case descriptions written from the sources (and any real cases you can collect from cat owners you know); report agreement for condition and urgency, and discuss every disagreement.

## 14. Build order

| Step | Work | Done when |
|---|---|---|
| 0 | Send the approval message to the instructor | He approves the domain |
| 1 | Verify every ⚠️ claim against its source | Each rule has a source quote or a stated safety reason |
| 2 | KB: params with help/why/synonyms/bands, conditions, urgency levels, 58 rules, options | `kb_check` clean |
| 3 | Engine: goal groups, `start_with`, goal premises, policies, certainty words | CatCare clean paths ≥ 0.85 |
| 4 | Normaliser + free-text start + fuzz tests | All flexible forms parse; fuzz finds no crash |
| 5 | Streamlit app | Full session works on a phone |
| 6 | Deploy to Streamlit Cloud, Slow 3G test | Live URL loads on 3G |
| 7 | Decision tree, evaluation cases, report | Ready for viva |

## 15. Known limitations (say them before the examiner does)

- Not a vet: no examination, no tests, no medicines.
- Only three conditions; others end as "not one of the three, see a vet".
- Owners judge symptoms by eye; most can't take a cat's temperature, so that input is optional.
- Rules come from written sources and safety principles, not a vet interview; CFs are starting values tuned against scenario tests.
- No Pakistan study on cat parvo was found; local relevance rests on unvaccinated kittens and the Islamabad calicivirus study.

## Sources

- [Cornell Feline Health Center: Respiratory infections](https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center/health-information/feline-health-topics/respiratory-infections)
- [Cornell Feline Health Center: Feline lower urinary tract disease](https://vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center/health-information/feline-health-topics/feline-lower-urinary-tract-disease)
- [WSU Veterinary Teaching Hospital: Feline panleukopenia virus (FPV) in cats](https://hospital.vetmed.wsu.edu/2026/03/02/feline-panleukopenia-virus-fpv-in-cats/)
- [VCA Hospitals: Feline Panleukopenia](https://vcahospitals.com/know-your-pet/feline-panleukopenia)
- [ASPCApro: Feline Panleukopenia](https://www.aspcapro.org/node/104430)
- [Feline calicivirus in Islamabad, Pakistan (researcherslinks)](https://researcherslinks.com/current-issues/Investigation-of-Clinical-Diseases-and-Surgical/18/1/10550/html)
