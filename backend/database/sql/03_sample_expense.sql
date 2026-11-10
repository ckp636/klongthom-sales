-- KlongthomSales — sample expenses (หัก ค่าใช้จ่าย)
-- Run after 02_sample_data.sql. Gives about two out of three live reports an
-- expense of ฿100–600 (rounded to ฿50), worked out from the report number so
-- every run gives the same values. Only touches rows that still have t1Expense = 0.

SET XACT_ABORT ON;
SET NOCOUNT ON;

UPDATE t
SET t1Expense = (100 + x.h % 500) / 50 * 50
FROM [mod1$_Transaction] t
CROSS APPLY (SELECT ABS(CAST(CAST(HASHBYTES('MD5', CONCAT('exp|', t.t1TNo)) AS BINARY(4)) AS INT) % 1000003)) x(h)
WHERE t.t1Status <> N'void' AND t.t1Expense = 0 AND x.h % 3 <> 0;

SELECT COUNT(*) AS reports_with_expense, SUM(t1Expense) AS total_expense
FROM [mod1$_Transaction] WHERE t1Expense > 0;
