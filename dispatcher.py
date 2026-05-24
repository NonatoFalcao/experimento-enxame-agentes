import json
import boto3
from datasets import load_dataset

# Configurações da AWS
REGION = "us-east-1"
QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/266490062694/gsm8k-tasks"

# Cria o cliente SQS pra poder enviar mensagens
sqs = boto3.client("sqs", region_name=REGION)


def main():
    # Quantos problemas vamos usar do dataset
    n_problemas = 5

    # Lista das estratégias que o worker vai testar
    estrategias = ["zero_shot", "cot", "self_consistency"]

    # Quantas tentativas pra self_consistency (as outras fazem só 1)
    k_self_consistency = 5

    # Carrega o dataset GSM8K do HuggingFace
    print("Carregando GSM8K (test split)...")
    ds = load_dataset("gsm8k", "main", split="test")

    # Pega só os primeiros n_problemas
    subset = ds.select(range(n_problemas))
    print(f"Subset: {n_problemas} problemas")

    # Conta quantas mensagens foram enviadas no total
    count = 0

    # Loop por cada problema do subset
    for i, item in enumerate(subset):

        # Loop por cada estratégia
        for estrategia in estrategias:

            # Self consistency roda várias vezes, as outras só 1
            if estrategia == "self_consistency":
                tentativas = k_self_consistency
            else:
                tentativas = 1

            # Envia uma mensagem pra cada tentativa
            for t in range(1, tentativas + 1):
                # Monta o dicionário com os dados do problema
                msg = {
                    "problema_id": f"gsm8k_{i:04d}",
                    "enunciado": item["question"],
                    "gabarito": item["answer"],
                    "estrategia": estrategia,
                    "tentativa": t,
                }

                # Converte pra JSON e envia pra fila SQS
                sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(msg))
                count += 1

                # Mostra progresso a cada 10 mensagens
                if count % 10 == 0:
                    print(f"  publicadas {count} mensagens...")

    print(f"OK. Total publicado: {count} mensagens.")


if __name__ == "__main__":
    main()
