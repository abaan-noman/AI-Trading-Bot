import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from lumibot.brokers import Alpaca
from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies.strategy import Strategy
from datetime import datetime
from alpaca_trade_api import REST
from timedelta import Timedelta
from sentiment_analysis import estimate_sentiment
from lumibot.traders import Trader

class MLTrader(Strategy):
    #Input your alpaca credentials here
    API_KEY = ""
    API_SECRET = ""
    BASE_URL = ""
    ALPACA_CREDS = {
        "API_KEY": API_KEY,
        "API_SECRET": API_SECRET,
        "PAPER": True
    }

    def initialize(self, symbol: str = "SPY", cash_at_risk: float = 0.5):
        self.symbol = symbol
        self.sleeptime = "12H"
        self.last_trade = None
        self.cash_at_risk = cash_at_risk
        self.api = REST(
            base_url=self.BASE_URL, 
            key_id=self.API_KEY, 
            secret_key=self.API_SECRET
        )

    def position_sizing(self):
        cash = self.get_cash()
        last_price = self.get_last_price(self.symbol)
        quantity = int(cash * self.cash_at_risk / last_price)
        return cash, last_price, quantity

    def get_dates(self):
        today = self.get_datetime()
        three_days_prior = today - Timedelta(days=3)
        return today.strftime('%Y-%m-%d'), three_days_prior.strftime('%Y-%m-%d')

    def get_sentiment(self):
        today, three_days_prior = self.get_dates()
        news = self.api.get_news(symbol=self.symbol, start=three_days_prior, end=today)
        news_headlines = [ev.__dict__["_raw"]["headline"] for ev in news]
        probability, sentiment = estimate_sentiment(news_headlines)
        return probability, sentiment

    def execute_trade(self, action: str, quantity: int, last_price: float):
        order = self.create_order(
            self.symbol,
            quantity,
            action,
            type="bracket",
            take_profit_price=last_price * (1.30 if action == "buy" else 0.7),
            stop_loss_price=last_price * (0.90 if action == "buy" else 1.10)
        )
        self.submit_order(order)
        self.last_trade = action

    def on_trading_iteration(self):
        cash, last_price, quantity = self.position_sizing()
        probability, sentiment = self.get_sentiment()

        if cash > last_price:
            if sentiment == "positive" and probability > 0.999:
                if self.last_trade == "sell":
                    self.sell_all()
                self.execute_trade("buy", quantity, last_price)
            elif sentiment == "negative" and probability > 0.999:
                if self.last_trade == "buy":
                    self.sell_all()
                self.execute_trade("sell", quantity, last_price)

if __name__ == "__main__":
    start_date = datetime(2020, 1, 1)
    end_date = datetime(2024, 7, 23)
    broker = Alpaca(MLTrader.ALPACA_CREDS)
    strategy = MLTrader(name='mlstrat', broker=broker, parameters={"symbol": "SPY", "cash_at_risk": 0.5})
    strategy.backtest(YahooDataBacktesting, start_date, end_date, parameters={"symbol": "SPY", "cash_at_risk": 0.5})