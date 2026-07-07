DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user' AND column_name = 'verification_token_created_at'
  ) THEN
    ALTER TABLE "user" ADD COLUMN verification_token_created_at TIMESTAMP;
  END IF;
END
$$;
