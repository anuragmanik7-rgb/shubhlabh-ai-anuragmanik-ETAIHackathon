# Customer research kit (C1 Significance, C6 Impact)

Goal by Fri 9 Oct evening: 1–2 operator interviews with an observed, timed planning task; 20 survey responses.
Ask permission before quoting anyone; anonymise by default ("category manager, multi-city grocery chain, Bengaluru").

## 1. Interview (30 minutes)
1. Walk me through the last festival promotion you planned. Who was involved, which files, how long end to end?
2. Where does the evidence come from — competitor prices, schemes, HQ policy? (WhatsApp? Excel? app screenshots?)
3. How do you decide *which* products and *how deep* a discount? How do you know it worked?
4. Tell me about a promotion that lost money or caused a stock-out. What went wrong?
5. How do you handle near-expiry stock today?
6. What happens when HQ changes the budget or a competitor cuts prices mid-promotion?
7. What would you never let software decide on its own?
8. (Show PromoPilot for 5 minutes.) What is useful? What is missing? What would make you distrust it?
9. Would you try it in shadow mode for four weeks (it plans, you compare, nothing goes live)? What would it be worth per month?
10. May we quote you (name/role/anonymous)?

## 2. Observed task (timed)
Task: "Plan a 7-day Navratri promotion for three cities with ₹30,000, no Home essentials in Delhi, clear near-expiry dairy."
- Round A, their usual way (spreadsheet/WhatsApp): record start, end, number of files/tools touched, decisions made, errors.
- Round B, PromoPilot: record start, end, number of corrections, whether they trusted the certificate, approval reason.
- Repeat round B with 3–5 proxy users (friends in retail/ops). Record task success (yes/no), time, and a System Usability Scale (10 items below).
- External anchor: RELEX reports a promotion campaign going from 4+ hours to under 2 minutes with agents (Google Cloud case study).

SUS items (1–5 scale): frequent use · unnecessarily complex · easy to use · need technical support · well integrated · too much inconsistency · learn quickly · cumbersome · confident · needed to learn a lot first.

## 3. Survey (10 questions, Google Form, share in WhatsApp groups and LinkedIn)
1. Role (category/promotion manager · kirana owner · distributor/sales · other)
2. City
3. Promotions you plan per month (0–5 · 6–20 · 21–50 · 50+)
4. Hours per promotion from idea to launch
5. Where competitor/scheme evidence arrives (WhatsApp images · app screenshots · PDFs · Excel · field reps)
6. In the last festival season, what share of your promotions do you think lost money? (0–20% · 21–40% · 41–60% · 60%+ · don't know)
7. Biggest pain (pick 2): choosing products · discount depth · stock-outs · expiry waste · competitor moves · HQ approvals · measuring results
8. Would you trust AI to read evidence and propose plans if a person approves? (1–5)
9. What must never be automated? (free text)
10. Would you try a free 4-week shadow pilot? (yes/maybe/no) + contact (optional)

## 4. What to bring back for the submission
- One quote for the video opening (with permission), the timed comparison (minutes vs hours), survey counts with n.
- Put numbers into `docs/evidence/research.json`: `{"interviews": n, "observed_task_minutes": {"usual": x, "promopilot": y}, "survey_n": n, "sus_mean": s, "pilot_interest": k}` and add a line to the tracker.
