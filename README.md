![figure-ledger](assets/header.png)

# figure-ledger

The reply names an amount. The trace never returned it.

An agent says the reserve is ZAR 4,280, the waybill is AWB-100442, or the driver will call in 2 hours. figure-ledger reads each figure and compares it with tool output above that sentence. The same value is sourced. A different value of the same kind is a mismatch. No value of that kind is an orphan. An earlier sentence from the model is not evidence. The command prints a report and leaves the file untouched.

## Run

From the repo root. Python 3.11 or newer. No install and no API key.

```bash
python3 -m figure_ledger transcripts/*.jsonl
python3 -m figure_ledger --verbose transcripts/swapped.jsonl
python3 -m unittest discover -s tests -v
```

## Verdicts

| Verdict | Meaning |
|---|---|
| sourced | The same value is in an earlier tool result |
| mismatch | An earlier tool result has a different value of the same kind |
| orphan | No earlier tool result has that kind of figure |

Integrity is sourced divided by figures, printed to three decimal places. A transcript with no figures has integrity n/a. The total row adds the counts, then divides.

## Score

On the transcripts in this repo:

```
transcript                  figures  sourced  mismatch  orphan  integrity
--------------------------  -------  -------  --------  ------  ---------
transcripts/honest.jsonl    3        3        0         0       1.000
transcripts/invented.jsonl  2        1        1         0       0.500
transcripts/swapped.jsonl   3        1        1         1       0.333
TOTAL                       8        5        2         1       0.625
```

8 figures, 5 sourced, 2 mismatches, 1 orphan.

`honest` looks up claim CLM-4418 and repeats the reserve ZAR 4,280 and the incident date 14 March 2026. Three sourced. `invented` gets the same lookup and says the claim is settled for ZAR 12,400. The reference is sourced. The amount is a mismatch. `swapped` looks up waybill AWB-882190 and the slot 18 April 2026. The reply books AWB-100442, keeps the date, and adds a callback in 2 hours.

```
transcripts/swapped.jsonl
  mismatch   reference  AWB-100442  value AWB-100442  earlier AWB-882190
  sourced    date       18 April 2026  value 2026-04-18  earlier 2026-04-18
  orphan     count      2 hours  value 2 hour  earlier none
```

## What counts

| In the reply | Kind | Same value |
|---|---|---|
| An amount with R, ZAR, USD, $, EUR, €, GBP, £, NGN, or ₦ | money | The same amount. Commas and spaces are thousands separators. `ZAR 4,280` and `R4,280.00` are the same value. |
| `2026-03-14`, `14 March 2026`, or `March 14, 2026` | date | The same calendar day |
| `CLM-4418` or `AWB-882190` | reference | Two to eight letters, a hyphen, then three to eight digits. Case does not matter. |
| `2 hours` or `1 parcel` | count | The same number and unit. A plural matches the singular. Units are day, hour, minute, item, parcel, and call. |

A bare number is not a figure. Text inside a fenced block is not a figure. A number in the user turn is not evidence. A tool result below the reply is not evidence.

## Transcript

One JSON object per line.

```json
{"type":"tool","name":"lookup_claim","output":"reference CLM-4418\namount ZAR 4280\nincident_date 2026-03-14"}
{"type":"assistant","text":"Claim CLM-4418 is open. The reserve is ZAR 4,280. The incident date is 14 March 2026."}
```

`user` turns are kept in the file and ignored by the score. A tool event needs `output` as a string.

## Order

Evidence has to appear above the sentence. A lookup that starts after the reply does not make the figure sourced.

## License

MIT
