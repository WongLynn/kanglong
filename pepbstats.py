# -*- coding: utf-8 -*-

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import bisect

import warnings
warnings.filterwarnings("ignore")

#指定日期的指数PE(市值加权)
def get_index_pe_date(index_code,date):
    stocks = get_index_stocks(index_code, date)
    q = query(valuation).filter(valuation.code.in_(stocks))
    df = get_fundamentals(q, date)
    df = df[df['pe_ratio'] > 0]
    if len(df) > 0:
        #pe = len(df)/sum([1/p if p>0 else 0 for p in df.pe_ratio])
        #pe = df['pe_ratio'].size/(1/df['pe_ratio']).sum()
        pe = df['circulating_market_cap'].sum()/(df['circulating_market_cap']/df['pe_ratio']).sum()
        return pe
    else:
        return float('NaN')

#指定日期的指数PB(市值加权)
def get_index_pb_date(index_code,date):
    stocks = get_index_stocks(index_code, date)
    q = query(valuation).filter(valuation.code.in_(stocks))
    df = get_fundamentals(q, date)
    df = df[df['pb_ratio']>0]
    if len(df)>0:
        #pb = len(df)/sum([1/p if p>0 else 0 for p in df.pb_ratio])
        #pb = df['pb_ratio'].size/(1/df['pb_ratio']).sum()
        pb = df['circulating_market_cap'].sum()/(df['circulating_market_cap']/df['pb_ratio']).sum()
        return pb
    else:
        return float('NaN')

#指数历史PEPB
def get_index_pe_pb(index_code):
    start='2011-1-1'
    end = pd.datetime.today();
    dates=[]
    pes=[]
    pbs=[]
    for d in pd.date_range(start,end,freq='W'): #频率为周
        dates.append(d)
        pes.append(get_index_pe_date(index_code,d))
        pbs.append(get_index_pb_date(index_code,d))
    d = {
            'PE' : pd.Series(pes, index=dates),
            'PB' : pd.Series(pbs, index=dates)
        }
    PB_PE = pd.DataFrame(d)
    return PB_PE


all_index = get_all_securities(['index'])
index_choose = [
    '000300.XSHG', # :'沪深300',    #000176.OF 嘉实沪深300增强
    '000905.XSHG', # :'中证500',    #000478.OF 建信中证500增强
    '000919.XSHG', #:'300价值',    #310398.OF 申万沪深300价值
    '000922.XSHG', #:'中证红利',   #100032.OF 富国中证红利
    '399702.XSHE', #:'深证F120',   #070023.OF 嘉实深F120基本面联接
    '399978.XSHE', #:'中证医药100',#001550.OF 天弘中证医药100
    '399812.XSHE',  #:'中证养老'    #000968.OF 广发中证养老指数
    '000932.XSHG', # 中证消费
]

df_pe_pb = pd.DataFrame()
frames =pd.DataFrame()
today = pd.datetime.today()

for code in index_choose:
    index_name = all_index.ix[code].display_name
    print('正在处理: ', index_name)
    df_pe_pb = get_index_pe_pb(code)

    results=[]
    pe = get_index_pe_date(code, today)
    q_pes = [df_pe_pb['PE'].quantile(i / 10.0)  for i in range(11)]
    idx = bisect.bisect(q_pes, pe)
    quantile = idx - (q_pes[idx] - pe) / (q_pes[idx] - q_pes[idx-1])
    #index_name = all_index.ix[code].display_name
    results.append([index_name,
                    format(pe, '.2f'),
                    format(quantile * 10, '.2f')] +
                    [format(q, '.2f')  for q in q_pes] +
                    [df_pe_pb['PE'].count()])

    pb = get_index_pb_date(code, today)
    q_pbs = [df_pe_pb['PB'].quantile(i / 10.0)  for i in range(11)]
    idx = bisect.bisect(q_pbs, pb)
    quantile = idx - (q_pbs[idx] - pb) / (q_pbs[idx] - q_pbs[idx-1])
    #index_name = all_index.ix[code].display_name
    results.append([index_name,
                    format(pb, '.2f'),
                    format(quantile * 10, '.2f')] +
                    [format(q, '.2f')  for q in q_pbs] +
                    [df_pe_pb['PB'].count()])


    df_pe_pb['10% PE']=q_pes[1]
    df_pe_pb['50% PE']=q_pes[5]
    df_pe_pb['90% PE']=q_pes[9]
    df_pe_pb['10% PB']=q_pbs[1]
    df_pe_pb['50% PB']=q_pbs[5]
    df_pe_pb['90% PB']=q_pbs[9]

    plt.rcParams['font.sans-serif']=['SimHei']
    df_pe_pb.plot(secondary_y=['PB','10% PB','50% PB','90% PB'],
                  figsize=(14,8), title = index_name,
                  style=['k-.', 'k', 'g', 'y', 'r', 'g-.', 'y-.', 'r-.'])

    columns=['名称', '当前估值', '分位点%', '最小估值'] + \
            [format(i * 10, 'd') + '%%' for i in range(1,10)] + \
            ['最大估值' , '数据个数']

    df= pd.DataFrame(data = results,
                     index = ['PE','PB'],
                     columns = columns)
    frames = pd.concat([frames, df])

frames
