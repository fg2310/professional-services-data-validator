SELECT schema,tablename,columns
FROM (
    SELECT nsp.nspname::text  AS schema
    ,      cls.relname::text  AS tablename
    ,      cons.conname::text AS name
    ,      string_agg(col.attname,',' ORDER BY attnum) AS columns
    FROM   pg_constraint    AS cons
    INNER JOIN pg_class     AS cls ON (cons.conrelid = cls.oid)
    INNER JOIN pg_namespace AS nsp ON (nsp.oid = cls.relnamespace)
    INNER JOIN pg_attribute AS col ON (col.attrelid = cons.conrelid AND attnum = ANY(cons.conkey))
    WHERE cons.contype = 'f'
    AND   nsp.nspname::text NOT IN ('pg_catalog','pg_toast')
    GROUP BY nsp.nspname::text
    ,        cls.relname::text
    ,        cons.conname::text
) q
