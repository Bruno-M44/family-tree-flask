DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'pet'
      AND column_name = 'species'
      AND is_nullable = 'NO'
  ) THEN
    ALTER TABLE pet ALTER COLUMN species DROP NOT NULL;
  END IF;
END
$$;
