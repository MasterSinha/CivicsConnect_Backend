CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
  CREATE TYPE user_role AS ENUM ('citizen', 'authority', 'admin');
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE issue_status AS ENUM ('pending', 'in_review', 'resolved');
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE issue_severity AS ENUM ('low', 'medium', 'high');
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE issue_category AS ENUM ('pothole', 'garbage', 'water_leakage', 'streetlight', 'drainage');
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(160) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  phone_number VARCHAR(32) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role user_role NOT NULL DEFAULT 'citizen',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_role ON users (role);

CREATE TABLE IF NOT EXISTS issues (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title VARCHAR(180) NOT NULL,
  description TEXT NOT NULL,
  image_url VARCHAR(500),
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  status issue_status NOT NULL DEFAULT 'pending',
  severity issue_severity NOT NULL DEFAULT 'medium',
  category issue_category NOT NULL,
  ai_category VARCHAR(80),
  ai_severity VARCHAR(40),
  ai_department VARCHAR(120),
  ai_description TEXT,
  votes INTEGER NOT NULL DEFAULT 0,
  verified_count INTEGER NOT NULL DEFAULT 0,
  trust_score INTEGER NOT NULL DEFAULT 72,
  reporter_id UUID REFERENCES users(id) ON DELETE SET NULL,
  resolution_summary TEXT,
  resolution_public_note TEXT,
  resolution_worker VARCHAR(160),
  resolution_date DATE,
  resolution_materials VARCHAR(255),
  resolution_before_image TEXT,
  resolution_after_image TEXT,
  ai_resolution_resolved BOOLEAN,
  ai_resolution_confidence INTEGER,
  ai_resolution_remarks TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_issues_status ON issues (status);
CREATE INDEX IF NOT EXISTS ix_issues_category ON issues (category);
CREATE INDEX IF NOT EXISTS ix_issues_created_at ON issues (created_at);

ALTER TABLE issues ADD COLUMN IF NOT EXISTS ai_category VARCHAR(80);
ALTER TABLE issues ADD COLUMN IF NOT EXISTS ai_severity VARCHAR(40);
ALTER TABLE issues ADD COLUMN IF NOT EXISTS ai_department VARCHAR(120);
ALTER TABLE issues ADD COLUMN IF NOT EXISTS ai_description TEXT;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS votes INTEGER NOT NULL DEFAULT 0;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS verified_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS trust_score INTEGER NOT NULL DEFAULT 72;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS reporter_id UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_summary TEXT;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_public_note TEXT;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_worker VARCHAR(160);
ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_date DATE;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_materials VARCHAR(255);
ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_before_image TEXT;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_after_image TEXT;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS ai_resolution_resolved BOOLEAN;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS ai_resolution_confidence INTEGER;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS ai_resolution_remarks TEXT;

CREATE TABLE IF NOT EXISTS authority_profiles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  department VARCHAR(120) NOT NULL,
  zone VARCHAR(160) NOT NULL DEFAULT 'Central Civic Zone',
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  radius_km DOUBLE PRECISION NOT NULL DEFAULT 20,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_authority_profiles_user_id ON authority_profiles (user_id);
CREATE INDEX IF NOT EXISTS ix_authority_profiles_department ON authority_profiles (department);

CREATE TABLE IF NOT EXISTS issue_assignments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  issue_id UUID NOT NULL UNIQUE REFERENCES issues(id) ON DELETE CASCADE,
  authority_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  authority_profile_id UUID NOT NULL REFERENCES authority_profiles(id) ON DELETE CASCADE,
  department VARCHAR(120) NOT NULL,
  distance_km DOUBLE PRECISION NOT NULL,
  routed_by_fallback BOOLEAN NOT NULL DEFAULT FALSE,
  field_worker VARCHAR(160),
  priority VARCHAR(40),
  eta DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE issue_assignments ADD COLUMN IF NOT EXISTS field_worker VARCHAR(160);
ALTER TABLE issue_assignments ADD COLUMN IF NOT EXISTS priority VARCHAR(40);
ALTER TABLE issue_assignments ADD COLUMN IF NOT EXISTS eta DATE;

CREATE INDEX IF NOT EXISTS ix_issue_assignments_issue_id ON issue_assignments (issue_id);
CREATE INDEX IF NOT EXISTS ix_issue_assignments_authority_id ON issue_assignments (authority_id);
CREATE INDEX IF NOT EXISTS ix_issue_assignments_department ON issue_assignments (department);

CREATE TABLE IF NOT EXISTS authority_workers (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  authority_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  department VARCHAR(120) NOT NULL,
  name VARCHAR(160) NOT NULL,
  phone_number VARCHAR(32),
  role_label VARCHAR(120),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_authority_workers_authority_id ON authority_workers (authority_id);
CREATE INDEX IF NOT EXISTS ix_authority_workers_department ON authority_workers (department);

CREATE TABLE IF NOT EXISTS votes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  issue_id UUID NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  user_label VARCHAR(120) NOT NULL DEFAULT 'Community Member',
  vote_type VARCHAR(24) NOT NULL DEFAULT 'upvote',
  evidence_url VARCHAR(500),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE votes ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;

CREATE TABLE IF NOT EXISTS comments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  issue_id UUID NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
  user_label VARCHAR(120) NOT NULL DEFAULT 'Community Member',
  body TEXT NOT NULL,
  evidence_url VARCHAR(500),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_votes_issue_id ON votes (issue_id);
CREATE INDEX IF NOT EXISTS ix_votes_user_id ON votes (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_votes_issue_user_type ON votes (issue_id, user_id, vote_type) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_comments_issue_id ON comments (issue_id);
