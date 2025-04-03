#!/bin/bash

# Cron job setup script for Automated Crypto Bot
# This script will help set up the cron jobs to run your crypto bot at specified times

# Define the path to your Python executable and bot script
# Update these paths to match your VPS setup
PYTHON_PATH="/usr/bin/python3"
BOT_DIR="/home/ubuntu"
BOT_SCRIPT="$BOT_DIR/automated_crypto_bot.py"
LOG_DIR="$BOT_DIR/logs"
ENV_FILE="$BOT_DIR/.env"

# Create logs directory if it doesn't exist
mkdir -p $LOG_DIR

# Function to create a cron job entry
create_cron_entry() {
    local hour=$1
    local minute=$2
    local command=$3
    local log_file=$4
    
    echo "$minute $hour * * * cd $BOT_DIR && $PYTHON_PATH -c \"import sys; sys.path.append('$BOT_DIR'); import asyncio, automated_crypto_bot; asyncio.run($command)\" >> $log_file 2>&1"
}

# Create cron entries for each update at different times
BTC_CRON=$(create_cron_entry "2" "0" "automated_crypto_bot.post_crypto_update('btc')" "$LOG_DIR/btc_update.log")
ETH_CRON=$(create_cron_entry "4" "20" "automated_crypto_bot.post_crypto_update('eth')" "$LOG_DIR/eth_update.log")
SOL_CRON=$(create_cron_entry "12" "0" "automated_crypto_bot.post_crypto_update('sol')" "$LOG_DIR/sol_update.log")
NEWS_CRON=$(create_cron_entry "23" "0" "automated_crypto_bot.post_crypto_news()" "$LOG_DIR/news_update.log")

# Create a temporary crontab file
TEMP_CRONTAB=$(mktemp)

# Get existing crontab
crontab -l > $TEMP_CRONTAB 2>/dev/null || true

# Add comments for clarity
echo "# Automated Crypto Bot scheduled updates" >> $TEMP_CRONTAB
echo "# Added on $(date)" >> $TEMP_CRONTAB
echo "$BTC_CRON" >> $TEMP_CRONTAB
echo "$ETH_CRON" >> $TEMP_CRONTAB
echo "$SOL_CRON" >> $TEMP_CRONTAB
echo "$NEWS_CRON" >> $TEMP_CRONTAB
echo "" >> $TEMP_CRONTAB

# Install the new crontab
crontab $TEMP_CRONTAB
rm $TEMP_CRONTAB

echo "Cron jobs have been set up successfully!"
echo "Bitcoin updates will run daily at 02:00"
echo "Ethereum updates will run daily at 04:20"
echo "Solana updates will run daily at 12:00"
echo "Crypto News updates will run daily at 23:00"
echo "Logs will be saved in $LOG_DIR"
