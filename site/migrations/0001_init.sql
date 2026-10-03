-- poe2lab's site: accounts, builds (what is searched and sorted; the whole package is in R2), reviews, favourites,
-- follows, notifications, reports; the app's connection by a device code (docs/SITE.md). Times are Unix seconds.

CREATE TABLE users (
  id          TEXT PRIMARY KEY,
  discord_id  TEXT UNIQUE,
  nick        TEXT NOT NULL UNIQUE COLLATE NOCASE,
  avatar      TEXT,                                -- the Discord avatar's address, or none: the nick's letters
  hue         INTEGER NOT NULL DEFAULT 210,        -- the letters' colour
  bio         TEXT NOT NULL DEFAULT '',
  links       TEXT NOT NULL DEFAULT '[]',          -- [{"kind": "twitch" | "youtube", "url"}]
  role        TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'mod', 'owner')),
  lang        TEXT NOT NULL DEFAULT 'ru',
  notify      TEXT NOT NULL DEFAULT '{"reviews":true,"replies":true,"follows":false}',
  banned_at   INTEGER,
  created_at  INTEGER NOT NULL
);

CREATE TABLE sessions (
  id          TEXT PRIMARY KEY,                    -- the cookie's value (random, httpOnly)
  user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at  INTEGER NOT NULL,
  created_at  INTEGER NOT NULL
);
CREATE INDEX sessions_user ON sessions(user_id);

-- the app's tokens: only their hash is kept
CREATE TABLE app_tokens (
  id           TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash   TEXT NOT NULL UNIQUE,
  name         TEXT NOT NULL,                      -- "poe2lab на Boot-PC"
  created_at   INTEGER NOT NULL,
  last_used_at INTEGER
);

-- the app asks (a code to show), the player confirms on the site, the app takes its token once
CREATE TABLE device_codes (
  code        TEXT PRIMARY KEY,                    -- 6 letters and digits the player compares
  device_id   TEXT NOT NULL UNIQUE,                -- the app's secret for taking the token
  name        TEXT NOT NULL,
  user_id     TEXT REFERENCES users(id) ON DELETE CASCADE,
  state       TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'allowed', 'declined', 'taken')),
  expires_at  INTEGER NOT NULL
);

CREATE TABLE builds (
  id           TEXT PRIMARY KEY,
  author_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  app_key      TEXT NOT NULL,                      -- the build's key in the app: publishing again updates it
  title        TEXT NOT NULL,
  cls          TEXT NOT NULL,                      -- warrior | ranger | witch | sorc | merc | monk | huntress | druid
  asc          TEXT NOT NULL DEFAULT '',
  main_skill   TEXT NOT NULL,
  skill_icon   TEXT,
  dmg          TEXT NOT NULL,                      -- phys | fire | cold | light | chaos
  weapon       TEXT NOT NULL DEFAULT '',
  tags         TEXT NOT NULL DEFAULT '[]',
  cover        TEXT,
  tint         TEXT,
  patch        TEXT NOT NULL,
  version      INTEGER NOT NULL DEFAULT 1,
  package_key  TEXT NOT NULL,                      -- R2: builds/<id>/<version>.json
  dps          REAL NOT NULL DEFAULT 0,
  life         REAL NOT NULL DEFAULT 0,
  es           REAL NOT NULL DEFAULT 0,
  description  TEXT NOT NULL DEFAULT '',
  search       TEXT NOT NULL DEFAULT '',           -- lower-case words to find it by: title, skill, class, tags...
  rating_sum   INTEGER NOT NULL DEFAULT 0,
  rating_n     INTEGER NOT NULL DEFAULT 0,
  views        INTEGER NOT NULL DEFAULT 0,
  opens        INTEGER NOT NULL DEFAULT 0,
  status       TEXT NOT NULL DEFAULT 'published' CHECK (status IN ('published', 'hidden', 'removed')),
  created_at   INTEGER NOT NULL,
  updated_at   INTEGER NOT NULL,
  UNIQUE (author_id, app_key)
);
CREATE INDEX builds_list ON builds(status, patch, cls);
CREATE INDEX builds_author ON builds(author_id);

CREATE TABLE reviews (
  id          TEXT PRIMARY KEY,
  build_id    TEXT NOT NULL REFERENCES builds(id) ON DELETE CASCADE,
  user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  stars       INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
  crit        TEXT NOT NULL DEFAULT '{}',          -- {"dmg": 1-5, "tank": 1-5, "budget": 1-5, "ease": 1-5}
  text        TEXT NOT NULL,
  char_cls    TEXT,
  char_level  INTEGER,
  helpful_n   INTEGER NOT NULL DEFAULT 0,
  reply       TEXT,                                -- the build's author's answer
  reply_at    INTEGER,
  status      TEXT NOT NULL DEFAULT 'visible' CHECK (status IN ('visible', 'hidden')),
  created_at  INTEGER NOT NULL,
  updated_at  INTEGER NOT NULL,
  UNIQUE (build_id, user_id)                       -- one review per account
);
CREATE INDEX reviews_build ON reviews(build_id, status);

CREATE TABLE review_votes (
  review_id  TEXT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY (review_id, user_id)
);

CREATE TABLE favorites (
  user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  build_id    TEXT NOT NULL REFERENCES builds(id) ON DELETE CASCADE,
  created_at  INTEGER NOT NULL,
  PRIMARY KEY (user_id, build_id)
);

CREATE TABLE follows (
  user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  author_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at  INTEGER NOT NULL,
  PRIMARY KEY (user_id, author_id)
);

CREATE TABLE notifications (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        TEXT NOT NULL CHECK (kind IN ('review', 'reply', 'follow', 'patch', 'mod')),
  actor_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
  build_id    TEXT REFERENCES builds(id) ON DELETE CASCADE,
  review_id   TEXT REFERENCES reviews(id) ON DELETE CASCADE,
  text        TEXT NOT NULL DEFAULT '',
  read_at     INTEGER,
  created_at  INTEGER NOT NULL
);
CREATE INDEX notifications_user ON notifications(user_id, read_at);

CREATE TABLE reports (
  id           TEXT PRIMARY KEY,
  reporter_id  TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target       TEXT NOT NULL CHECK (target IN ('build', 'review', 'user')),
  target_id    TEXT NOT NULL,
  reason       TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'solved')),
  resolution   TEXT,
  created_at   INTEGER NOT NULL,
  resolved_at  INTEGER,
  UNIQUE (reporter_id, target, target_id)
);
CREATE INDEX reports_open ON reports(status, created_at);
