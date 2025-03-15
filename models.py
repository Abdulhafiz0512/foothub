import sqlalchemy as db
from datetime import datetime

from sqlalchemy import func

from database import Base


class User(Base):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, unique=True)
    nickname = db.Column(db.String)
    join_date = db.Column(db.DateTime, default=datetime.now)


class Submission(Base):
    __tablename__ = 'submissions'

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.String, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    nickname = db.Column(db.String)
    image_count = db.Column(db.Integer)
    people_count = db.Column(db.Integer)
    delivery_source = db.Column(db.String)
    status = db.Column(db.String, default='pending')  # pending, approved, rejected, deleted
    created_at = db.Column(db.DateTime, default=datetime.now)
    channel_post_id = db.Column(db.Integer, nullable=True)  # ID of the post in the channel, if approved


class Image(Base):
    __tablename__ = 'images'

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.String, db.ForeignKey('submissions.submission_id'))
    file_id = db.Column(db.String)
    is_check_image = db.Column(db.Boolean, default=False)
    sequence = db.Column(db.Integer, nullable=True)