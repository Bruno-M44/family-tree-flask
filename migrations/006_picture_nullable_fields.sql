DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'picture'
      AND column_name = 'picture_date'
      AND is_nullable = 'NO'
  ) THEN
    ALTER TABLE picture ALTER COLUMN picture_date DROP NOT NULL;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'picture'
      AND column_name = 'comments'
      AND is_nullable = 'NO'
  ) THEN
    ALTER TABLE picture ALTER COLUMN comments DROP NOT NULL;
  END IF;
END
$$;
