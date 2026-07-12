"""Initial unified schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(), unique=True, index=True),
        sa.Column("email", sa.String(), unique=True, index=True),
        sa.Column("password_hash", sa.String()),
        sa.Column("display_name", sa.String()),
        sa.Column("bio", sa.Text()),
        sa.Column("registration_source", sa.String(), default="email_password"),
        sa.Column("login_count", sa.Integer(), default=0),
        sa.Column("current_role", sa.String()),
        sa.Column("target_role", sa.String()),
        sa.Column("location_preference", sa.String()),
        sa.Column("skills_json", sa.JSON()),
        sa.Column("resume_token", sa.String()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "ai_resources",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("category", sa.String()),
        sa.Column("tags", sa.JSON()),
        sa.Column("difficulty", sa.String()),
        sa.Column("cost", sa.String()),
        sa.Column("verified", sa.Boolean(), default=True),
        sa.Column("upvotes", sa.Integer(), default=0),
        sa.Column("added_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("featured", sa.Boolean(), default=False),
    )
    op.create_table(
        "learning_paths",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id")),
        sa.Column("title", sa.String()),
        sa.Column("topic", sa.String()),
        sa.Column("expertise_level", sa.String()),
        sa.Column("path_data_json", sa.JSON(), nullable=False),
        sa.Column("target_role", sa.String()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("is_archived", sa.Boolean(), default=False),
    )
    op.create_table(
        "skill_gaps",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id")),
        sa.Column("learning_path_id", sa.String(), sa.ForeignKey("learning_paths.id")),
        sa.Column("target_role", sa.String()),
        sa.Column("missing_skills", sa.JSON()),
        sa.Column("recommended_resources", sa.JSON()),
        sa.Column("ai_analysis", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "resumes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id")),
        sa.Column("resume_token", sa.String(), unique=True, index=True),
        sa.Column("original_pdf_url", sa.String()),
        sa.Column("parsed_data_json", sa.JSON()),
        sa.Column("tailored_versions_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "job_searches",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id")),
        sa.Column("run_id", sa.String(), index=True),
        sa.Column("location", sa.String()),
        sa.Column("role", sa.String()),
        sa.Column("filters_json", sa.JSON()),
        sa.Column("results_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "job_applications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id")),
        sa.Column("learning_path_id", sa.String(), sa.ForeignKey("learning_paths.id")),
        sa.Column("job_search_id", sa.String(), sa.ForeignKey("job_searches.id")),
        sa.Column("company_name", sa.String()),
        sa.Column("job_title", sa.String()),
        sa.Column("job_url", sa.String()),
        sa.Column("application_status", sa.String()),
        sa.Column("tailored_resume_id", sa.String(), sa.ForeignKey("resumes.id")),
        sa.Column("outreach_email_id", sa.String()),
        sa.Column("applied_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "progress_tracking",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id")),
        sa.Column("learning_path_id", sa.String(), sa.ForeignKey("learning_paths.id")),
        sa.Column("milestone_identifier", sa.String()),
        sa.Column("resource_url", sa.String()),
        sa.Column("completion_status", sa.String()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("notes", sa.Text()),
    )
    op.create_table(
        "resource_bookmarks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("resource_id", sa.String(), sa.ForeignKey("ai_resources.id"), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("completed", sa.Boolean(), default=False),
        sa.Column("bookmarked_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("resource_bookmarks")
    op.drop_table("progress_tracking")
    op.drop_table("job_applications")
    op.drop_table("job_searches")
    op.drop_table("resumes")
    op.drop_table("skill_gaps")
    op.drop_table("learning_paths")
    op.drop_table("ai_resources")
    op.drop_table("users")
