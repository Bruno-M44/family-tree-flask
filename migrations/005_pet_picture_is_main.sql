DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'pet_picture'
      AND column_name = 'is_main'
  ) THEN
    ALTER TABLE pet_picture ADD COLUMN is_main BOOLEAN NOT NULL DEFAULT FALSE;
  END IF;
END
$$;
