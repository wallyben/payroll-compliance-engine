# tests/test_contract_freeze.py

import inspect
from core.normalize import mapper
from core.rules import engine

def test_normalization_signature_freeze():
    sig = inspect.signature(mapper.normalize)
    params = list(sig.parameters.keys())

    # Must accept df + mapping
    assert params == ["df", "mapping"]

def test_normalization_return_shape():
    # Ensure function still returns tuple of length 2
    import pandas as pd
    df = pd.DataFrame(columns=["employee_id", "gross_pay", "net_pay"])
    mapping = {
        "employee_id": "employee_id",
        "gross_pay": "gross_pay",
        "net_pay": "net_pay"
    }

    result = mapper.normalize(df, mapping)
    assert isinstance(result, tuple)
    assert len(result) == 2

def test_engine_module_exists():
    assert engine is not None
