from src.models import Outcome, Priority, RiskFlag, Symptom
from src.triage_rules import decide_triage, normalize_symptom


def test_normalizes_supported_symptoms():
    assert normalize_symptom("O cooler está congelando bebidas") is Symptom.FREEZING_DRINKS
    assert normalize_symptom("a porta não fecha") is Symptom.DOOR_NOT_CLOSING
    assert normalize_symptom("geladeira não gela") is Symptom.NOT_COOLING
    assert normalize_symptom("equipamento não liga") is Symptom.NOT_POWERING_ON
    assert normalize_symptom("barulho muito alto") is Symptom.ABNORMAL_NOISE


def test_critical_risk_always_routes_urgently():
    result = decide_triage(Symptom.FREEZING_DRINKS, {RiskFlag.BURNING_SMELL})
    assert result.outcome is Outcome.SUPPLIER
    assert result.priority is Priority.URGENT
    assert result.checklist == []


def test_remote_candidate_returns_safe_checklist():
    result = decide_triage(Symptom.FREEZING_DRINKS, set())
    assert result.outcome is Outcome.REMOTE_CHECKLIST
    assert "ajuste de temperatura" in " ".join(result.checklist).lower()


def test_noise_routes_to_supplier():
    result = decide_triage(Symptom.ABNORMAL_NOISE, set())
    assert result.outcome is Outcome.SUPPLIER
    assert result.priority is Priority.NORMAL


def test_not_cooling_uses_the_complete_approved_checklist():
    result = decide_triage(Symptom.NOT_COOLING, set())

    assert result.outcome is Outcome.REMOTE_CHECKLIST
    assert result.checklist == [
        "Confira se a ventilação externa está livre.",
        "Verifique se a porta fecha completamente.",
        "Verifique o ajuste de temperatura.",
        "Observe se há gelo visível bloqueando a circulação.",
    ]


def test_not_powering_on_has_one_visual_external_step_before_supplier_decision():
    result = decide_triage(Symptom.NOT_POWERING_ON, set())

    assert result.outcome is Outcome.REMOTE_CHECKLIST
    assert result.checklist == [
        "Observe, sem tocar no cabo, plugue ou tomada, se o plugue externo está conectado."
    ]


def test_no_approved_checklist_mentions_opening_or_internal_repair():
    forbidden = ("abra", "painel", "componente interno", "reparo elétrico")

    for symptom in (
        Symptom.FREEZING_DRINKS,
        Symptom.DOOR_NOT_CLOSING,
        Symptom.NOT_COOLING,
        Symptom.NOT_POWERING_ON,
    ):
        checklist = " ".join(decide_triage(symptom, set()).checklist).casefold()
        assert all(term not in checklist for term in forbidden)
