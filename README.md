# monetra-api
Backend oficial da Monetra

## Camada de IA — Foundation 1.1

A Monetra agora possui uma camada opcional de inteligência baseada na OpenAI Responses API.
Quando `OPENAI_API_KEY` está configurada, o webhook envia a mensagem para a IA, que pode
usar ferramentas financeiras seguras para consultar ou registrar dados. Sem a chave, o
processador determinístico existente continua funcionando como fallback.

Variáveis opcionais:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (padrão: `gpt-5.6-luna`)
