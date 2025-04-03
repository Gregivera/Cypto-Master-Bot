import os
import io
import discord
import asyncio
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from discord.ext import commands, tasks
from dotenv import load_dotenv
from pycoingecko import CoinGeckoAPI
from datetime import datetime, timedelta
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")

# Channel IDs - Replace these with your actual channel IDs
BTC_CHANNEL_ID = int(os.getenv("BTC_CHANNEL_ID", "0"))
ETH_CHANNEL_ID = int(os.getenv("ETH_CHANNEL_ID", "0"))
SOL_CHANNEL_ID = int(os.getenv("SOL_CHANNEL_ID", "0"))
NEWS_CHANNEL_ID = int(os.getenv("NEWS_CHANNEL_ID", "0"))

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize CoinGecko API client for price data
cg = CoinGeckoAPI()

# Initialize Discord client with intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True

# Create bot instance
bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionary mapping coin commands to their CoinGecko IDs and symbols
COIN_MAP = {
    'btc': {'id': 'bitcoin', 'symbol': 'BTC', 'name': 'Bitcoin', 'channel_id': BTC_CHANNEL_ID},
    'eth': {'id': 'ethereum', 'symbol': 'ETH', 'name': 'Ethereum', 'channel_id': ETH_CHANNEL_ID},
    'sol': {'id': 'solana', 'symbol': 'SOL', 'name': 'Solana', 'channel_id': SOL_CHANNEL_ID}
}

# Function to fetch crypto price data from CoinGecko
def fetch_crypto_price_data(coin_id):
    try:
        # Get current price data
        price_data = cg.get_coin_by_id(
            id=coin_id,
            localization=False,
            tickers=False,
            market_data=True,
            community_data=False,
            developer_data=False,
            sparkline=False
        )
        
        # Get 24h historical data for high/low
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=24)
        historical_data = cg.get_coin_market_chart_range_by_id(
            id=coin_id,
            vs_currency='usd',
            from_timestamp=start_date.timestamp(),
            to_timestamp=end_date.timestamp()
        )
        
        return {
            'price_data': price_data,
            'historical_data': historical_data
        }
    except Exception as e:
        print(f"Error fetching {coin_id} price data: {e}")
        return None

# Function to generate a 24-hour price chart
def generate_price_chart(historical_data, coin_symbol, coin_name):
    try:
        prices = historical_data['prices']

        # Extract timestamps and prices
        timestamps = [datetime.fromtimestamp(price[0] / 1000) for price in prices]
        price_values = [price[1] for price in prices]

        # Create the plot
        plt.figure(figsize=(10, 5))
        plt.plot(timestamps, price_values, label=f'{coin_symbol} Price (USD)')
        
        # Format the x-axis to show hours
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=2))
        
        plt.xlabel('Time (24-hour period)')
        plt.ylabel('Price (USD)')
        plt.title(f'{coin_name} Price Over the Past 24 Hours')
        plt.legend()
        plt.grid(True)
        plt.gcf().autofmt_xdate()
        
        # Save the plot to a BytesIO object
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        print(f"Error generating price chart: {e}")
        return None

# Function to format price data in the specified layout
def format_price_update(data, coin_symbol):
    try:
        price_data = data['price_data']
        historical_data = data['historical_data']
        
        # Extract current price and 24h change percentage
        current_price = price_data['market_data']['current_price']['usd']
        price_change_24h = price_data['market_data']['price_change_percentage_24h']
        
        # Determine if price is up or down
        change_symbol = "▲" if price_change_24h >= 0 else "▼"
        
        # Extract 24h high and low
        high_24h = price_data['market_data']['high_24h']['usd']
        low_24h = price_data['market_data']['low_24h']['usd']
        
        # Extract 24h volume and market cap
        volume_24h = price_data['market_data']['total_volume']['usd'] / 1_000_000_000  # Convert to billions
        market_cap = price_data['market_data']['market_cap']['usd'] / 1_000_000_000_000  # Convert to trillions
        
        # Extract circulating supply
        circulating_supply = price_data['market_data']['circulating_supply'] / 1_000_000  # Convert to millions
        
        # Format the price update
        price_update = f"${coin_symbol}\n"
        price_update += f"🔹 Price: ${current_price:,.2f} ({change_symbol} {abs(price_change_24h):.2f}%)\n"
        price_update += f"🔹 24H High: ${high_24h:,.2f} | 24H Low: ${low_24h:,.2f}\n"
        price_update += f"🔹 24H Volume: ${volume_24h:.2f}B\n"
        price_update += f"🔹 Market Cap: ${market_cap:.2f}T\n"
        price_update += f"🔹 Circulating Supply: {circulating_supply:.2f}M {coin_symbol}\n"
        
        return price_update
    except Exception as e:
        print(f"Error formatting price update: {e}")
        return "Error formatting price data."

# Function to generate technical analysis with OpenAI
async def generate_technical_analysis(data, coin_symbol, coin_name):
    try:
        price_data = data['price_data']
        historical_data = data['historical_data']
        
        # Prepare the data for OpenAI
        current_price = price_data['market_data']['current_price']['usd']
        price_change_24h = price_data['market_data']['price_change_percentage_24h']
        high_24h = price_data['market_data']['high_24h']['usd']
        low_24h = price_data['market_data']['low_24h']['usd']
        volume_24h = price_data['market_data']['total_volume']['usd']
        market_cap = price_data['market_data']['market_cap']['usd']
        
        # Extract price data points for technical analysis
        prices = historical_data['prices']
        price_points = [price[1] for price in prices]
        
        # Create a prompt with the data
        prompt = f"""
        Current {coin_name} ({coin_symbol}) data:
        - Current Price: ${current_price:,.2f}
        - 24h Change: {price_change_24h:.2f}%
        - 24h High: ${high_24h:,.2f}
        - 24h Low: ${low_24h:,.2f}
        - 24h Volume: ${volume_24h:,.2f}
        - Market Cap: ${market_cap:,.2f}
        
        Recent price points (24h): {price_points}
        """
        
        # Call OpenAI API for technical analysis
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a professional cryptocurrency analyst specializing in {coin_name} technical analysis. Create a detailed technical breakdown following EXACTLY this format:\n\n📊 Technical Breakdown:\n[Brief overview of price movement with percentage and key levels]\n• Support Zones: [key support levels]\n• Resistance Levels: [key resistance levels]\n• Momentum: [brief momentum analysis]\n\n⚡ Key Indicators to Watch:\n✅ RSI: [RSI analysis]\n✅ Volume Trends: [volume analysis]\n✅ Moving Averages: [MA analysis]\n\n💡 Strategy:\n🔸 [Bull strategy point]\n🔸 [Bear strategy point]\n🔸 [Final strategic consideration]"},
                {"role": "user", "content": f"Based on this {coin_name} data, provide a technical analysis exactly in the format specified. Make it realistic and actionable:\n\n{prompt}"}
            ],
            max_tokens=700
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating technical analysis: {e}")
        return "Error generating technical analysis."

# Function to fetch crypto news from NewsData.io free API
def fetch_crypto_news():
    try:
        # Use NewsData.io free API for crypto news
        url = "https://newsdata.io/api/1/news"
        params = {
            "apikey": NEWSDATA_API_KEY,
            "q": "cryptocurrency OR bitcoin OR ethereum OR crypto",  # Search for crypto news
            "language": "en",  # English language news
            "size": 5  # Get 5 news articles for more comprehensive coverage
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("status") == "success":
            return data.get("results", [])
        else:
            print(f"Error fetching news: {data.get('results', {}).get('message', 'Unknown error')}")
            return []
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []

# Function to generate crypto news summary with OpenAI
async def generate_news_summary(news_items):
    try:
        if not news_items:
            return "No cryptocurrency news available at this time."
        
        # Prepare the news content for OpenAI with more detailed structure
        news_content = ""
        for item in news_items:
            title = item.get('title', 'No title')
            description = item.get('description', 'No description')
            content = item.get('content', '')
            source = item.get('source_id', 'Unknown source')
            published_date = item.get('pubDate', 'Unknown date')
            
            news_content += f"Title: {title}\n"
            news_content += f"Source: {source}\n"
            news_content += f"Date: {published_date}\n"
            news_content += f"Description: {description}\n"
            if content:
                news_content += f"Content: {content}\n"
            news_content += "\n---\n\n"
        
        # Call OpenAI API with enhanced prompt for a unique news update
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional cryptocurrency news reporter. Create a unique, original cryptocurrency news update that synthesizes information from multiple sources without referencing them. Write as if this is your own original reporting. Cover important developments across major cryptocurrencies including Bitcoin, Ethereum, and Solana. Format your report as a professional news article with a catchy headline, current date, and engaging content. Your response MUST be under 1800 characters total to fit within Discord's message limits."},
                {"role": "user", "content": f"Based on these news sources, create a unique cryptocurrency news update as if you're a professional crypto reporter. Don't mention or cite the original sources - make it appear as original reporting. Include a catchy headline and today's date ({datetime.now().strftime('%B %d, %Y')}). Keep your response under 1800 characters:\n\n{news_content}"}
            ],
            max_tokens=700  # Limit token count to ensure response fits in Discord
        )
        
        # Extract the response content using the new syntax
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating news summary: {e}")
        return f"Failed to generate cryptocurrency news update: {str(e)}"

# Function to post crypto price update to specific channel
async def post_crypto_update(coin_key):
    try:
        coin_info = COIN_MAP[coin_key]
        channel = bot.get_channel(coin_info['channel_id'])
        
        if not channel:
            print(f"Error: Could not find channel with ID {coin_info['channel_id']} for {coin_info['name']}")
            return
        
        await channel.send(f"Generating {coin_info['name']} update for {datetime.now().strftime('%B %d, %Y')}...")
        
        # Fetch crypto price data
        data = fetch_crypto_price_data(coin_info['id'])
        if not data:
            await channel.send(f"Failed to retrieve {coin_info['name']} price data.")
            return
        
        # Format the price update
        price_update = format_price_update(data, coin_info['symbol'])
        
        # Generate technical analysis
        technical_analysis = await generate_technical_analysis(data, coin_info['symbol'], coin_info['name'])
        
        # Combine and send the complete update
        complete_update = f"{price_update}\n{technical_analysis}"
        await channel.send(complete_update)
        
        # Generate and send the 24-hour price chart
        chart = generate_price_chart(data['historical_data'], coin_info['symbol'], coin_info['name'])
        if chart:
            await channel.send(file=discord.File(chart, filename=f'{coin_info["id"]}_price_chart.png'))
        else:
            await channel.send(f"Failed to generate the {coin_info['name']} price chart.")
            
        print(f"Successfully posted {coin_info['name']} update to channel {coin_info['channel_id']}")
    except Exception as e:
        print(f"Error posting {coin_key} update: {e}")

# Function to post crypto news to specific channel
async def post_crypto_news():
    try:
        channel = bot.get_channel(NEWS_CHANNEL_ID)
        
        if not channel:
            print(f"Error: Could not find channel with ID {NEWS_CHANNEL_ID} for Crypto News")
            return
        
        await channel.send(f"Generating Cryptocurrency News update for {datetime.now().strftime('%B %d, %Y')}...")
        
        # Fetch news updates
        news_items = fetch_crypto_news()
        if not news_items:
            await channel.send("Failed to retrieve cryptocurrency news.")
            return
        
        # Generate a unique news update
        news_update = await generate_news_summary(news_items)
        await channel.send(news_update)
        
        print(f"Successfully posted Crypto News update to channel {NEWS_CHANNEL_ID}")
    except Exception as e:
        print(f"Error posting crypto news: {e}")

# Event: Bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')
    print('Bot is ready to post automated updates to channels:')
    print(f'Bitcoin updates -> Channel ID: {BTC_CHANNEL_ID}')
    print(f'Ethereum updates -> Channel ID: {ETH_CHANNEL_ID}')
    print(f'Solana updates -> Channel ID: {SOL_CHANNEL_ID}')
    print(f'Crypto News -> Channel ID: {NEWS_CHANNEL_ID}')
    print('------')
    print('Available admin commands:')
    print('!update_btc - Manually trigger Bitcoin update')
    print('!update_eth - Manually trigger Ethereum update')
    print('!update_sol - Manually trigger Solana update')
    print('!update_news - Manually trigger Crypto News update')
    print('!update_all - Manually trigger all updates')

# Admin command to manually trigger Bitcoin update
@bot.command(name='update_btc')
@commands.is_owner()
async def update_btc(ctx):
    await ctx.send("Manually triggering Bitcoin update...")
    await post_crypto_update('btc')
    await ctx.send("Bitcoin update completed!")

# Admin command to manually trigger Ethereum update
@bot.command(name='update_eth')
@commands.is_owner()
async def update_eth(ctx):
    await ctx.send("Manually triggering Ethereum update...")
    await post_crypto_update('eth')
    await ctx.send("Ethereum update completed!")

# Admin command to manually trigger Solana update
@bot.command(name='update_sol')
@commands.is_owner()
async def update_sol(ctx):
    await ctx.send("Manually triggering Solana update...")
    await post_crypto_update('sol')
    await ctx.send("Solana update completed!")

# Admin command to manually trigger Crypto News update
@bot.command(name='update_news')
@commands.is_owner()
async def update_news(ctx):
    await ctx.send("Manually triggering Crypto News update...")
    await post_crypto_news()
    await ctx.send("Crypto News update completed!")

# Admin command to manually trigger all updates
@bot.command(name='update_all')
@commands.is_owner()
async def update_all(ctx):
    await ctx.send("Manually triggering all updates...")
    await post_crypto_update('btc')
    await post_crypto_update('eth')
    await post_crypto_update('sol')
    await post_crypto_news()
    await ctx.send("All updates completed!")

# Run the bot
if __name__ == "__main__":
    print("Starting Automated Crypto Update Bot...")
    bot.run(DISCORD_TOKEN)
