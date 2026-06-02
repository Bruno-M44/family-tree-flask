DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'family_tree_cell' AND column_name = 'birth_place'
  ) THEN
    ALTER TABLE family_tree_cell ADD COLUMN birth_place TEXT;
    ALTER TABLE family_tree_cell ADD COLUMN death_place TEXT;
  END IF;
END
$$;
