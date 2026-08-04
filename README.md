# Money Labs · Dashboard Meta Ads

Dashboard estática e PII-free que cruza, em modo somente leitura, a aba `Bubba` de mídia com os eventos `Lead salvo` e `Venda registrada` da VMFY SHEETS.

## Regras de cálculo

- Gasto usado em todas as métricas: `Amount Spent × 1,1385`.
- Leads: linhas cujo evento normalizado é exatamente `lead salvo`.
- Vendas: linhas cujo evento normalizado é exatamente `venda registrada`.
- Campanha: `UTM Campaign`; anúncio: `UTM Content`; conjunto: lookup campanha+anúncio na aba Bubba.
- Venda sem UTM: último lead anterior do mesmo e-mail, quando ele pertence a uma campanha presente na Bubba.
- Receita USD convertida para BRL pela taxa Frankfurter/ECB; fallback configurável por `USD_BRL_RATE`.
- O arquivo público não contém nome, e-mail nem telefone.

## Automação

O workflow roda a cada 3 horas, manualmente ou pelo evento `repository_dispatch` do tipo `dashboard_refresh`, gera `public/data.json` em memória do runner e publica o diretório `public` no GitHub Pages.

## Execução local

```bash
python scripts/build_data.py
python -m http.server 8000 -d public
```
