from sqlalchemy import Column, Integer, VARCHAR
from sqlalchemy.orm import column_property
from sqlalchemy.ext.declarative import declarative_base

# Define the base class
Base = declarative_base()

class ClaimQuotes(Base):
    __tablename__ = 'claimQuotes'

    quoteId = Column(Integer, index=True, primary_key=True)
    nftGroupName = column_property(Column('NFTGroupName', VARCHAR))
    taxonId = Column(Integer)
    description = Column(VARCHAR)