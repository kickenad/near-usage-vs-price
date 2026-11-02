# Usage vs Price: NEAR's token price is not tracking its on-chain usage

## Claim

Over {{range.days}} days of NEAR mainnet data ({{range.first_day}} → {{range.last_day}}), changes in on-chain usage explain very little of the changes in the NEAR price. Since the usage peak, the headline usage counts have fallen much further than the price:

| Series (30-day average) | Peak | Peak date | Latest | Latest as % of peak |
|---|---|---|---|---|
| NEAR price (USD) | {{peaks.near_price.peak_30d_avg}} | {{peaks.near_price.peak_date}} | {{peaks.near_price.latest_30d_avg}} | {{peaks.near_price.pct_of_peak}}% |
| Transactions / day | {{peaks.txns.peak_30d_avg}} | {{peaks.txns.peak_date}} | {{peaks.txns.latest_30d_avg}} | {{peaks.txns.pct_of_peak}}% |
| Active accounts / day | {{peaks.active_accounts.peak_30d_avg}} | {{peaks.active_accounts.peak_date}} | {{peaks.active_accounts.latest_30d_avg}} | {{peaks.active_accounts.pct_of_peak}}% |
| Gas used / day (PGas) | {{peaks.gas_pgas.peak_30d_avg}} | {{peaks.gas_pgas.peak_date}} | {{peaks.gas_pgas.latest_30d_avg}} | {{peaks.gas_pgas.pct_of_peak}}% |

Our reading: headline usage on NEAR is dominated by a few high-volume apps whose activity comes and goes (see the April 2026 cliff below), and the price is set by things other than on-chain activity. A rising price with falling usage counts is not a contradiction once you accept that.

## Evidence for

1. **Weak co-movement.** Correlation of ~monthly log changes between price and transactions is {{correlations_monthly_log_change.all.txns}} over the whole history ({{correlations_monthly_log_change.all.weeks}} weekly samples). For active accounts it is {{correlations_monthly_log_change.all.active_accounts}}. In 2025–2026 the active-account figure is {{correlations_monthly_log_change.2025_2026.active_accounts}}, which is effectively no relationship.
2. **Usage moves in shocks the price ignores.** Of the {{shock_summary.n}} largest one-day transaction shocks since 2022, {{shock_summary.flat_price_n}} came with the price moving less than 5%. The most recent was {{shock_summary.latest.date}}: transactions {{shock_summary.latest.txns_pct}}%, gas used {{shock_summary.latest.gas_pct}}%, active accounts {{shock_summary.latest.accounts_pct}}%, price {{shock_summary.latest.price_pct}}%. Gas used is measured by consensus, so this was a real change in load and not an indexer glitch. It simply didn't matter to price.
3. **2026 runs the opposite way.** From the 30-day average on {{since_2026_01.from}} to today, NEAR's price changed {{since_2026_01.near_price}}%, while transactions changed {{since_2026_01.txns}}%, active accounts {{since_2026_01.active_accounts}}% and gas used {{since_2026_01.gas_pgas}}%.
4. **Fees can't carry the valuation.** On {{latest.date}} the market cap was ${{latest.market_cap_usd_bn}}bn and the network collected ${{latest.fee_usd}} in fees that day. That puts market cap at {{latest.mcap_to_annual_fees}}× annualised (30-day) fees. Fee revenue isn't what's pricing the token.

## The April 2026 cliff, traced to one app

Daily transactions fell {{shock_summary.latest.txns_pct}}% on {{shock_summary.latest.date}}. To find out why, we read raw blocks rather than trusting an indexer. We took {{rpc_crosscheck.2026-03-25.sampled_blocks}} evenly spaced blocks on {{april_2026_cliff.before}} and on {{april_2026_cliff.after}}, then counted signed transactions by the app that owns the receiving account.

- On {{april_2026_cliff.before}}, **`{{april_2026_cliff.parent}}`** sub-accounts received {{april_2026_cliff.share_before_pct}}% of sampled transactions, about {{april_2026_cliff.est_txns_day_before}} a day.
- On {{april_2026_cliff.after}}, its share was {{april_2026_cliff.share_after_pct}}%.
- That one app accounts for {{april_2026_cliff.total_drop_explained_pct}}% of the whole drop in daily transactions between the two days.

So the largest usage collapse of 2026 was a single app switching off its on-chain activity. It wasn't a broad user exodus, and the price didn't react to it. Headline transaction counts are dominated by whichever app is busiest, and that is a weak base for any "usage drives price" argument.

## Evidence against (what weakens the claim)

1. **Gas is the honest usage measure, and it does correlate somewhat with price.** In 2025–2026, price vs gas used is {{correlations_monthly_log_change.2025_2026.gas_used}}, the highest of any pair we measured. Raw transaction and account counts are noisy (bots, airdrops, relayers). Measured by compute used, usage and price are more linked than the headline counts suggest.
2. **Indexer definitions.** "Active accounts" and "transactions" are NearBlocks' definitions. A methodology change could look like a usage collapse. Our raw-block samples agree with the indexer's daily transaction counts: the indexer-to-raw ratio was {{rpc_crosscheck.2026-03-25.indexer_over_rpc}} on {{april_2026_cliff.before}}, {{rpc_crosscheck.2026-04-10.indexer_over_rpc}} on {{april_2026_cliff.after}} {{rpc_crosscheck.2026-11-01.indexer_over_rpc}} on 2026-11-01, and {{rpc_crosscheck.2024-06-15.indexer_over_rpc}} and {{rpc_crosscheck.2025-06-15.indexer_over_rpc}} on 2024-06-15 and 2025-06-15. But these are samples ({{rpc_crosscheck.2026-11-01.sampled_txns}} transactions on the quietest day), not full recounts, and we did not verify "active accounts" at all.
3. **Activity may have moved, not vanished.** NEAR Intents (`intents.near`) has {{intents_near_lifetime_txns}} lifetime transactions. Intents batch many user actions into one transaction, so per-transaction counts understate cross-chain usage settled on NEAR.
4. **Correlation of changes over ~monthly windows** misses lagged effects (usage today, price next quarter). We did not test lags.

## What would change our mind

- Monthly price/usage correlation rising above 0.5 for two consecutive years on any usage series.
- Fees rising enough to bring market cap below ~100× annualised fees.
- Evidence that the activity which left (for example `{{april_2026_cliff.parent}}`) was what supported the price. That would mean a price drop following its exit with a lag, which we did not test.

## Method in one paragraph

`fetch.py` saves the raw API responses unchanged and writes SHA-256 hashes. `sample_rpc.py` samples blocks from archival RPC on chosen days and counts signed transactions per receiving contract. `metrics.py` computes every number shown here into `data/derived/metrics.json`. `build.py` fills this file's `{{…}}` placeholders from that JSON and fails on any unknown key. Tests check that every number in THESIS.md appears in metrics.json and that the raw files match the manifest.
