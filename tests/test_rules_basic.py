from core.rules.rules import _usc_calc_annual

def test_usc_calc_basic():
    cfg = {"bands":[{"cap":12012,"rate":0.005},{"cap":12012+16688,"rate":0.02},{"cap":12012+16688+41344,"rate":0.03},{"cap":None,"rate":0.08}]}
    # income below first cap
    assert round(_usc_calc_annual(10000, cfg), 2) == round(10000*0.005, 2)
