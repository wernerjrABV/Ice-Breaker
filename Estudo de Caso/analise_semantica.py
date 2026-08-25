"""Analise semantica mensal de tickets sem uso de LLM.

Exemplo: python analise_semantica.py --entrada data.csv --saida resultados
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[_/\\|\-]+", " ", text.lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def aggregate_by_month_and_category(rows):
    result = defaultdict(Counter)
    for row in rows:
        month = pd.to_datetime(row["CreatedAt"], dayfirst=True).strftime("%m/%Y")
        result[month][row["semantic_category"]] += 1
    return result


def combine_description_fields(row: dict) -> str:
    values = [row.get("Descriptions", ""), row.get("Description", ""), row.get("TicketStatusDetail", "")]
    return " ".join(normalize_text(value) for value in values if normalize_text(value)).strip()


def read_input(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str).fillna("")
    except UnicodeDecodeError:
        return pd.read_csv(path, sep=";", encoding="latin1", dtype=str).fillna("")


def build_categories(df: pd.DataFrame, clusters: int) -> tuple[pd.Series, dict[int, str]]:
    text = (df["Descriptions"].map(normalize_text) + " " + df["Description"].map(normalize_text) + " " + df["TicketStatusDetail"].map(normalize_text)).str.strip()
    text = text.replace("", "sem descricao")
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2)
    matrix = vectorizer.fit_transform(text)
    n_clusters = max(1, min(clusters, matrix.shape[0]))
    labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(matrix)
    terms = vectorizer.get_feature_names_out()
    names = {}
    for label in range(n_clusters):
        indexes = [i for i, value in enumerate(labels) if value == label]
        scores = matrix[indexes].mean(axis=0).A1
        top = scores.argsort()[::-1][:3]
        names[label] = " / ".join(terms[i] for i in top if scores[i] > 0) or "Sem descricao"
    return pd.Series(labels, index=df.index), names


def generate_reports(input_path: Path, output_dir: Path, clusters: int = 12) -> tuple[Path, Path]:
    df = read_input(input_path)
    required = {"CreatedAt", "Description", "Descriptions", "TicketStatusDetail"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Colunas ausentes: {', '.join(sorted(missing))}")
    df["created_month"] = pd.to_datetime(df["CreatedAt"], dayfirst=True).dt.strftime("%m/%Y")
    labels, names = build_categories(df, clusters)
    df["semantic_category"] = labels.map(names)
    summary = (df.groupby(["created_month", "semantic_category"]).size().reset_index(name="tickets")
               .sort_values(["created_month", "tickets"], ascending=[True, False]))
    summary["percentage_in_month"] = summary["tickets"] / summary.groupby("created_month")["tickets"].transform("sum") * 100
    summary["percentage_in_month"] = summary["percentage_in_month"].round(2)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "relatorio_semantico_por_mes.csv"
    xlsx_path = output_dir / "relatorio_semantico_por_mes.xlsx"
    summary.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Resumo mensal", index=False)
        df.to_excel(writer, sheet_name="Tickets classificados", index=False)
        pd.DataFrame({"cluster": list(names), "categoria": list(names.values())}).to_excel(writer, sheet_name="Categorias", index=False)
    return csv_path, xlsx_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", default="data.csv", type=Path)
    parser.add_argument("--saida", default="resultados_semanticos", type=Path)
    parser.add_argument("--clusters", default=12, type=int, help="Quantidade maxima de grupos semanticos")
    args = parser.parse_args()
    csv_path, xlsx_path = generate_reports(args.entrada, args.saida, args.clusters)
    print(f"CSV gerado: {csv_path.resolve()}")
    print(f"Excel gerado: {xlsx_path.resolve()}")


if __name__ == "__main__":
    main()
