from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker
from database.models.rewardstable import RewardsTable
from database.models.nftTraitList import NFTTraitList
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime
from datetime import timedelta
from sqlalchemy.future import select

class XparrotDB:
    def __init__(self, host, dbName, username, password, verbose):
        
        #                   username          if empty, do not add :, else :password      host   dbName
        sqlLink = f"mysql+aiomysql://{username}{'' if password in ['', None] else f':{password}'}@{host}/{dbName}"
        self.dbEngine = create_async_engine(sqlLink, verbose)
        self.asyncSessionMaker = async_sessionmaker(bind=self.dbEngine, expire_on_commit=False)
        self.vebose = verbose
    
    async def getDailyStatus(self, xrpId: str) -> dict:
        # Return structure
        funcResult = {"result":"", 
                      'timeRemaining':
                          {
                              'hour':0,
                              'minute':0,
                              'second':0,
                          }}
        
        async with self.asyncSessionMaker() as session:
                
            # Query the required columns
            query = select(
                RewardsTable.dailyBonusFlagDate,
                func.now()
            ).filter(RewardsTable.xrpId == xrpId)
            result = await session.execute(query)
            result = result.first()
            
            print(f"[DB]    Query Result: {result}") if self.vebose else None
            
            # Check if there are results
            # No result would only mean that xrpId is not found
            if result:
                lastClaim, currentTime = result
                
                # Check if the user has ever claimed their dailies
                # If not, the dailies are available to redeem
                if lastClaim:
                    nextClaim = lastClaim + timedelta(days=1)
                                
                    # Check if the currentTime is past than nextClaim
                    if nextClaim > currentTime:
                        
                        
                        # compute the remaining time
                        timeDiff:timedelta = nextClaim - currentTime
                        
                        # Parse the remaining time
                        remainingHour, remainingMin, remainingSec = str(timeDiff).split(":")
                        
                        # Ready the return structure
                        funcResult["result"] = 'NotReady'
                        funcResult['timeRemaining']['hour'] = remainingHour
                        funcResult['timeRemaining']['minute'] = remainingMin
                        funcResult['timeRemaining']['second'] = remainingSec
                        
                        print(f"[DB]    getDailyStatus({xrpId}): {funcResult}") if self.vebose else None
                        
                        return funcResult
                        
                    else:
                        funcResult["result"] = 'Claimable'
                        print(f"[DB]    getDailyStatus({xrpId}): {funcResult['result']}") if self.vebose else None
                        return funcResult
                else:
                    funcResult["result"] = 'Claimable'
                    print(f"[DB]    getDailyStatus({xrpId}): {funcResult['result']}") if self.vebose else None
                    return funcResult
            else:
                funcResult['result'] = "XrpIdNotFound"
                print(f"[DB]    getDailyStatus({xrpId}): {funcResult['result']}") if self.vebose else None
                return funcResult
        
    async def getDailyAmount(self, xrpId: str) -> dict:
        async with self.asyncSessionMaker as session:
            funcResult = {'result':None,'amount':None,'nftLink':None}
            query = select(
                NFTTraitList.totalXRAIN, NFTTraitList.nftlink
            ).filter(
                NFTTraitList.xrpId == xrpId,
                NFTTraitList.nftlink != ''
            ).order_by(
                func.random()
            ).limit(1)
            queryResult = await session.execute()
            queryResult = queryResult.first()
            
            if queryResult:
                xrainValue, nftLink = queryResult
                
                if nftLink == "":
                    funcResult['result'] = 'ImageLinkNotFound'
                    print(f"[DB]    getDailyAmount({xrpId}): {funcResult['result']}") if self.vebose else None
                    return funcResult
                
                funcResult['result'] = 'Success'
                funcResult['nftLink'] = nftLink
                funcResult['amount'] = xrainValue
                print(f"[DB]    getDailyAmount({xrpId}): {funcResult['result']}") if self.vebose else None
                return funcResult            
            else:
                funcResult['result'] = "XrpIdNotFound"
                print(f"[DB]    getDailyAmount({xrpId}): {funcResult['result']}") if self.vebose else None
                return funcResult
    
    def getBiWeeklyStatus(self, xrpId) -> bool | int:
        # Return structure
        query = self.rewardsSession.query(RewardsTable.penaltyReputationRewards,
                                          RewardsTable.bonusXrainFlag, 
                                          RewardsTable.reputationFlag)\
                                    .filter(RewardsTable.xrpId == xrpId)
        queryResult = query.first()
        
        if queryResult:
            rewardAmount, bonusFlag, repFlag = queryResult
            if bonusFlag == 1 or repFlag == 1:
                
                print(f"[DB]    getBiWeeklyStatus({xrpId}): BonusReputationFlagTriggered ") if self.vebose else None
                return False
            
            print(f"[DB]    getBiWeeklyStatus({xrpId}): Bi-Weekly reward is {rewardAmount}") if self.vebose else None
            return rewardAmount
        
        else:
            print(f"[DB]    getBiWeeklyStatus({xrpId}): XrpIdNotFound") if self.vebose else None
            return False
    
    def biweeklySet(self, xrpId) -> None:
        try:
            self.rewardsSession.query(RewardsTable)\
                                        .filter(RewardsTable.xrpId == xrpId)\
                                        .update({RewardsTable.bonusXrainFlag: 1})
            self.rewardsSession.commit()
            print(f"biweeklySet({xrpId}): Success") if self.vebose else None
        except Exception as e:
            print(f"biweeklySet({xrpId}): {e}") if self.vebose else None
            self.rewardsSession.rollback()
            
    
    def dailySet(self, xrpId) -> None:
        try:
            self.rewardsSession.query(RewardsTable)\
                                        .filter(RewardsTable.xrpId == xrpId)\
                                        .update({RewardsTable.dailyBonusFlagDate: func.now()})
            self.rewardsSession.commit()
            print(f"dailySet({xrpId}): Success") if self.vebose else None
        except Exception as e:
            print(f"dailySet({xrpId}): {e}") if self.vebose else None
            self.rewardsSession.rollback()