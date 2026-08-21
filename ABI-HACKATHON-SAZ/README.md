# Hackathon SAZ - Grand Slam

*Templates para aplicações de front-end, back-end e agentes baseados em CrewAI.*

# Primeira vez por aqui?

Este repositório contém três projetos que funcionam em conjunto e podem ser usados como projeto-base/template para
desenvolver sua solução durante o Hackathon SAZ - Grand Slam:

- **`agent/`** — um fluxo de trabalho baseado em CrewAI exposto por meio de um serviço FastAPI (API do Agente).
- **`backend/`** — um serviço FastAPI que recebe solicitações do front-end, gerencia solicitações em um banco SQLite e as encaminha para a API do Agente (API de Back-end).
- **`frontend/`** — uma aplicação React de página única que se comunica com a API de Back-end.

O fluxo típico de solicitações é: **Front-end → API de Back-end → API do Agente**.

![Hackathon SAZ - Grand Slam](hackathon.png)

## Pré-requisitos

Para executar o projeto em sua máquina, instale primeiro os seguintes pré-requisitos:

- [Python](https://www.python.org/) (para os projetos Python `agent` e `backend`)
- [uv](https://docs.astral.sh/uv/) (para os projetos Python `agent` e `backend`)
- [Node.js](https://nodejs.org/) e npm (para o projeto `frontend`)

## Executando os três projetos em conjunto

Você pode pedir facilmente a um agente de IA que execute os três projetos em conjunto, fornecendo as instruções abaixo.

Se precisar executar cada projeto separadamente, siga manualmente estas instruções a partir do diretório raiz:

## Executando a API do Agente

```bash
cd agent
uv sync
.venv\Scripts\activate
uv run api
```

Copie `agent/.env.example` para `agent/.env` e preencha as variáveis `OPENAI_*` antes de iniciar o serviço.

A API do Agente é iniciada em `http://127.0.0.1:8000`.

## Executando a API de Back-end

```bash
cd backend
uv sync
.venv\Scripts\activate
uv run api
```

Copie `backend/.env.example` para `backend/.env` e verifique se `AGENT_API_URL` aponta para a API do Agente (o padrão é `http://127.0.0.1:8000/kickoff`).

A API de Back-end é iniciada em `http://127.0.0.1:8001`. Verifique se a API do Agente já está em execução, pois a API de Back-end encaminha as solicitações para ela.

## Executando o Front-end

```bash
cd frontend
npm install
npm run dev
```

Copie `frontend/.env.example` para `frontend/.env` e verifique se `VITE_API_BASE_URL` aponta para a API de Back-end (o padrão é `http://127.0.0.1:8001`).

O front-end é iniciado em `http://localhost:5173`. Verifique se a API de Back-end já está em execução, pois o front-end depende dela.

## Ordem de inicialização sugerida

1. API do Agente (`agent/`)
2. API de Back-end (`backend/`)
3. Front-end (`frontend/`)
