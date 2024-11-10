from sqlalchemy import Column, Integer, DateTime, VARCHAR
from sqlalchemy.orm import column_property
from sqlalchemy.ext.declarative import declarative_base

# Define the base class
Base = declarative_base()


class RewardsTable(Base):
    __tablename__ = "RewardsTable"

    xrpId = Column(VARCHAR, primary_key=True)
    OGReputationRewards = Column(Integer)
    birdReputationRewards = Column(Integer)
    totalReputationRewards = Column(Integer)
    traits_2DRewards = column_property(Column("2DTraitsRewards", Integer))
    traits_3DCollabRewards = column_property(Column("3DCollabRewards", Integer))
    totalTraits3DRewards = column_property(Column("TotalTrait3DRewards", Integer))
    activeSells = Column(Integer)
    penaltyPercent = Column(Integer)
    penaltyReputationRewards = Column(Integer)
    bonusXrainFlag = Column(Integer)
    traitXrainFlag = Column(Integer)
    dailyBonusFlagDate = Column(DateTime)
    penaltyTraits3DRewards = Column(Integer)
    reputationFlag = Column(Integer)
    finalRepTraitRewards = column_property(Column("FINALRepTraitRewards", Integer))
    tokenIdBattleNFT = Column(VARCHAR)
    xrainPower = Column(Integer)
    nftlink = Column(VARCHAR)
    reserveXRAIN = Column(Integer)
    reserveBoosts = Column(Integer)
    battleWins = Column(Integer)
    nftGroupName = column_property(Column("NFTGroupName", Integer))
    taxonId = Column(Integer)
    discordId = Column(VARCHAR)
