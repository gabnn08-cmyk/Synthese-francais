create schema if not exists app_private;

create table if not exists app_private.users (
    id serial primary key,
    username text unique not null,
    password text not null default '',
    password_hash text,
    full_name text not null,
    role text not null check (role in ('teacher', 'student')),
    created_at text not null default ''
);

create table if not exists app_private.evaluations (
    id serial primary key,
    student_id integer not null references app_private.users(id) on delete cascade,
    title text not null,
    evaluation_type text not null check (evaluation_type in ('ecrit', 'oral')),
    subject_area text not null,
    evaluation_date text not null,
    score double precision not null check (score >= 0),
    max_score double precision not null check (max_score > 0),
    appreciation text not null,
    created_at text not null
);

create table if not exists app_private.sessions (
    token text primary key,
    user_id integer not null references app_private.users(id) on delete cascade,
    created_at text not null,
    expires_at text not null
);

create index if not exists evaluations_student_id_idx on app_private.evaluations(student_id);
create index if not exists evaluations_date_idx on app_private.evaluations(evaluation_date desc, created_at desc);
create index if not exists sessions_user_id_idx on app_private.sessions(user_id);
create index if not exists sessions_expires_at_idx on app_private.sessions(expires_at);
