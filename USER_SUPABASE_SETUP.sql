-- ============================================================================
-- Doki Schema Introspection Setup
-- ============================================================================
-- Run this SQL in YOUR Supabase project's SQL Editor
-- (Not in Doki's backend database)
-- 
-- This creates a helper function that allows Doki to read your table schemas
-- ============================================================================

-- Create function to get table schema information
CREATE OR REPLACE FUNCTION get_table_schema(target_schema text DEFAULT 'public')
RETURNS TABLE (
    table_name text,
    column_name text,
    data_type text,
    is_nullable text,
    column_default text
) 
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.table_name::text,
        c.column_name::text,
        c.data_type::text,
        c.is_nullable::text,
        c.column_default::text
    FROM information_schema.columns c
    WHERE c.table_schema = target_schema
    ORDER BY c.table_name, c.ordinal_position;
END;
$$;

-- Grant execute permission to service_role (used by Doki backend)
GRANT EXECUTE ON FUNCTION get_table_schema(text) TO authenticated;
GRANT EXECUTE ON FUNCTION get_table_schema(text) TO service_role;

-- ============================================================================
-- Verification
-- ============================================================================
-- Test the function (optional):
-- SELECT * FROM get_table_schema('public') LIMIT 10;
