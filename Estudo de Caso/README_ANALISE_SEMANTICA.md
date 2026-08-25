# Análise semântica mensal de tickets

O script `analise_semantica.py` usa normalização de texto, TF-IDF e K-Means. Não usa LLM nem conexão com a internet.

## Instalação

```powershell
python -m pip install -r requirements.txt
```

## Execução

```powershell
python analise_semantica.py --entrada data.csv --saida resultados_semanticos
```

Para controlar a quantidade máxima de categorias:

```powershell
python analise_semantica.py --entrada data.csv --saida resultados_semanticos --clusters 12
```

## Arquivos gerados

- `relatorio_semantico_por_mes.csv`: contagem e percentual por mês e categoria.
- `relatorio_semantico_por_mes.xlsx`: abas `Resumo mensal`, `Tickets classificados` e `Categorias`.

As categorias são nomes automáticos baseados nos termos mais relevantes de cada grupo. Como o método é estatístico e baseado no texto disponível, vale revisar a aba `Categorias` na primeira execução.
