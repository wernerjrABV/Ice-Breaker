import unicodedata

from src.models import Outcome, Priority, RiskFlag, Symptom, TriageDecision


_CRITICAL_RISKS = frozenset(RiskFlag)

_SYMPTOM_PHRASES: tuple[tuple[Symptom, tuple[str, ...]], ...] = (
    (
        Symptom.FREEZING_DRINKS,
        ("congela bebidas", "congelando bebidas", "bebidas congelando"),
    ),
    (
        Symptom.DOOR_NOT_CLOSING,
        ("porta nao fecha", "porta nao esta fechando"),
    ),
    (
        Symptom.NOT_COOLING,
        ("nao gela", "nao esta gelando", "nao refrigera"),
    ),
    (
        Symptom.NOT_POWERING_ON,
        ("nao liga", "nao esta ligando", "nao acende"),
    ),
    (
        Symptom.ABNORMAL_NOISE,
        ("barulho muito alto", "barulho estranho", "ruido muito alto", "ruido estranho"),
    ),
)

_REMOTE_CHECKLISTS: dict[Symptom, list[str]] = {
    Symptom.FREEZING_DRINKS: [
        "Verifique o ajuste de temperatura.",
        "Confira se há obstrução ou se a organização interna está adequada.",
        "Observe se há gelo visível bloqueando a circulação.",
    ],
    Symptom.DOOR_NOT_CLOSING: [
        "Confira se há obstrução ou itens fora da organização interna.",
        "Observe a porta e a vedação visível.",
        "Verifique se há gelo visível impedindo o fechamento.",
    ],
    Symptom.NOT_COOLING: [
        "Verifique o ajuste de temperatura.",
        "Confira se há obstrução ou se a organização interna está adequada.",
        "Confira se a ventilação externa está livre.",
    ],
}


def _remove_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def normalize_symptom(text: str) -> Symptom:
    normalized = " ".join(_remove_accents(text).split())
    for symptom, phrases in _SYMPTOM_PHRASES:
        if any(phrase in normalized for phrase in phrases):
            return symptom
    return Symptom.UNKNOWN


def decide_triage(symptom: Symptom, risks: set[RiskFlag]) -> TriageDecision:
    if _CRITICAL_RISKS.intersection(risks):
        return TriageDecision(
            outcome=Outcome.SUPPLIER,
            priority=Priority.URGENT,
            reason="Risco crítico identificado.",
        )

    if symptom in {Symptom.ABNORMAL_NOISE, Symptom.NOT_POWERING_ON}:
        return TriageDecision(
            outcome=Outcome.SUPPLIER,
            reason="Sintoma requer encaminhamento ao fornecedor.",
        )

    if symptom in _REMOTE_CHECKLISTS:
        return TriageDecision(
            outcome=Outcome.REMOTE_CHECKLIST,
            checklist=_REMOTE_CHECKLISTS[symptom].copy(),
            reason="Sintoma pode seguir checklist remoto seguro.",
        )

    return TriageDecision(
        outcome=Outcome.SUPPLIER,
        reason="Sintoma não reconhecido; encaminhamento ao fornecedor necessário.",
    )
