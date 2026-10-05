import os
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from werkzeug.security import generate_password_hash
from server import create_app, User

app = create_app()

# Optional first-start setup. Existing accounts are never overwritten.
bootstrap_email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
bootstrap_password = os.environ.get('ADMIN_PASSWORD', '')
if bootstrap_email and bootstrap_password:
    if len(bootstrap_password) < 10:
        raise RuntimeError('ADMIN_PASSWORD precisa ter ao menos 10 caracteres.')
    engine = app.extensions['engine']
    with Session(engine) as db:
        existing = db.scalar(select(User).where(User.email == bootstrap_email))
        if existing is None:
            insert = pg_insert if engine.dialect.name == 'postgresql' else sqlite_insert
            statement = insert(User).values(
                id=str(uuid.uuid4()), email=bootstrap_email,
                password_hash=generate_password_hash(bootstrap_password), role='owner'
            ).on_conflict_do_nothing(index_elements=['email'])
            db.execute(statement)
            db.commit()
    os.environ.pop('ADMIN_PASSWORD', None)
bootstrap_password = None
