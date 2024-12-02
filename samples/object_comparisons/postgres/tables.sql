SELECT nsp.nspname::text                                AS schema
,      cls.relname::text                                AS name
,      CASE WHEN relispartition THEN 'YES' ELSE 'N' END AS partitioned
FROM pg_class cls
JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
WHERE nsp.nspname NOT IN ('pg_catalog','pg_toast')
AND   cls.relkind = 'r';
