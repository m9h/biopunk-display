from datetime import datetime, timezone
from app import db


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(200), nullable=False)
    transition = db.Column(db.String(30), default='righttoleft')
    source = db.Column(db.String(20), default='web')  # web, api, voice, gesture, webhook
    priority = db.Column(db.Integer, default=0)
    played = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, index=True, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'body': self.body,
            'transition': self.transition,
            'source': self.source,
            'priority': self.priority,
            'played': self.played,
            'created_at': self.created_at.isoformat() + 'Z',
        }

    def __repr__(self):
        return f'<Message {self.id}: {self.body[:30]}>'
