# -*- coding: utf-8 -*-

# 导入函数库

import bisect
from jqdata import get_all_trade_days
from datetime import datetime, timedelta

class KLYHStrategy(object):

    # 期望年化收益率15%
    EXPECTED_EARN_RATE = 0.15

    # 期望5年达到平均收益
    EXPECTED_EARN_YEAR = 5

    def __init__(self, index_stock):
        self._index_stock = index_stock
        self._pe, self._pb, self._roe = self._index_stock.get_index_beta_factor()
        self._history_factors = self._index_stock.get_index_beta_history_factors()

    def get_trading_position(self, national_debt_rate=0.035):
        """
        根据pe, pb的绝对值以及相对历史估值决定买入或卖出仓位，规则如下：

        买入条件:
            市场出现系统性低估机会可以买入 (市场出现PE<7、PB<1、股息率>5% (ROE>18%)的品种)，此时满仓(100%)
            单一标的PE、PB 处于历史30%以下可以买入
            PE处于历史30%以下，且PB<1.5可以买入
            PB处于历史30%以下，且PE<10 或 1/PE<十年期国债利率X2，可以买入

        卖出条件:
            市场出现系统性高估机会可以卖出 (市场整体50 PE，整体PB>4.5)，此时清仓(-100%)
            单一标的PE、PB 处于历史70%以上可以卖出
            PE处于历史70%以上，且PB>2可以卖出
            PB处于历史70%以上，且PE>25可以卖出
            1/PE<市场能找到的最小无风险收益率(简单的用国债利率X3)，可以卖出置换

        input:
            national_debt_rate: 当前国债利率

        output:
            -1 ~~ 1, -1代表清仓，0代表持仓不动， 1代表全仓买入； -0.5代表清半仓，0.5代表半仓买入
        """
        pe_quantile = self._index_stock.get_quantile_of_history_factors(
                                        self._pe, self._history_factors['pe'])
        pb_quantile = self._index_stock.get_quantile_of_history_factors(
                                        self._pb, self._history_factors['pb'])

        avg_roe = self._history_factors['roe'].mean()

        debug_msg = "当前PE:{:.2f},百分位:{:.2f}，当前PB{:.2f},百分位:{:.2f},平均ROE:{:.2f}, 国债利率:{},推荐仓位:".format(self._pe,
                               pe_quantile, self._pb, pb_quantile, avg_roe, national_debt_rate)

        # 当市场出现系统性机会时，满仓或清仓
        if self._pe<7.0 and self._pb<1.0 and self._pb/self._pe>0.18:
            print(debug_msg + '1.0')
            return 1.0
        if self._pe>50.0 or self._pb>4.5:
            print(debug_msg + '-1.0')
            return -1.0

        if (pe_quantile<0.3 and pb_quantile<0.3 and self._pb<2) or \
           (pb_quantile<0.3 and 1.0/self._pe>national_debt_rate*3):
            position =  self.kelly(self._pe, avg_roe, national_debt_rate, action=1)
            print("{}{:.2f}".format(debug_msg, position))
            return position

        if (pe_quantile>0.7 and pb_quantile>0.7) or \
           (1.0/self._pe<national_debt_rate*2):
            position = self.kelly(self._pe, avg_roe, national_debt_rate, action=0)
            print("{}{:.2f}".format(debug_msg, position))
            return position
        return 0

    def kelly(self, pe, history_avg_roe, national_debt_rate, action=1):
        """
        买入时用凯利公式计算仓位：https://happy123.me/blog/2019/04/08/zhi-shu-tou-zi-ce-lue/
        卖出时简单的用 70% 清仓0.5成， 80%清仓2成，90%清仓3成

        input:
            pe: 当前pe
            history_avg_roe: 历史平均roe
            history_pes: 历史PE数据集合
            national_debt_rate: 当前国债利率
            action=1代表买， action=0代表卖
        """


        pe_quantile = self._index_stock.get_quantile_of_history_factors(
                                        pe, self._history_factors['pe'])
        position = 0
        if action == 0:
            if pe_quantile>=0.7 and pe_quantile<0.8:
                position = -0.05
            elif pe_quantile>=0.8 and pe_quantile<0.85:
                position = -0.1
            elif pe_quantile>=0.85 and pe_quantile<0.9:
                position = -0.3
            elif pe_quantile>=0.9 and pe_quantile<0.95:
                position = -0.5
            elif pe_quantile>=0.95 and pe_quantile<0.99:
                position = -0.7
            elif pe_quantile>=0.99:
                position = -1
            else:
                pass
            return position
        else:
            odds = pow(1 + self.EXPECTED_EARN_RATE, self.EXPECTED_EARN_YEAR)
            except_sell_pe = odds / pow(1+history_avg_roe, self.EXPECTED_EARN_YEAR) * pe

            win_rate = 1.0 - self._index_stock.get_quantile_of_history_factors(except_sell_pe,
                                                                               self._history_factors['pe'])
            print('历史平均roe:{},期待pe:{}, 胜率:{}, 赔率:{}'.format(history_avg_roe, except_sell_pe, win_rate, odds))

            position = (odds * win_rate - (1.0 - win_rate)) * 1.0 / odds
            return position if position > 0 else 0


class IndexStockBeta(object):

    def __init__(self, index_code, index_type=0, base_date=None, history_days=365*8):
        """
        input:
            index_code: 要查询指数的代码
            index_type: 1为等权重方式计算，0为按市值加权计算
            base_date: 查询时间，格式为'yyyy-MM-dd'，默认为当天
            history_days: 默认历史区间位前八年
        """
        self._index_code = index_code
        self._index_type = index_type
        if not base_date:
            self._base_date = datetime.now().date()
        else:
            self._base_date = datetime.strptime(base_date, '%Y-%m-%d')

        self._begin_date = self._base_date - timedelta(history_days)
        self._end_date = self._base_date

        self._begin_date = self._begin_date.strftime('%Y-%m-%d')
        self._end_date = self._end_date.strftime('%Y-%m-%d')
        self._base_date = self._base_date.strftime('%Y-%m-%d')

    def get_index_beta_factor(self, day=None):
        """
        获取当前时间的pe, pb值

        input:
            day: datetime.date类型，如果为None，默认代表取当前时间

        output:
            (pe, pb, roe)
        """
        if not day:
            day = datetime.strptime(self._base_date, '%Y-%m-%d')

        stocks = get_index_stocks(self._index_code, day)
        q = query(
            valuation.pe_ratio, valuation.pb_ratio, valuation.circulating_market_cap
        ).filter(
            valuation.code.in_(stocks)
        )

        df = get_fundamentals(q, day)

        df = df[df['pe_ratio']>0]

        if len(df)>0:
            if(self._index_type == 0):
                pe = df['circulating_market_cap'].sum() / (df['circulating_market_cap']/df['pe_ratio']).sum()
                pb = df['circulating_market_cap'].sum() / (df['circulating_market_cap']/df['pb_ratio']).sum()
            else:
                pe = df['pe_ratio'].size / (1/df['pe_ratio']).sum()
                pb = df['pb_ratio'].size / (1/df['pb_ratio']).sum()
            return (pe, pb, pb/pe)
        else:
            return (None, None, None)

    def get_index_beta_history_factors(self, interval=7):
        """
        获取任意指数一段时间的历史 pe,pb 估值列表，通过计算当前的估值在历史估值的百分位，来判断当前市场的估值高低。
        由于加权方式可能不同，可能各个指数公开的估值数据有差异，但用于判断估值相对高低没有问题

        input：
            interval: 计算指数估值的间隔天数，增加间隔时间可提高计算性能

        output：
            result:  指数历史估值的 DataFrame，index 为时间，列为pe，pb,roe
        """
        all_days = get_all_trade_days()

        pes = []
        roes = []
        pbs = []
        days = []

        begin = datetime.strptime(self._begin_date, '%Y-%m-%d').date()
        end = datetime.strptime(self._end_date, '%Y-%m-%d').date()
        i = 0
        for day in all_days:
            if(day <= begin or day >= end):
                continue

            i += 1

            if(i % interval != 0):
                continue

            pe, pb, roe = self.get_index_beta_factor(day)
            if pe and pb and roe:
                pes.append(pe)
                pbs.append(pb)
                roes.append(roe)
                days.append(day)

        result = pd.DataFrame({'pe':pes,'pb':pbs, 'roe':roes}, index=days)
        return result

    def get_quantile_of_history_factors(self, factor, history_list):
        """
            获取某个因子在历史上的百分位，比如当前PE处于历史上的70%区间，意味着历史PE有70%都在当前值之下

        input:
            factor: beta因子
            history_list: 历史估值列表, DataFrame

        output:
            quantile: 历史估值百分位 (0.7)
        """
        factors = [history_list.quantile(i / 10.0)  for i in range(11)]
        idx = bisect.bisect(factors, factor)
        if idx < 10:
            quantile = idx - (factors[idx] - factor) / (factors[idx] - factors[idx-1])
            return quantile / 10.0
        else:
            return 1.0

BENCHMARK_INDEX_STOCK = '000300.XSHG'
INDEX_STOCKS = {
    '000300.XSHG':'163407.OF',    #163407.OF 兴全沪深300增强
    '000905.XSHG':'161017.OF',    #161017.OF 富国中证500增强
    '000919.XSHG':'519671.OF',    #519671.OF 银河300价值
    '000922.XSHG':'100032.OF',    #100032.OF 富国中证红利
    '399702.XSHE':'070023.OF',    #070023.OF 嘉实深F120基本面联接
    #'399978.XSHE':'001550.OF',    #001550.OF 天弘中证医药100
    #'399812.XSHE':'000968.OF'     #000968.OF 广发中证养老指数
}

TOTAL_CASH = 50000 * len(INDEX_STOCKS)
UNIT_CASH = TOTAL_CASH / len(INDEX_STOCKS) / 50


# =============================================================
# 初始化函数，设定基准等等
def initialize(context):
    set_benchmark(BENCHMARK_INDEX_STOCK)
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)

    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.0000, close_commission=0.0000, min_commission=0), type='stock')

    # 设定账户为场外基金账户，初始资金为 TOTAL_CASH 变量代表的数值（如不使用设置多账户，默认只有subportfolios[0]一个账户，Portfolio 指向该账户。）
    set_subportfolios([SubPortfolioConfig(cash=TOTAL_CASH, type='open_fund')])
    # 用基金的单位净值进行撮合成交
    set_option('use_real_price', True)
    # 设置 QDII 的赎回到账日为 T+3
    set_redeem_latency(3, 'QDII_fund')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security=BENCHMARK_INDEX_STOCK )
      # 开盘时或每分钟开始时运行
    run_daily(market_open, time='every_bar', reference_security=BENCHMARK_INDEX_STOCK )
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security=BENCHMARK_INDEX_STOCK )

    run_daily(weekly, time='every_bar')

## 开盘前运行函数
def before_market_open(context):
    pass

## 开盘时运行函数
def market_open(context):
    pass

## 收盘后运行函数
def after_market_close(context):
    pass

def weekly(context):
    if context.current_dt.isoweekday() != 2:
        # 不在周二, 跳过执行
        return

    for stock_index, stock_fund in INDEX_STOCKS.items():
        fund_info = get_fund_info(stock_fund)
        cash = context.portfolio.available_cash
        fund_value =  context.portfolio.positions_value

        if fund_value > 0:
            fund_amount = context.portfolio.positions[stock_fund].closeable_amount
        else:
            fund_amount = 0

        print("cash:{}, fund:{}, fund_value:{}, fund_amount:{}".format(cash, fund_info['fund_name'], fund_value, fund_amount))

        current_date = context.current_dt.strftime("%Y-%m-%d")
        stock = IndexStockBeta(stock_index, base_date=current_date, history_days=5*365)
        stragety = KLYHStrategy(stock)
        position = stragety.get_trading_position()

        if position > 0 and cash > 10:
            if cash >= UNIT_CASH*position:
                purchase(stock_fund, UNIT_CASH*position)
            else:
                purchase(stock_fund, cash)
        elif position < 0:
            if fund_amount > 0 and int(0-fund_amount*position) > 0:
                redeem(stock_fund, int(0-fund_amount*position))
            else:
                pass
        else:
            print('HOLDING')

def period(context):
    pass

