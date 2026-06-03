DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'family_tree_hidden_branches'
      AND column_name = 'hidden_above'
      AND data_type = 'ARRAY'
  ) THEN
    ALTER TABLE family_tree_hidden_branches
      ALTER COLUMN hidden_above TYPE json USING to_json(hidden_above);
    ALTER TABLE family_tree_hidden_branches
      ALTER COLUMN hidden_below TYPE json USING to_json(hidden_below);
  END IF;
END
$$;
