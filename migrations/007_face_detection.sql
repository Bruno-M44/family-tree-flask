DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'picture' AND column_name = 'face_x'
  ) THEN
    ALTER TABLE picture ADD COLUMN face_x INTEGER;
    ALTER TABLE picture ADD COLUMN face_y INTEGER;
    ALTER TABLE picture ADD COLUMN face_width INTEGER;
    ALTER TABLE picture ADD COLUMN face_height INTEGER;
  END IF;
END
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'pet_picture' AND column_name = 'face_x'
  ) THEN
    ALTER TABLE pet_picture ADD COLUMN face_x INTEGER;
    ALTER TABLE pet_picture ADD COLUMN face_y INTEGER;
    ALTER TABLE pet_picture ADD COLUMN face_width INTEGER;
    ALTER TABLE pet_picture ADD COLUMN face_height INTEGER;
  END IF;
END
$$;
