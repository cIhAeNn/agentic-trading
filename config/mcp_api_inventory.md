# MCP API Inventory

## IF-RH01: Robinhood MCP

get_account_balances()
get_watchlist_instruments(watchlist_name:str)
add_to_watchlist(symbol:str, target_frame:str)
execute_trade(symbol:str, size:float, side:str, price:float)

## IF-AV02: Alpha Vantage Technicals

TIME_SERIES_DAILY(symbol:str, outputsize:str="compact")
TIME_SERIES_INTRADAY(symbol:str, interval:str)
COMPANY_OVERVIEW(symbol:str)
RSI(symbol:str, period:int, series_type:str)

## IF-TR03: TipRanks Sentiment

get_assets_data(symbol:str)

## IF-WA04: Windsor.ai Data Bridge

get_data(source:str="yahoo", tracking_matrix:list)
get_fields(pipe_id:str)
