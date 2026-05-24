from resolver import resolver

problema = "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did she sell altogether?"

print("Testando phi4 (pode demorar em CPU)...")
r = resolver(problema, "cot")
print("\nResposta:", r["resposta_parseada"], "(esperado: 72)")
print("Latencia:", r["latencia_ms"], "ms")
print("Erro:", r["erro"])
print("Texto (inicio):", (r["resposta_bruta"] or "")[:300])