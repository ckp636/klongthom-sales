-- SQL photo bytes expire independently from retained reports/file metadata.
SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF COL_LENGTH(N'mod1$_TxnFile', N'f1Content') IS NULL
    ALTER TABLE [mod1$_TxnFile] ADD f1Content VARBINARY(MAX) NULL;
IF COL_LENGTH(N'mod1$_TxnFile', N'f1ExpiresAt') IS NULL
    ALTER TABLE [mod1$_TxnFile] ADD f1ExpiresAt DATETIME2(0) NULL;
IF COL_LENGTH(N'mod1$_TxnFile', N'f1PurgedAt') IS NULL
    ALTER TABLE [mod1$_TxnFile] ADD f1PurgedAt DATETIME2(0) NULL;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_f1ExpiresAt'
               AND object_id = OBJECT_ID(N'mod1$_TxnFile'))
    EXEC(N'CREATE INDEX ix_f1ExpiresAt ON [mod1$_TxnFile](f1ExpiresAt, f1FID)
           WHERE f1ExpiresAt IS NOT NULL');

COMMIT TRANSACTION;
