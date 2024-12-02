SELECT nsp.nspname::text AS schema
,      cls.relname::text AS tablename
,      att.attname::text AS columns
FROM pg_class cls
JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
JOIN pg_attribute att ON att.attrelid = cls.oid
WHERE nsp.nspname NOT IN ('pg_catalog','pg_toast')
AND   att.attnotnull
AND   att.attnum >= 1
