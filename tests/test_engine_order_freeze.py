import inspect
import core.rules.engine as engine

def test_engine_order_freeze():
    src = inspect.getsource(engine.run_all)

    # Deterministic rules must appear before plausibility calls
    idx_det_usc = src.find("rule_usc_deterministic_bounds")
    idx_det_prsi = src.find("rule_prsi_deterministic_bounds")
    idx_det_net = src.find("rule_net_deterministic_upper_bound")
    idx_det_paye = src.find("rule_paye_deterministic_bounds")
    idx_det_mw = src.find("rule_minimum_wage_deterministic")
    idx_det_ae = src.find("rule_auto_enrolment_deterministic")

    idx_plaus_usc = src.find("rule_usc_plausibility")
    idx_plaus_prsi = src.find("rule_prsi_plausibility_class_a")

    assert idx_det_usc != -1
    assert idx_det_prsi != -1
    assert idx_det_net != -1
    assert idx_det_paye != -1
    assert idx_det_mw != -1
    assert idx_det_ae != -1
    assert idx_plaus_usc != -1
    assert idx_plaus_prsi != -1

    assert idx_det_usc < idx_plaus_usc
    assert idx_det_prsi < idx_plaus_prsi
    assert idx_det_net < idx_plaus_usc
    assert idx_det_paye < idx_plaus_usc
    assert idx_det_mw < idx_plaus_usc
    assert idx_det_ae < idx_plaus_usc
