# Two-Factor Momentum Screen — S&P 500 ∩ Nasdaq-100

**Run date:** 2026-06-21 · **Latest close used:** 2026-06-18

**Universe:** Full S&P 500 ∪ Nasdaq-100 membership — **516 unique tickers** — from the local Slickcharts exports (`S&P 500 Component YTD Returns.xlsx`, `Nasdaq 100 Component YTD Returns.xlsx`, 2026-06-21).
**YTD leg:** YTD returns straight from those Slickcharts files.
**1-Yr leg:** Trailing 1-year price return computed from the connected brokerage (Robinhood/Legend) `get_equity_historicals`, daily bars, split-adjusted, vs ~2025-06-20 — **swept across all 516 constituents** (full coverage, no gaps).
**Method:** Rank Top-20 by YTD and Top-20 by trailing 1-Yr over the full universe; inner-join the two lists.

> **Cross-check:** Slickcharts YTD and brokerage-computed YTD agree to within rounding (e.g. SNDK 820.36% vs 820.4%, WDC 333.17% vs 333.2%), so the two data sources are consistent.

## Result: 17 overlapping tickers (Top-20 YTD ∩ Top-20 1-Yr)

Sorted descending by Trailing 1-Yr Return.

| #   | Ticker | 1-Yr Return | YTD Return | Technical Rationale                                                                                                        |
| --- | ------ | ----------: | ---------: | -------------------------------------------------------------------------------------------------------------------------- |
| 1   | SNDK   |    +4590.3% |    +820.4% | NAND-memory super-cycle; the largest move in the entire screen and #1 on both legs.                                        |
| 2   | WDC    |    +1158.6% |    +333.2% | HDD + flash storage leverage to the AI-data buildout; near-vertical 1-Yr trend.                                            |
| 3   | LITE   |     +848.0% |    +130.6% | Optical-component surge on datacenter-interconnect demand; huge 1-Yr with strong YTD follow-through.                       |
| 4   | MU     |     +817.5% |    +297.3% | DRAM/HBM memory leader; price extended well above rising long-term moving averages.                                        |
| 5   | STX    |     +717.2% |    +288.6% | Mass-capacity HDD cycle; among the strongest dual-window movers.                                                           |
| 6   | INTC   |     +535.6% |    +263.1% | Turnaround re-rating with accelerating YTD confirming the longer-term trend.                                               |
| 7   | TER    |     +407.5% |    +126.3% | Semiconductor-test (Teradyne) riding AI capex; top-decile on both horizons.                                                |
| 8   | COHR   |     +379.8% |    +111.1% | Photonics/laser supplier to AI networking; powerful 1-Yr with solid YTD.                                                   |
| 9   | LRCX   |     +329.9% |    +127.3% | Wafer-fab-equipment leader in a durable uptrend.                                                                           |
| 10  | MRVL   |     +322.5% |    +265.5% | Custom-silicon / AI-networking momentum; highest YTD of the semis cluster bar ARM.                                         |
| 11  | AMD    |     +319.0% |    +150.9% | Datacenter-GPU traction driving a persistent uptrend in both windows.                                                      |
| 12  | FIX    |     +293.5% |    +110.8% | Data-center mechanical/HVAC contractor (Comfort Systems) — a picks-and-shovels AI-infrastructure play with broad strength. |
| 13  | GLW    |     +286.6% |    +122.6% | Corning optical-fiber/glass demand from AI datacenters; strong on both legs.                                               |
| 14  | AMAT   |     +264.2% |    +140.1% | Broad semicap strength, consistently top-ranked on both horizons.                                                          |
| 15  | DELL   |     +243.1% |    +225.3% | AI-server demand — the highest-YTD hardware name with a top-tier 1-Yr.                                                     |
| 16  | KLAC   |     +205.4% |    +113.6% | Process-control franchise with a durable uptrend.                                                                          |
| 17  | ARM    |     +203.0% |    +302.0% | Royalty/licensing momentum; the strongest YTD acceleration in the group.                                                   |

## Lists behind the join

**Top-20 YTD (Slickcharts, S&P 500 ∪ Nasdaq-100):** SNDK, WDC, ARM, MU, STX, MRVL, INTC, DELL, AMD, AMAT, LITE, LRCX, TER, ON, GLW, MRNA, KLAC, COHR, FIX, Q

**Top-20 Trailing 1-Yr (full-universe sweep):** SNDK, WDC, LITE, MU, STX, INTC, CIEN, TER, COHR, SATS, LRCX, MRVL, AMD, FIX, GLW, AMAT, DELL, KLAC, ARM, ALB

**In one list but not both (excluded):** ON (+130% 1-Yr), MRNA (+147%), Q (+80%) — top-20 YTD but below the +183% 1-Yr cutoff; CIEN (+475%/+83% YTD), SATS (+335%/+0.4% YTD), ALB (+183%/+13% YTD) — top-20 1-Yr but YTD below the +107% top-20 cutoff (the "ran in H2-2025, flat in 2026" profile).

## Method notes & caveats

- **Two-leg screen only.** The analyst-target "upside potential" leg was dropped: the brokerage connector has no analyst price-target data, and the connected Alpha Vantage key is free-tier (25 req/day, exhausted). Add a premium Alpha Vantage / FMP key to restore the third leg.
- **1-Yr leg — full coverage.** Trailing 1-Yr was computed for **all 516 constituents** (no sampling). The sweep surfaced two names with a strong 1-Yr but weak YTD — SATS (+335% 1-Yr / +0.4% YTD) and ALB (+183% / +13%) — which entered the 1-Yr Top-20 and raised its cutoff to +183%. Because every intersection member exceeds that (ARM, the lowest, is +203%), none were displaced, so the full sweep confirms the same 17-name result.
- **Source fidelity — verified.** The universe and YTD leg come from the local Slickcharts spreadsheet exports (clean, structured data — no OCR or web-fetch truncation). The full 516-name membership reproduces the union Top-20 YTD exactly. (MRVL is sourced from the Nasdaq-100 file; it does not appear in the S&P 500 list.)
- Returns are **price-only** (dividends excluded), split-adjusted, as of the 2026-06-18 close.

---

_Not investment advice. Figures reflect the connected data feeds as of the run date._
