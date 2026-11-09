USE [dbo].[credit_scores]

CREATE SYNONYM credit_scores FOR [dbo].[credit_scores]

SELECT COUNT(*) AS total FROM credit_scores

SELECT TOP 10 * FROM credit_scores

SELECT 
    MIN(person_age) AS edad_min,
    MAX(person_age) AS edad_max,
    MIN(person_emp_length) AS antig_min,
    MAX(person_emp_length) AS antig_max,
    SUM(CASE WHEN loan_int_rate IS NULL THEN 1 ELSE 0 END) AS nulos_tasa
FROM credit_scores

-- Distribucion de riesgo (cuantos clientes en cada categoria)
SELECT riesgo, COUNT(*) AS clientes, AVG(prob_default) AS prob_promedio
FROM credit_scores
GROUP BY riesgo;

-- Tasa de default real vs probabilidad predicha (validacion visual)
SELECT loan_status, AVG(prob_default) AS prob_promedio, COUNT(*) AS total
FROM credit_scores
GROUP BY loan_status;

-- 0=DEBTCONSOLIDATION, 1=EDUCATION, 2=HOMEIMPROVEMENT, 3=MEDICAL, 4=PERSONAL, 5=VENTURE. 

-- Riesgo por intencion de prestamo (que propositos concentran mayor riesgo?)
SELECT loan_intent, AVG(prob_default) AS prob_promedio, COUNT(*) AS total
FROM credit_scores
GROUP BY loan_intent
ORDER BY prob_promedio DESC;

SELECT DISTINCT loan_intent FROM credit_scores ORDER BY loan_intent;
-- Riesgo por grado de credito (loan_grade)
SELECT loan_grade, AVG(prob_default) AS prob_promedio, COUNT(*) AS total
FROM credit_scores
GROUP BY loan_grade
ORDER BY loan_grade;