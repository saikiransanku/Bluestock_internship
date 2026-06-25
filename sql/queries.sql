-- 1. Top 5 funds by latest available AUM.
WITH latest_aum AS (
    SELECT scheme_code, MAX(date_key) AS latest_date_key
    FROM fact_aum
    GROUP BY scheme_code
)
SELECT f.scheme_name, d.date, a.aum_crore
FROM fact_aum a
JOIN latest_aum la
    ON a.scheme_code = la.scheme_code
   AND a.date_key = la.latest_date_key
JOIN dim_fund f
    ON a.scheme_code = f.scheme_code
JOIN dim_date d
    ON a.date_key = d.date_key
ORDER BY a.aum_crore DESC
LIMIT 5;

-- 2. Average NAV per fund per month.
SELECT
    f.scheme_name,
    d.year,
    d.month,
    ROUND(AVG(n.nav), 4) AS average_nav
FROM fact_nav n
JOIN dim_fund f
    ON n.scheme_code = f.scheme_code
JOIN dim_date d
    ON n.date_key = d.date_key
GROUP BY f.scheme_name, d.year, d.month
ORDER BY d.year, d.month, f.scheme_name;

-- 3. SIP year-over-year growth by transaction amount.
WITH sip_year AS (
    SELECT
        d.year,
        SUM(t.amount) AS sip_amount
    FROM fact_transactions t
    JOIN dim_date d
        ON t.date_key = d.date_key
    WHERE t.transaction_type = 'SIP'
    GROUP BY d.year
)
SELECT
    year,
    sip_amount,
    ROUND(
        (sip_amount - LAG(sip_amount) OVER (ORDER BY year))
        * 100.0 / NULLIF(LAG(sip_amount) OVER (ORDER BY year), 0),
        2
    ) AS yoy_growth_pct
FROM sip_year
ORDER BY year;

-- 4. Transactions by investor state.
SELECT
    COALESCE(state, 'Unknown') AS state,
    COUNT(*) AS transaction_count,
    ROUND(SUM(amount), 2) AS total_amount
FROM fact_transactions
GROUP BY COALESCE(state, 'Unknown')
ORDER BY total_amount DESC;

-- 5. Funds with expense ratio below 1 percent.
SELECT
    f.scheme_name,
    p.expense_ratio,
    d.date AS as_of_date
FROM fact_performance p
JOIN dim_fund f
    ON p.scheme_code = f.scheme_code
JOIN dim_date d
    ON p.date_key = d.date_key
WHERE p.expense_ratio < 1
ORDER BY p.expense_ratio, f.scheme_name;

-- 6. Latest NAV for each fund.
WITH latest_nav AS (
    SELECT scheme_code, MAX(date_key) AS latest_date_key
    FROM fact_nav
    GROUP BY scheme_code
)
SELECT
    f.scheme_name,
    d.date,
    n.nav
FROM fact_nav n
JOIN latest_nav ln
    ON n.scheme_code = ln.scheme_code
   AND n.date_key = ln.latest_date_key
JOIN dim_fund f
    ON n.scheme_code = f.scheme_code
JOIN dim_date d
    ON n.date_key = d.date_key
ORDER BY f.scheme_name;

-- 7. Rank funds by 1-year return.
SELECT
    f.scheme_name,
    p.return_1y,
    d.date AS as_of_date
FROM fact_performance p
JOIN dim_fund f
    ON p.scheme_code = f.scheme_code
JOIN dim_date d
    ON p.date_key = d.date_key
WHERE p.return_1y IS NOT NULL
ORDER BY p.return_1y DESC;

-- 8. Average absolute daily NAV movement by fund.
WITH nav_changes AS (
    SELECT
        scheme_code,
        date_key,
        nav,
        LAG(nav) OVER (PARTITION BY scheme_code ORDER BY date_key) AS previous_nav
    FROM fact_nav
)
SELECT
    f.scheme_name,
    ROUND(AVG(ABS((nc.nav - nc.previous_nav) / nc.previous_nav)) * 100, 4)
        AS avg_abs_daily_move_pct
FROM nav_changes nc
JOIN dim_fund f
    ON nc.scheme_code = f.scheme_code
WHERE nc.previous_nav IS NOT NULL
GROUP BY f.scheme_name
ORDER BY avg_abs_daily_move_pct DESC;

-- 9. Count forward-filled NAV rows by fund.
SELECT
    f.scheme_name,
    SUM(n.is_forward_filled) AS forward_filled_days,
    COUNT(*) AS total_nav_days,
    ROUND(SUM(n.is_forward_filled) * 100.0 / COUNT(*), 2) AS filled_pct
FROM fact_nav n
JOIN dim_fund f
    ON n.scheme_code = f.scheme_code
GROUP BY f.scheme_name
ORDER BY forward_filled_days DESC;

-- 10. Category-wise fund count and latest average NAV.
WITH latest_nav AS (
    SELECT scheme_code, MAX(date_key) AS latest_date_key
    FROM fact_nav
    GROUP BY scheme_code
)
SELECT
    COALESCE(f.category_group, 'Unknown') AS category_group,
    COUNT(DISTINCT f.scheme_code) AS fund_count,
    ROUND(AVG(n.nav), 4) AS average_latest_nav
FROM dim_fund f
LEFT JOIN latest_nav ln
    ON f.scheme_code = ln.scheme_code
LEFT JOIN fact_nav n
    ON ln.scheme_code = n.scheme_code
   AND ln.latest_date_key = n.date_key
GROUP BY COALESCE(f.category_group, 'Unknown')
ORDER BY fund_count DESC, category_group;
