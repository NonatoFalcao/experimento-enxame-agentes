# Harness GSM8K — Avaliação de Estratégias de Prompting

Experimento que avalia três estratégias de prompting (Zero-shot, Chain-of-Thought e Self-Consistency) no benchmark GSM8K usando o modelo **phi4** via Ollama, com orquestração paralela via AWS SQS + DynamoDB + S3.

## Visão geral da arquitetura

```
dispatcher.py  →  SQS (gsm8k-tasks)  →  worker.py (N paralelos)
                                              ↓
                                        DynamoDB (gsm8k-results)
                                              ↓
                                        agregador.py
                                              ↓
                              S3 (gsm8k-deva-202605191021) + resultados_finais.json
```

- **dispatcher.py** — carrega N problemas do GSM8K e publica mensagens na fila SQS (1 por tentativa)
- **worker.py** — consome a fila, chama `resolver.py`, salva resultado no DynamoDB
- **resolver.py** — faz a chamada real ao modelo phi4 via Ollama
- **agregador.py** — lê o DynamoDB, aplica voto majoritário e salva o JSON final
- **AnaliseGrafica.ipynb** — notebook para visualização e análise dos resultados

## Pré-requisitos

### 1. Python e dependências

```powershell
pip install boto3 datasets ollama
```

### 2. Ollama com o modelo phi4

Instale o [Ollama](https://ollama.com) e baixe o modelo:

```powershell
ollama pull phi4
```

Verifique que o servidor está rodando:

```powershell
ollama serve
```

### 3. Credenciais AWS

Configure suas credenciais com acesso a SQS, DynamoDB e S3 na região `us-east-1`:

```powershell
aws configure
```

Ou edite `~/.aws/credentials` diretamente:

```ini
[default]
aws_access_key_id     = SUA_ACCESS_KEY
aws_secret_access_key = SUA_SECRET_KEY
region                = us-east-1
```

## Reprodução passo a passo

### Passo 1 — Publicar os problemas na fila

```powershell
py dispatcher.py
```

Por padrão, publica **5 problemas** × 3 estratégias = **35 mensagens** (zero_shot: 1, cot: 1, self_consistency: 5 por problema).

Para alterar a quantidade de problemas, edite `n_problemas` em [dispatcher.py](dispatcher.py#L16).

### Passo 2 — Rodar os workers (em paralelo)

Abra 2 ou 3 terminais separados e execute em cada um:

```powershell
py worker.py
```

Cada worker consome mensagens da fila e chama o modelo phi4. Os logs são emitidos em formato JSON-line. O worker para sozinho quando a fila fica vazia por tempo suficiente (ou encerre com `Ctrl+C` após ver mensagens `sem_mensagens` repetidas).

> **Paralelismo:** quanto mais workers, menor o tempo total. 3 workers processam ~3× mais rápido.

### Passo 3 — Agregar os resultados

Após todos os workers finalizarem, execute:

```powershell
py agregador.py
```

Isso irá:
1. Ler todos os registros do DynamoDB
2. Aplicar voto majoritário por `(problema_id, estrategia)`
3. Salvar `resultados_finais.json` localmente
4. Fazer upload do arquivo para `s3://gsm8k-deva-202605191021/resultados_finais.json`
5. Imprimir a acurácia por estratégia no terminal

### Passo 4 — Analisar os resultados

Abra o notebook [AnaliseGrafica.ipynb](AnaliseGrafica.ipynb) para visualizações gráficas dos resultados.

## Estratégias de prompting

| Estratégia        | Tentativas | Temperatura | Descrição |
|-------------------|:----------:|:-----------:|-----------|
| `zero_shot`       | 1          | 0.0         | Enunciado direto, sem exemplos |
| `cot`             | 1          | 0.0         | Chain-of-Thought: pede raciocínio passo a passo |
| `self_consistency`| 5          | 0.7         | 5 respostas variadas; voto majoritário decide |

Os prompts base estão em [prompts/](prompts/).

## Recursos AWS

| Recurso    | Nome / URL |
|------------|-----------|
| Região     | `us-east-1` |
| Fila SQS   | `gsm8k-tasks` |
| DLQ        | `gsm8k-tasks-dlq` (mensagens após 3 falhas) |
| Tabela     | `gsm8k-results` (DynamoDB) |
| Bucket S3  | `gsm8k-deva-202605191021` |

## Tolerância a falhas

- **Retry com backoff exponencial** no worker: 1 s → 2 s → 4 s entre tentativas
- **DLQ automática** pelo SQS após 3 falhas consecutivas
- **Idempotência**: o worker consulta o DynamoDB antes de processar; mensagens duplicadas são ignoradas

## Formato dos logs do worker

Cada linha impressa pelo worker é um JSON com os campos:

```json
{
  "ts": "2026-05-24T12:00:00+00:00",
  "worker_id": "HOSTNAME_1234",
  "evento": "fim_ok",
  "problema_id": "gsm8k_0002",
  "chave": "cot#1",
  "latencia_ms": 4321
}
```

Eventos possíveis: `worker_iniciado`, `inicio`, `fim_ok`, `erro_retry`, `erro_fatal`, `ja_processado`, `sem_mensagens`.
