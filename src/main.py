from database.db import XparrotDB
from utils.xrplCommands import XRPClient
from utils.config import botConfig, xrplConfig, dbConfig, coinsConfig
from utils.logging import loggingInstance

from interactions import Intents, Client, listen, InteractionContext # General discord Interactions import
from interactions import slash_command, slash_str_option # Slash command imports
from interactions import Embed

# Other imports
from datetime import datetime

intents = Intents.DEFAULT | Intents.MESSAGE_CONTENT
client = Client(intents=intents, token=botConfig['token'])

# Initialize DB connection
dbInstance = XparrotDB(
    host=dbConfig['db_server'],
    dbName=dbConfig['db_name'],
    username=dbConfig['db_username'],
    password=dbConfig['db_password'],
    verbose=dbConfig.getboolean('verbose')
)

xrplInstance = XRPClient(xrplConfig)

botVerbosity = botConfig.getboolean('verbose')

def escapeMarkdown(text: str) -> str:
    escapeChars = ['*', '_', '~', '`']
    for char in escapeChars:
        text = text.replace(char, f'\\{char}')
    return text

@listen()
async def on_ready():
    # Some function to do when the bot is ready
    await xrplInstance.registerSeed(xrplConfig['seed'])
    loggingInstance.info(f"Discord Bot Ready!")

# Dailies Command:
# Parameters:
#       XRP ID: [Required] XRP Address where the users hold their NFTs and the receipient of the reward
@slash_command(
        name="bonus-xrain",
        description="Redeem bonus rewards",
        options= [
            slash_str_option(
                name = "xrpid",
                description = "XRP Address that will receive the bonus reward",
                required = True
            )
        ])
async def bonusXrain(ctx: InteractionContext):
    await ctx.defer() # Defer the response to wait for the function to run.
    
    loggingInstance.info(f"Bonus Claim requested by {ctx.author.display_name}") if botVerbosity else None
    
    xrpId = ctx.args[0]
    
    result = await dbInstance.getBonusStatus(xrpId)
    
    if result['result'] == 'Claimable':
        claimInfo = await dbInstance.getBonusAmount(xrpId)
        if claimInfo['result'] == "Success":
            claimAmount = claimInfo['amount']
            claimImage = claimInfo['nftLink']
            tokenId = claimInfo['tokenId']
            
            await xrplInstance.registerSeed(xrplConfig['seed'])
            sendSuccess = await xrplInstance.sendCoin(address=xrpId,
                                                  value=int(claimAmount),
                                                  coinHex=coinsConfig['XRAIN'],
                                                  memos="XRPLRainforest Bonus Rewards")
            
            if not sendSuccess['result']:
                embed = Embed(title="XRAIN Claim",
                              description=f"{sendSuccess['error'] if sendSuccess['error'] is not None else 'Unknown'} error occurred",
                              timestamp=datetime.now())
                await ctx.send(embed=embed)
                return
            
            await dbInstance.bonusSet(xrpId)
            
            embed = Embed(title="XRAIN Claim",
                      description=f"Congratulations {ctx.author.display_name} you have claimed your XRPLRainforest Bonus XRAIN rewards totaling **__{claimAmount}__** XRAIN!! Claim again in **__48 Hours__**!\n\n[View NFT Details](https://xrp.cafe/nft/{tokenId})",
                      timestamp=datetime.now())

            embed.set_image(url=claimImage)
            embed.set_footer(text="XRPLRainforest Bonus")

            await ctx.send(embed=embed)
        else:
            embed = Embed(title="XRAIN Claim",
                      description=f"{claimInfo['result']} error occurred",
                      timestamp=datetime.now())
            
            embed.set_footer(text="XRPLRainforest Bonus")
            
            await ctx.send(embed=embed)
            
    elif result['result'] == 'NotReady':
        remainingHour = result['timeRemaining']['hour']
        remainingMinute = result['timeRemaining']['minute']
        remainingSecond = result['timeRemaining']['second']
        
        description = "Your Bonus XRAIN rewards have already been claimed, please wait **__"
        description += f"{remainingHour}hr" if int(remainingHour) != 0 else ''
        description += f" {remainingMinute}min" if int(remainingMinute) != 0 else ''
        description += f" {remainingSecond}s" if int(remainingSecond) != 0 else ''
        description += "__** to the next XRAIN claim period."
        
        embed = Embed(title="XRAIN Claim",
                      description=description,
                      timestamp=datetime.now())

        embed.set_footer(text="XRPLRainforest Bonus")

        await ctx.send(embed=embed)
        
    else:
        embed = Embed(title="XRAIN Claim",
                      description=f"{result['result']} error occurred",
                      timestamp=datetime.now())
            
        embed.set_footer(text="XRPLRainforest Bonus")
        
        await ctx.send(embed=embed)

    
# Biweekly Command:
# Parameters:
#       XRP ID: [Required] XRP Address where the users hold their NFTs and the receipient of the reward 
@slash_command(
        name="biweekly-xrain",
        description="Redeem bi-weekly rewards",
        options= [
            slash_str_option(
                name = "xrpid",
                description = "XRP Address that will receive the bonus reward",
                required = True
            )
        ])
async def biweeklyXrain(ctx: InteractionContext):
    
    loggingInstance.info(f"Biweekly claim requested by {ctx.author.display_name}") if botVerbosity else None
    
    await ctx.defer() # Defer the response to wait for the function to run.
    
    xrpId = ctx.args[0]
    
    amount = await dbInstance.getBiWeeklyStatus(xrpId)
    
    if amount:
        
        await xrplInstance.registerSeed(xrplConfig['seed'])
        sendSuccess = await xrplInstance.sendCoin(address=xrpId,
                                            value=int(amount),
                                            coinHex=coinsConfig['XRAIN'],
                                            memos="XRPLRainforest Bonus Biweekly Reputation Rewards")
        
        if not sendSuccess['result']:
            embed = Embed(title="XRAIN Claim",
                            description=f"{sendSuccess['error'] if sendSuccess['error'] is not None else 'Unknown'} error occurred",
                            timestamp=datetime.now())
            await ctx.send(embed=embed)
            return
        
        
        await dbInstance.biweeklySet(xrpId)
        nftData = await dbInstance.getRandomNFT(xrpId)
        tokenId = nftData['tokenId']
        nftLink = nftData['nftLink']

        embed = Embed(title="XRAIN Claim",
                      description=f"Congratulations {ctx.author.display_name} you have claimed your XRPLRainforest Bonus Bi-weekly XRAIN Reputation Rewards totaling **__{amount}__** XRAINs !!\n\n[View NFT Details](https://xrp.cafe/nft/{tokenId})",
                      timestamp=datetime.now())

        embed.set_footer(text="XRPLRainforest Bi-weekly Bonus")
        
        if nftLink != "NoNFTFound":
            embed.add_image(nftLink)

        await ctx.send(embed=embed)
        
    else:
        embed = Embed(title="XRAIN Claim",
                      description="Bonus Bi-weekly XRAIN rewards has already been claimed or the ReputationalFlag has been triggered for this xrpId",
                      timestamp=datetime.now())
        
        embed.set_footer(text="XRPLRainforest Bi-weekly Bonus")

        await ctx.send(embed=embed)
    
        
if __name__ == "__main__":
    client.start()