import json
import re
import boto3
from collections import Counter

# Configurações da AWS
REGION = "us-east-1"
TABLE_NAME = "gsm8k-results"
BUCKET = None  # vai ser preenchido abaixo

# Lê o nome do bucket a partir do arquivo de configuração
with open("aws_config.env") as f:
    for linha in f:
        if linha.startswith("BUCKET="):
            # Remove espaços e pega o valor depois do "="
            BUCKET = linha.strip().split("=", 1)[1]

# Se não encontrou o bucket, para tudo com erro
if not BUCKET:
    raise RuntimeError("BUCKET nao encontrado em aws_config.env")

# Cria os clientes AWS
dynamodb = boto3.resource("dynamodb", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def extrair_numero_gabarito(gabarito_str):
    # O GSM8K guarda o gabarito no formato: "...explicação... #### 72"
    # Usamos regex pra achar o número depois do ####
    match = re.search(r"####\s*([-+]?\d+(?:\.\d+)?)", gabarito_str)

    if match:
        # Converte pra int (remove vírgulas caso tenha, ex: "1,000")
        return int(float(match.group(1).replace(",", "")))

    # Se não encontrou o padrão, retorna None
    return None


def main():
    print("Lendo resultados do DynamoDB...")

    # Lista que vai acumular todos os itens lidos
    items = []

    # Faz a primeira leitura da tabela
    resp = table.scan()
    items.extend(resp["Items"])

    # O DynamoDB pagina os resultados, então precisamos continuar lendo
    # enquanto houver mais páginas
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp["Items"])

    print(f"Total de registros lidos: {len(items)}")

    # Se não veio nada, avisa e sai
    if not items:
        print("Nenhum registro encontrado. Rode o dispatcher e o worker primeiro.")
        return

    # Agrupa os itens por (problema_id, estrategia)
    # Cada grupo vai ter todas as tentativas daquele problema+estratégia
    grupos = {}
    for item in items:
        chave = (item["problema_id"], item["estrategia"])

        # Se a chave ainda não existe no dicionário, cria uma lista vazia
        if chave not in grupos:
            grupos[chave] = []

        grupos[chave].append(item)

    # Lista final com o resultado de cada (problema, estratégia)
    resultados_finais = []

    for (problema_id, estrategia), tentativas in grupos.items():
        # Pega as respostas numéricas de todas as tentativas
        respostas = []
        for t in tentativas:
            respostas.append(int(t["resposta_parseada"]))

        # Voto majoritário: pega a resposta que apareceu mais vezes
        contador = Counter(respostas)
        voto = contador.most_common(1)[0][0]

        # Extrai o número do gabarito (só precisa pegar de uma tentativa)
        gabarito_num = extrair_numero_gabarito(tentativas[0]["gabarito"])

        # Agrega latência e tokens das tentativas
        latencias = [int(t["latencia_ms"]) for t in tentativas]
        tokens_in = [int(t["tokens_in"]) for t in tentativas]
        tokens_out = [int(t["tokens_out"]) for t in tentativas]

        # Monta o resultado final desse grupo
        resultado = {
            "problema_id": problema_id,
            "estrategia": estrategia,
            "k_tentativas": len(tentativas),
            "respostas_brutas": respostas,
            "voto_majoritario": voto,
            "gabarito": gabarito_num,
            "acertou": voto == gabarito_num,  # True se acertou, False se errou
            "latencia_media_ms": round(sum(latencias) / len(latencias)),
            "latencia_total_ms": sum(latencias),
            "tokens_in_total": sum(tokens_in),
            "tokens_out_total": sum(tokens_out),
        }
        resultados_finais.append(resultado)

    # Salva o arquivo JSON localmente e no S3
    conteudo = json.dumps(resultados_finais, indent=2)
    with open("resultados_finais.json", "w") as f:
        f.write(conteudo)
    print("Salvo localmente em resultados_finais.json")

    s3.put_object(
        Bucket=BUCKET,
        Key="resultados_finais.json",
        Body=conteudo,
    )
    print(f"Salvo em s3://{BUCKET}/resultados_finais.json")

    # Calcula e imprime a acurácia por estratégia
    print("\n=== ACURACIA POR ESTRATEGIA ===")

    # Agrupa os resultados por estratégia
    por_est = {}
    for r in resultados_finais:
        est = r["estrategia"]

        if est not in por_est:
            por_est[est] = []

        por_est[est].append(r["acertou"])

    # Imprime o resumo de cada estratégia em ordem alfabética
    for est, acertos in sorted(por_est.items()):
        n = len(acertos)        # total de problemas
        a = sum(acertos)        # quantos acertou (True = 1, False = 0)
        print(f"  {est}: {a}/{n} = {100*a/n:.1f}%")


if __name__ == "__main__":
    main()
