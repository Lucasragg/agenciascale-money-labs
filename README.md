# Money Labs · Dashboard Meta Ads

Dashboard estática e PII-free que cruza, em modo somente leitura, as abas de mídia `Bubba` e `MoneyLabs Dolar` com os eventos `Lead salvo` e `Venda registrada` da VMFY SHEETS.

## Regras de cálculo

- A aba `Bubba` usa campanhas cujo nome contenha `SD | E2-CAP`, `BUBA-ING | E2-CAP` ou `BUBBA | E2-CAP`.
- A aba `Mari` usa campanhas cujo nome contenha `MARI | E2-CAP`.
- A aba `Harumi` usa campanhas cujo nome contenha `Harumi | E2-CAP`.
- A aba `Lucas` usa campanhas cujo nome contenha `Lucas | E2-CAP`.
- A aba `Alice` usa campanhas cujo nome contenha `Alice | E2-CAP`.
- A aba `Lucas` também aceita campanhas `Lucas | PT-BR | LEADS`.
- A aba `Matheus` usa campanhas `MATHEUS | E2-CAP` e `Matheus | PT-BR | LEADS`.
- A aba `Gabi` usa campanhas `GABI | E2-CAP` e `Gabriela | ES | LEADS`; linhas da fonte `Bubba` são convertidas de BRL para USD por R$ 5,10, enquanto `MoneyLabs Dolar` permanece em USD.
- A aba `Nick` usa campanhas cujo nome contenha `Nick | EN | LEADS` e converte o investimento da fonte `Bubba` de BRL para USD por R$ 5,10.
- O seletor global de período inclui os atalhos `Hoje` e `Ontem`, além de 7, 14, 30 dias e todo o histórico.
- Nas abas individuais, a tabela de decisão de mídia permite navegar por `Campanha → Conjunto → Anúncio`; a seleção de cada nível filtra o nível seguinte sem alterar os totais dos cards e gráficos.
- Os gráficos exibem detalhes ao passar o mouse. O gráfico de CPL e CAC abaixo da tabela acompanha os filtros de campanha e conjunto aplicados na decisão de mídia.
- A aba `Money Labs` consolida todos os funis e apresenta a tabela de decisão agrupada por funil.
- Todo gasto é exibido em USD e sem imposto: a aba `Bubba` chega em BRL e usa `Amount Spent ÷ 5,10`; a aba `MoneyLabs Dolar` já chega em USD e mantém `Amount Spent`.
- O período inclui o dia atual no fuso `America/Sao_Paulo`.
- Leads: linhas cujo evento normalizado é exatamente `lead salvo`.
- Vendas: linhas cujo evento é `venda registrada` e cuja etapa, na mesma linha, é `validação de plano`.
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
