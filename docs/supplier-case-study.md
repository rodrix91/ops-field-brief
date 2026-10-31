# Supplier assignment and shipment integrity: reproducible case study

This is a **synthetic reference scenario**, not a real customer, logistics operator, deployed monitoring system or measured business impact. It shows how one operational data-quality policy can reject a risky shipment export and accept a corrected version without moving the thresholds.

## Business question

Can an eight-shipment extract proceed to downstream dispatch reporting when supplier assignments are missing, one shipment ID is repeated and a single identified supplier dominates the assigned workload?

The two small, UTF-8 CSV fixtures are deliberately Excel-compatible semicolon exports with a leading `sep=;` directive:

- [At-risk extract](../examples/supplier-risk-synthetic.csv)
- [Corrected extract](../examples/supplier-clean-synthetic.csv)

## Run the exact same controls on both extracts

From the repository root with Python 3.10+, use the following in a POSIX shell (or set `PYTHONPATH=src` for your own shell before running):

```bash
PYTHONPATH=src python -m ops_field_brief examples/supplier-risk-synthetic.csv \
  --required shipment_id,supplier,eta --key shipment_id --max-duplicates 0 \
  --group supplier --casefold-group --max-missing 0 \
  --max-assigned-group-share 0.60 --max-missing-group-share 0.20 \
  --min-distinct-groups 3 --min-rows 8 \
  --delimiter auto --strict-csv --json
```

To run the passing version, change **only** the input path to `examples/supplier-clean-synthetic.csv`. The quality gates and thresholds remain identical. Alternatively, run the automated regression:

```bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test_supplier_case_study.py' -v
```

## Expected results

| Measurement | At-risk extract | Corrected extract | Policy |
|---|---:|---:|---|
| Parsed shipments | 8 | 8 | At least 8 |
| Additional rows with repeated shipment IDs | 1 | 0 | 0 allowed |
| Rows missing supplier assignment | 2 | 0 | Required supplier; 0 missing |
| Rows missing ETA | 1 | 0 | Required ETA; 0 missing |
| Share without supplier assignment | 25% | 0% | At most 20% |
| Identified suppliers, after case-insensitive matching | 2 | 3 | At least 3 |
| Largest share **among assigned** shipments | 4/6 = 66.67% | 3/8 = 37.5% | At most 60% |
| CLI exit status | **1: quality failure** | **0: passes enabled gates** | Pass only on 0 |

The first extract deliberately uses `Andes Freight`, `andes freight` and `ANDES FREIGHT` as spellings of the same supplier. Without `--casefold-group`, a report could incorrectly split that concentration across several labels. The missing supplier placeholders (blank and `s/d`) count as *unassigned*, not as distinct vendors. The duplicate `S-003` shipment ID is an **extra row after the first occurrence**, not a claim that two distinct IDs are bad.

The 60% threshold is evaluated among the six **assigned** rows, not all eight shipments. Consequently, the at-risk extract fails even though its largest overall group accounts for only four of eight rows. The corrected fixture models an illustrative cleanup with complete assignments, distinct shipment IDs and a broader supplier mix. It does not represent actual source-system remediation.

## Operational decision

An exit status of `1` signals that the export should be quarantined for review before it feeds a dashboard, scheduling report or supplier reconciliation. Exit `2` means configuration or input is invalid; it must not be mistaken for a passed quality gate. The automation should only advance when its agreed checks exit `0`.

**For reviewers / Para evaluadores:** this example demonstrates data completeness, supplier concentration, duplicate identifiers, Excel-compatible regional CSV parsing and reproducible before/after quality gates. It does not prove a production deployment, validated business thresholds, improved supplier performance or financial savings. Production thresholds must be selected by the responsible data owner.

See [the operations playbook](README.md) for other policies and [the main README](../README.md) for command reference.
