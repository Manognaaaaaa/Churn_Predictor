def test_churn_imports():
    import churn
    import churn.models  # noqa: F401

    assert churn is not None
