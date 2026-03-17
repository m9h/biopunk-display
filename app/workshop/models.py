"""
Workshop mode database models.

Submission: a message submitted by a workshop participant
Vote: tracks who voted for what (one vote per voter per submission)
"""

from datetime import datetime, timezone
from app import db


class Submission(db.Model):
    __tablename__ = 'workshop_submission'

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(200), nullable=False)
    nickname = db.Column(db.String(30), default='ANON')
    status = db.Column(db.String(10), default='pending')  # pending, approved, rejected
    vote_count = db.Column(db.Integer, default=0)
    played = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, index=True,
                           default=lambda: datetime.now(timezone.utc))

    votes = db.relationship('Vote', backref='submission', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'body': self.body,
            'nickname': self.nickname,
            'status': self.status,
            'vote_count': self.vote_count,
            'played': self.played,
            'created_at': self.created_at.isoformat() + 'Z',
        }

    def __repr__(self):
        return f'<Submission {self.id}: {self.body[:30]}>'


class Vote(db.Model):
    __tablename__ = 'workshop_vote'

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('workshop_submission.id'),
                              nullable=False)
    voter_id = db.Column(db.String(16), nullable=False)  # cookie-based
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('submission_id', 'voter_id', name='uq_vote_unique'),
    )
