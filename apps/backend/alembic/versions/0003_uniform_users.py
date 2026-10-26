"""One employee role with equal permissions throughout the application."""
from alembic import op

revision = "0003_uniform_users"
down_revision = "0002_corporate"


def upgrade():
    op.execute("UPDATE users SET role = 'user'")
    op.create_check_constraint("ck_users_uniform_role", "users", "role = 'user'")


def downgrade():
    op.drop_constraint("ck_users_uniform_role", "users", type_="check")
