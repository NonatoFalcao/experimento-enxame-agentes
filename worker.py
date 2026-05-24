import json
import time
import socket
import random
import boto3
from resolver import resolver
from datetime import datetime, timezone

# Configurações da AWS
REGION = "us-east-1"
QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/266490062694/gsm8k-tasks"
TABLE_NAME = "gsm8k-results"

# Cria os clientes AWS
sqs = boto3.client("sqs", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

# ID único desse worker (hostname + número aleatório)
WORKER_ID = f"{socket.gethostname()}_{random.randint(1000, 9999)}"


def log(evento, **kwargs):
    # Monta um dicionário com timestamp, worker_id e o evento
    registro = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "worker_id": WORKER_ID,
        "evento": evento,
    }

    # Adiciona os kwargs extras ao registro (ex: problema_id, erro, etc)
    for chave, valor in kwargs.items():
        registro[chave] = valor

    # Imprime como JSON pra facilitar leitura por ferramentas de log
    print(json.dumps(registro))


def resolver_mock(enunciado, estrategia):
    # Simula o tempo que o modelo levaria pra responder
    time.sleep(random.uniform(0.5, 2.0))

    # Simula falha 5% das vezes pra testar o retry
    if random.random() < 0.05:
        raise Exception("Falha simulada do modelo")

    # Retorna uma resposta falsa (será substituído pela chamada real ao modelo)
    resultado = {
        "resposta_parseada": random.randint(0, 100),
        "resposta_bruta": f"mock_resposta_{estrategia}",
        "tokens_in": random.randint(150, 300),
        "tokens_out": random.randint(200, 500),
        "latencia_ms": random.randint(800, 3000),
        "erro": None,
    }
    return resultado


def ja_processado(problema_id, estrategia_tentativa):
    # Busca no DynamoDB se já existe um resultado pra essa combinação
    resp = table.get_item(
        Key={"problema_id": problema_id, "estrategia_tentativa": estrategia_tentativa}
    )

    # Se "Item" estiver na resposta, é porque já foi processado antes
    if "Item" in resp:
        return True
    return False


def processar_mensagem(msg):
    # Converte o corpo da mensagem de JSON pra dicionário Python
    body = json.loads(msg["Body"])

    # Chave única que identifica essa tentativa específica
    chave = f"{body['estrategia']}#{body['tentativa']}"

    # Verifica se já processamos isso antes (evita duplicata)
    if ja_processado(body["problema_id"], chave):
        log("ja_processado", problema_id=body["problema_id"], chave=chave)
        return

    log("inicio", problema_id=body["problema_id"], estrategia=body["estrategia"], tentativa=body["tentativa"])

    # Tenta processar até 3 vezes em caso de erro
    ultimo_erro = None
    for retry in range(3):
        try:
            # Marca o tempo de início pra calcular latência real
            inicio = time.time()

            # Chama o modelo 
            resultado = resolver(body["enunciado"], body["estrategia"])

            # Calcula quanto tempo demorou em milissegundos
            latencia_real = int((time.time() - inicio) * 1000)

            # Salva o resultado no DynamoDB
            table.put_item(Item={
                "problema_id": body["problema_id"],
                "estrategia_tentativa": chave,
                "estrategia": body["estrategia"],
                "tentativa": body["tentativa"],
                "gabarito": body["gabarito"],
                "resposta_parseada": resultado["resposta_parseada"],
                "resposta_bruta": resultado["resposta_bruta"],
                "tokens_in": resultado["tokens_in"],
                "tokens_out": resultado["tokens_out"],
                "latencia_ms": latencia_real,
                "worker_id": WORKER_ID,
                "ts": datetime.now(timezone.utc).isoformat(),
            })

            log("fim_ok", problema_id=body["problema_id"], chave=chave, latencia_ms=latencia_real)
            return  # Deu certo, sai da função

        except Exception as e:
            ultimo_erro = str(e)
            log("erro_retry", retry=retry, erro=ultimo_erro)

            # Espera antes de tentar de novo: 1s, 2s, 4s (backoff exponencial)
            time.sleep(2 ** retry)

    # Se chegou aqui, as 3 tentativas falharam
    raise Exception(f"Falhou apos 3 tentativas: {ultimo_erro}")


def main():
    log("worker_iniciado", queue=QUEUE_URL)

    # Loop infinito: fica escutando a fila pra sempre
    while True:
        # Tenta pegar 1 mensagem da fila (espera até 20s se não tiver nada)
        resp = sqs.receive_message(QueueUrl=QUEUE_URL, MaxNumberOfMessages=1, WaitTimeSeconds=20)
        msgs = resp.get("Messages", [])

        # Se não veio nenhuma mensagem, vai pro próximo loop
        if not msgs:
            log("sem_mensagens")
            continue

        # Pega a primeira (e única) mensagem
        msg = msgs[0]

        try:
            # Processa a mensagem
            processar_mensagem(msg)

            # Se deu certo, deleta da fila pra não processar de novo
            sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])

        except Exception as e:
            log("erro_fatal", erro=str(e))
            # Não deleta a mensagem: SQS vai reenviar automaticamente
            # Depois de 3 falhas, a mensagem vai pra Dead Letter Queue (DLQ)


if __name__ == "__main__":
    main()
