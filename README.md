# monetra-api
Backend oficial da Prospere (antiga Monetra)

## Camada de IA — Foundation 1.1

A Prospere possui uma camada opcional de inteligência baseada na OpenAI Responses API.
Quando `OPENAI_API_KEY` está configurada, o webhook envia a mensagem para a IA, que pode
usar ferramentas financeiras seguras para consultar, registrar, editar ou excluir dados.
Sem a chave, o processador determinístico existente continua funcionando como fallback.

Variáveis opcionais:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (padrão: `gpt-5.6-luna`)

## Núcleo financeiro pelo WhatsApp

O webhook identifica o usuário pelo número, cadastra quem ainda não tem conta e responde
por texto. Recebimentos entram como categoria `Renda`; as demais categorias padrão estão
em `app/categorias.py` (Alimentação, Moradia, Transporte, Saúde, Lazer, Compras e
assinaturas, Educação, Renda, Investimentos e Outros), aceitando categorias
personalizadas.

O que a assistente já responde/executa por mensagem:

| Pedido do usuário | Exemplo |
| --- | --- |
| Registrar despesa ou receita | `gastei 30 com gasolina`, `recebi 5000 de salário` |
| Saldo atual | `qual é meu saldo?` |
| Gastos do mês | `quanto gastei esse mês?` |
| Gastos por período | `quanto gastei hoje?`, `quanto gastei essa semana?` |
| Gastos de uma categoria | `quanto gastei com transporte?` |
| Todas as categorias | `quanto gastei por categoria?` |
| Últimas transações | `quais são minhas últimas transações?` |
| Buscar no histórico | `busca mercado` |
| Corrigir valor | `corrigir mercado para 45`, `não foram 30, foram 45` |
| Excluir lançamento | `excluir o mercado`, `excluir a última transação` |

Correções e exclusões só acontecem quando o lançamento é identificado com segurança: com
mais de um candidato, a assistente mostra as opções e pergunta em vez de escolher.

## API

Endpoints do app (autenticados por `Bearer`):

- `GET /categorias` — categorias padrão.
- `GET /transacoes` — histórico do usuário com filtros `termo`, `categoria`, `tipo`,
  `periodo` (dia, semana, mes, ano), `dias`, `valor_min`, `valor_max` e `limite`.
- `PATCH /transacoes/{id}` — edita valor, descrição, categoria, tipo ou data.
- `DELETE /transacoes/{id}` — exclui o lançamento.
- `POST /transacoes`, `GET /minhas-transacoes`, `GET /saldo`, `GET /resumo/{usuario_id}`
  seguem como antes. Lançamentos agora devolvem também a `data`.

## Pendências planejadas

Orçamento e limites, análises comparativas entre meses, metas financeiras, agenda e
lembretes, documentos e comprovantes, investimentos e a reformulação da interface web.
