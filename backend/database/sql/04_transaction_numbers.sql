-- Apply once to an existing database; preserves all transaction rows/numbers.
SET XACT_ABORT ON;
IF OBJECT_ID(N'mod1$_Transaction', N'U') IS NULL
    THROW 50010, N'Create the base schema before applying transaction-number migration.', 1;
BEGIN TRANSACTION;

IF COL_LENGTH(N'mod1$_Transaction', N't1TNo') < 128
BEGIN
    ALTER TABLE [mod1$_Transaction] DROP CONSTRAINT uq_t1TNo;
    ALTER TABLE [mod1$_Transaction] ALTER COLUMN t1TNo NVARCHAR(64) NOT NULL;
    ALTER TABLE [mod1$_Transaction] ADD CONSTRAINT uq_t1TNo UNIQUE (t1TNo);
END;

IF OBJECT_ID(N'seq_t1ReportNo', N'SO') IS NULL
    EXEC(N'CREATE SEQUENCE [seq_t1ReportNo] AS BIGINT START WITH 1 INCREMENT BY 1 NO CYCLE');

COMMIT TRANSACTION;
