# Money Labs · Dashboard Meta Ads

Dashboard estática e PII-free que cruza, em modo somente leitura, a aba `Bubba` de mídia com os eventos `Lead salvo` e `Venda registrada` da VMFY SHEETS.

## Regras de cálculo

- A aba `Bubba` usa campanhas cujo nome contenha `SD | E2-CAP`.
- A aba `Mari` usa campanhas cujo nome contenha `MARI | E2-CAP`.
- A aba `Harumi` usa campanhas cujo nome contenha `Harumi | E2-CAP`.
- Gasto usado em todas as métricas: `(Amount Spent × 1,1385) ÷ 5,10`, exibido em USD.
- O período termina sempre em D−1 no fuso `America/Sao_Paulo` para respeitar o atraso das conversões.
- Leads: linhas cujo evento normalizado é exatamente `lead salvo`.
- Vendas: linhas cujo evento normalizado é exatamente `venda registrada`.
- Campanha: `UTM Campaign`; anúncio: `UTM Content`; conjunto: lookup campanha+anúncio na aba Bubba.
- Vendas são atribuídas exclusivamente pela UTM presente na própria linha; não há fallback por e-mail.
- Receita e ROAS não são publicados.
- O arquivo público não contém nome, e-mail nem telefone.

## Automação

O workflow roda a cada 3 horas, manualmente ou pelo evento `repository_dispatch` do tipo `dashboard_refresh`, gera `public/data.json` em memória do runner e publica o diretório `public` no GitHub Pages.

## Execução local

```bash
python scripts/build_data.py
python -m http.server 8000 -d public
```
