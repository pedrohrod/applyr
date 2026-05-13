# apply-job

Workflow automatizado para aplicação em vagas de emprego com matching por IA.

Busca vagas no LinkedIn e Gupy, calcula um score de compatibilidade com seu currículo, gera cover letters personalizadas e aplica automaticamente — tudo dentro de um container Docker.

---

## Como funciona

```
Scrapers (LinkedIn · Gupy)
        ↓
  Filtros (blacklist, nível, tipo, data)
        ↓
  Match IA (score 0–100)
        ↓  score ≥ threshold
  Cover letter personalizada
        ↓
  Auto-apply (Playwright)
        ↓
  Tracking (SQLite + CSV)
```

---

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e Docker Compose
- Conta no LinkedIn e/ou Gupy
- API key de um dos providers de IA suportados

---

## Instalação

```bash
git clone https://github.com/seu-usuario/apply-job.git
cd apply-job

cp .env.example .env
```

---

## Configuração

### 1. Variáveis de ambiente (`.env`)

```env
# Provider de IA: anthropic | openai | gemini | ollama
LLM_PROVIDER=anthropic
LLM_MODEL=                        # deixe vazio para usar o padrão do provider
LLM_API_URL=http://localhost:11434  # apenas para ollama

ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

LINKEDIN_EMAIL=seu@email.com
LINKEDIN_PASSWORD=suasenha
GUPY_EMAIL=seu@email.com
GUPY_PASSWORD=suasenha
```

### 2. Providers de IA suportados

| Provider | Modelo padrão | Variável necessária |
|---|---|---|
| `anthropic` | `claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `gemini` | `gemini-1.5-flash` | `GEMINI_API_KEY` |
| `ollama` | `llama3` | `LLM_API_URL` (sem key) |

Para trocar de provider, basta alterar `LLM_PROVIDER` no `.env` — sem mexer em código.

### 3. Preferências de busca (`config/settings.yaml`)

```yaml
job_search:
  keywords:
    - "Software Engineer"
    - "Backend Developer"
  locations:
    - "Brasil"
  remote: true
  hybrid: true
  onsite: false

  experience_level:
    entry: true
    mid_senior_level: true

  job_types:
    full_time: true
    contract: true

  date_posted: "month"   # all_time | month | week | 24_hours

filters:
  company_blacklist:
    - "Stefanini"
  title_blacklist:
    - "Diretor"
  apply_once_at_company: true

matching:
  threshold: 70           # score mínimo (0–100) para aplicar

application:
  max_per_session: 50
  attach_cover_letter: true
```

### 4. Perfil do candidato (`config/profile.yaml`)

Preencha com seus dados reais. Esse arquivo é usado para:
- calcular o match com as vagas
- gerar cover letters personalizadas
- responder perguntas de triagem nos formulários automaticamente

Campos importantes:

```yaml
personal:
  name: "Seu Nome"
  email: "seu@email.com"

salary_expectations:
  range: "R$ 8.000 - R$ 12.000"

availability:
  notice_period: "Imediato"

legal_authorization:
  brazil_work_authorization: "Sim"

work_preferences:
  remote_work: "Sim"
  open_to_relocation: "Sim"
  willing_to_undergo_background_checks: "Sim"
```

### 5. Currículo

Coloque seu currículo em PDF na pasta `resume/`:

```bash
cp /caminho/para/seu/curriculo.pdf resume/resume.pdf
```

---

## Rodando

```bash
docker compose up --build
```

Para rodar em background:

```bash
docker compose up --build -d
docker compose logs -f
```

---

## Resultados

Após cada execução, os dados ficam em `data/`:

| Arquivo | Conteúdo |
|---|---|
| `data/applications.db` | Banco SQLite com histórico completo |
| `data/applications.csv` | Planilha exportável com todas as candidaturas |
| `logs/apply-job.log` | Log detalhado da execução |

Colunas do CSV: `data`, `empresa`, `cargo`, `plataforma`, `score`, `url`, `cover_letter`

---

## Plataformas suportadas

| Plataforma | Scraping | Auto-apply |
|---|---|---|
| LinkedIn Easy Apply | ✅ | ✅ |
| Gupy | ✅ | ✅ |
| Portais de empresas (Greenhouse, Lever) | 🔜 | 🔜 |

---

## Estrutura do projeto

```
apply-job/
├── config/
│   ├── settings.yaml       # filtros de busca, threshold, limites
│   └── profile.yaml        # seus dados pessoais e profissionais
├── resume/
│   └── resume.pdf          # seu currículo (adicione aqui)
├── src/
│   ├── ai/
│   │   ├── llm_provider.py     # abstração de providers (Anthropic, OpenAI, Gemini, Ollama)
│   │   ├── matcher.py          # scoring de match currículo ↔ vaga
│   │   ├── cover_letter.py     # geração de cover letter por vaga
│   │   ├── question_answerer.py # responde perguntas de triagem
│   │   └── resume_parser.py    # extração de texto do PDF
│   ├── scrapers/
│   │   ├── linkedin.py         # scraper do LinkedIn
│   │   └── gupy.py             # scraper da Gupy
│   ├── applicator/
│   │   ├── linkedin.py         # bot de aplicação LinkedIn Easy Apply
│   │   └── gupy.py             # bot de aplicação Gupy
│   ├── tracker/
│   │   └── db.py               # tracking em SQLite + CSV
│   └── orchestrator.py         # orquestra todo o fluxo
├── data/                   # gerado automaticamente
├── logs/                   # gerado automaticamente
├── Dockerfile
├── docker-compose.yml
└── main.py
```

---

## Aviso

Este projeto automatiza ações em plataformas de terceiros. Use com responsabilidade:

- Respeite os limites diários configurados em `settings.yaml`
- Revise o `profile.yaml` antes de rodar — as respostas automáticas são baseadas nesses dados
- Algumas plataformas podem detectar e bloquear automações em caso de uso excessivo

---

## Licença

MIT
