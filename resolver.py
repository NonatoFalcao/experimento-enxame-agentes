# imports para tempo, ollama, regex e contagem
import time
import re
from ollama import chat
from collections import Counter

#Inicio da funcão resolver, que recebe enunciado e estratégia como parametros
def resolver(enunciado: str, estrategia: str) -> dict:
    #Estratégias de prompt que podem ser utilizadas
    strategy_prompts = {
        "zero_shot": enunciado,
        "cot": f"{enunciado}\nThink step by step before giving your final answer.",
        "self_consistency": f"{enunciado}\nSolve this and give a final numeric answer."
    }

    #variavel que recebe o tipo de prompt + o enunciado
    prompt = strategy_prompts.get(estrategia.lower(), enunciado)

    try:
        #inicio do chat
        start = time.time()

        # IMPORTANTE: esta função faz UMA chamada ao modelo por vez.
        # No self_consistency, quem manda o mesmo problema 5 vezes é o dispatcher
        # (ele publica 5 mensagens na fila) e quem escolhe a resposta mais votada
        # é o agregador. Aqui só mudamos a temperatura: 0.7 faz o modelo responder
        # de forma um pouco diferente a cada vez, pra que as 5 respostas variem e o
        # voto majoritário faça sentido. Nas outras estratégias usamos 0 (resposta fixa).
        temperatura = 0.7 if estrategia.lower() == "self_consistency" else 0.0

        response = chat(
            model="phi4",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": temperatura}
        )
        latency_ms = int((time.time() - start) * 1000)
        raw_answer = response.message.content
        tokens_in = response.prompt_eval_count or 0
        tokens_out = response.eval_count or 0

        #findall extrai o ultimo numero encontrado na resposta
        numbers = re.findall(r"-?\d+(?:\.\d+)?", raw_answer.replace(",", ""))
        parsed_response = int(float(numbers[-1])) if numbers else None

        # return dos resultados
        return {
            "resposta_parseada": parsed_response,
            "resposta_bruta": raw_answer,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latencia_ms": latency_ms,
            "erro": None
        }

    #Exceção caso haja erro ou a conexão é perdida
    except Exception as e:
        return {
            "resposta_parseada": None,
            "resposta_bruta": None,
            "tokens_in": 0,
            "tokens_out": 0,
            "latencia_ms": 0,
            "erro": str(e)
        }