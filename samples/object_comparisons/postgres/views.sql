SELECT schemaname::text AS schema
,      viewname::text   AS name
FROM   pg_views
WHERE schemaname::text NOT IN ('pg_catalog','pg_toast')
