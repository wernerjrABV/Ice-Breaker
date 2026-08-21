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
