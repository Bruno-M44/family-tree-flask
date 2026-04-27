DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'family_tree_cell'
      AND column_name = 'birthday'
      AND is_nullable = 'NO'
  ) THEN
    ALTER TABLE family_tree_cell ALTER COLUMN birthday DROP NOT NULL;
  END IF;
END
$$;
