USE [KardexVH];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('dbo.facturas_test', 'U') IS NOT NULL
    DROP TABLE dbo.facturas_test;
GO

IF OBJECT_ID('dbo.facturas_det_test', 'U') IS NOT NULL
    DROP TABLE dbo.facturas_det_test;
GO

SELECT *
INTO dbo.facturas_test
FROM dbo.Facturas;
GO

SELECT *
INTO dbo.facturas_det_test
FROM dbo.facturas_det;
GO

DECLARE @src_table SYSNAME;
DECLARE @dst_table SYSNAME;
DECLARE @sql NVARCHAR(MAX);

DECLARE table_cursor CURSOR FAST_FORWARD FOR
SELECT src_table, dst_table
FROM (VALUES
    ('Facturas', 'facturas_test'),
    ('facturas_det', 'facturas_det_test')
) t(src_table, dst_table);

OPEN table_cursor;
FETCH NEXT FROM table_cursor INTO @src_table, @dst_table;

WHILE @@FETCH_STATUS = 0
BEGIN
    ;WITH idx AS (
        SELECT
            i.index_id,
            i.name,
            i.type_desc,
            i.is_unique,
            i.filter_definition,
            key_cols = STUFF((
                SELECT
                    ', ' + QUOTENAME(c.name) +
                    CASE WHEN ic.is_descending_key = 1 THEN ' DESC' ELSE ' ASC' END
                FROM sys.index_columns ic
                JOIN sys.columns c
                    ON c.object_id = ic.object_id
                   AND c.column_id = ic.column_id
                WHERE ic.object_id = OBJECT_ID('dbo.' + @src_table)
                  AND ic.index_id = i.index_id
                  AND ic.is_included_column = 0
                ORDER BY ic.key_ordinal
                FOR XML PATH(''), TYPE
            ).value('.', 'nvarchar(max)'), 1, 2, ''),
            include_cols = STUFF((
                SELECT ', ' + QUOTENAME(c.name)
                FROM sys.index_columns ic
                JOIN sys.columns c
                    ON c.object_id = ic.object_id
                   AND c.column_id = ic.column_id
                WHERE ic.object_id = OBJECT_ID('dbo.' + @src_table)
                  AND ic.index_id = i.index_id
                  AND ic.is_included_column = 1
                ORDER BY c.column_id
                FOR XML PATH(''), TYPE
            ).value('.', 'nvarchar(max)'), 1, 2, '')
        FROM sys.indexes i
        WHERE i.object_id = OBJECT_ID('dbo.' + @src_table)
          AND i.type IN (1, 2)
          AND i.is_hypothetical = 0
    )
    SELECT @sql = STRING_AGG(
        'CREATE ' +
        CASE WHEN is_unique = 1 THEN 'UNIQUE ' ELSE '' END +
        type_desc + ' INDEX ' + QUOTENAME('IX_' + @dst_table + '_' + CAST(index_id AS VARCHAR(10))) +
        ' ON dbo.' + QUOTENAME(@dst_table) + ' (' + key_cols + ')' +
        CASE WHEN include_cols IS NOT NULL AND include_cols <> '' THEN ' INCLUDE (' + include_cols + ')' ELSE '' END +
        CASE WHEN filter_definition IS NOT NULL THEN ' WHERE ' + filter_definition ELSE '' END + ';'
    , CHAR(10))
    FROM idx
    WHERE key_cols IS NOT NULL AND key_cols <> '';

    IF @sql IS NOT NULL AND LEN(@sql) > 0
        EXEC sp_executesql @sql;

    FETCH NEXT FROM table_cursor INTO @src_table, @dst_table;
END

CLOSE table_cursor;
DEALLOCATE table_cursor;
GO
