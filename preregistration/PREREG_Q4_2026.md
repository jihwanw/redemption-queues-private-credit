# Pre-specified test for the next tender cycle: queue stock versus new demand

**Status: FROZEN 2026-10-22 23:28 KST by the author (Jihwan Woo), before any next-cycle results filing (first expected 2026-10-24, OCIC/OTIC; the Q4 monitor reported no new filings as of 2026-10-22). SHA-256 of this file with this status line removed: `36e5b40df280da04df0c967ff4712f218336a4eb440600d621433bc7a392dc92`. Any edit after this point is recorded as a dated amendment at the bottom of this file and does not alter the committed tests P1--P3.**

Manuscript: "Redemption Queues behind Quarterly Gates: Requests, Rationing, and Balance-Sheet Adjustment in Semi-Liquid Private Credit Funds, 2024–2026" (working title of the JFS re-edit; the JFSR version, "Do Redemption Gates Discipline or Destabilize?", was rejected 2026-10-09). Predecessor pre-registration: draft v3 §3.3 (2026-07-28) for the 2026Q3 cycle, whose committed result is reported in the manuscript §5.6.

## 1. What is known at the time of writing

Results filings (SC TO-I/A) observed through 2026-10-09, latest per fund:

| Fund | Latest results filing | Gross tendered | Accepted | Oversub. | Unfilled in prior offer | Resubmission ceiling share of latest queue | Group |
|---|---|---|---|---|---|---|---|
| OCIC | 2026-07-24 | 395.4M | 105.2M | 3.76 | 358.0M | 90% | stock-dominated |
| OTIC | 2026-07-24 | 109.9M | 14.4M | 7.61 | 102.7M | 93% | stock-dominated |
| ASIF | 2026-09-25 | 50.4M | 19.3M | 2.62 | 37.1M | 74% | stock-dominated |
| GCRED | 2026-08-11 | 9.0M | all (no proration) | 1.00 | 6.3M | 69% | stock-dominated |
| BCRED | 2026-08-04 | 191.8M | 93.1M | 2.06 | 0 (March offer filled 100%) | 0% | flow-dominated |
| HLEND | 2026-08-04 | 66.7M | 25.1M | 2.66 | 21.0M | 31% | flow-dominated |
| ADS | 2026-08-06 | 101.5M | 30.2M | 3.36 | 36.6M | 36% | flow-dominated |
| FPCF | 2026-07-29 | 1.55M | all | 1.00 | 0 | 0% | never gated |
| PCAP | 2026-07-31 | 1.40M | all | 1.00 | 0 | 0% | never gated |
| OSCF | 2026-08-14 | 8.86M | all (99.99% accepted) | 1.00 | 0 | 0% | never gated |

Source: `results/offer_master_v3.json` (offer-keyed, evidence-backed rebuild of 2026-10-16/18). Pre-freeze update 2026-10-19: the 2026-10-09 draft carried BCRED's prior unfilled as 66.8M from a mis-tabulated March offer; the data census found that BCRED's March 2026 offer (133,689,552 shares) was accepted in full, so its prior unfilled stock is 0 and its ceiling share 0% (group unchanged: flow-dominated). OSCF's final results do state accepted shares (99.99% of tenders), so OSCF enters as never gated rather than excluded; P3 keeps StockShare = 0 for it.

Group rule (fixed here): **stock-dominated** if the resubmission ceiling share of the latest queue exceeds 50 percent; **flow-dominated** otherwise among funds that prorated in 2026; **never gated** if no 2026 proration.

No fund has filed results for its next offer. Expected next results filings: OCIC, OTIC ~2026-10-24; FPCF ~10-28; BCRED, HLEND ~11-02; ADS, PCAP ~11-05; GCRED ~11-11; OSCF ~11-13; ASIF ~12-28.

## 2. Hypothesis

Appendix A (revised 2026-10-09), equation (stock–flow): under continued rationing with a stable threshold, gross tenders evolve as T_{n+1} = (1 − f) T_n + N_{n+1}. The first term is a stock of resubmitted requests that drains geometrically; the second is new demand. Where the latest queue is mostly stock, the next queue should be **smaller**; where it is mostly new flow, the model makes **no sign prediction** for the next cycle (the peak may come in the next cycle or later).

## 3. Committed tests

**P1 (primary; exact permutation).** For every 2026-gated fund with accepted-share counts whose next results filing is available by **2026-11-20**, compute g_i = ln T_{i,next} − ln T_{i,latest}. Predictions: (a) g_i < 0 for every stock-dominated fund; (b) mean g over stock-dominated funds is lower than over flow-dominated funds. For (b), the exact one-sided permutation p-value over all assignments of the group labels (expected 6 funds, 3 and 3, so 20 assignments and an attainable minimum of 0.05). Report (a) fund by fund regardless of outcome.

**P2 (secondary; levels).** For the same funds, compute NewFloor_{i,next} = max{0, T_{i,next} − Unfilled_{i,latest}} and report it against the fund's 2025 mean gross tender. Prediction: for stock-dominated funds the floor is at most twice the 2025 mean (drain complete). For flow-dominated funds, report whether the floor rises or falls relative to NewFloor_{i,latest}; no sign is predicted.

**P3 (committed regression; all ten funds with a next-cycle filing by 2026-11-20).**
Δln T_{i,next} = a + b · StockShare_i + c · ln ω_{i,latest} + e_i,
where StockShare_i = Unfilled_{i,latest−1} / T_{i,latest} (0 for never-gated funds, including OSCF) and ω_{i,latest} is the latest oversubscription ratio (1 if no proration). Prediction: b < 0. The model predicts c ≈ 0 once StockShare is controlled: the depth of the latest gate should not predict the next queue beyond its stock content (this is the point on which the JFSR referee and the manuscript's §5.6 split disagreed). Report HC1 p-values and an exact permutation p-value for b (n ≈ 10).

**Falsification.** If stock-dominated funds' gross tenders rise in the next cycle, the stock–flow reading of Appendix A is rejected and the manuscript's original "gates queue it, and the queue grows" conclusion is reinstated in stronger form. We commit to reporting either outcome in the main text.

## 4. Conditioning events

If, between 2026-10-09 and a fund's next results filing, the fund announces a change in its repurchase cap, a suspension of the offer, a third-party tender offer for its shares, a merger or listing, or a material credit event (a non-accrual increase of more than two percentage points of cost disclosed in a 10-Q), the fund is flagged and all tests are reported with and without it.

## 5. Late filers

Funds whose next results are filed after 2026-11-20 (ASIF ~12-28; OCIC/OTIC's subsequent offers) are reported in an addendum if they arrive before the manuscript is resubmitted, using the same tests; they are not used to alter P1–P3.

## 6. Data collection

`code/monitor_q4_filings.py` (cutoff 2026-09-26; log `results/q4_monitor_log.json`), same parser as the Q3 monitor. The Q3 monitor and `code/h3_test.py` are left untouched so the manuscript's committed Q3 result remains reproducible.

## Amendments

(none after freezing)

## Pre-freeze updates (draft still open)

- 2026-10-19: title line, BCRED and OSCF rows and the P3 note updated to the verified offer master (`results/offer_master_v3.json`); group assignments unchanged except OSCF (excluded → never gated). Recomputed table (latest result per fund filed by 2026-10-09): OCIC 91%, OTIC 93%, ASIF 74%, GCRED 69% stock-dominated; ADS 36%, HLEND 31%, BCRED 0% flow-dominated; FPCF, PCAP, OSCF never gated.

- 2026-10-23 09:55 KST (after freeze; does not touch P1--P3): the manuscript's working title now ends "2023--2026" instead of "2024--2026", to match the sample's first offers (late 2023).
