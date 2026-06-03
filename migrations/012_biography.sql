DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'family_tree_cell' AND column_name = 'biography'
  ) THEN
    ALTER TABLE family_tree_cell ADD COLUMN biography TEXT;
  END IF;
END
$$;
