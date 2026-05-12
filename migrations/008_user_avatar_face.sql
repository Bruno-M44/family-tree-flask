DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user' AND column_name = 'avatar_face_x'
  ) THEN
    ALTER TABLE "user" ADD COLUMN avatar_face_x INTEGER;
    ALTER TABLE "user" ADD COLUMN avatar_face_y INTEGER;
    ALTER TABLE "user" ADD COLUMN avatar_face_width INTEGER;
    ALTER TABLE "user" ADD COLUMN avatar_face_height INTEGER;
  END IF;
END
$$;
