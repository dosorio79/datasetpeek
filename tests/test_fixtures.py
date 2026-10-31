from pathlib import Path

import polars as pl

FIXTURES = Path(__file__).parent / "fixtures"


def _top_non_null_ratio(series: pl.Series) -> float:
    values = series.drop_nulls()
    if values.is_empty():
        return 0.0
    counts = values.value_counts().sort("count", descending=True)
    return counts["count"][0] / values.len()


def _unique_ratio(series: pl.Series) -> float:
    values = series.drop_nulls()
    if values.is_empty():
        return 0.0
    return values.n_unique() / values.len()


def _load_csv() -> pl.DataFrame:
    return pl.read_csv(FIXTURES / "sample_profile.csv")


def _load_parquet() -> pl.DataFrame:
    return pl.read_parquet(FIXTURES / "sample_profile.parquet")


def test_csv_fixture_parses_with_expected_shape():
    df = _load_csv()

    assert df.height == 12
    assert df.width == 9
    assert df.columns == [
        "customer_id",
        "status",
        "churn_flag",
        "segment",
        "mostly_missing",
        "notes",
        "mixed_value",
        "opt_in_text",
        "score",
    ]


def test_parquet_fixture_matches_csv_row_data():
    csv_df = _load_csv()
    parquet_df = _load_parquet()

    assert parquet_df.height == csv_df.height
    assert parquet_df.columns == csv_df.columns
    assert parquet_df.to_dicts() == csv_df.to_dicts()


def test_fixture_columns_trigger_core_profile_signals():
    df = _load_csv()

    assert _unique_ratio(df["customer_id"]) == 1.0
    assert _top_non_null_ratio(df["status"]) == 1.0
    assert df["mostly_missing"].null_count() / df.height > 0.5

    churn_values = df["churn_flag"].drop_nulls().unique().to_list()
    assert sorted(churn_values) == [0, 1]

    assert _top_non_null_ratio(df["churn_flag"]) < 0.95
    assert _unique_ratio(df["segment"]) <= 0.3

    mixed_values = {str(value).lower() for value in df["mixed_value"].to_list()}
    assert any(value.isdigit() for value in mixed_values)
    assert any(not value.isdigit() for value in mixed_values)

    opt_in_values = {
        str(value).lower() for value in df["opt_in_text"].drop_nulls().unique().to_list()
    }
    assert opt_in_values <= {"yes", "no"}
