"""S4 stage 3: the reset outbox becomes the mail outbox; addresses can be verified.

* ``password_reset_deliveries`` is renamed ``mail_deliveries`` and gains ``kind``
  (existing rows are ``password_reset``) and ``recipient``. Pending reset rows
  stay deliverable: same rows, same cipher key, same validity check.
* ``users`` gains the verification code columns (``pending_email`` already exists).
* Existing accounts are marked verified. Before this stage nothing could verify
  an address, and a reset by mail now needs a verified one: leaving them
  unverified would lock every pilot learner out of password recovery. New
  accounts start unverified and get a code at sign-up.

Revision ID: d8f0a2c4e6b1
Revises: d6f8a0b2c4e7
"""
import sqlalchemy as sa

from alembic import op

revision = "d8f0a2c4e6b1"
down_revision = "d6f8a0b2c4e7"
branch_labels = None
depends_on = None

_INDEXED = ("user_id", "status", "next_attempt_at")


def upgrade() -> None:
    op.rename_table("password_reset_deliveries", "mail_deliveries")
    for column in _INDEXED:
        op.execute(f"ALTER INDEX IF EXISTS ix_password_reset_deliveries_{column} RENAME TO ix_mail_deliveries_{column}")
    op.add_column(
        "mail_deliveries",
        sa.Column("kind", sa.String(32), nullable=False, server_default="password_reset"),
    )
    op.add_column("mail_deliveries", sa.Column("recipient", sa.String(255), nullable=True))
    op.create_index("ix_mail_deliveries_kind", "mail_deliveries", ["kind"])

    op.add_column("users", sa.Column("email_verification_code_hash", sa.String(128), nullable=True))
    op.add_column("users", sa.Column("email_verification_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("email_verification_attempts", sa.Integer(), nullable=True, server_default="0"))
    op.execute("UPDATE users SET is_verified = true WHERE is_verified IS NOT true")


def downgrade() -> None:
    op.drop_column("users", "email_verification_attempts")
    op.drop_column("users", "email_verification_sent_at")
    op.drop_column("users", "email_verification_code_hash")
    # Only reset rows existed before; the other kinds have no table to return to.
    op.execute("DELETE FROM mail_deliveries WHERE kind <> 'password_reset'")
    op.drop_index("ix_mail_deliveries_kind", table_name="mail_deliveries")
    op.drop_column("mail_deliveries", "recipient")
    op.drop_column("mail_deliveries", "kind")
    for column in _INDEXED:
        op.execute(f"ALTER INDEX IF EXISTS ix_mail_deliveries_{column} RENAME TO ix_password_reset_deliveries_{column}")
    op.rename_table("mail_deliveries", "password_reset_deliveries")
