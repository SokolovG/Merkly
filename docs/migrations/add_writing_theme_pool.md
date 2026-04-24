# Migration: Writing Theme Pool

## Tables

```sql
-- Global catalog of exam-style writing topics
CREATE TABLE writing_theme_pool (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    theme       TEXT        NOT NULL,
    target_lang TEXT        NOT NULL,
    level       TEXT,                          -- NULL = suitable for all levels
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_writing_theme_pool_lang_level
    ON writing_theme_pool (target_lang, level);

-- Per-user history: tracks which themes have been shown
CREATE TABLE writing_theme_history (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID        NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    theme_id   UUID        NOT NULL REFERENCES writing_theme_pool(id) ON DELETE CASCADE,
    used_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_writing_theme_history_user_theme UNIQUE (user_id, theme_id)
);

CREATE INDEX ix_writing_theme_history_user
    ON writing_theme_history (user_id);
```

## Seed data — German (B1/B2 exam topics)

These are topics commonly appearing in Goethe-Zertifikat B1/B2 and TestDaF exams.
Level NULL means the theme is suitable for all levels.

```sql
INSERT INTO writing_theme_pool (theme, target_lang, level) VALUES
-- Gesellschaft & Leben
('Arbeitsmigration: Chancen und Herausforderungen',               'de', NULL),
('Umwelt und Klimawandel: Was kann jeder Einzelne tun?',          'de', NULL),
('Universität oder Fachhochschule – was ist die bessere Wahl?',   'de', NULL),
('Haustiere kaufen oder aus dem Tierheim adoptieren?',            'de', NULL),
('Homeoffice: Vor- und Nachteile für Arbeitnehmer',               'de', NULL),
('Ehrenamtliche Arbeit – warum ist sie wichtig?',                 'de', NULL),
('Soziale Medien: Fluch oder Segen für die Gesellschaft?',        'de', NULL),
('Wohnen in der Stadt oder auf dem Land?',                        'de', NULL),
('Öffentlicher Nahverkehr vs. eigenes Auto',                      'de', NULL),
('Gesundheit und Sport: Sollte Sport in der Schule Pflicht sein?','de', NULL),
-- B1 topics
('Meine ideale Wohnung',                                          'de', 'B1'),
('Ein unvergesslicher Urlaub',                                    'de', 'B1'),
('Mein liebstes Hobby und warum ich es empfehle',                 'de', 'B1'),
('Digitale Medien in der Schule – Pro und Kontra',                'de', 'B1'),
('Freundschaft: Was macht einen guten Freund aus?',               'de', 'B1'),
-- B2 topics
('Globalisierung: Gewinner und Verlierer',                        'de', 'B2'),
('Künstliche Intelligenz: Bedrohung oder Chance für die Arbeitswelt?', 'de', 'B2'),
('Feminismus heute: Ist Gleichstellung erreicht?',                'de', 'B2'),
('Generationenkonflikt: Jung vs. Alt in der modernen Gesellschaft','de', 'B2'),
('Bildungssystem im Wandel: Brauchen wir neue Lernmodelle?',      'de', 'B2')
ON CONFLICT DO NOTHING;
```
