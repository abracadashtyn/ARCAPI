import logging
import sqlalchemy as sa
import sqlalchemy.orm as so
from typing import Optional, List
from app import db

class Player(db.Model):
    __tablename__ = 'players'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(250))
    matches: so.Mapped[List['Match']] = so.relationship('PlayerMatch', back_populates='player')

    def __repr__(self):
        return f"<Player id:{self.id}, name:{self.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'match_count': len(self.matches)
        }

    @classmethod
    def get_or_create(cls, name: str):
        player_record = cls.query.filter_by(name=name).first()
        if player_record is None:
            player_record = cls(name=name)
            db.session.add(player_record)
            db.session.commit()
        return player_record