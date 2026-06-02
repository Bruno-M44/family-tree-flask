DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'family_tree_cell' AND column_name = 'sexe'
  ) THEN
    ALTER TABLE family_tree_cell ADD COLUMN sexe VARCHAR(2) DEFAULT 'ND';
  END IF;
END
$$;
