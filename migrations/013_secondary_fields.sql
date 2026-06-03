DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'family_tree_cell' AND column_name = 'alias'
  ) THEN
    ALTER TABLE family_tree_cell ADD COLUMN alias            TEXT;
    ALTER TABLE family_tree_cell ADD COLUMN nationality      TEXT;
    ALTER TABLE family_tree_cell ADD COLUMN baptism_date     TEXT;
    ALTER TABLE family_tree_cell ADD COLUMN baptism_place    TEXT;
    ALTER TABLE family_tree_cell ADD COLUMN burial_date      TEXT;
    ALTER TABLE family_tree_cell ADD COLUMN burial_place     TEXT;
    ALTER TABLE family_tree_cell ADD COLUMN education        TEXT;
    ALTER TABLE family_tree_cell ADD COLUMN military_service TEXT;
    ALTER TABLE family_tree_cell ADD COLUMN burial_type      VARCHAR(20);
  END IF;
END
$$;
