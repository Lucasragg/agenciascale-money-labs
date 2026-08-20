# Money Labs · Dashboard Meta Ads

Dashboard estática e PII-free que cruza, em modo somente leitura, as abas de mídia `Bubba` e `MoneyLabs Dolar` com os eventos `Lead salvo` e `Venda registrada` da VMFY SHEETS.

As vendas são identificadas pela coluna `Tipo de registro` (AA) com o valor normalizado `APROVAÇÃO DE PLANO`.

## Regras de cálculo

- A aba `Bubba` usa campanhas em português cujo nome contenha `SD | E2-CAP`, `BUBBA | E2-CAP`, `BUBA | E2-CAP`, `Buba | PT-BR | LEADS` ou `Buba | PT-BR | PUR`; a campanha exata `[LEADS][ABO]` também entra porque utiliza criativos Buba e possui cruzamento exato na VMFY.
- A aba `Buba-EN` concentra exclusivamente as campanhas da Buba cujo nome contenha `BUBA-ING`.
- A aba `Mari` usa campanhas cujo nome contenha `MARI | E2-CAP` ou `Mari | PT-BR | LEADS`.
- A aba `Harumi` usa campanhas cujo nome contenha `Harumi | E2-CAP`.
- A aba `Lucas` usa campanhas cujo nome contenha `Lucas | E2-CAP`.
- A aba `Alice` usa campanhas cujo nome contenha `Alice | E2-CAP` ou `Alice | PT-BR | LEADS`.
- A aba `Lucas` também aceita campanhas `Lucas | PT-BR | LEADS`.
- A aba `Matheus` usa campanhas `MATHEUS | E2-CAP` e `Matheus | PT-BR | LEADS`.
- A aba `Gabi` usa campanhas `GABI | E2-CAP` e `Gabriela | ES | LEADS`; linhas da fonte `Bubba` são convertidas de BRL para USD por R$ 5,10, enquanto `MoneyLabs Dolar` permanece em USD.
- A aba `Nick` usa campanhas cujo nome contenha `Nick | EN | LEADS` e converte o investimento da fonte `Bubba` de BRL para USD por R$ 5,10.
- A aba `Bubba` também aceita campanhas `Buba | PT-BR | LEADS` quando há correspondência exata com o gerenciador; as linhas dessa campanha na fonte `MoneyLabs Dolar` permanecem em USD.
- O seletor global de período inclui os atalhos `Hoje` e `Ontem`, além de 7, 14, 30 dias e todo o histórico.
- O seletor global de período permanece no cabeçalho fixo durante a rolagem, incluindo os atalhos e o intervalo personalizado, para facilitar a análise das tabelas de campanha, conjunto e anúncio.
- Nas abas individuais, a tabela de decisão de mídia permite navegar por `Campanha → Conjunto → Anúncio`; ao clicar em um anúncio, o gráfico de CPL e CAC é filtrado para esse anúncio, sem alterar os totais dos cards e do gráfico principal.
- Os gráficos exibem detalhes ao passar o mouse. O gráfico principal de performance diária inclui investimento, leads, vendas, CPL e CAC; o gráfico de CPL e CAC abaixo da tabela acompanha os filtros de campanha, conjunto e anúncio aplicados na decisão de mídia.
- A aba `Money Labs` consolida todos os funis e apresenta a tabela de decisão agrupada por funil.
- Todo gasto é exibido em USD e sem imposto: a aba `Bubba` chega em BRL e usa `Amount Spent ÷ 5,10`; a aba `MoneyLabs Dolar` já chega em USD e mantém `Amount Spent`.
- O período inclui o dia atual no fuso `America/Sao_Paulo`.
- Leads: linhas cujo evento normalizado é exatamente `lead salvo`.
- Vendas: linhas cuja coluna AA `Tipo de registro` é `APROVAÇÃO DE PLANO`; as colunas antigas `Evento` e `Etapa` não determinam mais a venda.
- A atribuição prioriza `Ad ID`; depois usa `Campaign ID` e `Ad Set ID`; `UTM Campaign` e `UTM Content` permanecem como fallback para linhas antigas sem IDs.
- Vendas são atribuídas exclusivamente pela UTM presente na própria linha; não há fallback por e-mail.
- Leads e vendas sem qualquer UTM são orgânicos. Quando o `Sub ID 1` identifica o expert, entram na aba dele como `Orgânico` e passam a compor seu CPL/CAC; os demais permanecem na aba geral `Orgânico`.
- A aba `Orgânico` consolida todos os registros orgânicos e mostra leads e vendas separados por expert, sem duplicá-los no total da Money Labs.
- Os cards separam `Vendas global` (tráfego + orgânico) de `Vendas tráfego`; `CAC global` usa todas as vendas e `CAC tráfego` usa somente vendas atribuídas ao tráfego pago.
- Receita e ROAS não são publicados.
- O arquivo público não contém nome, e-mail nem telefone.

## Automação

O workflow roda a cada 3 horas, manualmente ou pelo evento `repository_dispatch` do tipo `dashboard_refresh`, gera `public/data.json` em memória do runner e publica o diretório `public` no GitHub Pages.

## Execução local

```bash
python scripts/build_data.py
python -m http.server 8000 -d public
```
