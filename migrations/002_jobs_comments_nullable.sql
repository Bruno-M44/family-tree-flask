DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'family_tree_cell'
      AND column_name = 'jobs'
      AND is_nullable = 'NO'
  ) THEN
    ALTER TABLE family_tree_cell ALTER COLUMN jobs DROP NOT NULL;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'family_tree_cell'
      AND column_name = 'comments'
      AND is_nullable = 'NO'
  ) THEN
    ALTER TABLE family_tree_cell ALTER COLUMN comments DROP NOT NULL;
  END IF;
END
$$;
