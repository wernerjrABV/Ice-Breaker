from dataclasses import dataclass

from src import db


@dataclass(frozen=True)
class DemoCase:
    ticket_id: str
    nome_pdv: str
    assunto: str
    descricao_base: str


DEMO_CASES = (
    DemoCase(
        "DEMO-REMOTE",
        "Mercado Central",
        "Congela bebidas",
        "As bebidas estão congelando dentro do cooler.",
    ),
    DemoCase(
        "DEMO-DOOR",
        "Bar do João",
        "Porta não fecha",
        "A porta do cooler não permanece fechada.",
    ),
    DemoCase(
        "DEMO-SUPPLIER",
        "Padaria Primavera",
        "Não liga",
        "O cooler não liga.",
    ),
    DemoCase(
        "DEMO-URGENT",
        "Conveniência Estação",
        "Cheiro de queimado",
        "O PDV precisa relatar o sinal de risco durante a triagem.",
    ),
)


def _opening(case: DemoCase) -> str:
    return (
        f"Olá! Recebi um chamado do {case.nome_pdv} sobre {case.assunto}. "
        "Quero entender melhor o que está acontecendo e verificar se já consigo ajudar "
        "você agora. Você está próximo ao equipamento?"
    )


def seed_demo_cases() -> list[str]:
    """Insert missing presentation cases without changing an existing demo journey."""
    ticket_ids = []
    for case in DEMO_CASES:
        ticket_ids.append(case.ticket_id)
        if db.get_ticket(case.ticket_id) is not None:
            continue
        db.create_ticket(
            case.ticket_id,
            case.nome_pdv,
            case.assunto,
            case.descricao_base,
        )
        db.append_message(case.ticket_id, "assistant", _opening(case), "opening")
    return ticket_ids


def reset_demo_cases() -> list[str]:
    """Remove only fixed demo IDs, then recreate their initial logical state."""
    ticket_ids = [case.ticket_id for case in DEMO_CASES]
    placeholders = ", ".join("?" for _ in ticket_ids)
    with db._connect() as conn:
        conn.execute(
            f"DELETE FROM equipment WHERE ticket_id IN ({placeholders})",
            ticket_ids,
        )
        conn.execute(
            f"DELETE FROM messages WHERE ticket_id IN ({placeholders})",
            ticket_ids,
        )
        conn.execute(
            f"DELETE FROM tickets WHERE id IN ({placeholders})",
            ticket_ids,
        )
    return seed_demo_cases()
