# Infraestrutura como Código — Tema 8

Este diretório contém a infraestrutura AWS do projeto descrita como código
(CloudFormation), permitindo recriar todos os recursos sem precisar configurar
nada manualmente pelo console.

## O que o template cria

| Recurso | Nome | Função |
|---|---|---|
| Fila SQS | `gsm8k-tasks` | Recebe as tarefas publicadas pelo dispatcher |
| Dead Letter Queue | `gsm8k-tasks-dlq` | Recebe mensagens que falharam 3 vezes |
| Tabela DynamoDB | `gsm8k-results` | Resultados de cada inferência + checkpoint de idempotência |
| Bucket S3 | `gsm8k-results-<conta>-<regiao>` | Guarda o `resultados_finais.json` consolidado |

A fila principal já vem com a *redrive policy* apontando para a DLQ após 3
tentativas, e a tabela usa chave composta (`problema_id` + `estrategia_tentativa`)
no modo on-demand, igual ao que foi usado no desenvolvimento.

## Como subir

### Opção A — pelo console (mais simples no AWS Academy)

1. Abra o console e vá em **CloudFormation → Create stack → With new resources**.
2. Em *Specify template*, escolha **Upload a template file** e selecione `infra.yaml`.
3. Dê um nome à stack (ex.: `gsm8k-infra`) e siga **Next** até **Submit**.
4. Aguarde o status ficar `CREATE_COMPLETE` (~1 a 2 minutos).
5. Abra a aba **Outputs** da stack para copiar a URL da fila e o nome do bucket.

### Opção B — pela linha de comando (AWS CLI)

```bash
aws cloudformation deploy \
  --template-file infra.yaml \
  --stack-name gsm8k-infra \
  --region us-east-1

# ver as saídas (URL da fila, nome do bucket, etc.)
aws cloudformation describe-stacks \
  --stack-name gsm8k-infra \
  --region us-east-1 \
  --query "Stacks[0].Outputs"
```

## Depois de subir

Copie os valores da aba **Outputs** para o código:

- `FilaPrincipalUrl` → variável `QUEUE_URL` no `dispatcher.py` e no `worker.py`
- `BucketResultados` → variável `BUCKET` no `agregador.py`

## Como remover tudo

Para apagar todos os recursos de uma vez (o bucket precisa estar vazio):

```bash
aws s3 rm s3://<nome-do-bucket> --recursive
aws cloudformation delete-stack --stack-name gsm8k-infra --region us-east-1
```

## Observação

No AWS Academy o token de credenciais expira a cada sessão. Caso a CLI retorne
erro de credencial, gere um novo token no laboratório e atualize o
`~/.aws/credentials` antes de rodar os comandos acima.
