SELECT schema,tablename,columns
FROM (
    SELECT nsp.nspname::text  AS schema
    ,      cls.relname::text  AS tablename
    ,      ind.indexrelid::text AS name
    ,      string_agg(col.attname,',' ORDER BY attnum) AS columns
    FROM   pg_index ind
    INNER JOIN pg_class     AS cls ON (ind.indrelid = cls.oid)
    INNER JOIN pg_namespace AS nsp ON (nsp.oid = cls.relnamespace)
    INNER JOIN pg_attribute AS col ON (col.attrelid = ind.indrelid AND col.attnum = ANY(ind.indkey))
    WHERE ind.indisprimary
    AND   nsp.nspname::text NOT IN ('pg_catalog','pg_toast')
    GROUP BY nsp.nspname::text
    ,        cls.relname::text
    ,        ind.indexrelid::text
) q
