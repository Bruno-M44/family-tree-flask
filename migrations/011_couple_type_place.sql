DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'association_couple' AND column_name = 'type_union'
  ) THEN
    ALTER TABLE association_couple ADD COLUMN type_union  VARCHAR(20);
    ALTER TABLE association_couple ADD COLUMN place_union TEXT;
  END IF;
END
$$;
