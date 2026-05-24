import boto3

REGION = "us-east-1"
TABLE_NAME = "gsm8k-results"

with open("aws_config.env") as f:
    for linha in f:
        if linha.startswith("BUCKET="):
            BUCKET = linha.strip().split("=", 1)[1]

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

print("Apagando registros do DynamoDB...")
resp = table.scan()
items = resp["Items"]
while "LastEvaluatedKey" in resp:
    resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
    items.extend(resp["Items"])

with table.batch_writer() as batch:
    for item in items:
        batch.delete_item(Key={
            "problema_id": item["problema_id"],
            "estrategia_tentativa": item["estrategia_tentativa"]
        })

print(f"Apagados {len(items)} registros. DynamoDB limpo.")