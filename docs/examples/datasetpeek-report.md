# DatasetPeek Profile Report

DatasetPeek version: 0.4.1

## File Summary

- Filename: synthetic_financial_sentiment_dataset_20k.csv
- Type: CSV
- Rows: 19998
- Columns: 3
- Read time: 1252 ms

## Orientation

- synthetic_financial_sentiment_dataset_20k.csv is a CSV dataset with 19998 rows and 3 columns.
- Detected 3 categorical/flag columns and 0 numeric columns.

## Signals

| Column | Signal | Detail |
| --- | --- | --- |
| text | Likely categorical | 180 distinct values |
| language | Likely categorical | 6 distinct values |
| sentiment | Likely categorical | 3 distinct values |

## Column Overview

| Name | Dtype | Role | Non-null % | Missing % | Unique | Top values |
| --- | --- | --- | --- | --- | --- | --- |
| text | String | Category | 100.0% | 0.0% | 180 | Demasiados cargos ocultos, no son transparentes. (133, 0.7%), Personale professionale e cortese, esperienza ecc… (132, 0.7%), Customer service was rude and unhelpful. (131, 0.7%), Troppe spese nascoste, non sono trasparenti. (131, 0.7%), Aprovação rápida e os fundos estavam disponíveis … (129, 0.6%) |
| language | String | Category | 100.0% | 0.0% | 6 | en (3333, 16.7%), pt (3333, 16.7%), es (3333, 16.7%), fr (3333, 16.7%), de (3333, 16.7%) |
| sentiment | String | Category | 100.0% | 0.0% | 3 | positive (6666, 33.3%), negative (6666, 33.3%), neutral (6666, 33.3%) |

## Numeric Summary

No numeric columns detected.

## Next Checks

- Review inferred roles and sample rows before downstream use.
