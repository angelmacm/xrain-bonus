from database.db import XparrotDB
from utils.xrplCommands import XRPClient
from utils.config import botConfig, xrplConfig, dbConfig
from interactions import Intents, Client, listen, InteractionContext # General discord Interactions import
from interactions import slash_command, slash_attachment_option, slash_str_option, slash_bool_option # Slash command imports
from interactions import Button, ButtonStyle, Embed # Confirmation Imports
from interactions.api.events import Component

# Other imports
from aiohttp import ClientSession
from io import StringIO
from csv import reader as csvReader
from asyncio import TimeoutError
from configparser import ConfigParser
from datetime import datetime

config = ConfigParser()
config.read("config.ini", encoding='utf-8')

intents = Intents.DEFAULT | Intents.MESSAGE_CONTENT
client = Client(intents=intents, token=config['BOT']['token'])

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

@listen()
async def on_ready():
    # Some function to do when the bot is ready
    print("[BOT]    Discord Bot Ready!")

# Dailies Command:
# Parameters:
#       XRP ID: [Required] XRP Address where the users hold their NFTs and the receipient of the reward
@slash_command(
        name="daily-xrain",
        description="Redeem daily rewards",
        options= [
            slash_str_option(
                name = "xrpid",
                description = "XRP Address that will receive the daily reward",
                required = True
            )
        ])
async def dailyXrain(ctx: InteractionContext):
    await ctx.defer() # Defer the response to wait for the function to run.
    
    print(f"[BOT]   Daily Claim requested by {ctx.author.display_name}") if botVerbosity else None
    
    xrpId = ctx.args[0]
    
    result = await dbInstance.getDailyStatus(xrpId)
    
    if result['result'] == 'Claimable':
        claimInfo = await dbInstance.getDailyAmount(xrpId)
        if claimInfo['result'] == "Success":
            claimAmount = claimInfo['amount']
            claimImage = claimInfo['nftLink']
            
            await dbInstance.dailySet(xrpId)
            
            embed = Embed(title="XRAIN Claim",
                      description=f"Congratulations {ctx.author.display_name} you have claimed your XRPLRainforest Daily Bonus XRAIN rewards totaling **__{claimAmount}__** XRAIN!!",
                      timestamp=datetime.now())

            embed.set_image(url=claimImage)
            embed.set_footer(text="XRPLRainforest Daily Bonus")

            await ctx.send(embed=embed)
        else:
            pass
        pass
    elif result['result'] == 'NotReady':
        remainingHour = result['timeRemaining']['hour']
        remainingMinute = result['timeRemaining']['minute']
        remainingSecond = result['timeRemaining']['second']
        
        description = "Your Daily Bonus XRAIN rewards have already been claimed, please wait **__"
        description += f"{remainingHour}hr" if int(remainingHour) != 0 else ''
        description += f" {remainingMinute}min" if int(remainingMinute) != 0 else ''
        description += f" {remainingSecond}s" if int(remainingSecond) != 0 else ''
        description += "__** to the next XRAIN claim period."
        
        embed = Embed(title="XRAIN Claim",
                      description=description,
                      timestamp=datetime.now())

        embed.set_footer(text="XRPLRainforest Daily Bonus")

        await ctx.send(embed=embed)
    else:
        pass

    
# Biweekly Command:
# Parameters:
#       XRP ID: [Required] XRP Address where the users hold their NFTs and the receipient of the reward 
@slash_command(
        name="biweekly-xrain",
        description="Redeem bi-weekly rewards",
        options= [
            slash_str_option(
                name = "xrpid",
                description = "XRP Address that will receive the daily reward",
                required = True
            )
        ])
async def biweeklyXrain(ctx: InteractionContext):
    
    print(f"[BOT]   Biweekly claim requested by {ctx.author.display_name}") if botVerbosity else None
    
    await ctx.defer() # Defer the response to wait for the function to run.
    
    xrpId = ctx.args[0]
    
    result = await dbInstance.getBiWeeklyStatus(xrpId)
    
    if result:
        
        await dbInstance.biweeklySet(xrpId)
        nftLink = await dbInstance.getRandomNFT(xrpId)
        
        embed = Embed(title="XRAIN Claim",
                      description=f"Congratulations you have claimed your XRPLRainforest Bonus Bi-weekly XRAIN rewards totaling **__{result}__** XRAINs !!",
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