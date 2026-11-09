"""
train_model.py
--------------
Pipeline completo de riesgo crediticio:
  1. Carga del dataset
  2. Limpieza con criterio documentado
  3. Entrenamiento de Random Forest
  4. Evaluación del modelo
  5. Predicción de probabilidad de default
  6. Carga de resultados a SQL Server para Power BI
"""

import os
import numpy as np
import pandas as pd
import pyodbc
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    roc_auc_score,
    classification_report,
    confusion_matrix,
)

# 0. Configuración
load_dotenv()
CONN_STRING = os.getenv("SQL_CONNECTION_STRING")
if not CONN_STRING:
    raise ValueError("Falta SQL_CONNECTION_STRING en el archivo .env")

DATA_PATH = "data/credit_risk_dataset.csv"
RANDOM_STATE = 42
TEST_SIZE = 0.2

CAT_COLS = [
    "person_home_ownership",
    "loan_intent",
    "loan_grade",
    "cb_person_default_on_file",
]


# 1 Limpieza
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpieza del dataset de riesgo crediticio.
    Cada decisión está documentada para trazabilidad.
    """
    df = df.copy()
    n_original = len(df)

    # Eliminar edades y antigüedades laborales irreales (errores de captura)
    df = df[df["person_age"] <= 100]
    df = df[df["person_emp_length"].isna() | (df["person_emp_length"] <= 60)]

    # Imputar loan_int_rate con la mediana del loan_grade correspondiente
    #  (la tasa depende del grado asignado, no del promedio global)
    df["loan_int_rate"] = df.groupby("loan_grade")["loan_int_rate"].transform(
        lambda x: x.fillna(x.median())
    )

    # Imputar person_emp_length con la mediana global
    df["person_emp_length"] = df["person_emp_length"].fillna(
        df["person_emp_length"].median()
    )

    # Eliminar cualquier nulo restante (pocos casos)
    df = df.dropna()

    # Winsorizar ingreso al percentil 99 para reducir outliers
    p99 = df["person_income"].quantile(0.99)
    df["person_income"] = np.clip(df["person_income"], None, p99)

    print(f"[LIMPIEZA] Registros originales: {n_original}")
    print(f"[LIMPIEZA] Registros tras limpieza: {len(df)}")
    print(f"[LIMPIEZA] Eliminados: {n_original - len(df)} "
          f"({(n_original - len(df)) / n_original:.2%})")

    return df.reset_index(drop=True)


# 2 Preparación de features
def prepare_features(df: pd.DataFrame):
    """
    Codifica variables categóricas y separa X / y.
    Devuelve también los encoders para trazabilidad.
    """
    df = df.copy()
    encoders = {}

    for col in CAT_COLS:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = dict(zip(le.classes_, le.transform(le.classes_)))

    X = df.drop("loan_status", axis=1)
    y = df["loan_status"]

    print(f"[FEATURES] Variables predictoras: {list(X.columns)}")
    print(f"[FEATURES] Distribución de clases:\n{y.value_counts(normalize=True)}")

    return df, X, y, encoders


# 3 Entrenamiento y evaluación
def train_and_evaluate(X, y):
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, y_proba)
    print(f"\n[MODELO] AUC en test: {auc:.4f}")
    print(f"[MODELO] Matriz de confusión:\n{confusion_matrix(y_test, y_pred)}")
    print(f"[MODELO] Reporte de clasificación:\n"
          f"{classification_report(y_test, y_pred, digits=3)}")

    importances = pd.Series(
        model.feature_importances_, index=X.columns
    ).sort_values(ascending=False)
    print(f"[MODELO] Top 5 variables más predictivas:\n{importances.head(5)}")

    return model, auc, importances


# 4 Predicción sobre todo el dataset
def add_predictions(df_encoded: pd.DataFrame, X, model) -> pd.DataFrame:
    """
    Calcula probabilidad de default para cada registro y asigna nivel de riesgo.
    """
    df_out = df_encoded.copy()
    df_out["prob_default"] = model.predict_proba(X)[:, 1]
    df_out["riesgo"] = pd.cut(
        df_out["prob_default"],
        bins=[0, 0.3, 0.6, 1.0],
        labels=["Bajo", "Medio", "Alto"],
        include_lowest=True,
    ).astype(str)

    print(f"\n[SCORES] Distribución de niveles de riesgo:\n"
          f"{df_out['riesgo'].value_counts(normalize=True)}")

    return df_out


# 5 Carga a SQL Server
def load_to_sql(df: pd.DataFrame):
    """
    Carga los datos con scores en la tabla credit_scores.
    
    """
    cols = [
        "person_age", "person_income", "person_home_ownership",
        "person_emp_length", "loan_intent", "loan_grade",
        "loan_amnt", "loan_int_rate", "loan_status",
        "loan_percent_income", "cb_person_default_on_file",
        "cb_person_cred_hist_length", "prob_default", "riesgo",
    ]
    df_sql = df[cols].copy()

    conn = pyodbc.connect(CONN_STRING, timeout=30)
    cursor = conn.cursor()

    cursor.execute("IF OBJECT_ID('credit_scores', 'U') IS NOT NULL DROP TABLE credit_scores")
    cursor.execute("""
        CREATE TABLE credit_scores (
            person_age INT,
            person_income FLOAT,
            person_home_ownership INT,
            person_emp_length FLOAT,
            loan_intent INT,
            loan_grade INT,
            loan_amnt FLOAT,
            loan_int_rate FLOAT,
            loan_status INT,
            loan_percent_income FLOAT,
            cb_person_default_on_file INT,
            cb_person_cred_hist_length INT,
            prob_default FLOAT,
            riesgo VARCHAR(10)
        )
    """)

    rows = [tuple(x) for x in df_sql.to_numpy()]
    cursor.fast_executemany = True
    cursor.executemany(
        "INSERT INTO credit_scores VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM credit_scores")
    total = cursor.fetchone()[0]
    conn.close()

    print(f"\n[SQL] Registros cargados en credit_scores: {total}")


# 6  Main
def main():
    print("PIPELINE DE RIESGO CREDITICIO")
    
    df_raw = pd.read_csv(DATA_PATH)
    df_clean = clean_data(df_raw)
    df_encoded, X, y, encoders = prepare_features(df_clean)
    model, auc, importances = train_and_evaluate(X, y)
    df_scored = add_predictions(df_encoded, X, model)
    load_to_sql(df_scored)

    print(f"PIPELINE COMPLETADO — AUC: {auc:.4f}")
    

if __name__ == "__main__":
    main()