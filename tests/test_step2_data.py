import numpy as np
import pandas as pd
import pytest

from churn.data.clean import CleaningPipeline, derive_features
from churn.data.label import monthly_snapshot_labels, static_labels


@pytest.fixture
def raw():
    base = {
        "CustomerId": ["1", "2", "3", "4"],
        "Exited": [0, 1, 1, 0],
        "EstimatedSalary": [10.0, 20.0, 20.0, 30.0],
        "CreditScore": [600, 700, 700, 800],
        "Geography": ["France", None, "France", None],
        "Gender": ["Male", "Female", "Female", "Male"],
        "Surname": ["A", "B", "B", "C"],
        "RowNumber": [1, 2, 3, 4],
    }
    for col in ["Age", "Tenure", "Balance", "NumOfProducts", "HasCrCard", "IsActiveMember"]:
        base[col] = [1, 2, 3, 4]
    return pd.DataFrame(base)


def _cfg():
    from churn.config import load_config
    return load_config()


def test_standardize_drops_and_renames(raw):
    from churn.data.ingest import standardize
    out = standardize(raw, _cfg())
    assert "customer_id" in out.columns and "churned" in out.columns
    assert "Surname" not in out.columns and "RowNumber" not in out.columns
    assert out["churned"].isin([0, 1]).all()


def test_schema_checks_reject_bad(raw):
    from churn.data.ingest import schema_checks
    assert schema_checks(raw, _cfg())["n_rows"] == 4
    dup = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate ids"):
        schema_checks(dup, _cfg())


def test_cleaning_pipeline_no_leakage_shapes(raw):
    std = raw.drop(columns=["RowNumber", "Surname"])
    train, test = std.iloc[:3], std.iloc[3:]
    pipe = CleaningPipeline(numeric=["CreditScore", "EstimatedSalary"], categorical=["Geography", "Gender"])
    tr = pipe.fit_transform(train)
    te = pipe.transform(test)  # only uses fitted params
    assert tr["CreditScore"].isna().sum() == 0
    assert te["Geography"].iloc[0] == "France"  # mode of train imputes missing test value
    # transform is deterministic given fit
    assert np.allclose(te["CreditScore"], pipe.transform(test)["CreditScore"])


def test_derived_features():
    df = pd.DataFrame({"Balance": [0.0, 100.0], "EstimatedSalary": [50.0, 50.0]})
    out = derive_features(df)
    assert out["zero_balance"].tolist() == [1, 0]
    assert np.allclose(out["balance_salary_ratio"], [0.0, 100.0 / 51.0])


def test_monthly_snapshot_labels():
    months = pd.PeriodIndex([f"2024-0{m}" for m in range(1, 7)], freq="M")
    rows = []
    for m in months:
        rows.append({"customer_id": "a", "month": m})
        rows.append({"customer_id": "b", "month": m})
    act = pd.DataFrame(rows)
    act = pd.concat([act, pd.DataFrame([{"customer_id": "b", "month": months[-1]}])], ignore_index=True)
    out = monthly_snapshot_labels(act, "customer_id", "month", horizon_months=2)
    # b stays active to the end -> labeled churned in months without 2 future active months
    b_last = out[(out.customer_id == "b")].sort_values("snapshot_date").iloc[-1]
    assert b_last["churned"] == 1
    assert set(out.columns) >= {"customer_id", "snapshot_date", "churned"}


def test_static_labels():
    df = pd.DataFrame({"customer_id": ["1"], "churned": [1]})
    out = static_labels(df)
    assert "snapshot_date" in out.columns
