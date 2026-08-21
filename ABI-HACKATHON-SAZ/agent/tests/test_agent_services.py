from workflow.contracts import ConversationRequest, EquipmentLabel
from workflow.conversation import generate_reply
from workflow.label_reader import read_label


class FakeLlm:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def call(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def test_reads_label_with_injected_llm():
    expected = EquipmentLabel(modelo="CX-400", numero_serie="BR-12345", confianca=0.98)
    llm = FakeLlm(expected)

    assert read_label("data:image/jpeg;base64,abc", llm) == expected
    assert llm.calls[0]["response_format"] is EquipmentLabel
    assert llm.calls[0]["messages"][0]["content"][1]["image_url"]["url"] == "data:image/jpeg;base64,abc"


def test_reads_incomplete_label_with_low_confidence():
    result = read_label(
        "data:image/jpeg;base64,abc",
        FakeLlm({"modelo": "CX-400", "numero_serie": "", "confianca": 0.98}),
    )

    assert result.modelo == "CX-400"
    assert result.numero_serie == ""
    assert result.confianca < 0.5


def test_conversation_returns_one_short_question():
    request = ConversationRequest(
        nome_pdv="Bar do João",
        assunto="Não gela",
        stage="diagnostico",
        messages=[],
    )

    llm = FakeLlm(
        {
            "message": "A porta está fechando completamente?",
            "risks": [],
            "symptom": "nao_gela",
        }
    )
    result = generate_reply(
        request,
        llm,
    )

    assert result.message.count("?") == 1
    assert result.symptom == "nao_gela"
    assert llm.calls[0]["response_format"].__name__ == "ConversationReply"
    prompt = llm.calls[0]["messages"][0]["content"]
    assert "reparos elétricos" in prompt
    assert "abertura do equipamento" in prompt
    assert "nunca substitui as regras de segurança" in prompt
