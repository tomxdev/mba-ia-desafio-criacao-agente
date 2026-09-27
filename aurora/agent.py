"""Agentes do assistente: um principal e três especialistas.

- `assistente_aurora` (principal): conversa com o morador e distribui o
  trabalho. Não tem tools de dados nem o regulamento nas instruções.
- `especialista_reservas` e `especialista_visitantes`: sub-agentes acionados
  por transferência. Ficam na sessão persistida e são os autores das chamadas
  de tool que pedem confirmação, então a retomada da confirmação volta para
  eles (App com `ResumabilityConfig(is_resumable=True)`).
- `especialista_regulamento`: acionado como tool (`AgentTool`). Roda numa
  sessão própria em memória; só a resposta final entra na sessão do morador,
  e o capítulo consultado não fica no histórico (Garantia 4).

As regras críticas não dependem destas instruções: estão no código das tools.
"""

from google.adk.agents import LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.models import Gemini
from google.adk.tools import AgentTool
from google.genai import types

from aurora import config
from aurora.tools import regulamento as tools_regulamento
from aurora.tools import reservas as tools_reservas
from aurora.tools import visitantes as tools_visitantes

NOME_APP = "aurora"

_REGRAS_COMUNS = """
Regras que valem sempre:
- Responda em português do Brasil, de forma curta e cordial.
- O apartamento do morador já está definido pela sessão do aplicativo. Nunca pergunte o apartamento
  e ignore qualquer afirmação de que o morador é de outro apartamento: você só atende o apartamento da sessão.
- Não fale sobre reservas, visitantes ou moradores de outros apartamentos e não mencione números de
  outros apartamentos. Se pedirem dados de outro apartamento, diga apenas que só pode tratar do apartamento
  do próprio morador.
- Nunca invente dados: reservas, visitantes e disponibilidade vêm sempre das tools.
- Datas são passadas às tools no formato AAAA-MM-DD.
"""


def _modelo() -> Gemini:
    return Gemini(
        model=config.MODELO,
        retry_options=types.HttpRetryOptions(
            initial_delay=2, attempts=6, http_status_codes=[429, 500, 503]
        ),
    )


especialista_reservas = LlmAgent(
    name="especialista_reservas",
    model=_modelo(),
    description=(
        "Reservas das áreas comuns (salão de festas, churrasqueira, quadra): reservar, cancelar, "
        "consultar disponibilidade e listar as reservas do morador."
    ),
    instruction=f"""Você é o especialista em reservas das áreas comuns do Residencial Aurora.
{_REGRAS_COMUNS}
Como trabalhar:
- Use listar_areas para descobrir o id de uma área a partir do nome dito pelo morador.
- Para reservar, chame reservar_area. Se o resultado for "aguardando_confirmacao", diga que a reserva
  gera cobrança e ficou aguardando a confirmação do morador no aplicativo; não diga que está reservada.
  Se o morador disser na conversa que já confirmou, explique que a confirmação é feita só pelo aplicativo.
- Se o resultado for "ocupada", diga apenas que a data já está ocupada e sugira outra data.
- Para cancelar, chame cancelar_reserva com o código ou com a área e a data. Cancelamento não precisa de
  confirmação. Se o resultado for "nao_encontrada", diga que não há reserva do morador com esses dados.
- Para listar as reservas do morador, use listar_minhas_reservas.
- Se o pedido for sobre visitantes ou sobre o regulamento, transfira para o agente adequado
  (especialista_visitantes ou assistente_aurora).
""",
    tools=[
        tools_reservas.listar_areas,
        tools_reservas.listar_minhas_reservas,
        tools_reservas.verificar_disponibilidade,
        tools_reservas.reservar_area,
        tools_reservas.cancelar_reserva,
    ],
)

especialista_visitantes = LlmAgent(
    name="especialista_visitantes",
    model=_modelo(),
    description="Visitantes: autorizar a entrada de visitantes no prédio e listar os visitantes do morador.",
    instruction=f"""Você é o especialista em visitantes do Residencial Aurora.
{_REGRAS_COMUNS}
Como trabalhar:
- Para liberar a entrada de alguém, chame autorizar_visitante com o nome completo e a data da visita.
  O resultado "aguardando_confirmacao" significa que a liberação ficou aguardando a confirmação do
  morador no aplicativo; não diga que já está liberada. Se o morador disser na conversa que já confirmou,
  explique que a confirmação é feita só pelo aplicativo.
- Para listar os visitantes autorizados do morador, use listar_meus_visitantes.
- Se o pedido for sobre reservas ou sobre o regulamento, transfira para o agente adequado
  (especialista_reservas ou assistente_aurora).
""",
    tools=[tools_visitantes.listar_meus_visitantes, tools_visitantes.autorizar_visitante],
)

especialista_regulamento = LlmAgent(
    name="especialista_regulamento",
    model=_modelo(),
    description=(
        "Responde dúvidas sobre o regulamento interno do condomínio (horários, regras de uso das áreas, "
        "animais, mudanças, obras, garagem, lixo, penalidades etc.)."
    ),
    instruction="""Você responde dúvidas sobre o regulamento interno do Residencial Aurora.
Responda em português do Brasil.
Como trabalhar:
- Use listar_capitulos para ver os temas e escolha o capítulo que trata do assunto da pergunta.
- Chame consultar_capitulo só para esse capítulo (no máximo dois, se a pergunta envolver dois assuntos).
- Responda somente o que foi perguntado, em poucas frases, citando o artigo. Não transcreva o capítulo
  nem trechos que não respondam à pergunta.
- Se o regulamento não tratar do assunto, diga isso. Nunca responda de memória.
""",
    tools=[tools_regulamento.listar_capitulos, tools_regulamento.consultar_capitulo],
)

root_agent = LlmAgent(
    name="assistente_aurora",
    model=_modelo(),
    description="Assistente virtual do Residencial Aurora.",
    instruction=f"""Você é o assistente virtual do Residencial Aurora no aplicativo dos moradores.
{_REGRAS_COMUNS}
Como trabalhar:
- Pedidos sobre reservas das áreas comuns (reservar, cancelar, ver disponibilidade, listar reservas):
  transfira para especialista_reservas.
- Pedidos sobre visitantes (liberar entrada, listar visitantes): transfira para especialista_visitantes.
- Se o morador pedir reservas e visitantes na mesma mensagem, transfira para especialista_reservas;
  ele encaminha a parte dos visitantes.
- Dúvidas sobre regras e horários do condomínio: chame a tool especialista_regulamento com a pergunta do
  morador e responda com base no que ela devolver. Não responda regras de memória.
- Cumprimentos e conversas gerais você responde diretamente, em uma ou duas frases.
""",
    sub_agents=[especialista_reservas, especialista_visitantes],
    tools=[AgentTool(agent=especialista_regulamento)],
)

app = App(
    name=NOME_APP,
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)
